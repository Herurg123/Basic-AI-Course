from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from stepik_uploader.canonical import build_structural_manifest
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.fingerprints import canonical_hash
    from stepik_uploader.history_runtime import find_object_events
    from stepik_uploader.replacement_update import (
        ReplacementPlan,
        ReplacementUpdateError,
        dispatch_replacement_put,
        plan_replacement_put,
    )
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
else:
    from .api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from .canonical import build_structural_manifest
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .fingerprints import canonical_hash
    from .history_runtime import find_object_events
    from .replacement_update import (
        ReplacementPlan,
        ReplacementUpdateError,
        dispatch_replacement_put,
        plan_replacement_put,
    )
    from .reporting import write_json
    from .stepik_uploader import source_sha

COURSE_ID = 299189
RECOVERY_KIND = "section-position-recovery"
RECOVERY_OPERATION = "section-position-recovery"
RECOVERY_OPERATION_ID = "position-put"

SECTION_IDS = {
    "M00": 755023,
    "M01": 755025,
    "M02": 755027,
    "M03": 755028,
    "M04": 755029,
    "M05": 755030,
    "M06": 755031,
    "M07": 755032,
    "M08": 755033,
}
TARGET_POSITIONS = {module_id: index + 1 for index, module_id in enumerate(SECTION_IDS)}
MALFORMED_POSITIONS = {
    "M00": 1,
    "M01": 1,
    "M02": 1,
    "M03": 1,
    "M04": 1,
    "M05": 1,
    "M06": 1,
    "M07": 1,
    "M08": 9,
}

# Frozen from the last confirmed pre-recovery production snapshot. Recovery never writes units/lessons.
UNIT_LAYOUT = {
    "M00": ((2631074, 1, 2591708), (2631076, 2, 2591710), (2631077, 3, 2591711)),
    "M01": ((2631081, 1, 2591715), (2631082, 2, 2591716)),
    "M02": ((2631083, 1, 2591717), (2631084, 2, 2591718)),
    "M03": ((2631085, 1, 2591719), (2631086, 2, 2591720)),
    "M04": ((2631087, 1, 2591721), (2631088, 2, 2591722), (2631089, 3, 2591723)),
    "M05": ((2631090, 1, 2591724), (2631091, 2, 2591725)),
    "M06": ((2631092, 1, 2591726), (2631093, 2, 2591727), (2631094, 3, 2591728), (2631095, 4, 2591729)),
    "M07": ((2631097, 1, 2591731), (2631098, 2, 2591732)),
    "M08": ((2631100, 1, 2591734),),
}


class SectionRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SectionSpec:
    canonical_id: str
    section_id: int
    title: str
    malformed_position: int
    target_position: int
    units: tuple[tuple[int, int, int], ...]

    @property
    def object_id(self) -> str:
        return f"section-position:{self.canonical_id}"


@dataclass
class RecoveryItem:
    spec: SectionSpec
    live_state: dict[str, Any]
    desired_state: dict[str, Any]
    baseline_state: dict[str, Any]
    status: str
    identity: Any | None = None
    records: list[dict[str, Any]] | None = None
    summary: dict[str, Any] | None = None
    replacement_plan: ReplacementPlan | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded recovery section positions for Stepik course 299189")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-section-position-recovery"))
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SectionRecoveryError("Для Stepik recovery нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_specs(manifest: dict[str, Any]) -> list[SectionSpec]:
    modules = list(manifest.get("modules", []))
    by_id = {str(item.get("canonical_id")): item for item in modules if isinstance(item, dict)}
    if set(by_id) != set(SECTION_IDS):
        raise SectionRecoveryError("Canonical manifest modules не равны exact M00..M08 recovery set")
    specs: list[SectionSpec] = []
    for canonical_id, section_id in SECTION_IDS.items():
        module = by_id[canonical_id]
        target = TARGET_POSITIONS[canonical_id]
        if int(module.get("position", -1)) != target:
            raise SectionRecoveryError(f"{canonical_id}: canonical module position изменился")
        title = str(module.get("title") or "")
        if not title:
            raise SectionRecoveryError(f"{canonical_id}: canonical title отсутствует")
        if canonical_id == "M08":
            title = f"M08 — {title}"
        specs.append(
            SectionSpec(
                canonical_id=canonical_id,
                section_id=section_id,
                title=title,
                malformed_position=MALFORMED_POSITIONS[canonical_id],
                target_position=target,
                units=UNIT_LAYOUT[canonical_id],
            )
        )
    return specs


def _normalized_section(snapshot: dict[str, Any], section_id: int) -> dict[str, Any]:
    matches = [item for item in snapshot.get("sections", []) if int(item.get("id", -1)) == int(section_id)]
    if len(matches) != 1:
        raise SectionRecoveryError(f"section {section_id}: expected exactly one normalized section, got {len(matches)}")
    return matches[0]


def _layout_from_normalized(section: dict[str, Any]) -> tuple[tuple[int, int, int], ...]:
    layout: list[tuple[int, int, int]] = []
    for unit in section.get("units", []):
        lesson = unit.get("lesson")
        if not isinstance(lesson, dict):
            raise SectionRecoveryError("Normalized unit не содержит lesson")
        layout.append((int(unit["id"]), int(unit["position"]), int(lesson["id"])))
    return tuple(sorted(layout, key=lambda row: (row[1], row[0])))


def _state(spec: SectionSpec, *, position: int) -> dict[str, Any]:
    return {
        "kind": RECOVERY_KIND,
        "course_id": COURSE_ID,
        "canonical_id": spec.canonical_id,
        "section_id": spec.section_id,
        "title": spec.title,
        "position": int(position),
        "unit_layout": [
            {"unit_id": unit_id, "position": unit_position, "lesson_id": lesson_id}
            for unit_id, unit_position, lesson_id in spec.units
        ],
    }


def _fingerprint(state: dict[str, Any]) -> str:
    return canonical_hash(state)


def _validate_snapshot_static(snapshot: dict[str, Any], specs: list[SectionSpec]) -> None:
    course = snapshot.get("course")
    if not isinstance(course, dict) or int(course.get("id", -1)) != COURSE_ID:
        raise SectionRecoveryError("Live course ID не совпадает с recovery target")
    if course.get("language") != "ru" or course.get("is_public") is not False:
        raise SectionRecoveryError("Recovery разрешён только для непубличного русскоязычного project course")
    live_sections = list(snapshot.get("sections", []))
    live_ids = {int(item.get("id", -1)) for item in live_sections}
    expected_ids = {spec.section_id for spec in specs}
    if live_ids != expected_ids or len(live_sections) != len(specs):
        raise SectionRecoveryError(f"Live section IDs drift: {sorted(live_ids)} != {sorted(expected_ids)}")
    for spec in specs:
        section = _normalized_section(snapshot, spec.section_id)
        if str(section.get("title")) != spec.title:
            raise SectionRecoveryError(
                f"{spec.canonical_id}: live title drift {section.get('title')!r} != {spec.title!r}"
            )
        if _layout_from_normalized(section) != spec.units:
            raise SectionRecoveryError(f"{spec.canonical_id}: unit/lesson topology drift")
        try:
            position = int(section.get("position"))
        except (TypeError, ValueError) as exc:
            raise SectionRecoveryError(f"{spec.canonical_id}: section position повреждён") from exc
        if position not in {spec.malformed_position, spec.target_position}:
            raise SectionRecoveryError(
                f"{spec.canonical_id}: arbitrary position drift {position}; "
                f"allowed pre-recovery states={sorted({spec.malformed_position, spec.target_position})}"
            )


def _verify_raw_section(client: Any, spec: SectionSpec, expected_position: int) -> dict[str, Any]:
    raw = client.fetch_one("sections", spec.section_id)
    try:
        live_id = int(raw.get("id", -1))
        live_course = int(raw.get("course", -1))
        live_position = int(raw.get("position", -1))
    except (TypeError, ValueError) as exc:
        raise SectionRecoveryError(f"{spec.canonical_id}: raw section structural fields повреждены") from exc
    if live_id != spec.section_id or live_course != COURSE_ID:
        raise SectionRecoveryError(f"{spec.canonical_id}: raw section id/course drift")
    if str(raw.get("title")) != spec.title:
        raise SectionRecoveryError(f"{spec.canonical_id}: raw section title drift")
    if live_position != expected_position:
        raise SectionRecoveryError(
            f"{spec.canonical_id}: raw section position {live_position} != {expected_position}"
        )
    unit_ids = [row[0] for row in spec.units]
    raw_unit_ids = [int(value) for value in raw.get("units", [])]
    if set(raw_unit_ids) != set(unit_ids) or len(raw_unit_ids) != len(unit_ids):
        raise SectionRecoveryError(f"{spec.canonical_id}: raw section unit IDs drift")
    units = client.fetch_many("units", unit_ids)
    live_layout = tuple(
        sorted(
            (int(unit.get("id", -1)), int(unit.get("position", -1)), int(unit.get("lesson", -1)))
            for unit in units
        )
    )
    if live_layout != tuple(sorted(spec.units)):
        raise SectionRecoveryError(f"{spec.canonical_id}: unit positions/lesson bindings drift")
    for unit in units:
        if int(unit.get("section", spec.section_id)) != spec.section_id:
            raise SectionRecoveryError(f"{spec.canonical_id}: unit section binding drift")
    return _state(spec, position=live_position)


def _verify_all_raw(client: Any, snapshot: dict[str, Any], specs: list[SectionSpec], *, require_target: bool) -> None:
    for spec in specs:
        normalized = _normalized_section(snapshot, spec.section_id)
        position = int(normalized["position"])
        if require_target and position != spec.target_position:
            raise SectionRecoveryError(
                f"{spec.canonical_id}: final normalized position {position} != {spec.target_position}"
            )
        raw_state = _verify_raw_section(client, spec, position)
        if raw_state != _state(spec, position=position):
            raise SectionRecoveryError(f"{spec.canonical_id}: raw/normalized structural state mismatch")


def _matching_history(item: RecoveryItem, store: Any, current_sha: str) -> RecoveryItem:
    spec = item.spec
    desired_fp = _fingerprint(item.desired_state)
    baseline_fp = _fingerprint(item.baseline_state)
    expected_identity = event_identity_from_environment(
        course_id=COURSE_ID,
        object_id=spec.object_id,
        kind=RECOVERY_KIND,
        source_sha=current_sha,
        desired_fingerprint=desired_fp,
        baseline_fingerprint=baseline_fp,
        pending_first_sha=None,
    )
    events = find_object_events(store, object_id=spec.object_id)
    incomplete = [event for event in events if not event[2].get("machine_state_committed")]
    if len(incomplete) > 1:
        raise SectionRecoveryError(f"{spec.object_id}: несколько incomplete recovery events")
    if incomplete:
        identity, records, summary = incomplete[0]
        if identity.event_id != expected_identity.event_id:
            raise SectionRecoveryError(
                f"{spec.object_id}: incomplete recovery event относится к другому main/semantics"
            )
        if identity.kind != RECOVERY_KIND or identity.course_id != COURSE_ID:
            raise SectionRecoveryError(f"{spec.object_id}: recovery history identity повреждена")
        item.identity, item.records, item.summary = identity, records, summary
        return item

    committed_matches = [
        event
        for event in events
        if event[0].kind == RECOVERY_KIND
        and event[0].course_id == COURSE_ID
        and event[0].desired_fingerprint == desired_fp
        and event[2].get("machine_state_committed")
    ]
    if committed_matches:
        identity, records, summary = committed_matches[-1]
        item.identity, item.records, item.summary = identity, records, summary
        return item

    item.identity, item.records, item.summary = expected_identity, [], None
    return item


def _completed_write_without_readback(records: list[dict[str, Any]] | None) -> bool:
    if not records:
        return False
    phases = [record.get("phase") for record in records]
    return phases.count("WRITE_DISPATCH_STARTED") == 1 and phases.count("WRITE_COMPLETED") == 1 and phases.count("OP_READBACK_CONFIRMED") == 0


def _classify_items(snapshot: dict[str, Any], specs: list[SectionSpec], store: Any, current_sha: str) -> list[RecoveryItem]:
    items: list[RecoveryItem] = []
    for spec in specs:
        section = _normalized_section(snapshot, spec.section_id)
        position = int(section["position"])
        live = _state(spec, position=position)
        baseline = _state(spec, position=spec.malformed_position)
        desired = _state(spec, position=spec.target_position)
        item = RecoveryItem(spec=spec, live_state=live, desired_state=desired, baseline_state=baseline, status="UNKNOWN")
        if spec.malformed_position == spec.target_position:
            item.status = "ANCHOR_CONFIRMED"
            items.append(item)
            continue

        _matching_history(item, store, current_sha)
        summary = item.summary
        if position == spec.malformed_position:
            if summary and summary.get("machine_state_committed"):
                raise SectionRecoveryError(f"{spec.object_id}: live position regressed after committed recovery")
            if summary and (
                summary.get("writes_started")
                or summary.get("ambiguous")
                or summary.get("readback_failed")
                or summary.get("known_failed_writes")
            ):
                raise SectionRecoveryError(
                    f"{spec.object_id}: prior dispatch exists while live is malformed; blind retry forbidden"
                )
            item.status = "WRITE_REQUIRED"
        elif position == spec.target_position:
            if summary is None:
                raise SectionRecoveryError(
                    f"{spec.object_id}: target position exists without durable recovery evidence; auto-adoption forbidden"
                )
            if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
                raise SectionRecoveryError(
                    f"{spec.object_id}: target position follows ambiguous/failed history; explicit reconcile required"
                )
            if summary.get("machine_state_committed"):
                if summary.get("committed_baseline_after") != desired:
                    raise SectionRecoveryError(f"{spec.object_id}: committed recovery baseline conflicts with live target")
                item.status = "ALREADY_RECOVERED"
            elif summary.get("final_readback_confirmed"):
                item.status = "FINAL_NEEDS_COMMIT"
            elif summary.get("writes_started") == 1 and summary.get("confirmed_operation_count") == 1:
                item.status = "GLOBAL_FINAL_PENDING"
            elif _completed_write_without_readback(item.records):
                item.status = "OP_READBACK_RECOVERABLE"
            else:
                raise SectionRecoveryError(
                    f"{spec.object_id}: live target cannot be explained by confirmed recovery boundary"
                )
        items.append(item)
    return items


def _plan_write(client: Any, item: RecoveryItem) -> ReplacementPlan:
    spec = item.spec
    plan = plan_replacement_put(
        client,
        resource="sections",
        object_id=spec.section_id,
        changes={"position": spec.target_position},
        required_preserved_fields=("title", "position", "course"),
    )
    before = plan.before
    if str(before.get("title")) != spec.title:
        raise SectionRecoveryError(f"{spec.canonical_id}: title changed during replacement preflight")
    if int(before.get("course", -1)) != COURSE_ID:
        raise SectionRecoveryError(f"{spec.canonical_id}: course changed during replacement preflight")
    if int(before.get("position", -1)) != spec.malformed_position:
        raise SectionRecoveryError(f"{spec.canonical_id}: position changed during replacement preflight")
    payload = plan.payload.get("section")
    if not isinstance(payload, dict) or int(payload.get("position", -1)) != spec.target_position:
        raise SectionRecoveryError(f"{spec.canonical_id}: replacement payload does not contain target position")
    if str(payload.get("title")) != spec.title or int(payload.get("course", -1)) != COURSE_ID:
        raise SectionRecoveryError(f"{spec.canonical_id}: replacement payload does not preserve title/course")
    return plan


def _confirm_plan_still_current(client: Any, item: RecoveryItem, plan: ReplacementPlan) -> None:
    raw = client.fetch_one("sections", item.spec.section_id)
    body = plan.payload["section"]
    for field in plan.writable_fields:
        if field == "position":
            if int(raw.get(field, -1)) != item.spec.malformed_position:
                raise SectionRecoveryError(f"{item.spec.canonical_id}: position changed before dispatch")
            continue
        if field in body and raw.get(field) != body[field]:
            raise SectionRecoveryError(
                f"{item.spec.canonical_id}: writable field {field!r} changed before dispatch"
            )


def _execute_write(client: Any, store: Any, item: RecoveryItem, current_sha: str) -> None:
    spec = item.spec
    plan = item.replacement_plan or _plan_write(client, item)
    desired_fp = _fingerprint(item.desired_state)
    baseline_fp = _fingerprint(item.baseline_state)
    identity = item.identity or event_identity_from_environment(
        course_id=COURSE_ID,
        object_id=spec.object_id,
        kind=RECOVERY_KIND,
        source_sha=current_sha,
        desired_fingerprint=desired_fp,
        baseline_fingerprint=baseline_fp,
        pending_first_sha=None,
    )
    recorder = DeploymentRecorder(store, identity)
    recorder.ensure_started(
        operation_type=RECOVERY_OPERATION,
        state_before=item.baseline_state,
        expected_state=item.desired_state,
        stepik_object_ids={"section_id": spec.section_id},
        fingerprint_before=baseline_fp,
    )
    recorder.write_intent(
        operation_id=RECOVERY_OPERATION_ID,
        method="PUT",
        target=f"sections/{spec.section_id}",
        fingerprint_before=baseline_fp,
        expected_fingerprint_after=desired_fp,
    )
    _confirm_plan_still_current(client, item, plan)
    recorder.write_dispatch_started(operation_id=RECOVERY_OPERATION_ID)
    try:
        dispatch_replacement_put(client, plan)
    except StepikWriteAmbiguousError:
        recorder.write_result(
            operation_id=RECOVERY_OPERATION_ID,
            status="AMBIGUOUS",
            reason_code="section-position-write-ambiguous",
        )
        raise
    except StepikAPIError:
        recorder.write_result(
            operation_id=RECOVERY_OPERATION_ID,
            status="FAILED_KNOWN",
            reason_code="section-position-write-failed-known",
        )
        raise
    except Exception:
        recorder.write_result(
            operation_id=RECOVERY_OPERATION_ID,
            status="AMBIGUOUS",
            reason_code="section-position-exception-after-dispatch",
        )
        raise
    recorder.write_result(operation_id=RECOVERY_OPERATION_ID, status="COMPLETED")

    try:
        immediate = _verify_raw_section(client, spec, spec.target_position)
        if immediate != item.desired_state:
            raise SectionRecoveryError(f"{spec.canonical_id}: immediate structural read-back mismatch")
    except Exception:
        recorder.readback_failed(
            operation_id=RECOVERY_OPERATION_ID,
            reason_code="section-position-immediate-readback-failed",
        )
        raise
    recorder.operation_readback(operation_id=RECOVERY_OPERATION_ID, expected_fingerprint_after=desired_fp)
    item.identity = identity
    item.status = "GLOBAL_FINAL_PENDING"


def _recover_completed_write_readback(client: Any, store: Any, item: RecoveryItem) -> None:
    if item.identity is None or item.status != "OP_READBACK_RECOVERABLE":
        raise SectionRecoveryError(f"{item.spec.object_id}: invalid read-back recovery request")
    live = _verify_raw_section(client, item.spec, item.spec.target_position)
    if live != item.desired_state:
        raise SectionRecoveryError(f"{item.spec.object_id}: completed write live state is not desired")
    recorder = DeploymentRecorder(store, item.identity)
    recorder.operation_readback(
        operation_id=RECOVERY_OPERATION_ID,
        expected_fingerprint_after=_fingerprint(item.desired_state),
    )
    item.status = "GLOBAL_FINAL_PENDING"


def _verify_recovered_snapshot(client: Any, snapshot: dict[str, Any], specs: list[SectionSpec]) -> None:
    _validate_snapshot_static(snapshot, specs)
    positions: dict[str, int] = {}
    for spec in specs:
        section = _normalized_section(snapshot, spec.section_id)
        position = int(section["position"])
        positions[spec.canonical_id] = position
        if position != spec.target_position:
            raise SectionRecoveryError(
                f"{spec.canonical_id}: final position {position} != {spec.target_position}"
            )
    if sorted(positions.values()) != list(range(1, 10)):
        raise SectionRecoveryError(f"Final section positions are not exact 1..9: {positions}")
    _verify_all_raw(client, snapshot, specs, require_target=True)


def _close_global_boundaries(store: Any, items: list[RecoveryItem]) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    for item in items:
        if item.spec.malformed_position == item.spec.target_position or item.status == "ALREADY_RECOVERED":
            continue
        if item.identity is None:
            raise SectionRecoveryError(f"{item.spec.object_id}: missing recovery identity at global close")
        recorder = DeploymentRecorder(store, item.identity)
        summary = summarize_event(recorder.records(refresh=True))
        desired_fp = _fingerprint(item.desired_state)
        if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
            raise SectionRecoveryError(f"{item.spec.object_id}: unsafe history at global close")
        if not summary.get("final_readback_confirmed"):
            if summary.get("writes_started") != 1 or summary.get("confirmed_operation_count") != 1:
                raise SectionRecoveryError(f"{item.spec.object_id}: operation read-back missing at global close")
            recorder.final_readback(
                fingerprint_after=desired_fp,
                stepik_object_ids={"section_id": item.spec.section_id},
                status="APPLIED",
                baseline_after=item.desired_state,
            )
        summary = summarize_event(recorder.records(refresh=True))
        if not summary.get("machine_state_committed"):
            recorder.state_committed(baseline_after=item.desired_state, status="APPLIED")
        closed.append({"canonical_id": item.spec.canonical_id, "event_id": item.identity.event_id})
    return closed


def run_recovery(
    *,
    client: Any,
    store: Any,
    manifest: dict[str, Any],
    current_sha: str,
    confirm_write: bool,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    specs = _manifest_specs(manifest)
    before = client.inspect_course(COURSE_ID)
    _validate_snapshot_static(before, specs)
    # Exact preflight proves raw section.course/title/position and frozen unit bindings for all nine sections.
    _verify_all_raw(client, before, specs, require_target=False)
    items = _classify_items(before, specs, store, current_sha)

    # Complete GET/OPTIONS/read-modify-write planning for every pending write before the first dispatch.
    capabilities: list[dict[str, Any]] = []
    for item in items:
        if item.status != "WRITE_REQUIRED":
            continue
        item.replacement_plan = _plan_write(client, item)
        capabilities.append(
            {
                "canonical_id": item.spec.canonical_id,
                "section_id": item.spec.section_id,
                "allow": item.replacement_plan.allow,
                "writable_fields": list(item.replacement_plan.writable_fields),
                "payload_fields": sorted(item.replacement_plan.payload["section"]),
            }
        )

    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        write_json(report_dir / "course-snapshot.before.json", before)
        write_json(report_dir / "replacement-capabilities.json", capabilities)
        write_json(
            report_dir / "preflight-report.json",
            {
                "course_id": COURSE_ID,
                "source_main_sha": current_sha,
                "items": [
                    {
                        "canonical_id": item.spec.canonical_id,
                        "section_id": item.spec.section_id,
                        "live_position": item.live_state["position"],
                        "target_position": item.spec.target_position,
                        "status": item.status,
                    }
                    for item in items
                ],
                "stepik_writes": 0,
            },
        )

    if not confirm_write:
        return {
            "mode": "section-position-recovery-preflight",
            "course_id": COURSE_ID,
            "source_main_sha": current_sha,
            "verdict": "PREFLIGHT_PASS",
            "write_authorized": False,
            "stepik_writes": 0,
            "recovery_required": [item.spec.canonical_id for item in items if item.status == "WRITE_REQUIRED"],
            "recovery_pending_global": [
                item.spec.canonical_id
                for item in items
                if item.status in {"OP_READBACK_RECOVERABLE", "GLOBAL_FINAL_PENDING", "FINAL_NEEDS_COMMIT"}
            ],
            "already_recovered": [item.spec.canonical_id for item in items if item.status == "ALREADY_RECOVERED"],
            "ready_for_bulk_write": False,
        }

    for item in items:
        if item.status == "OP_READBACK_RECOVERABLE":
            _recover_completed_write_readback(client, store, item)

    writes = 0
    for item in items:
        if item.status != "WRITE_REQUIRED":
            continue
        _execute_write(client, store, item, current_sha)
        writes += 1

    final_snapshot = client.inspect_course(COURSE_ID)
    _verify_recovered_snapshot(client, final_snapshot, specs)
    if report_dir is not None:
        write_json(report_dir / "course-snapshot.after.json", final_snapshot)

    closed = _close_global_boundaries(store, items)
    return {
        "mode": "section-position-recovery",
        "course_id": COURSE_ID,
        "source_main_sha": current_sha,
        "verdict": "PASS",
        "write_authorized": True,
        "stepik_writes": writes,
        "positions_confirmed": {spec.canonical_id: spec.target_position for spec in specs},
        "unit_topology_confirmed": True,
        "history_boundaries_closed": closed,
        "lesson_or_unit_writes": 0,
        "create_operations": 0,
        "delete_operations": 0,
        "ready_for_bulk_write": False,
        "next_action": "fresh learner-hygiene preflight only after Issue #74 recovery evidence is reviewed",
    }


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else (repo_root / args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    if args.course_id != COURSE_ID:
        report = {
            "mode": "section-position-recovery",
            "course_id": args.course_id,
            "verdict": "BLOCKED",
            "blockers": [f"fixed-course-id-required:{COURSE_ID}"],
            "stepik_writes": 0,
            "ready_for_bulk_write": False,
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    try:
        sha = source_sha(repo_root)
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        store = _history_store(sha)
        report = run_recovery(
            client=client,
            store=store,
            manifest=manifest,
            current_sha=sha,
            confirm_write=args.confirm_write,
            report_dir=report_dir,
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        DeploymentHistoryError,
        ReplacementUpdateError,
        SectionRecoveryError,
        StepikAPIError,
        OSError,
        ValueError,
    ) as exc:
        report = {
            "mode": "section-position-recovery",
            "course_id": COURSE_ID,
            "verdict": "BLOCKED",
            "blockers": [str(exc)],
            "stepik_writes": None,
            "write_count_status": "Не выводить из exception path; authoritative evidence = append-only recovery history + artifacts.",
            "ready_for_bulk_write": False,
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
