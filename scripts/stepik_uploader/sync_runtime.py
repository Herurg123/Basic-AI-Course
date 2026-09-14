from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reporting import build_report, write_json
    from stepik_uploader.stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from stepik_uploader.sync_state import SyncStateError, assess_sync, baseline_for, load_state, with_record
    from stepik_uploader.writer import ContentWriteError, execute_content_sync_one
else:
    from .api import StepikAPIError, StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .planner import plan_dry_run
    from .reporting import build_report, write_json
    from .stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from .sync_state import SyncStateError, assess_sync, baseline_for, load_state, with_record
    from .writer import ContentWriteError, execute_content_sync_one

GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
BLOCKED_SYNC_STATUSES = {
    "BASELINE_BOOTSTRAP_REQUIRED",
    "BASELINE_MISSING_BLOCKED",
    "DRIFT_BLOCKED",
    "METADATA_UPDATE_BLOCKED",
    "STRUCTURAL_UPDATE_BLOCKED",
}


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для live sync нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в GitHub Actions Secrets")
    return client_id, client_secret


def _manifest_lesson(manifest: dict[str, Any], canonical_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == canonical_id:
                return module, lesson
    raise ContentCompileError(f"В derived manifest отсутствует {canonical_id}")


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [s for s in snapshot.get("sections", []) if s.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден единственный section position={module_position}")
    units = [u for u in sections[0].get("units", []) if u.get("position") == lesson_position]
    if len(units) != 1:
        raise ContentWriteError(
            f"Не найден единственный unit section={module_position} position={lesson_position}"
        )
    lesson = units[0].get("lesson")
    if not isinstance(lesson, dict):
        raise ContentWriteError("В unit отсутствует lesson")
    return lesson


def _journal_markdown(*, source_sha_value: str, result: Any, record: dict[str, Any]) -> str:
    run_url = ""
    if os.getenv("GITHUB_SERVER_URL") and os.getenv("GITHUB_REPOSITORY") and os.getenv("GITHUB_RUN_ID"):
        run_url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    updated_positions = [op.get("position") for op in result.operations if op.get("action") == "UPDATE_STEP"]
    if updated_positions:
        heading = f"### APPLIED: `{TEST_LESSON_ID}` синхронизирован со Stepik"
        operation_line = f"- обновлённые позиции steps: `{updated_positions}`"
        final_note = (
            "Запись baseline выполнена только после успешного read-back. Следующее обновление разрешается лишь если "
            "live Stepik всё ещё совпадает с этим fingerprint."
        )
    else:
        heading = f"### NOOP_CONFIRMED: `{TEST_LESSON_ID}` уже синхронизирован"
        operation_line = "- Stepik writes: `0`"
        final_note = (
            "Live Stepik, текущий канон и подтверждённый baseline совпали. Никаких PUT/POST не отправлялось; "
            "PENDING-запись этого source SHA не требует фактического обновления платформы."
        )
    lines = [
        heading,
        "",
        f"- source main SHA: `{source_sha_value}`",
        f"- Stepik lesson ID: `{result.lesson_id}`",
        operation_line,
        f"- подтверждённый baseline/read-back: `{record['applied_at']}`",
        f"- fingerprint: `{record['applied_fingerprint']}`",
    ]
    if run_url:
        lines.append(f"- workflow run: {run_url}")
    lines.extend(["", final_note])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drift-guarded Stepik sync runtime")
    parser.add_argument("mode", choices=["sync-status", "sync-changed"])
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-uploader-live"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
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
            raise ContentWriteError(
                "pre-sync live guards не пройдены: " + "; ".join(sorted(set(profile_blockers + plan.blockers)))
            )

        module, lesson = _manifest_lesson(manifest, TEST_LESSON_ID)
        if lesson.get("golden_read_only") or lesson.get("independence_sensitive") or lesson.get("f1_sensitive"):
            raise ContentWriteError("Текущий pilot sync target попал в protected lesson")
        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("В golden profile отсутствует free_answer_source")
        compiled = compile_test_lesson(repo_root, free_answer_source=free_answer_source, lesson_id=TEST_LESSON_ID)
        expected_title = f"{TEST_LESSON_ID} — {lesson['title']}"
        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson["position"]),
        )
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        baseline = baseline_for(state, TEST_LESSON_ID)
        assessment = assess_sync(
            canonical_id=TEST_LESSON_ID,
            live_lesson=live_lesson,
            expected_title=expected_title,
            expected_steps=compiled,
            baseline=baseline,
        )
        sync_payload = {
            "scope": "pilot-M02-L01-until-general-compiler-is-enabled",
            "canonical_id": TEST_LESSON_ID,
            "course_is_public": snapshot.get("course", {}).get("is_public"),
            "lesson_is_public": live_lesson.get("is_public"),
            "status": assessment.status,
            "desired_fingerprint": assessment.desired_fingerprint,
            "live_fingerprint": assessment.live_fingerprint,
            "baseline_fingerprint": assessment.baseline_fingerprint,
            "changed_step_positions": list(assessment.changed_step_positions),
            "reasons": list(assessment.reasons),
        }
        write_json(report_dir / "sync-status.json", sync_payload)

        report = build_report(
            mode=args.mode,
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=count_snapshot(snapshot),
        )
        report["sync"] = sync_payload
        report["golden_profile_status"] = golden_status

        if args.mode == "sync-status":
            report["verdict"] = "BLOCKED" if assessment.status in BLOCKED_SYNC_STATUSES else "PASS"
            report["blockers"] = list(assessment.reasons) if report["verdict"] == "BLOCKED" else []
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["verdict"] == "BLOCKED" else 0

        if not args.confirm_write:
            raise ContentWriteError("sync-changed требует явный confirm_write")

        result = execute_content_sync_one(
            client,
            snapshot,
            canonical_id=TEST_LESSON_ID,
            expected_steps=compiled,
            module_position=int(module["position"]),
            lesson_position=int(lesson["position"]),
            expected_title=expected_title,
            baseline=baseline,
            source_sha=sha,
        )
        if result.after_snapshot is not None:
            write_json(report_dir / "course-snapshot.after.json", result.after_snapshot)
        report["stepik_lesson_id"] = result.lesson_id
        report["write_operations"] = result.operations
        report["updated"] = sum(1 for op in result.operations if op.get("action") == "UPDATE_STEP")
        report["created"] = 0
        report["final_step_ids"] = result.final_step_ids
        report["readback_verified"] = result.verified
        report["blockers"] = []
        report["verdict"] = "PASS" if result.verified else "BLOCKED"

        if result.state_record is not None:
            if report["updated"] > 0:
                next_state = with_record(state, canonical_id=TEST_LESSON_ID, record=result.state_record)
                write_json(report_dir / "sync-state.next.json", next_state)
            (report_dir / "sync-journal.md").write_text(
                _journal_markdown(source_sha_value=sha, result=result, record=result.state_record),
                encoding="utf-8",
            )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if result.verified else 2
    except (
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
            "mode": args.mode,
            "verdict": "BLOCKED",
            "blockers": [f"sync:{exc}"],
            "write_retry_policy": "no automatic write retry; inspect drift before rerun",
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
