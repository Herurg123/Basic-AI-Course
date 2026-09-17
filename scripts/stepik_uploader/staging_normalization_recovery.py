from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from .api import StepikAPIError, StepikWriteAmbiguousError
from .content import CompiledStep
from .deployment_history import DeploymentRecorder, utc_now
from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from .history_runtime import final_confirmed_record, find_incomplete_object_events
from .initial_upload_writer import _lesson_after_created_step
from .sync_state import baseline_for, build_record, close_lesson_pending, with_record
from .verified_rendering import (
    STEPIC_HTML_NORMALIZATION_V2,
    build_rendering_plan,
    normalize_stepik_html,
    normalize_stepik_html_v1,
    require_render_ready,
)
from .writer import (
    ContentWriteError,
    _assert_readback,
    _created_id,
    _step_source,
    _target_lesson,
    classify_existing_steps,
)

COURSE_ID = 299189
RECOVERY_TARGET = "M06-L02"
INCIDENT_EVENT_ID = "evt-9eda53dbf70ce5b73dfe70a60f138224"
INCIDENT_SOURCE_SHA = "71cddb42eb31156f7c3ce89f84142128b16ab6c9"
INCIDENT_PENDING_FIRST_SHA = "d3c11c9ca9da9b0ed17b888f2d7f5330f450a421"
INCIDENT_LESSON_ID = 2591727
INCIDENT_STEP_IDS = (11291312, 11339675)
INCIDENT_FIRST_OPERATION = "step-0001-11291312"
INCIDENT_FAILED_OPERATION = "step-create-0002"
INCIDENT_LEGACY_DESIRED = "sha256:7a01fca670daa84fb6d35cac969e430ef81c9ad944ae4d65d07edcdbece7d1ee"
INCIDENT_LEGACY_STEP2_AFTER = "sha256:adab3fbd16f44f22cf9732f2a810609b8f1eb5cdecce25aebf2abfd8a12ab2d1"


@dataclass(frozen=True)
class StagingNormalizationRecoveryPlan:
    mode: str
    identity: Any
    records: tuple[dict[str, Any], ...]
    lesson_id: int
    module_position: int
    lesson_position: int
    expected_title: str
    current_source_sha: str
    legacy_steps: tuple[CompiledStep, ...]
    normalized_steps: tuple[CompiledStep, ...]
    legacy_desired_fingerprint: str
    normalized_desired_fingerprint: str
    current_live_fingerprint: str
    current_step_ids: tuple[int, ...]
    matched_prefix: int
    source_git_paths: tuple[str, ...]
    final_state_record: dict[str, Any] | None = None

    @property
    def stepik_writes_planned(self) -> int:
        if self.mode == "FINAL_READBACK_COMMIT_GAP":
            return 0
        return len(self.normalized_steps) - self.matched_prefix

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": RECOVERY_TARGET,
            "mode": self.mode,
            "action": (
                "ADOPT_PROVEN_NORMALIZED_STEP2_AND_CONTINUE"
                if self.mode == "NORMALIZATION_PREFIX_RECOVERY"
                else "COMMIT_ALREADY_CONFIRMED_NORMALIZED_FINAL"
            ),
            "event_id": self.identity.event_id,
            "event_source_sha": self.identity.source_sha,
            "current_source_sha": self.current_source_sha,
            "stepik_lesson_id": self.lesson_id,
            "normalization_contract": STEPIC_HTML_NORMALIZATION_V2,
            "legacy_desired_fingerprint": self.legacy_desired_fingerprint,
            "normalized_desired_fingerprint": self.normalized_desired_fingerprint,
            "current_live_fingerprint": self.current_live_fingerprint,
            "current_step_ids": list(self.current_step_ids),
            "matched_prefix": self.matched_prefix,
            "confirmation_only_operation": (
                INCIDENT_FAILED_OPERATION if self.mode == "NORMALIZATION_PREFIX_RECOVERY" else None
            ),
            "remaining_step_positions": (
                [step.position for step in self.normalized_steps[self.matched_prefix :]]
                if self.mode == "NORMALIZATION_PREFIX_RECOVERY"
                else []
            ),
            "stepik_writes_planned": self.stepik_writes_planned,
            "duplicate_step2_post_planned": False,
            "deletes_planned": False,
            "structural_reorder_planned": False,
        }


@dataclass(frozen=True)
class StagingNormalizationRecoveryResult:
    plan: StagingNormalizationRecoveryPlan
    next_state: dict[str, Any]
    state_record: dict[str, Any]
    final_snapshot: dict[str, Any]
    stepik_writes: int

    def event_artifact(self) -> dict[str, Any]:
        return {
            "event_id": self.plan.identity.event_id,
            "source_sha": self.plan.identity.source_sha,
            "status": "APPLIED",
            "kind": "lesson",
            "canonical_id": RECOVERY_TARGET,
        }


def _legacy_v1_steps(
    *,
    repo_root: Path,
    source_steps: Iterable[Any],
    asset_report: dict[str, Any],
) -> tuple[CompiledStep, ...]:
    raw_plan = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=RECOVERY_TARGET,
        source_steps=source_steps,
        asset_report=asset_report,
        apply_stepik_html_normalization=False,
    )
    raw_steps = require_render_ready(raw_plan)
    return tuple(
        replace(step, text=normalize_stepik_html_v1(step.text).strip())
        for step in raw_steps
    )


def _normalized_v2_steps(
    *,
    repo_root: Path,
    source_steps: Iterable[Any],
    asset_report: dict[str, Any],
) -> tuple[CompiledStep, ...]:
    plan = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=RECOVERY_TARGET,
        source_steps=source_steps,
        asset_report=asset_report,
    )
    return tuple(require_render_ready(plan))


def _ordered_step_ids(lesson: dict[str, Any]) -> tuple[int, ...]:
    ordered = sorted(lesson.get("steps", []), key=lambda item: int(_step_source(item).get("position", 10**9)))
    return tuple(int(_step_source(item)["id"]) for item in ordered)


def _phase_operation_ids(records: Iterable[dict[str, Any]], phase: str) -> set[str]:
    return {
        str(record.get("operation_id"))
        for record in records
        if record.get("phase") == phase and record.get("operation_id")
    }


def _single_record(records: Iterable[dict[str, Any]], *, phase: str, operation_id: str) -> dict[str, Any]:
    matches = [
        record for record in records
        if record.get("phase") == phase and record.get("operation_id") == operation_id
    ]
    if len(matches) != 1:
        raise ContentWriteError(f"{RECOVERY_TARGET}: ожидается ровно один {phase} для {operation_id}")
    return matches[0]


def _assert_exact_incident_identity(identity: Any) -> None:
    if identity.event_id != INCIDENT_EVENT_ID:
        raise ContentWriteError(f"{RECOVERY_TARGET}: normalization recovery разрешён только для exact incident event")
    if identity.course_id != COURSE_ID or identity.kind != "lesson" or identity.object_id != RECOVERY_TARGET:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident identity имеет неожиданный scope")
    if identity.source_sha != INCIDENT_SOURCE_SHA:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident source SHA не совпадает с подтверждённым")
    if identity.desired_fingerprint != INCIDENT_LEGACY_DESIRED:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident desired fingerprint не совпадает с подтверждённым")
    if identity.baseline_fingerprint_before is not None:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident неожиданно содержит pre-existing baseline")
    if identity.pending_first_sha != INCIDENT_PENDING_FIRST_SHA:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident pending_first_sha не совпадает с подтверждённым")


def _assert_current_canonical_is_same_lesson(
    *,
    expected_title: str,
    legacy_steps: tuple[CompiledStep, ...],
    normalized_steps: tuple[CompiledStep, ...],
) -> tuple[str, str]:
    if len(legacy_steps) != 6 or len(normalized_steps) != 6:
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery ожидает ровно 6 learner-facing steps")
    legacy_shape = [(step.position, step.block_name, step.source) for step in legacy_steps]
    normalized_shape = [(step.position, step.block_name, step.source) for step in normalized_steps]
    if legacy_shape != normalized_shape:
        raise ContentWriteError(f"{RECOVERY_TARGET}: normalization изменила semantic step shape")
    for legacy, normalized in zip(legacy_steps, normalized_steps, strict=True):
        rebuilt = replace(legacy, text=normalize_stepik_html(legacy.text).strip())
        if rebuilt.block() != normalized.block():
            raise ContentWriteError(
                f"{RECOVERY_TARGET}: v2 rendering нельзя получить только доказанной HTML normalization"
            )
    legacy_desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=legacy_steps)
    normalized_desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=normalized_steps)
    if legacy_desired != INCIDENT_LEGACY_DESIRED:
        raise ContentWriteError(
            f"{RECOVERY_TARGET}: current canonical под historical v1 больше не совпадает с incident desired"
        )
    if normalized_desired == legacy_desired:
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery не обнаружил доказанную v1→v2 normalization delta")
    return legacy_desired, normalized_desired


def _assert_pending_without_baseline(state: dict[str, Any]) -> None:
    if baseline_for(state, RECOVERY_TARGET) is not None:
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident recovery не должен усыновлять поверх существующего baseline")
    pending = state.get("pending", {}).get("lessons", {}).get(RECOVERY_TARGET)
    if not isinstance(pending, dict) or pending.get("status") != "PENDING":
        raise ContentWriteError(f"{RECOVERY_TARGET}: incident recovery требует действующий PENDING machine state")
    if pending.get("first_pending_sha") != INCIDENT_PENDING_FIRST_SHA:
        raise ContentWriteError(f"{RECOVERY_TARGET}: PENDING first SHA не совпадает с incident identity")


def _assert_original_history_boundary(records: tuple[dict[str, Any], ...]) -> None:
    if any(record.get("phase") in {"WRITE_AMBIGUOUS", "WRITE_FAILED_KNOWN"} for record in records):
        raise ContentWriteError(f"{RECOVERY_TARGET}: ambiguous/known-failed write запрещает normalization recovery")
    dispatch = _phase_operation_ids(records, "WRITE_DISPATCH_STARTED")
    completed = _phase_operation_ids(records, "WRITE_COMPLETED")
    confirmed = _phase_operation_ids(records, "OP_READBACK_CONFIRMED")
    failed = _phase_operation_ids(records, "READBACK_FAILED")
    exact_dispatch = {INCIDENT_FIRST_OPERATION, INCIDENT_FAILED_OPERATION}
    if dispatch != exact_dispatch or completed != exact_dispatch:
        raise ContentWriteError(f"{RECOVERY_TARGET}: dispatched/completed history больше не равна exact incident prefix")
    if failed != {INCIDENT_FAILED_OPERATION}:
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery требует единственный historical READBACK_FAILED step2")
    if not {INCIDENT_FIRST_OPERATION}.issubset(confirmed):
        raise ContentWriteError(f"{RECOVERY_TARGET}: step1 не имеет historical read-back confirmation")
    if confirmed - exact_dispatch:
        raise ContentWriteError(f"{RECOVERY_TARGET}: history содержит unexpected confirmed operation")
    if INCIDENT_FAILED_OPERATION in confirmed:
        recovered = _single_record(
            records,
            phase="OP_READBACK_CONFIRMED",
            operation_id=INCIDENT_FAILED_OPERATION,
        )
        if recovered.get("read_back_result") != "CONFIRMED_NORMALIZED":
            raise ContentWriteError(f"{RECOVERY_TARGET}: существующий step2 recovery record имеет другой basis")
        if recovered.get("normalization_contract") != STEPIC_HTML_NORMALIZATION_V2:
            raise ContentWriteError(f"{RECOVERY_TARGET}: step2 recovery record относится к другому normalization contract")
    step2_intent = _single_record(records, phase="WRITE_INTENT", operation_id=INCIDENT_FAILED_OPERATION)
    if step2_intent.get("expected_fingerprint_after") != INCIDENT_LEGACY_STEP2_AFTER:
        raise ContentWriteError(f"{RECOVERY_TARGET}: historical step2 intent fingerprint изменился")


def build_staging_normalization_recovery_plan(
    *,
    target_id: str,
    client: Any,
    repo_root: Path,
    state: dict[str, Any],
    store: Any,
    current_source_sha: str,
    source_steps: Iterable[Any],
    asset_report: dict[str, Any],
    module_position: int,
    lesson_position: int,
    expected_title: str,
) -> StagingNormalizationRecoveryPlan | None:
    if target_id != RECOVERY_TARGET:
        return None
    incomplete = find_incomplete_object_events(store, object_id=RECOVERY_TARGET)
    if not incomplete:
        return None
    if len(incomplete) != 1:
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery требует ровно один incomplete event")
    identity, raw_records, summary = incomplete[0]
    _assert_exact_incident_identity(identity)
    _assert_pending_without_baseline(state)
    records = tuple(deepcopy(raw_records))

    legacy_steps = _legacy_v1_steps(
        repo_root=repo_root,
        source_steps=source_steps,
        asset_report=asset_report,
    )
    normalized_steps = _normalized_v2_steps(
        repo_root=repo_root,
        source_steps=source_steps,
        asset_report=asset_report,
    )
    legacy_desired, normalized_desired = _assert_current_canonical_is_same_lesson(
        expected_title=expected_title,
        legacy_steps=legacy_steps,
        normalized_steps=normalized_steps,
    )

    snapshot = client.inspect_course(COURSE_ID)
    live_lesson = _target_lesson(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    if int(live_lesson.get("id", -1)) != INCIDENT_LESSON_ID:
        raise ContentWriteError(f"{RECOVERY_TARGET}: live lesson ID не совпадает с exact incident")
    live_fp = live_lesson_fingerprint(live_lesson)
    step_ids = _ordered_step_ids(live_lesson)
    source_paths = tuple(path for step in normalized_steps for path in step.source_git_paths)

    if summary.get("machine_state_committed"):
        return None
    if summary.get("final_readback_confirmed"):
        final = final_confirmed_record(list(records))
        if not isinstance(final, dict) or final.get("status") != "APPLIED":
            raise ContentWriteError(f"{RECOVERY_TARGET}: final incident history имеет неожиданный status")
        state_record = final.get("actual_confirmed_state")
        if not isinstance(state_record, dict):
            raise ContentWriteError(f"{RECOVERY_TARGET}: final incident history не содержит normalized baseline")
        if state_record.get("applied_fingerprint") != normalized_desired:
            raise ContentWriteError(f"{RECOVERY_TARGET}: final incident baseline не совпадает с current v2 desired")
        if state_record.get("applied_source_sha") != current_source_sha:
            raise ContentWriteError(f"{RECOVERY_TARGET}: final incident baseline относится не к current main")
        if int(state_record.get("stepik_lesson_id", -1)) != INCIDENT_LESSON_ID:
            raise ContentWriteError(f"{RECOVERY_TARGET}: final incident baseline относится к другому lesson")
        state_after, matched_after = classify_existing_steps(list(live_lesson.get("steps", [])), list(normalized_steps))
        if state_after != "complete" or matched_after != len(normalized_steps) or live_fp != normalized_desired:
            raise ContentWriteError(f"{RECOVERY_TARGET}: live drift после final normalized read-back")
        return StagingNormalizationRecoveryPlan(
            mode="FINAL_READBACK_COMMIT_GAP",
            identity=identity,
            records=records,
            lesson_id=INCIDENT_LESSON_ID,
            module_position=module_position,
            lesson_position=lesson_position,
            expected_title=expected_title,
            current_source_sha=current_source_sha,
            legacy_steps=legacy_steps,
            normalized_steps=normalized_steps,
            legacy_desired_fingerprint=legacy_desired,
            normalized_desired_fingerprint=normalized_desired,
            current_live_fingerprint=live_fp,
            current_step_ids=step_ids,
            matched_prefix=len(normalized_steps),
            source_git_paths=source_paths,
            final_state_record=deepcopy(state_record),
        )

    _assert_original_history_boundary(records)
    state_after, matched = classify_existing_steps(list(live_lesson.get("steps", [])), list(normalized_steps))
    if state_after != "partial" or matched != 2:
        raise ContentWriteError(f"{RECOVERY_TARGET}: live state должен быть exact normalized prefix из двух steps")
    if step_ids != INCIDENT_STEP_IDS:
        raise ContentWriteError(f"{RECOVERY_TARGET}: live step IDs отличаются от exact incident")
    if live_fp == INCIDENT_LEGACY_STEP2_AFTER:
        raise ContentWriteError(f"{RECOVERY_TARGET}: normalization recovery не применяется при legacy fingerprint match")

    return StagingNormalizationRecoveryPlan(
        mode="NORMALIZATION_PREFIX_RECOVERY",
        identity=identity,
        records=records,
        lesson_id=INCIDENT_LESSON_ID,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
        current_source_sha=current_source_sha,
        legacy_steps=legacy_steps,
        normalized_steps=normalized_steps,
        legacy_desired_fingerprint=legacy_desired,
        normalized_desired_fingerprint=normalized_desired,
        current_live_fingerprint=live_fp,
        current_step_ids=step_ids,
        matched_prefix=2,
        source_git_paths=source_paths,
    )


def _append_step2_normalized_confirmation(
    recorder: DeploymentRecorder,
    *,
    actual_normalized_fingerprint: str,
) -> None:
    existing = [
        record for record in recorder.records(refresh=True)
        if record.get("phase") == "OP_READBACK_CONFIRMED"
        and record.get("operation_id") == INCIDENT_FAILED_OPERATION
    ]
    if existing:
        if len(existing) != 1:
            raise ContentWriteError(f"{RECOVERY_TARGET}: несколько recovery confirmations для step2")
        record = existing[0]
        if (
            record.get("fingerprint_after") != INCIDENT_LEGACY_STEP2_AFTER
            or record.get("read_back_result") != "CONFIRMED_NORMALIZED"
            or record.get("normalization_contract") != STEPIC_HTML_NORMALIZATION_V2
            or record.get("actual_normalized_fingerprint") != actual_normalized_fingerprint
        ):
            raise ContentWriteError(f"{RECOVERY_TARGET}: existing step2 recovery confirmation конфликтует")
        return
    recorder._append(
        "OP_READBACK_CONFIRMED",
        {
            "confirmed_at": utc_now(),
            "operation_id": INCIDENT_FAILED_OPERATION,
            "fingerprint_after": INCIDENT_LEGACY_STEP2_AFTER,
            "read_back_result": "CONFIRMED_NORMALIZED",
            "confirmation_basis": "exact-m06-stepik-html-normalization-incident",
            "normalization_contract": STEPIC_HTML_NORMALIZATION_V2,
            "actual_normalized_fingerprint": actual_normalized_fingerprint,
        },
        operation_id=INCIDENT_FAILED_OPERATION,
    )


def _next_state(state: dict[str, Any], *, state_record: dict[str, Any]) -> dict[str, Any]:
    next_state = with_record(state, canonical_id=RECOVERY_TARGET, record=state_record)
    return close_lesson_pending(
        next_state,
        canonical_id=RECOVERY_TARGET,
        confirmed_at=str(state_record["applied_at"]),
        confirmation_status="APPLIED",
    )


def execute_staging_normalization_recovery(
    *,
    client: Any,
    plan: StagingNormalizationRecoveryPlan,
    store: Any,
    state: dict[str, Any],
) -> StagingNormalizationRecoveryResult:
    if plan.mode == "FINAL_READBACK_COMMIT_GAP":
        if not isinstance(plan.final_state_record, dict):
            raise ContentWriteError(f"{RECOVERY_TARGET}: commit-gap recovery не содержит final state record")
        snapshot = client.inspect_course(COURSE_ID)
        lesson = _target_lesson(
            snapshot,
            module_position=plan.module_position,
            lesson_position=plan.lesson_position,
            expected_title=plan.expected_title,
        )
        if live_lesson_fingerprint(lesson) != plan.normalized_desired_fingerprint:
            raise ContentWriteError(f"{RECOVERY_TARGET}: commit-gap race-check обнаружил live drift")
        return StagingNormalizationRecoveryResult(
            plan=plan,
            next_state=_next_state(state, state_record=plan.final_state_record),
            state_record=deepcopy(plan.final_state_record),
            final_snapshot=snapshot,
            stepik_writes=0,
        )

    if plan.mode != "NORMALIZATION_PREFIX_RECOVERY":
        raise ContentWriteError(f"{RECOVERY_TARGET}: неизвестный recovery mode {plan.mode!r}")

    recorder = DeploymentRecorder(store, plan.identity)
    fresh_snapshot = client.inspect_course(COURSE_ID)
    fresh_lesson = _target_lesson(
        fresh_snapshot,
        module_position=plan.module_position,
        lesson_position=plan.lesson_position,
        expected_title=plan.expected_title,
    )
    fresh_state, fresh_matched = classify_existing_steps(
        list(fresh_lesson.get("steps", [])),
        list(plan.normalized_steps),
    )
    if (
        fresh_state != "partial"
        or fresh_matched != 2
        or _ordered_step_ids(fresh_lesson) != INCIDENT_STEP_IDS
        or live_lesson_fingerprint(fresh_lesson) != plan.current_live_fingerprint
    ):
        raise ContentWriteError(f"{RECOVERY_TARGET}: recovery race-check обнаружил изменение live prefix")

    recorder.recovery_classified(
        classification="EXACT_M06_STEPIK_HTML_NORMALIZATION_V2",
        reason_codes=[
            "exact-incident-event-identity",
            "step2-write-completed-2xx",
            "single-step2-readback-failure",
            "live-two-step-prefix-matches-current-normalized-canonical",
            "current-legacy-v1-desired-matches-original-event",
            "duplicate-step2-post-forbidden",
        ],
    )
    _append_step2_normalized_confirmation(
        recorder,
        actual_normalized_fingerprint=live_lesson_fingerprint(fresh_lesson),
    )

    working_lesson = fresh_lesson
    writes = 0
    for expected in plan.normalized_steps[2:]:
        operation_id = f"step-create-{expected.position:04d}"
        before_fp = live_lesson_fingerprint(working_lesson)
        expected_lesson = _lesson_after_created_step(working_lesson, expected)
        expected_after_fp = live_lesson_fingerprint(expected_lesson)
        recorder.write_intent(
            operation_id=operation_id,
            method="POST",
            target="step-sources",
            fingerprint_before=before_fp,
            expected_fingerprint_after=expected_after_fp,
        )
        recorder.write_dispatch_started(operation_id=operation_id)
        try:
            payload = client.create_step_source(
                lesson_id=plan.lesson_id,
                position=expected.position,
                block=expected.block(),
            )
        except StepikWriteAmbiguousError:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="m06-normalized-recovery-create-ambiguous",
            )
            raise
        except StepikAPIError:
            recorder.write_result(
                operation_id=operation_id,
                status="FAILED_KNOWN",
                reason_code="m06-normalized-recovery-create-failed-known",
            )
            raise
        except Exception:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="m06-normalized-recovery-exception-after-dispatch",
            )
            raise
        step_id = _created_id(payload)
        recorder.write_result(operation_id=operation_id, status="COMPLETED")
        writes += 1

        actual_lesson: dict[str, Any] | None = None
        try:
            readback = client.fetch_one("step-sources", step_id)
            _assert_readback(readback, expected)
            current_snapshot = client.inspect_course(COURSE_ID)
            actual_lesson = _target_lesson(
                current_snapshot,
                module_position=plan.module_position,
                lesson_position=plan.lesson_position,
                expected_title=plan.expected_title,
            )
            state_after, matched_after = classify_existing_steps(
                list(actual_lesson.get("steps", [])),
                list(plan.normalized_steps),
            )
            expected_matched = int(expected.position)
            if expected_matched == len(plan.normalized_steps):
                if state_after != "complete" or matched_after != expected_matched:
                    raise ContentWriteError(f"{RECOVERY_TARGET}: final create prefix read-back mismatch")
            elif state_after != "partial" or matched_after != expected_matched:
                raise ContentWriteError(
                    f"{RECOVERY_TARGET}: recovery prefix after position={expected.position} не подтверждён"
                )
            actual_fp = live_lesson_fingerprint(actual_lesson)
            if actual_fp != expected_after_fp:
                raise ContentWriteError(
                    f"{RECOVERY_TARGET}: full-lesson fingerprint after position={expected.position} mismatch"
                )
        except Exception:
            recorder.readback_failed(
                operation_id=operation_id,
                reason_code="m06-normalized-recovery-readback-mismatch-or-unavailable",
            )
            raise
        recorder.operation_readback(
            operation_id=operation_id,
            expected_fingerprint_after=expected_after_fp,
        )
        working_lesson = actual_lesson

    final_snapshot = client.inspect_course(COURSE_ID)
    final_lesson = _target_lesson(
        final_snapshot,
        module_position=plan.module_position,
        lesson_position=plan.lesson_position,
        expected_title=plan.expected_title,
    )
    final_state, final_matched = classify_existing_steps(
        list(final_lesson.get("steps", [])),
        list(plan.normalized_steps),
    )
    final_fp = live_lesson_fingerprint(final_lesson)
    if (
        final_state != "complete"
        or final_matched != len(plan.normalized_steps)
        or final_fp != plan.normalized_desired_fingerprint
    ):
        recorder.readback_failed(
            operation_id=None,
            reason_code="m06-normalized-recovery-final-readback-mismatch",
        )
        raise ContentWriteError(f"{RECOVERY_TARGET}: final normalized live lesson не совпадает с current canonical")

    final_step_ids = _ordered_step_ids(final_lesson)
    state_record = build_record(
        canonical_id=RECOVERY_TARGET,
        stepik_lesson_id=plan.lesson_id,
        expected_title=plan.expected_title,
        expected_steps=plan.normalized_steps,
        source_sha=plan.current_source_sha,
        step_ids=final_step_ids,
        source_git_paths=plan.source_git_paths,
    )
    if state_record["applied_fingerprint"] != final_fp:
        raise ContentWriteError(f"{RECOVERY_TARGET}: normalized machine baseline не совпадает с final live fingerprint")

    # Immutable event validation still requires the historical desired fingerprint in this
    # field. The actual v2 fingerprint is carried by baseline_after and every new operation
    # read-back; changing the old event identity would destroy the append-only evidence chain.
    recorder.final_readback(
        fingerprint_after=plan.legacy_desired_fingerprint,
        stepik_object_ids={"lesson_id": plan.lesson_id, "step_ids": list(final_step_ids)},
        status="APPLIED",
        baseline_after=state_record,
    )

    return StagingNormalizationRecoveryResult(
        plan=plan,
        next_state=_next_state(state, state_record=state_record),
        state_record=state_record,
        final_snapshot=final_snapshot,
        stepik_writes=writes,
    )
