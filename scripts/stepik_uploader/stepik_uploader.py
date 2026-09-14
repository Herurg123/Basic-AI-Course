from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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
    from stepik_uploader.writer import ContentWriteError, execute_content_test_one
else:
    from .api import StepikAPIError, StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .planner import plan_dry_run
    from .reporting import build_report, write_json
    from .writer import ContentWriteError, execute_content_test_one


BLOCKED_WRITE_MODES = {
    "skeleton",
    "assets-test",
    "upload-remaining",
    "verify",
}
ACTIVE_WRITE_MODES = {"content-test-one"}
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")


def source_sha(repo_root: Path) -> str:
    explicit = os.getenv("GITHUB_SHA")
    if explicit:
        return explicit
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def require_credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "Для live режима нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в environment/GitHub Actions Secrets. "
            "Не передавайте их в чат и не коммитьте."
        )
    return client_id, client_secret


def count_snapshot(snapshot: dict) -> int:
    sections = snapshot.get("sections", [])
    units = [unit for section in sections for unit in section.get("units", [])]
    lessons = [unit.get("lesson", {}) for unit in units]
    steps = [step for lesson in lessons for step in lesson.get("steps", [])]
    return 1 + len(sections) + len(units) + len(lessons) + (2 * len(steps))


def load_and_validate_saved_golden_profile(
    repo_root: Path,
    snapshot: dict,
    manifest: dict,
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
    except GoldenProfileError as exc:
        return None, [f"golden-profile:{exc}"]
    return profile, validate_golden_profile(profile, snapshot, manifest)


def mark_golden_profile_result(plan: object, profile_blockers: list[str]) -> str:
    blockers = getattr(plan, "blockers", None)
    if not isinstance(blockers, list):
        return "invalid-plan"
    if profile_blockers:
        blockers.extend(profile_blockers)
        return "blocked"
    blockers[:] = [item for item in blockers if item != "needs-golden-profile"]
    return "confirmed"


def _manifest_lesson(manifest: dict[str, Any], canonical_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == canonical_id:
                return module, lesson
    raise ContentCompileError(f"В derived manifest отсутствует {canonical_id}")


def _compiled_plan_payload(steps: list[Any], *, lesson_id: str) -> dict[str, Any]:
    return {
        "lesson": lesson_id,
        "write_scope": "single-existing-draft-lesson",
        "steps": [
            {
                "position": step.position,
                "block_name": step.block_name,
                "html_sha256": hashlib.sha256(step.text.encode("utf-8")).hexdigest(),
                "source": step.source,
                "source_git_paths": list(step.source_git_paths),
            }
            for step in steps
        ],
        "delete_allowed": False,
        "golden_write_allowed": False,
    }


def _blocked_report(
    *,
    mode: str,
    sha: str,
    course_id: int | None,
    manifest: dict,
    blockers: list[str],
    plan: Any | None = None,
    read_objects: int = 0,
) -> dict[str, Any]:
    report = build_report(
        mode=mode,
        source_sha=sha,
        course_id=course_id,
        manifest=manifest,
        plan=plan,
        read_objects=read_objects,
    )
    report["blockers"] = sorted(set(report.get("blockers", []) + blockers))
    report["verdict"] = "BLOCKED"
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stepik uploader проекта «ИИ с нуля»")
    parser.add_argument(
        "mode",
        choices=["inspect", "dry-run", *sorted(BLOCKED_WRITE_MODES | ACTIVE_WRITE_MODES)],
        help="Режим. Массовые write-режимы остаются fail-closed; content-test-one ограничен одним уроком.",
    )
    parser.add_argument("--course-id", type=int, default=None, help="Обычный числовой Stepik course_id")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-uploader"))
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--test-lesson", default=TEST_LESSON_ID)
    parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="Явное подтверждение единственного content-test write; без него запись запрещена.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    sha = source_sha(repo_root)

    try:
        manifest = build_structural_manifest(repo_root, source_sha=sha)
    except CanonicalBuildError as exc:
        print(f"CANONICAL BLOCKER: {exc}", file=sys.stderr)
        return 2

    write_json(report_dir / "build-manifest.structural.json", manifest)

    if args.mode in BLOCKED_WRITE_MODES:
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            blockers=["write-mode-disabled-pre-content-test-checkpoint"],
        )
        report["golden_profile_status"] = "recorded-but-mass-write-still-locked"
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if args.mode == "content-test-one" and not args.confirm_write:
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            blockers=["explicit-confirm-write-required"],
        )
        report["test_lesson"] = args.test_lesson
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if args.mode == "content-test-one" and args.test_lesson != TEST_LESSON_ID:
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            blockers=[f"only-{TEST_LESSON_ID}-is-allowed-in-content-test-one"],
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    snapshot = None
    client = None
    read_objects = 0
    if args.course_id is not None:
        try:
            client_id, client_secret = require_credentials()
            client = StepikClient(client_id, client_secret, api_host=args.api_host)
            snapshot = client.inspect_course(args.course_id)
            read_objects = count_snapshot(snapshot)
            write_json(report_dir / "course-snapshot.json", snapshot)
        except (RuntimeError, StepikAPIError) as exc:
            print(f"LIVE MODE BLOCKER: {exc}", file=sys.stderr)
            return 2

    plan = plan_dry_run(manifest, snapshot)
    profile: dict[str, Any] | None = None
    profile_blockers: list[str] = []
    golden_profile_status = "not-checked"
    if snapshot is not None:
        profile, profile_blockers = load_and_validate_saved_golden_profile(repo_root, snapshot, manifest)
        golden_profile_status = mark_golden_profile_result(plan, profile_blockers)

    write_json(report_dir / "dry-run-plan.json", {"operations": plan.operations, "blockers": plan.blockers})

    if args.mode == "inspect":
        if args.course_id is None:
            print("LIVE INSPECT BLOCKER: inspect требует --course-id", file=sys.stderr)
            return 2
        write_json(
            report_dir / "golden-inspection.json",
            {
                "golden": plan.golden,
                "profile_status": golden_profile_status,
                "profile_blockers": profile_blockers,
                "blockers": plan.blockers,
            },
        )
        report = build_report(
            mode="inspect",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
        )
        report["golden_profile_status"] = golden_profile_status
        report["golden_profile_blockers"] = profile_blockers
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.mode == "dry-run":
        report = build_report(
            mode="dry-run",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
        )
        report["golden_profile_status"] = golden_profile_status
        report["golden_profile_blockers"] = profile_blockers
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.course_id is None or snapshot is None or client is None:
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
            blockers=["content-test-one-requires-course-id-and-live-inspect"],
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    if golden_profile_status != "confirmed" or plan.blockers:
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
            blockers=["prewrite-live-plan-not-clean"],
        )
        report["golden_profile_status"] = golden_profile_status
        report["golden_profile_blockers"] = profile_blockers
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
        if profile is None:
            raise ContentCompileError("Golden profile не загружен")
        module, lesson = _manifest_lesson(manifest, TEST_LESSON_ID)
        if lesson.get("golden_read_only") or lesson.get("independence_sensitive") or lesson.get("f1_sensitive"):
            raise ContentCompileError("Первый content test выбран на запрещённом для этой фазы уроке")
        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("В golden profile отсутствует free_answer_source")
        compiled = compile_test_lesson(
            repo_root,
            free_answer_source=free_answer_source,
            lesson_id=TEST_LESSON_ID,
        )
        if len(compiled) != len(lesson.get("steps", [])):
            raise ContentCompileError(
                f"Compiled step count={len(compiled)} не совпадает со Stepik-plan rows={len(lesson.get('steps', []))}"
            )
        write_json(
            report_dir / "content-test-plan.json",
            _compiled_plan_payload(compiled, lesson_id=TEST_LESSON_ID),
        )

        expected_title = f"{TEST_LESSON_ID} — {lesson['title']}"
        result = execute_content_test_one(
            client,
            snapshot,
            expected_steps=compiled,
            module_position=int(module["position"]),
            lesson_position=int(lesson["position"]),
            expected_title=expected_title,
        )
        if result.after_snapshot is not None:
            write_json(report_dir / "course-snapshot.after.json", result.after_snapshot)

        report = build_report(
            mode=args.mode,
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
        )
        report["golden_profile_status"] = golden_profile_status
        report["test_lesson"] = TEST_LESSON_ID
        report["stepik_lesson_id"] = result.lesson_id
        report["write_operations"] = result.operations
        report["created"] = sum(1 for op in result.operations if op.get("action") == "CREATE_STEP")
        report["updated"] = sum(1 for op in result.operations if op.get("action") == "UPDATE_PLACEHOLDER")
        report["final_step_ids"] = result.final_step_ids
        report["readback_verified"] = result.verified
        report["blockers"] = []
        report["verdict"] = "PASS" if result.verified else "BLOCKED"
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if result.verified else 2
    except (ContentCompileError, ContentWriteError, StepikAPIError, RuntimeError) as exc:
        try:
            after_failure = client.inspect_course(args.course_id)
            write_json(report_dir / "course-snapshot.after-failure.json", after_failure)
        except Exception:
            pass
        report = _blocked_report(
            mode=args.mode,
            sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
            blockers=[f"content-test-one:{exc}"],
        )
        report["golden_profile_status"] = golden_profile_status
        report["test_lesson"] = TEST_LESSON_ID
        report["write_retry_policy"] = "no automatic write retry; inspect state before rerun"
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
