from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from .api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
from .asset_inventory import build_asset_inventory
from .asset_resolution import assess_asset_publication, load_asset_publication_policy
from .canonical import build_structural_manifest
from .deployment_history import DeploymentRecorder, utc_now
from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint, live_lesson_payload
from .general_content import compile_lesson_source
from .golden import load_golden_profile, validate_golden_profile
from .history_runtime import find_incomplete_object_events
from .learner_hygiene_writer import (
    _lesson_after_step,
    _lesson_after_title,
    _ordered_live_steps,
    _planned_operations,
    _step_source,
    _target_lesson,
)
from .sync_state import baseline_for, build_record, close_lesson_pending, with_record
from .verified_rendering import build_rendering_plan, require_render_ready
from .writer import ContentWriteError, _assert_readback

COURSE_ID = 299189
RECOVERY_TARGET = "M02-L01"
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")
NORMALIZATION_CONTRACT = "stepik-plain-horizontal-rule-strip-v1"


@dataclass(frozen=True)
class RecoveryOperation:
    operation_id: str
    kind: str
    step_id: int | None
    legacy_fingerprint_before: str
    legacy_fingerprint_after: str
    normalized_fingerprint_before: str
    normalized_fingerprint_after: str
    normalized_expected_step: Any | None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "operation_id": self.operation_id,
            "kind": self.kind,
            "step_id": self.step_id,
            "legacy_fingerprint_before": self.legacy_fingerprint_before,
            "legacy_fingerprint_after": self.legacy_fingerprint_after,
            "normalized_fingerprint_before": self.normalized_fingerprint_before,
            "normalized_fingerprint_after": self.normalized_fingerprint_after,
        }
        if self.normalized_expected_step is not None:
            payload["expected_block"] = self.normalized_expected_step.block()
            payload["position"] = int(self.normalized_expected_step.position)
        return payload


@dataclass(frozen=True)
class NormalizationRecoveryPlan:
    event_id: str
    identity: Any
    records: tuple[dict[str, Any], ...]
    baseline: dict[str, Any]
    baseline_lesson: dict[str, Any]
    normalized_expected_steps: tuple[Any, ...]
    expected_title: str
    lesson_id: int
    module_position: int
    lesson_position: int
    unresolved_operation: RecoveryOperation
    remaining_operations: tuple[RecoveryOperation, ...]
    normalized_desired_fingerprint: str
    legacy_desired_fingerprint: str
    current_normalized_fingerprint: str
    current_source_sha: str
    source_git_paths: tuple[str, ...]

    @property
    def stepik_writes_planned(self) -> int:
        return len(self.remaining_operations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": RECOVERY_TARGET,
            "action": "RECOVER_NORMALIZED_READBACK_PREFIX_AND_CONTINUE",
            "event_id": self.event_id,
            "event_source_sha": self.identity.source_sha,
            "current_source_sha": self.current_source_sha,
            "stepik_lesson_id": self.lesson_id,
            "normalization_contract": NORMALIZATION_CONTRACT,
            "legacy_desired_fingerprint": self.legacy_desired_fingerprint,
            "normalized_desired_fingerprint": self.normalized_desired_fingerprint,
            "current_normalized_fingerprint": self.current_normalized_fingerprint,
            "confirmation_only_operation": self.unresolved_operation.as_dict(),
            "remaining_operations": [item.as_dict() for item in self.remaining_operations],
            "stepik_writes_planned": self.stepik_writes_planned,
            "creates_planned": False,
            "deletes_planned": False,
            "structural_writes_planned": False,
        }


@dataclass(frozen=True)
class NormalizationRecoveryResult:
    plan: NormalizationRecoveryPlan
    next_state: dict[str, Any]
    state_record: dict[str, Any]
    final_snapshot: dict[str, Any]
    stepik_writes: int

    def event_artifact(self) -> dict[str, Any]:
        return {
            "event_id": self.plan.event_id,
            "source_sha": self.plan.identity.source_sha,
            "status": "APPLIED",
            "kind": "lesson",
            "canonical_id": RECOVERY_TARGET,
        }


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ContentWriteError("Для learner-hygiene recovery нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def client_from_environment(*, api_host: str = "https://stepik.org") -> StepikClient:
    client_id, client_secret = _credentials()
    return StepikClient(client_id, client_secret, api_host=api_host)


def _manifest_target(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == RECOVERY_TARGET:
                matches.append((module, lesson))
    if len(matches) != 1:
        raise ContentWriteError(f"Recovery ожидает единственный canonical target {RECOVERY_TARGET}")
    return matches[0]


def _render_target(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    state: dict[str, Any],
    live_lesson: dict[str, Any],
    apply_stepik_html_normalization: bool,
) -> list[Any]:
    profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
    free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
    if not isinstance(free_answer_source, dict):
        raise ContentWriteError("Golden profile не содержит free_answer_source")
    source_steps = compile_lesson_source(
        repo_root,
        free_answer_source=free_answer_source,
        lesson_id=RECOVERY_TARGET,
    )
    inventory = build_asset_inventory(repo_root, manifest)
    policy = load_asset_publication_policy(repo_root / ASSET_POLICY_PATH)
    asset_report = assess_asset_publication(
        repo_root=repo_root,
        inventory=inventory,
        policy=policy,
        course_id=COURSE_ID,
    )
    if asset_report.get("route_gate_passed") is not True or asset_report.get("blockers"):
        raise ContentWriteError("Recovery asset publication gate не пройден")
    target_materializations = [
        row for row in asset_report.get("resolutions", [])
        if row.get("lesson") == RECOVERY_TARGET and row.get("materialization_required_at_write") is True
    ]
    if target_materializations:
        raise ContentWriteError("M02 recovery не должен зависеть от runtime attachment materialization")
    plan = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=RECOVERY_TARGET,
        source_steps=source_steps,
        asset_report=asset_report,
        apply_stepik_html_normalization=apply_stepik_html_normalization,
    )
    return list(require_render_ready(plan))


def _record_sets(records: list[dict[str, Any]]) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    dispatch = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_DISPATCH_STARTED" and item.get("operation_id")
    }
    completed = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_COMPLETED" and item.get("operation_id")
    }
    confirmed = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "OP_READBACK_CONFIRMED" and item.get("operation_id")
    }
    failed_readback = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "READBACK_FAILED" and item.get("operation_id")
    }
    intents = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_INTENT" and item.get("operation_id")
    }
    return intents, dispatch, completed, confirmed, failed_readback


def _operation_pairs(legacy_operations: list[Any], normalized_operations: list[Any]) -> list[RecoveryOperation]:
    if [item.operation_id for item in legacy_operations] != [item.operation_id for item in normalized_operations]:
        raise ContentWriteError("Normalization recovery изменила набор/порядок planned operations")
    result: list[RecoveryOperation] = []
    for legacy, normalized in zip(legacy_operations, normalized_operations, strict=True):
        if legacy.kind != normalized.kind or legacy.step_id != normalized.step_id:
            raise ContentWriteError("Normalization recovery изменила semantic operation identity")
        result.append(
            RecoveryOperation(
                operation_id=legacy.operation_id,
                kind=legacy.kind,
                step_id=legacy.step_id,
                legacy_fingerprint_before=legacy.fingerprint_before,
                legacy_fingerprint_after=legacy.fingerprint_after,
                normalized_fingerprint_before=normalized.fingerprint_before,
                normalized_fingerprint_after=normalized.fingerprint_after,
                normalized_expected_step=normalized.expected_step,
            )
        )
    return result


def build_normalization_recovery_plan(
    *,
    client: StepikClient,
    repo_root: Path,
    state: dict[str, Any],
    store: Any,
    current_source_sha: str,
) -> NormalizationRecoveryPlan | None:
    incomplete = find_incomplete_object_events(store, object_id=RECOVERY_TARGET)
    if not incomplete:
        return None
    if len(incomplete) != 1:
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery требует ровно один incomplete event")
    identity, records, summary = incomplete[0]
    if identity.kind != "lesson":
        raise ContentWriteError("Recovery target history имеет неожиданный kind")
    if summary.get("ambiguous") or int(summary.get("known_failed_writes") or 0) > 0:
        raise ContentWriteError("Recovery запрещён для ambiguous/known-failed Stepik write")
    if summary.get("final_readback_confirmed") or summary.get("machine_state_committed"):
        return None

    baseline = baseline_for(state, RECOVERY_TARGET)
    if not isinstance(baseline, dict):
        raise ContentWriteError("Recovery target не имеет confirmed machine baseline")
    baseline_fp = str(baseline.get("applied_fingerprint") or "")
    if identity.baseline_fingerprint_before != baseline_fp:
        raise ContentWriteError("Recovery event baseline identity не совпадает с Issue #54 baseline")

    snapshots = [item for item in records if item.get("phase") == "BASELINE_SNAPSHOT_CAPTURED"]
    if len(snapshots) != 1 or not isinstance(snapshots[0].get("baseline_lesson_snapshot"), dict):
        raise ContentWriteError("Recovery history не содержит единственный durable baseline snapshot")
    baseline_lesson = deepcopy(snapshots[0]["baseline_lesson_snapshot"])
    if live_lesson_fingerprint(baseline_lesson) != baseline_fp:
        raise ContentWriteError("Recovery durable baseline snapshot не совпадает с machine baseline")

    repo_root = repo_root.resolve()
    manifest = build_structural_manifest(repo_root, source_sha=current_source_sha)
    module, lesson_manifest = _manifest_target(manifest)
    snapshot = client.inspect_course(COURSE_ID)
    if snapshot.get("course", {}).get("id") != COURSE_ID:
        raise ContentWriteError("Recovery live course ID не совпадает с fixed target")
    if snapshot.get("course", {}).get("language") != "ru" or snapshot.get("course", {}).get("is_public") is not False:
        raise ContentWriteError("Recovery разрешён только для private ru project course")
    profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
    blockers = validate_golden_profile(profile, snapshot, manifest)
    if blockers:
        raise ContentWriteError("Recovery golden integrity не подтверждён: " + "; ".join(blockers))

    live_lesson = _target_lesson(
        snapshot,
        module_position=int(module["position"]),
        lesson_position=int(lesson_manifest["position"]),
    )
    lesson_id = int(live_lesson.get("id", -1))
    if lesson_id != int(baseline.get("stepik_lesson_id", -2)):
        raise ContentWriteError("Recovery live lesson ID отличается от baseline")

    normalized_steps = _render_target(
        repo_root=repo_root,
        manifest=manifest,
        state=state,
        live_lesson=live_lesson,
        apply_stepik_html_normalization=True,
    )
    legacy_steps = _render_target(
        repo_root=repo_root,
        manifest=manifest,
        state=state,
        live_lesson=live_lesson,
        apply_stepik_html_normalization=False,
    )
    expected_title = str(lesson_manifest["title"])
    legacy_desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=legacy_steps)
    normalized_desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=normalized_steps)
    if legacy_desired != identity.desired_fingerprint:
        raise ContentWriteError("Recovery current canonical legacy rendering не совпадает с incomplete event desired")
    if legacy_desired == normalized_desired:
        raise ContentWriteError("Recovery не обнаружил доказанную Stepik HTML normalization delta")

    legacy_operations, legacy_final = _planned_operations(
        baseline_lesson,
        expected_title=expected_title,
        expected_steps=legacy_steps,
    )
    normalized_operations, normalized_final = _planned_operations(
        baseline_lesson,
        expected_title=expected_title,
        expected_steps=normalized_steps,
    )
    if live_lesson_fingerprint(legacy_final) != legacy_desired:
        raise ContentWriteError("Recovery legacy planned final не совпадает с event desired")
    if live_lesson_fingerprint(normalized_final) != normalized_desired:
        raise ContentWriteError("Recovery normalized planned final не совпадает с normalized desired")
    pairs = _operation_pairs(legacy_operations, normalized_operations)
    planned_ids = [item.operation_id for item in pairs]

    if any(item.get("phase") in {"WRITE_AMBIGUOUS", "WRITE_FAILED_KNOWN"} for item in records):
        raise ContentWriteError("Recovery history содержит forbidden write result")
    intents, dispatch, completed, confirmed, failed_readback = _record_sets(records)
    if dispatch != completed or not dispatch.issubset(intents):
        raise ContentWriteError("Recovery history не доказывает 2xx для каждого dispatched write")
    if not dispatch:
        raise ContentWriteError("Recovery ожидает уже начатый learner-hygiene event")
    if not dispatch.issubset(set(planned_ids)):
        raise ContentWriteError("Recovery history содержит operation вне reconstructed plan")
    dispatched_positions = [planned_ids.index(operation_id) for operation_id in dispatch]
    max_dispatched = max(dispatched_positions)
    if dispatch != set(planned_ids[: max_dispatched + 1]):
        raise ContentWriteError("Recovery допускает только contiguous dispatched prefix")
    unresolved = dispatch - confirmed
    if len(unresolved) != 1:
        raise ContentWriteError("Recovery требует ровно один unconfirmed dispatched operation")
    unresolved_id = next(iter(unresolved))
    if unresolved_id != planned_ids[max_dispatched]:
        raise ContentWriteError("Recovery unconfirmed operation должна быть последней в dispatched prefix")
    if failed_readback != {unresolved_id}:
        raise ContentWriteError("Recovery требует ровно один matching READBACK_FAILED")

    current_normalized_fp = live_lesson_fingerprint(live_lesson)
    unresolved_pair = pairs[max_dispatched]
    if current_normalized_fp != unresolved_pair.normalized_fingerprint_after:
        raise ContentWriteError("Recovery live state не совпадает с normalized state после failed read-back operation")
    if current_normalized_fp == unresolved_pair.legacy_fingerprint_after:
        raise ContentWriteError("Recovery не должен использовать normalization route при exact legacy fingerprint match")

    source_paths = tuple(path for step in normalized_steps for path in step.source_git_paths)
    return NormalizationRecoveryPlan(
        event_id=identity.event_id,
        identity=identity,
        records=tuple(deepcopy(records)),
        baseline=deepcopy(baseline),
        baseline_lesson=baseline_lesson,
        normalized_expected_steps=tuple(normalized_steps),
        expected_title=expected_title,
        lesson_id=lesson_id,
        module_position=int(module["position"]),
        lesson_position=int(lesson_manifest["position"]),
        unresolved_operation=unresolved_pair,
        remaining_operations=tuple(pairs[max_dispatched + 1 :]),
        normalized_desired_fingerprint=normalized_desired,
        legacy_desired_fingerprint=legacy_desired,
        current_normalized_fingerprint=current_normalized_fp,
        current_source_sha=current_source_sha,
        source_git_paths=source_paths,
    )


def _append_normalized_readback(
    recorder: DeploymentRecorder,
    *,
    operation: RecoveryOperation,
    actual_normalized_fingerprint: str,
) -> None:
    recorder._append(
        "OP_READBACK_CONFIRMED",
        {
            "confirmed_at": utc_now(),
            "operation_id": operation.operation_id,
            "fingerprint_after": operation.legacy_fingerprint_after,
            "read_back_result": "CONFIRMED_NORMALIZED",
            "confirmation_basis": "stepik-html-normalization",
            "normalization_contract": NORMALIZATION_CONTRACT,
            "actual_normalized_fingerprint": actual_normalized_fingerprint,
        },
        operation_id=operation.operation_id,
    )


def _append_diagnostic(
    recorder: DeploymentRecorder,
    *,
    operation_id: str | None,
    expected_normalized_fingerprint: str,
    actual_lesson: dict[str, Any] | None,
    reason: str,
) -> None:
    actual_fp = None if actual_lesson is None else live_lesson_fingerprint(actual_lesson)
    actual_payload = None if actual_lesson is None else live_lesson_payload(actual_lesson)
    recorder._append(
        "READBACK_DIAGNOSTIC",
        {
            "recorded_at": utc_now(),
            "operation_id": operation_id,
            "reason_code": reason,
            "normalization_contract": NORMALIZATION_CONTRACT,
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "actual_fingerprint": actual_fp,
            "actual_lesson_payload": actual_payload,
        },
        operation_id=operation_id or "final-normalized-recovery",
    )


def execute_normalization_recovery(
    *,
    client: StepikClient,
    plan: NormalizationRecoveryPlan,
    store: Any,
    state: dict[str, Any],
) -> NormalizationRecoveryResult:
    recorder = DeploymentRecorder(store, plan.identity)
    fresh_snapshot = client.inspect_course(COURSE_ID)
    fresh_lesson = _target_lesson(
        fresh_snapshot,
        module_position=plan.module_position,
        lesson_position=plan.lesson_position,
    )
    fresh_fp = live_lesson_fingerprint(fresh_lesson)
    if fresh_fp != plan.current_normalized_fingerprint:
        raise ContentWriteError("Recovery race-check: live M02 изменился после preflight/classification")

    recorder.recovery_classified(
        classification="STEPIK_HTML_NORMALIZATION_PREFIX_PROVEN",
        reason_codes=[
            "readback-failed-but-write-completed",
            "live-matches-normalized-planned-prefix",
            "stepik-strips-plain-horizontal-rule",
            "blind-retry-of-confirmed-prefix-forbidden",
        ],
    )
    _append_normalized_readback(
        recorder,
        operation=plan.unresolved_operation,
        actual_normalized_fingerprint=fresh_fp,
    )

    working_snapshot = fresh_snapshot
    working_lesson = fresh_lesson
    writes = 0
    for operation in plan.remaining_operations:
        current_fp = live_lesson_fingerprint(working_lesson)
        if current_fp != operation.normalized_fingerprint_before:
            raise ContentWriteError(
                f"Recovery {operation.operation_id}: live before write не совпадает с normalized planned prefix"
            )
        recorder.write_intent(
            operation_id=operation.operation_id,
            method="PUT",
            target=(
                f"lessons/{plan.lesson_id}"
                if operation.kind == "title"
                else f"step-sources/{int(operation.step_id)}"
            ),
            fingerprint_before=operation.legacy_fingerprint_before,
            expected_fingerprint_after=operation.legacy_fingerprint_after,
        )
        recorder.write_dispatch_started(operation_id=operation.operation_id)
        try:
            if operation.kind == "title":
                client._request_write(
                    "PUT",
                    f"/api/lessons/{plan.lesson_id}",
                    {"lesson": {"title": plan.expected_title}},
                )
            else:
                if operation.step_id is None or operation.normalized_expected_step is None:
                    raise ContentWriteError("Recovery step operation повреждена")
                client.update_step_source(
                    step_id=int(operation.step_id),
                    lesson_id=plan.lesson_id,
                    position=int(operation.normalized_expected_step.position),
                    block=operation.normalized_expected_step.block(),
                )
        except StepikWriteAmbiguousError:
            recorder.write_result(
                operation_id=operation.operation_id,
                status="AMBIGUOUS",
                reason_code="normalized-recovery-write-ambiguous",
            )
            raise
        except StepikAPIError:
            recorder.write_result(
                operation_id=operation.operation_id,
                status="FAILED_KNOWN",
                reason_code="normalized-recovery-write-failed-known",
            )
            raise
        except Exception:
            recorder.write_result(
                operation_id=operation.operation_id,
                status="AMBIGUOUS",
                reason_code="normalized-recovery-exception-after-dispatch",
            )
            raise
        recorder.write_result(operation_id=operation.operation_id, status="COMPLETED")
        writes += 1

        actual_lesson: dict[str, Any] | None = None
        try:
            working_snapshot = client.inspect_course(COURSE_ID)
            actual_lesson = _target_lesson(
                working_snapshot,
                module_position=plan.module_position,
                lesson_position=plan.lesson_position,
            )
            actual_fp = live_lesson_fingerprint(actual_lesson)
            if actual_fp != operation.normalized_fingerprint_after:
                raise ContentWriteError(
                    f"Recovery {operation.operation_id}: normalized full lesson read-back mismatch"
                )
            if operation.kind == "step" and operation.step_id is not None and operation.normalized_expected_step is not None:
                _assert_readback(
                    client.fetch_one("step-sources", int(operation.step_id)),
                    operation.normalized_expected_step,
                )
        except Exception:
            _append_diagnostic(
                recorder,
                operation_id=operation.operation_id,
                expected_normalized_fingerprint=operation.normalized_fingerprint_after,
                actual_lesson=actual_lesson,
                reason="normalized-recovery-readback-mismatch-or-unavailable",
            )
            recorder.readback_failed(
                operation_id=operation.operation_id,
                reason_code="normalized-recovery-readback-mismatch-or-unavailable",
            )
            raise
        _append_normalized_readback(
            recorder,
            operation=operation,
            actual_normalized_fingerprint=actual_fp,
        )
        working_lesson = actual_lesson

    final_snapshot = client.inspect_course(COURSE_ID)
    final_lesson = _target_lesson(
        final_snapshot,
        module_position=plan.module_position,
        lesson_position=plan.lesson_position,
    )
    final_fp = live_lesson_fingerprint(final_lesson)
    if final_fp != plan.normalized_desired_fingerprint:
        _append_diagnostic(
            recorder,
            operation_id=None,
            expected_normalized_fingerprint=plan.normalized_desired_fingerprint,
            actual_lesson=final_lesson,
            reason="normalized-recovery-final-readback-mismatch",
        )
        recorder.readback_failed(
            operation_id=None,
            reason_code="normalized-recovery-final-readback-mismatch",
        )
        raise ContentWriteError("Recovery final live M02 не совпадает с normalized canonical desired")

    final_step_ids = [int(_step_source(item)["id"]) for item in _ordered_live_steps(final_lesson)]
    state_record = build_record(
        canonical_id=RECOVERY_TARGET,
        stepik_lesson_id=plan.lesson_id,
        expected_title=plan.expected_title,
        expected_steps=plan.normalized_expected_steps,
        source_sha=plan.current_source_sha,
        step_ids=final_step_ids,
        source_git_paths=plan.source_git_paths,
    )
    if state_record["applied_fingerprint"] != final_fp:
        raise ContentWriteError("Recovery normalized state record не совпадает с final live fingerprint")

    recorder.final_readback(
        fingerprint_after=plan.identity.desired_fingerprint,
        stepik_object_ids={"lesson_id": plan.lesson_id, "step_ids": final_step_ids},
        status="APPLIED",
        baseline_after=state_record,
    )

    next_state = with_record(state, canonical_id=RECOVERY_TARGET, record=state_record)
    next_state = close_lesson_pending(
        next_state,
        canonical_id=RECOVERY_TARGET,
        confirmed_at=str(state_record["applied_at"]),
        confirmation_status="APPLIED",
    )
    return NormalizationRecoveryResult(
        plan=plan,
        next_state=next_state,
        state_record=state_record,
        final_snapshot=final_snapshot,
        stepik_writes=writes,
    )
