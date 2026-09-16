from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.history_runtime import find_incomplete_object_events, identity_from_records
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.title_hygiene import (
        TitleHygieneError,
        TitleOperation,
        execute_title_only_operation,
        legacy_title,
        title_fingerprint,
    )
else:
    from .api import StepikAPIError, StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .history_runtime import find_incomplete_object_events, identity_from_records
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .title_hygiene import (
        TitleHygieneError,
        TitleOperation,
        execute_title_only_operation,
        legacy_title,
        title_fingerprint,
    )


COURSE_ID = 299189
TARGET_IDS = ("M00-L01", "M00-L02")
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")


class GoldenTitleMigrationError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Owner-approved golden lesson title migration")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-golden-title-migration"))
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise GoldenTitleMigrationError("Для golden title migration нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            result[str(lesson.get("canonical_id"))] = lesson
    return result


def build_golden_title_operations(
    profile: dict[str, Any],
    manifest: dict[str, Any],
) -> list[TitleOperation]:
    """Build the only two owner-approved title operations from canonical + observation fixture."""
    by_id = _manifest_index(manifest)
    golden = profile.get("golden_lessons", {})
    operations: list[TitleOperation] = []
    for canonical_id in TARGET_IDS:
        lesson = by_id.get(canonical_id)
        observed = golden.get(canonical_id) if isinstance(golden, dict) else None
        if not isinstance(lesson, dict) or not isinstance(observed, dict):
            raise GoldenTitleMigrationError(f"{canonical_id}: canonical/golden mapping отсутствует")
        if lesson.get("golden_read_only") is not True:
            raise GoldenTitleMigrationError(f"{canonical_id}: canonical больше не помечен golden_read_only")
        human_title = lesson.get("title")
        observed_title = observed.get("lesson_title")
        if not isinstance(human_title, str) or not human_title.strip():
            raise GoldenTitleMigrationError(f"{canonical_id}: canonical human title отсутствует")
        expected_legacy = legacy_title(canonical_id, human_title)
        if observed_title != expected_legacy:
            raise GoldenTitleMigrationError(
                f"{canonical_id}: observation fixture title {observed_title!r} не равен exact legacy {expected_legacy!r}"
            )
        lesson_id = observed.get("stepik_lesson_id")
        unit_position = observed.get("unit_position")
        if not isinstance(lesson_id, int) or not isinstance(unit_position, int):
            raise GoldenTitleMigrationError(f"{canonical_id}: golden fixture не содержит fixed lesson_id/unit_position")
        operations.append(
            TitleOperation(
                kind="lesson",
                canonical_id=canonical_id,
                stepik_id=lesson_id,
                position=unit_position,
                live_title=observed_title,
                expected_title=human_title,
            )
        )
    return operations


def _live_lesson(snapshot: dict[str, Any], lesson_id: int) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for section in snapshot.get("sections", []):
        for unit in section.get("units", []):
            lesson = unit.get("lesson")
            if isinstance(lesson, dict) and lesson.get("id") == lesson_id:
                matches.append(lesson)
    if len(matches) != 1:
        raise GoldenTitleMigrationError(f"lesson_id={lesson_id}: найдено {len(matches)} live matches")
    return matches[0]


def _event_identity(operation: TitleOperation, *, sha: str):
    return event_identity_from_environment(
        course_id=COURSE_ID,
        object_id=operation.object_id,
        kind="golden-title-metadata",
        source_sha=sha,
        desired_fingerprint=title_fingerprint(
            kind="lesson",
            stepik_id=operation.stepik_id,
            title=operation.expected_title,
        ),
        baseline_fingerprint=title_fingerprint(
            kind="lesson",
            stepik_id=operation.stepik_id,
            title=operation.live_title,
        ),
        pending_first_sha=None,
    )


def _history_summary(
    store: Any,
    operation: TitleOperation,
    *,
    sha: str,
) -> tuple[Any, list[dict[str, Any]], dict[str, Any] | None]:
    identity = _event_identity(operation, sha=sha)
    incomplete = find_incomplete_object_events(store, object_id=operation.object_id)
    foreign = [item[0].event_id for item in incomplete if item[0].event_id != identity.event_id]
    if foreign:
        raise DeploymentHistoryError(
            f"{operation.object_id}: существует incomplete event другой semantics/source: {foreign}"
        )
    records = store.load(identity.event_id)
    if not records:
        return identity, [], None
    loaded_identity = identity_from_records(records, expected_event_id=identity.event_id)
    if loaded_identity.source_sha != sha or loaded_identity.kind != "golden-title-metadata":
        raise DeploymentHistoryError(f"{operation.object_id}: history provenance не соответствует текущей migration")
    return identity, records, summarize_event(records)


def _target_title_is_proven(summary: dict[str, Any] | None) -> bool:
    if not summary:
        return False
    if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
        return False
    if summary.get("machine_state_committed") or summary.get("final_readback_confirmed"):
        return True
    return int(summary.get("writes_started") or 0) == 1 and int(summary.get("confirmed_operation_count") or 0) == 1


def _assess_operation(
    snapshot: dict[str, Any],
    store: Any,
    operation: TitleOperation,
    *,
    sha: str,
) -> dict[str, Any]:
    live = _live_lesson(snapshot, operation.stepik_id)
    title = live.get("title")
    if not isinstance(title, str):
        raise GoldenTitleMigrationError(f"{operation.canonical_id}: live lesson не содержит title")
    identity, records, summary = _history_summary(store, operation, sha=sha)
    if summary and (summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes")):
        raise DeploymentHistoryError(f"{operation.object_id}: unsafe prior write history требует owner reconcile")

    if title == operation.live_title:
        if summary and (
            summary.get("machine_state_committed")
            or summary.get("final_readback_confirmed")
            or int(summary.get("confirmed_operation_count") or 0) > 0
            or int(summary.get("writes_started") or 0) > 0
        ):
            raise DeploymentHistoryError(
                f"{operation.object_id}: live legacy title конфликтует с history, где write уже начинался/подтверждался"
            )
        return {
            "canonical_id": operation.canonical_id,
            "stepik_lesson_id": operation.stepik_id,
            "current_title": title,
            "target_title": operation.expected_title,
            "state": "LEGACY_READY",
            "stepik_write_required": True,
            "event_id": identity.event_id,
            "history_record_count": len(records),
        }

    if title == operation.expected_title:
        if not _target_title_is_proven(summary):
            raise DeploymentHistoryError(
                f"{operation.object_id}: target title уже live, но exact immutable migration history его не доказывает"
            )
        return {
            "canonical_id": operation.canonical_id,
            "stepik_lesson_id": operation.stepik_id,
            "current_title": title,
            "target_title": operation.expected_title,
            "state": "TARGET_PROVEN_HISTORY",
            "stepik_write_required": False,
            "event_id": identity.event_id,
            "history_record_count": len(records),
        }

    raise GoldenTitleMigrationError(
        f"{operation.canonical_id}: unknown/manual title drift {title!r}; разрешены только exact legacy или proven target"
    )


def _validate_full_golden_state(
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    assessments: list[dict[str, Any]],
) -> None:
    """Validate every golden invariant while allowing only migration-proven title states."""
    expected = deepcopy(profile)
    by_id = {str(item["canonical_id"]): item for item in assessments}
    for canonical_id in TARGET_IDS:
        row = by_id.get(canonical_id)
        if not isinstance(row, dict):
            raise GoldenTitleMigrationError(f"{canonical_id}: migration assessment отсутствует")
        expected["golden_lessons"][canonical_id]["lesson_title"] = row["current_title"]
    blockers = validate_golden_profile(expected, snapshot)
    if blockers:
        raise GoldenProfileError("Golden full-state integrity не подтверждён: " + "; ".join(blockers))


def _assess_snapshot(
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    store: Any,
    operations: list[TitleOperation],
    *,
    sha: str,
) -> list[dict[str, Any]]:
    assessments = [_assess_operation(snapshot, store, operation, sha=sha) for operation in operations]
    _validate_full_golden_state(profile, snapshot, assessments)
    return assessments


def _next_profile(
    profile: dict[str, Any],
    operations: list[TitleOperation],
    *,
    sha: str,
) -> dict[str, Any]:
    proposed = deepcopy(profile)
    by_id = {operation.canonical_id: operation for operation in operations}
    run_id_raw = os.getenv("GITHUB_RUN_ID")
    run_id: int | str | None = (
        int(run_id_raw) if isinstance(run_id_raw, str) and run_id_raw.isdigit() else run_id_raw
    )
    for canonical_id in TARGET_IDS:
        proposed["golden_lessons"][canonical_id]["lesson_title"] = by_id[canonical_id].expected_title
        proposed["golden_lessons"][canonical_id]["lesson_title_observed_run_id"] = run_id
    proposed["observed_run_id"] = run_id
    proposed["observed_source_sha"] = sha
    return proposed


def _history_counters(
    store: Any | None,
    operations: list[TitleOperation],
    *,
    sha: str | None,
) -> dict[str, int]:
    counters = {"write_dispatches_started": 0, "write_readbacks_confirmed": 0}
    if store is None or not isinstance(sha, str):
        return counters
    for operation in operations:
        try:
            identity = _event_identity(operation, sha=sha)
            records = store.load(identity.event_id)
            if not records:
                continue
            identity_from_records(records, expected_event_id=identity.event_id)
            summary = summarize_event(records)
            counters["write_dispatches_started"] += int(summary.get("writes_started") or 0)
            counters["write_readbacks_confirmed"] += int(summary.get("confirmed_operation_count") or 0)
        except DeploymentHistoryError:
            # Failure reporting must never disguise the original failure with a second exception.
            continue
    return counters


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "mode": "golden-title-owner-migration",
        "course_id": args.course_id,
        "confirm_write": bool(args.confirm_write),
        "ready_for_bulk_write": False,
        "creates_allowed": False,
        "deletes_allowed": False,
        "structural_writes_allowed": False,
        "stepik_writes": 0,
    }
    sha: str | None = None
    store: Any | None = None
    operations: list[TitleOperation] = []
    results: list[dict[str, Any]] = []
    try:
        if args.course_id != COURSE_ID:
            raise GoldenTitleMigrationError(f"Golden title migration разрешён только для course_id={COURSE_ID}")
        sha = source_sha(repo_root)
        report["source_main_sha"] = sha
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        operations = build_golden_title_operations(profile, manifest)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        course = snapshot.get("course", {})
        if course.get("id") != COURSE_ID or course.get("language") != "ru" or course.get("is_public") is not False:
            raise GoldenTitleMigrationError("Golden title migration разрешён только для fixed private ru course 299189")

        store = _history_store(sha)
        before = _assess_snapshot(profile, snapshot, store, operations, sha=sha)
        planned_writes = sum(1 for item in before if item["stepik_write_required"])
        write_json(
            report_dir / "golden-title-plan.json",
            {
                "targets": before,
                "operations": [operation.as_dict() for operation in operations],
                "stepik_writes_planned": planned_writes,
                "create_allowed": False,
                "delete_allowed": False,
                "structural_writes_allowed": False,
            },
        )

        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "blockers": [],
                    "stepik_writes": 0,
                    "stepik_writes_planned": planned_writes,
                    "ready_for_write": True,
                    "golden_profile_update_required_after_write": True,
                    "targets": before,
                }
            )
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        current_snapshot = snapshot
        for operation in operations:
            current_assessments = _assess_snapshot(profile, current_snapshot, store, operations, sha=sha)
            row = next(item for item in current_assessments if item["canonical_id"] == operation.canonical_id)
            identity = _event_identity(operation, sha=sha)
            result = execute_title_only_operation(client, operation, DeploymentRecorder(store, identity))
            if result.get("action") == "UPDATE_TITLE":
                report["stepik_writes"] = int(report["stepik_writes"]) + 1
            results.append({"event_id": identity.event_id, **result})
            write_json(report_dir / "migration-results.json", {"results": results})

            # Lesson PUT is treated as potentially replacement-like until a full course read-back proves otherwise.
            current_snapshot = client.inspect_course(args.course_id)
            write_json(report_dir / "course-snapshot.progress.json", current_snapshot)
            after_one = _assess_snapshot(profile, current_snapshot, store, operations, sha=sha)
            after_row = next(item for item in after_one if item["canonical_id"] == operation.canonical_id)
            if after_row["current_title"] != operation.expected_title:
                raise GoldenTitleMigrationError(f"{operation.canonical_id}: post-write full snapshot не подтвердил target title")
            if row["state"] == "LEGACY_READY" and result.get("action") not in {
                "UPDATE_TITLE",
                "RECOVER_FINAL",
                "RECOVER_COMMIT",
            }:
                raise GoldenTitleMigrationError(
                    f"{operation.canonical_id}: неожиданный action для legacy migration: {result.get('action')}"
                )

        final_snapshot = client.inspect_course(args.course_id)
        final_assessments = _assess_snapshot(profile, final_snapshot, store, operations, sha=sha)
        if any(item["current_title"] != item["target_title"] for item in final_assessments):
            raise GoldenTitleMigrationError("Не все golden titles достигли exact human-title target")
        write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        write_json(report_dir / "golden-profile.next.json", _next_profile(profile, operations, sha=sha))
        write_json(report_dir / "migration-results.json", {"results": results})

        report.update(
            {
                "verdict": "PASS",
                "blockers": [],
                "stepik_writes_planned": planned_writes,
                "targets": final_assessments,
                "results": results,
                **_history_counters(store, operations, sha=sha),
                "golden_profile_update_required_after_write": True,
                "ordinary_live_routes_expected_to_fail_closed_until_profile_update": True,
                "human_visual_validation": "RETEST_REQUIRED",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        GoldenTitleMigrationError,
        GoldenProfileError,
        CanonicalBuildError,
        TitleHygieneError,
        DeploymentHistoryError,
        StepikAPIError,
        RuntimeError,
    ) as exc:
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "ready_for_write": False,
                "results": results,
                **_history_counters(store, operations, sha=sha),
            }
        )
        write_json(report_dir / "migration-results.json", {"results": results})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
