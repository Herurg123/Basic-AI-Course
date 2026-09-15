from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.fingerprints import canonical_hash
    from stepik_uploader.history_runtime import find_incomplete_object_events
    from stepik_uploader.reporting import write_json
    from stepik_uploader.section_write import (
        SectionPutContract,
        SectionWriteContractError,
        assert_section_readback,
        execute_section_put,
        prepare_section_put,
    )
    from stepik_uploader.stepik_uploader import source_sha
else:
    from .api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .fingerprints import canonical_hash
    from .history_runtime import find_incomplete_object_events
    from .reporting import write_json
    from .section_write import (
        SectionPutContract,
        SectionWriteContractError,
        assert_section_readback,
        execute_section_put,
        prepare_section_put,
    )
    from .stepik_uploader import source_sha

COURSE_ID = 299189
BASELINE_PATH = Path("04_course/stepik/automation/section-position-recovery-2026-09-15.v1.json")


class SectionPositionRecoveryError(RuntimeError):
    pass


@dataclass
class RecoveryPlan:
    operations: list[dict[str, Any]] = field(default_factory=list)
    already_recovered: list[dict[str, Any]] = field(default_factory=list)
    sentinels: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "operations": deepcopy(self.operations),
            "already_recovered": deepcopy(self.already_recovered),
            "sentinels": deepcopy(self.sentinels),
            "blockers": list(self.blockers),
            "stepik_writes_planned": len(self.operations),
            "delete_allowed": False,
            "create_allowed": False,
            "lesson_or_unit_writes_allowed": False,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded one-off Stepik section position recovery")
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
        raise RuntimeError("Для section position recovery нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def load_recovery_baseline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SectionPositionRecoveryError(f"Не удалось прочитать recovery baseline: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SectionPositionRecoveryError("Recovery baseline имеет неподдерживаемую schema_version")
    if int(data.get("course_id", -1)) != COURSE_ID:
        raise SectionPositionRecoveryError(f"Recovery baseline должен относиться к course_id={COURSE_ID}")
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) != 9:
        raise SectionPositionRecoveryError("Recovery baseline должен содержать ровно 9 sections M00..M08")
    return data


def _manifest_modules(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for module in manifest.get("modules", []):
        canonical_id = str(module.get("canonical_id") or "")
        if canonical_id in result:
            raise SectionPositionRecoveryError(f"Duplicate module в canonical manifest: {canonical_id}")
        result[canonical_id] = module
    return result


def _section_map(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        raise SectionPositionRecoveryError("Stepik snapshot не содержит sections")
    result: dict[int, dict[str, Any]] = {}
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("id"), int):
            raise SectionPositionRecoveryError("Stepik snapshot содержит section без целочисленного id")
        section_id = int(section["id"])
        if section_id in result:
            raise SectionPositionRecoveryError(f"Duplicate section id={section_id}")
        result[section_id] = section
    return result


def _unit_ids(section: dict[str, Any]) -> list[int]:
    units = section.get("units")
    if not isinstance(units, list):
        raise SectionPositionRecoveryError(f"section:{section.get('id')}: units отсутствуют")
    result: list[int] = []
    for unit in units:
        if isinstance(unit, dict):
            unit_id = unit.get("id")
        else:
            unit_id = unit
        if not isinstance(unit_id, int):
            raise SectionPositionRecoveryError(f"section:{section.get('id')}: unit id повреждён")
        result.append(int(unit_id))
    return result


def _stable_content_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Snapshot invariant that intentionally excludes only section.position."""
    course = snapshot.get("course")
    if not isinstance(course, dict):
        raise SectionPositionRecoveryError("Stepik snapshot не содержит course")
    normalized_sections: list[dict[str, Any]] = []
    for section in _section_map(snapshot).values():
        units: list[dict[str, Any]] = []
        for unit in section.get("units", []):
            if not isinstance(unit, dict) or not isinstance(unit.get("lesson"), dict):
                raise SectionPositionRecoveryError("Normalized snapshot unit/lesson повреждён")
            lesson = unit["lesson"]
            steps: list[dict[str, Any]] = []
            for item in lesson.get("steps", []):
                if not isinstance(item, dict) or not isinstance(item.get("step_source"), dict):
                    raise SectionPositionRecoveryError("Normalized snapshot step_source повреждён")
                source = item["step_source"]
                steps.append(
                    {
                        "id": int(source["id"]),
                        "lesson": int(source["lesson"]),
                        "position": int(source["position"]),
                        "block": deepcopy(source.get("block")),
                    }
                )
            units.append(
                {
                    "id": int(unit["id"]),
                    "position": int(unit["position"]),
                    "lesson": {
                        "id": int(lesson["id"]),
                        "title": str(lesson.get("title") or ""),
                        "is_public": lesson.get("is_public"),
                        "language": lesson.get("language"),
                        "steps": sorted(steps, key=lambda row: (row["position"], row["id"])),
                    },
                }
            )
        normalized_sections.append(
            {
                "id": int(section["id"]),
                "title": str(section.get("title") or ""),
                "units": sorted(units, key=lambda row: (row["position"], row["id"])),
            }
        )
    return {
        "course": {
            "id": int(course["id"]),
            "title": str(course.get("title") or ""),
            "language": course.get("language"),
            "is_public": course.get("is_public"),
        },
        "sections": sorted(normalized_sections, key=lambda row: row["id"]),
    }


def snapshot_content_fingerprint(snapshot: dict[str, Any]) -> str:
    return canonical_hash(_stable_content_payload(snapshot))


def section_positions(snapshot: dict[str, Any]) -> dict[int, int]:
    result: dict[int, int] = {}
    for section_id, section in _section_map(snapshot).items():
        if not isinstance(section.get("position"), int):
            raise SectionPositionRecoveryError(f"section:{section_id}: position не целочисленная")
        result[section_id] = int(section["position"])
    return result


def build_recovery_plan(
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    baseline: dict[str, Any],
) -> RecoveryPlan:
    plan = RecoveryPlan()
    modules = _manifest_modules(manifest)
    sections = _section_map(snapshot)
    rows = baseline["sections"]

    expected_ids = {int(row["section_id"]) for row in rows}
    if set(sections) != expected_ids:
        plan.blockers.append(
            f"section ID set drift: live={sorted(sections)} expected={sorted(expected_ids)}"
        )
        return plan

    expected_positions = sorted(int(row["expected_position"]) for row in rows)
    if expected_positions != list(range(1, 10)):
        plan.blockers.append(f"Recovery baseline positions повреждены: {expected_positions}")
        return plan

    canonical_ids = [str(row.get("canonical_id") or "") for row in rows]
    if sorted(canonical_ids) != [f"M{index:02d}" for index in range(9)]:
        plan.blockers.append(f"Recovery baseline canonical IDs повреждены: {canonical_ids}")
        return plan

    for row in rows:
        canonical_id = str(row["canonical_id"])
        section_id = int(row["section_id"])
        expected_position = int(row["expected_position"])
        expected_title = str(row["expected_live_title"])
        expected_units = [int(value) for value in row["unit_ids"]]
        recover = row.get("recover") is True

        module = modules.get(canonical_id)
        if not isinstance(module, dict):
            plan.blockers.append(f"{canonical_id}: отсутствует в canonical manifest")
            continue
        if int(module.get("position", -1)) != expected_position:
            plan.blockers.append(
                f"{canonical_id}: recovery position={expected_position} != canonical manifest position={module.get('position')}"
            )
        canonical_title = str(module.get("title") or "")
        if str(row.get("canonical_title") or "") != canonical_title:
            plan.blockers.append(f"{canonical_id}: recovery canonical_title drift от main")

        live = sections[section_id]
        if live.get("title") != expected_title:
            plan.blockers.append(
                f"{canonical_id}: live title drift: {live.get('title')!r} != baseline {expected_title!r}"
            )
        live_units = _unit_ids(live)
        if live_units != expected_units:
            plan.blockers.append(
                f"{canonical_id}: unit IDs drift: {live_units} != baseline {expected_units}"
            )
        live_position = live.get("position")
        if not isinstance(live_position, int):
            plan.blockers.append(f"{canonical_id}: live position не целочисленная")
            continue

        item = {
            "canonical_id": canonical_id,
            "section_id": section_id,
            "current_position": int(live_position),
            "expected_position": expected_position,
            "title": expected_title,
            "unit_ids": expected_units,
        }
        if recover:
            if int(live_position) not in {1, expected_position}:
                plan.blockers.append(
                    f"{canonical_id}: position={live_position} не относится ни к incident-state=1, ни к target={expected_position}"
                )
            elif int(live_position) == expected_position:
                plan.already_recovered.append(item)
            else:
                plan.operations.append(item)
        else:
            if int(live_position) != expected_position:
                plan.blockers.append(
                    f"{canonical_id}: sentinel position drift {live_position} != {expected_position}"
                )
            else:
                plan.sentinels.append(item)

    plan.operations.sort(key=lambda item: int(item["expected_position"]), reverse=True)
    plan.already_recovered.sort(key=lambda item: int(item["expected_position"]), reverse=True)
    plan.sentinels.sort(key=lambda item: int(item["expected_position"]))
    return plan


def _raw_section_state(
    raw: dict[str, Any],
    *,
    row: dict[str, Any],
    position: int,
) -> dict[str, Any]:
    section_id = int(row["section_id"])
    if int(raw.get("id", -1)) != section_id:
        raise SectionPositionRecoveryError(f"{row['canonical_id']}: raw section id drift")
    raw_units = _unit_ids(raw)
    expected_units = [int(value) for value in row["unit_ids"]]
    if raw_units != expected_units:
        raise SectionPositionRecoveryError(
            f"{row['canonical_id']}: raw unit IDs drift {raw_units} != {expected_units}"
        )
    if raw.get("title") != row["expected_live_title"]:
        raise SectionPositionRecoveryError(f"{row['canonical_id']}: raw title drift")
    if "course" in raw and int(raw.get("course", -1)) != COURSE_ID:
        raise SectionPositionRecoveryError(f"{row['canonical_id']}: raw course drift")
    return {
        "canonical_id": str(row["canonical_id"]),
        "section_id": section_id,
        "course_id": COURSE_ID,
        "title": str(raw["title"]),
        "position": int(position),
        "unit_ids": expected_units,
    }


def _row_index(baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["canonical_id"]): row for row in baseline["sections"]}


def _preflight_contract(
    client: Any,
    row: dict[str, Any],
    *,
    expected_current_position: int,
) -> tuple[dict[str, Any], SectionPutContract]:
    raw = client.fetch_one("sections", int(row["section_id"]))
    if not isinstance(raw.get("position"), int) or int(raw["position"]) != int(expected_current_position):
        raise SectionPositionRecoveryError(
            f"{row['canonical_id']}: raw position drift перед PUT preflight: {raw.get('position')!r} != {expected_current_position}"
        )
    _raw_section_state(raw, row=row, position=int(raw["position"]))
    try:
        contract = prepare_section_put(
            client,
            raw,
            overrides={"position": int(row["expected_position"])},
        )
    except SectionWriteContractError as exc:
        raise SectionPositionRecoveryError(
            f"{row['canonical_id']}: unsafe section PUT contract: {exc}"
        ) from exc
    return raw, contract


def _execute_one(
    client: Any,
    store: GitHubHistoryStore,
    *,
    sha: str,
    row: dict[str, Any],
    expected_current_position: int,
) -> dict[str, Any]:
    canonical_id = str(row["canonical_id"])
    object_id = f"section-position:{canonical_id}"
    section_id = int(row["section_id"])
    target_position = int(row["expected_position"])
    raw = client.fetch_one("sections", section_id)
    if not isinstance(raw.get("position"), int):
        raise SectionPositionRecoveryError(f"{canonical_id}: raw position отсутствует")
    live_position = int(raw["position"])
    if live_position != int(expected_current_position):
        raise SectionPositionRecoveryError(
            f"{canonical_id}: live position изменилась между snapshot и dispatch: "
            f"{live_position} != {expected_current_position}"
        )

    before_state = _raw_section_state(raw, row=row, position=live_position)
    desired_state = _raw_section_state(raw, row=row, position=target_position)
    before_fp = canonical_hash(before_state)
    desired_fp = canonical_hash(desired_state)

    incomplete = find_incomplete_object_events(store, object_id=object_id)
    if len(incomplete) > 1:
        raise DeploymentHistoryError(f"{object_id}: несколько incomplete recovery events")

    if incomplete:
        identity, records, summary = incomplete[0]
        if identity.source_sha != sha or identity.desired_fingerprint != desired_fp:
            raise DeploymentHistoryError(
                f"{object_id}: incomplete recovery event относится к другому main/desired state"
            )
        recorder = DeploymentRecorder(store, identity)
        if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
            raise SectionPositionRecoveryError(
                f"{object_id}: неоднозначная/failed history запрещает blind recovery retry"
            )
        if summary.get("final_readback_confirmed"):
            if live_position != target_position:
                raise SectionPositionRecoveryError(
                    f"{object_id}: final history существует, но live position={live_position}"
                )
            recorder.state_committed(
                baseline_after=desired_state,
                status=str(summary.get("final_status")),
            )
            return {
                "canonical_id": canonical_id,
                "section_id": section_id,
                "action": "RECOVER_COMMIT",
                "event_id": identity.event_id,
                "position": target_position,
                "stepik_write": False,
            }
        if summary.get("writes_started"):
            if summary.get("confirmed_operation_count") == 1 and live_position == target_position:
                recorder.final_readback(
                    fingerprint_after=desired_fp,
                    stepik_object_ids={"section_id": section_id},
                    status="APPLIED",
                    baseline_after=desired_state,
                )
                recorder.state_committed(baseline_after=desired_state, status="APPLIED")
                return {
                    "canonical_id": canonical_id,
                    "section_id": section_id,
                    "action": "RECOVER_FINAL",
                    "event_id": identity.event_id,
                    "position": target_position,
                    "stepik_write": False,
                }
            raise SectionPositionRecoveryError(
                f"{object_id}: write dispatch без полного per-operation read-back; blind retry запрещён"
            )
        if identity.baseline_fingerprint_before != before_fp:
            raise DeploymentHistoryError(
                f"{object_id}: started-before-write event baseline не совпадает с live state"
            )
    else:
        if live_position == target_position:
            return {
                "canonical_id": canonical_id,
                "section_id": section_id,
                "action": "NOOP_ALREADY_RECOVERED",
                "event_id": None,
                "position": target_position,
                "stepik_write": False,
            }
        identity = event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=object_id,
            kind="section-position-recovery",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=before_fp,
            pending_first_sha=None,
        )
        recorder = DeploymentRecorder(store, identity)

    if live_position == target_position:
        raise SectionPositionRecoveryError(
            f"{object_id}: live уже target, но incomplete history не доказывает завершённый write"
        )

    raw, contract = _preflight_contract(
        client,
        row,
        expected_current_position=live_position,
    )
    recorder.ensure_started(
        operation_type="section-position-recovery",
        state_before=before_state,
        expected_state=desired_state,
        stepik_object_ids={"section_id": section_id},
        fingerprint_before=before_fp,
    )
    operation_id = "section-position-put"
    recorder.write_intent(
        operation_id=operation_id,
        method="PUT",
        target=f"sections/{section_id}",
        fingerprint_before=before_fp,
        expected_fingerprint_after=desired_fp,
    )
    recorder.write_dispatch_started(operation_id=operation_id)
    try:
        execute_section_put(client, contract)
    except StepikWriteAmbiguousError:
        recorder.write_result(
            operation_id=operation_id,
            status="AMBIGUOUS",
            reason_code="section-position-recovery-write-ambiguous",
        )
        raise
    except StepikAPIError:
        recorder.write_result(
            operation_id=operation_id,
            status="FAILED_KNOWN",
            reason_code="section-position-recovery-write-failed-known",
        )
        raise
    except Exception:
        recorder.write_result(
            operation_id=operation_id,
            status="AMBIGUOUS",
            reason_code="section-position-recovery-exception-after-dispatch",
        )
        raise
    recorder.write_result(operation_id=operation_id, status="COMPLETED")

    try:
        after_raw = client.fetch_one("sections", section_id)
        assert_section_readback(raw, after_raw, contract)
        if int(after_raw.get("position", -1)) != target_position:
            raise SectionPositionRecoveryError(
                f"{canonical_id}: read-back position={after_raw.get('position')} != target={target_position}"
            )
        confirmed_state = _raw_section_state(after_raw, row=row, position=target_position)
        if confirmed_state != desired_state:
            raise SectionPositionRecoveryError(f"{canonical_id}: raw read-back state != desired recovery state")
    except Exception:
        recorder.readback_failed(
            operation_id=operation_id,
            reason_code="section-position-recovery-readback-unavailable-or-mismatch",
        )
        raise

    recorder.operation_readback(
        operation_id=operation_id,
        expected_fingerprint_after=desired_fp,
    )
    recorder.final_readback(
        fingerprint_after=desired_fp,
        stepik_object_ids={"section_id": section_id},
        status="APPLIED",
        baseline_after=desired_state,
    )
    recorder.state_committed(baseline_after=desired_state, status="APPLIED")
    return {
        "canonical_id": canonical_id,
        "section_id": section_id,
        "action": "RECOVER_POSITION",
        "event_id": identity.event_id,
        "from_position": live_position,
        "position": target_position,
        "section_put_contract": contract.as_dict(),
        "stepik_write": True,
    }


def _write_journal(
    path: Path,
    *,
    sha: str,
    results: list[dict[str, Any]],
    before_positions: dict[int, int],
    after_positions: dict[int, int],
) -> None:
    lines = [
        "### SECTION_POSITION_RECOVERY: восстановлен порядок модулей",
        "",
        f"- source main SHA: `{sha}`",
        f"- before positions by section id: `{before_positions}`",
        f"- results: `{results}`",
        f"- after positions by section id: `{after_positions}`",
        "- lesson/unit/step content invariant: `CONFIRMED_UNCHANGED`",
        "- delete/create operations: `0`",
        "",
        "Recovery затрагивал только `section.position` и выполнялся через OPTIONS-derived full-preserving PUT + WAL/read-back.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "section-position-recovery",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "confirm_write": bool(args.confirm_write),
        "ready_for_recovery_write": False,
        "stepik_writes": 0,
    }

    if args.course_id != COURSE_ID:
        report.update({"verdict": "BLOCKED", "blockers": [f"fixed-course-id-required:{COURSE_ID}"]})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
        baseline = load_recovery_baseline(repo_root / BASELINE_PATH)
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)

        course = snapshot.get("course") or {}
        if int(course.get("id", -1)) != COURSE_ID:
            raise SectionPositionRecoveryError("Live course ID не совпадает с fixed recovery target")
        if course.get("language") != "ru" or course.get("is_public") is not False:
            raise SectionPositionRecoveryError(
                "Recovery разрешён только для непубличного русскоязычного project course"
            )

        plan = build_recovery_plan(manifest, snapshot, baseline)
        write_json(report_dir / "recovery-plan.json", plan.as_dict())
        if plan.blockers:
            raise SectionPositionRecoveryError("Recovery plan blocked: " + "; ".join(plan.blockers))

        content_fp = snapshot_content_fingerprint(snapshot)
        before_positions = section_positions(snapshot)
        contracts: list[dict[str, Any]] = []
        for operation in plan.operations:
            row = _row_index(baseline)[str(operation["canonical_id"])]
            _raw, contract = _preflight_contract(
                client,
                row,
                expected_current_position=int(operation["current_position"]),
            )
            contracts.append(
                {
                    "canonical_id": operation["canonical_id"],
                    **contract.as_dict(),
                }
            )
        write_json(report_dir / "section-put-contracts.json", {"contracts": contracts})

        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "blockers": [],
                    "ready_for_recovery_write": True,
                    "stepik_writes": 0,
                    "planned_operations": plan.operations,
                    "section_put_contracts": contracts,
                    "content_invariant_fingerprint": content_fp,
                    "human_visual_validation": "NOT_RUN",
                }
            )
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        store = _history_store(sha)
        current_positions = dict(before_positions)
        results: list[dict[str, Any]] = []

        recover_rows = [
            row for row in baseline["sections"] if row.get("recover") is True
        ]
        recover_rows.sort(key=lambda row: int(row["expected_position"]), reverse=True)

        for row in recover_rows:
            section_id = int(row["section_id"])
            current_snapshot = client.inspect_course(args.course_id)
            if snapshot_content_fingerprint(current_snapshot) != content_fp:
                raise SectionPositionRecoveryError(
                    f"{row['canonical_id']}: course content/title/unit invariant drift перед operation"
                )
            actual_positions = section_positions(current_snapshot)
            if actual_positions != current_positions:
                raise SectionPositionRecoveryError(
                    f"{row['canonical_id']}: unexpected section position drift перед operation: "
                    f"{actual_positions} != {current_positions}"
                )

            result = _execute_one(
                client,
                store,
                sha=sha,
                row=row,
                expected_current_position=current_positions[section_id],
            )
            if result.get("stepik_write") is True:
                report["stepik_writes"] = int(report["stepik_writes"]) + 1
            results.append(result)

            if result["action"] in {"RECOVER_POSITION", "RECOVER_FINAL", "RECOVER_COMMIT", "NOOP_ALREADY_RECOVERED"}:
                current_positions[section_id] = int(row["expected_position"])

            after_each = client.inspect_course(args.course_id)
            if snapshot_content_fingerprint(after_each) != content_fp:
                raise SectionPositionRecoveryError(
                    f"{row['canonical_id']}: recovery изменила content/title/unit invariant"
                )
            after_each_positions = section_positions(after_each)
            if after_each_positions != current_positions:
                raise SectionPositionRecoveryError(
                    f"{row['canonical_id']}: post-write positions {after_each_positions} != expected {current_positions}"
                )

        final_snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        if snapshot_content_fingerprint(final_snapshot) != content_fp:
            raise SectionPositionRecoveryError("Final content/title/unit invariant изменился")
        final_positions = section_positions(final_snapshot)

        final_plan = build_recovery_plan(manifest, final_snapshot, baseline)
        write_json(report_dir / "recovery-plan.after.json", final_plan.as_dict())
        if final_plan.blockers or final_plan.operations:
            raise SectionPositionRecoveryError(
                "После recovery остались structural blockers/operations"
            )

        expected_final = {
            int(row["section_id"]): int(row["expected_position"])
            for row in baseline["sections"]
        }
        if final_positions != expected_final:
            raise SectionPositionRecoveryError(
                f"Final positions {final_positions} != baseline target {expected_final}"
            )

        _write_journal(
            report_dir / "sync-journal.md",
            sha=sha,
            results=results,
            before_positions=before_positions,
            after_positions=final_positions,
        )
        report.update(
            {
                "verdict": "PASS",
                "blockers": [],
                "ready_for_recovery_write": False,
                "results": results,
                "before_positions": before_positions,
                "after_positions": final_positions,
                "content_invariant_fingerprint": content_fp,
                "content_invariant_after": snapshot_content_fingerprint(final_snapshot),
                "human_visual_validation": "RETEST_REQUIRED",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        RuntimeError,
        StepikAPIError,
        CanonicalBuildError,
        DeploymentHistoryError,
        SectionWriteContractError,
        SectionPositionRecoveryError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "ready_for_recovery_write": False,
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
