from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import AssetInventoryError, build_asset_inventory
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.planner import GOLDEN_IDS, plan_dry_run
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from stepik_uploader.sync_state import SyncStateError, assess_sync, baseline_for, load_state
    from stepik_uploader.writer import ContentWriteError
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import AssetInventoryError, build_asset_inventory
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .planner import GOLDEN_IDS, plan_dry_run
    from .reporting import write_json
    from .stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from .sync_state import SyncStateError, assess_sync, baseline_for, load_state
    from .writer import ContentWriteError

GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
PLACEHOLDER_TEXT = "Урок сгенерирован роботом ;)"
BLOCKED_SYNC_STATUSES = {
    "BASELINE_BOOTSTRAP_REQUIRED",
    "BASELINE_MISSING_BLOCKED",
    "DRIFT_BLOCKED",
    "METADATA_UPDATE_BLOCKED",
    "STRUCTURAL_UPDATE_BLOCKED",
}


class BulkStatusError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для bulk-status нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в GitHub Actions Secrets")
    return client_id, client_secret


def _live_lesson(snapshot: dict[str, Any], module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise BulkStatusError(f"section position={module_position}: ожидается ровно один объект, найдено {len(sections)}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1:
        raise BulkStatusError(
            f"section={module_position} unit position={lesson_position}: ожидается ровно один объект, найдено {len(units)}"
        )
    lesson = units[0].get("lesson")
    if not isinstance(lesson, dict):
        raise BulkStatusError(f"section={module_position} unit={lesson_position}: отсутствует lesson")
    return lesson


def _plain_html(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", without_tags).strip()


def _is_placeholder(lesson: dict[str, Any]) -> bool:
    steps = lesson.get("steps", [])
    if len(steps) != 1:
        return False
    source = steps[0].get("step_source", {})
    block = source.get("block", {})
    return (
        source.get("position") == 1
        and block.get("name") == "text"
        and (block.get("source") or {}) == {}
        and _plain_html(str(block.get("text") or "")) == PLACEHOLDER_TEXT
    )


def _plan_action_by_lesson(plan: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for operation in getattr(plan, "operations", []):
        lesson_id = operation.get("lesson")
        if isinstance(lesson_id, str):
            result[lesson_id] = operation
    return result


def _lesson_record(
    *,
    module: dict[str, Any],
    lesson: dict[str, Any],
    live: dict[str, Any],
    baseline: dict[str, Any] | None,
    plan_operation: dict[str, Any] | None,
) -> dict[str, Any]:
    canonical_id = str(lesson["canonical_id"])
    expected_title = f"{canonical_id} — {lesson['title']}"
    current_title = str(live.get("title") or "")
    exact_title = current_title == expected_title
    stable_id_title = current_title.startswith(f"{canonical_id} — ")
    if not (exact_title or stable_id_title):
        raise BulkStatusError(
            f"{canonical_id}: live title не содержит ожидаемый stable canonical ID: {current_title!r}"
        )

    record: dict[str, Any] = {
        "canonical_id": canonical_id,
        "module_position": int(module["position"]),
        "lesson_position": int(lesson["position"]),
        "stepik_lesson_id": int(live["id"]),
        "expected_title": expected_title,
        "current_title": current_title,
        "title_state": "EXACT" if exact_title else "STALE_TITLE",
        "live_step_count": len(live.get("steps", [])),
        "planned_step_count": len(lesson.get("steps", [])),
        "golden_read_only": bool(lesson.get("golden_read_only")),
        "independence_sensitive": bool(lesson.get("independence_sensitive")),
        "f1_sensitive": bool(lesson.get("f1_sensitive")),
        "asset_ids": list(lesson.get("asset_ids", [])),
        "baseline_present": baseline is not None,
        "live_is_public": live.get("is_public"),
        "plan_action": None if plan_operation is None else plan_operation.get("action"),
    }
    return record


def build_bulk_status(
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    state: dict[str, Any],
    profile: dict[str, Any],
    plan: Any,
) -> dict[str, Any]:
    free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
    if not isinstance(free_answer_source, dict):
        raise BulkStatusError("Golden profile не содержит free_answer_source")

    plan_actions = _plan_action_by_lesson(plan)
    lessons: list[dict[str, Any]] = []
    hard_blockers: list[str] = []
    pending_requirements: list[str] = []

    course_public = snapshot.get("course", {}).get("is_public")
    if course_public is not False:
        pending_requirements.append(
            "initial-bulk-write-requires-draft-course: bulk-status разрешён, но первичное заполнение skeleton lessons запрещено на public course"
        )

    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            canonical_id = str(lesson["canonical_id"])
            live = _live_lesson(snapshot, int(module["position"]), int(lesson["position"]))
            baseline = baseline_for(state, canonical_id)
            record = _lesson_record(
                module=module,
                lesson=lesson,
                live=live,
                baseline=baseline,
                plan_operation=plan_actions.get(canonical_id),
            )

            if canonical_id in GOLDEN_IDS:
                record["status"] = "READ_ONLY_GOLDEN"
                record["next_action"] = "none"
                lessons.append(record)
                continue

            if canonical_id == TEST_LESSON_ID:
                compiled = compile_test_lesson(
                    repo_root,
                    free_answer_source=free_answer_source,
                    lesson_id=TEST_LESSON_ID,
                )
                assessment = assess_sync(
                    canonical_id=canonical_id,
                    live_lesson=live,
                    expected_title=record["expected_title"],
                    expected_steps=compiled,
                    baseline=baseline,
                )
                record.update(
                    {
                        "status": assessment.status,
                        "next_action": "sync-changed" if assessment.status == "UPDATE_REQUIRED" else "none",
                        "desired_fingerprint": assessment.desired_fingerprint,
                        "live_fingerprint": assessment.live_fingerprint,
                        "baseline_fingerprint": assessment.baseline_fingerprint,
                        "changed_step_positions": list(assessment.changed_step_positions),
                        "reasons": list(assessment.reasons),
                    }
                )
                if assessment.status in BLOCKED_SYNC_STATUSES:
                    hard_blockers.append(f"{canonical_id}:{assessment.status}")
                lessons.append(record)
                continue

            if baseline is not None:
                record["status"] = "BASELINE_PRESENT_COMPILER_UNAVAILABLE_BLOCKED"
                record["next_action"] = "implement-general-compiler-before-any-write"
                hard_blockers.append(f"{canonical_id}:baseline-present-without-general-compiler")
            elif _is_placeholder(live):
                record["status"] = "INITIAL_UPLOAD_REQUIRED"
                record["next_action"] = "compile-and-verified-first-upload"
                pending_requirements.append(f"{canonical_id}:initial-upload")
            else:
                record["status"] = "UNMANAGED_EXISTING_CONTENT_BLOCKED"
                record["next_action"] = "inspect-existing-content-before-adoption"
                hard_blockers.append(f"{canonical_id}:existing-content-without-baseline")

            if record["title_state"] == "STALE_TITLE":
                pending_requirements.append(f"{canonical_id}:explicit-title-update-required")
            if record["independence_sensitive"] or record["f1_sensitive"]:
                record["requires_integrity_pass_before_write"] = True
                pending_requirements.append(f"{canonical_id}:sensitive-integrity-pass")
            else:
                record["requires_integrity_pass_before_write"] = False
            lessons.append(record)

    return {
        "schema_version": 1,
        "scope": "all-21-lessons-read-only-preflight",
        "course_id": snapshot.get("course", {}).get("id"),
        "course_is_public": course_public,
        "lessons": lessons,
        "hard_blockers": sorted(set(hard_blockers)),
        "pending_requirements": sorted(set(pending_requirements)),
        "summary": {
            "lessons": len(lessons),
            "golden_read_only": sum(1 for item in lessons if item["status"] == "READ_ONLY_GOLDEN"),
            "in_sync": sum(1 for item in lessons if item["status"] == "IN_SYNC"),
            "update_required": sum(1 for item in lessons if item["status"] == "UPDATE_REQUIRED"),
            "initial_upload_required": sum(1 for item in lessons if item["status"] == "INITIAL_UPLOAD_REQUIRED"),
            "stale_titles": sum(1 for item in lessons if item["title_state"] == "STALE_TITLE"),
            "sensitive_lessons": sum(1 for item in lessons if item.get("requires_integrity_pass_before_write")),
            "hard_blockers": len(set(hard_blockers)),
        },
        "ready_for_bulk_write": False,
        "next_gate": "general-content-compiler-plus-asset-publication-resolution",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only all-course Stepik bulk status")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-uploader-live"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)

    try:
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        asset_inventory = build_asset_inventory(repo_root, manifest)
        write_json(report_dir / "asset-inventory.json", asset_inventory)
        if asset_inventory["missing_files"]:
            raise BulkStatusError(
                "asset inventory содержит отсутствующие source files: " + ", ".join(asset_inventory["missing_files"])
            )

        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.json", snapshot)

        plan = plan_dry_run(manifest, snapshot)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        profile_blockers = validate_golden_profile(
            profile,
            snapshot,
            manifest,
            allow_course_publication_change=True,
        )
        golden_status = mark_golden_profile_result(plan, profile_blockers)
        if golden_status != "confirmed" or plan.blockers:
            raise BulkStatusError(
                "preflight guards не пройдены: " + "; ".join(sorted(set(profile_blockers + plan.blockers)))
            )

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state=state,
            profile=profile,
            plan=plan,
        )
        status["asset_summary"] = asset_inventory["summary"]
        write_json(report_dir / "bulk-status.json", status)

        report = {
            "course_id": args.course_id,
            "source_main_sha": sha,
            "mode": "bulk-status",
            "read_objects": count_snapshot(snapshot),
            "verdict": "BLOCKED" if status["hard_blockers"] else "PASS",
            "hard_blockers": status["hard_blockers"],
            "pending_requirements": status["pending_requirements"],
            "summary": status["summary"],
            "asset_summary": asset_inventory["summary"],
            "golden_profile_status": golden_status,
            "stepik_writes": 0,
            "ready_for_bulk_write": False,
            "next_gate": status["next_gate"],
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if status["hard_blockers"] else 0
    except (
        AssetInventoryError,
        BulkStatusError,
        CanonicalBuildError,
        ContentCompileError,
        ContentWriteError,
        GoldenProfileError,
        SyncStateError,
        StepikAPIError,
        RuntimeError,
    ) as exc:
        report = {
            "course_id": args.course_id,
            "source_main_sha": sha,
            "mode": "bulk-status",
            "verdict": "BLOCKED",
            "hard_blockers": [f"bulk-status:{exc}"],
            "stepik_writes": 0,
            "ready_for_bulk_write": False,
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
