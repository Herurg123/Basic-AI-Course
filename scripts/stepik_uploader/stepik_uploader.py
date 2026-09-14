from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikClient
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reporting import build_report, write_json
else:
    from .api import StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .planner import plan_dry_run
    from .reporting import build_report, write_json


BLOCKED_WRITE_MODES = {
    "skeleton",
    "assets-test",
    "content-test-one",
    "upload-remaining",
    "verify",
}


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
            "Для live inspect нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в environment/GitHub Actions Secrets. "
            "Не передавайте их в чат и не коммитьте."
        )
    return client_id, client_secret


def count_snapshot(snapshot: dict) -> int:
    sections = snapshot.get("sections", [])
    units = [unit for section in sections for unit in section.get("units", [])]
    lessons = [unit.get("lesson", {}) for unit in units]
    steps = [step for lesson in lessons for step in lesson.get("steps", [])]
    # Для каждого шага snapshot содержит step + step_source.
    return 1 + len(sections) + len(units) + len(lessons) + (2 * len(steps))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stepik uploader проекта «ИИ с нуля»")
    parser.add_argument(
        "mode",
        choices=["inspect", "dry-run", *sorted(BLOCKED_WRITE_MODES)],
        help="Режим. До golden inspection write-режимы fail-closed.",
    )
    parser.add_argument("--course-id", type=int, default=None, help="Обычный числовой Stepik course_id")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-uploader"))
    parser.add_argument("--api-host", default="https://stepik.org")
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
        report = build_report(
            mode=args.mode,
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
        )
        report["blockers"] = sorted(set(report["blockers"] + ["needs-golden-profile", "write-mode-disabled-pre-golden"]))
        report["verdict"] = "BLOCKED"
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    snapshot = None
    read_objects = 0
    if args.course_id is not None:
        try:
            client_id, client_secret = require_credentials()
            client = StepikClient(client_id, client_secret, api_host=args.api_host)
            snapshot = client.inspect_course(args.course_id)
            read_objects = count_snapshot(snapshot)
            write_json(report_dir / "course-snapshot.json", snapshot)
        except RuntimeError as exc:
            print(f"LIVE INSPECT BLOCKER: {exc}", file=sys.stderr)
            return 2

    if args.mode == "inspect":
        if args.course_id is None:
            print("LIVE INSPECT BLOCKER: inspect требует --course-id", file=sys.stderr)
            return 2
        plan = plan_dry_run(manifest, snapshot)
        write_json(
            report_dir / "golden-inspection.json",
            {"golden": plan.golden, "blockers": plan.blockers},
        )
        report = build_report(
            mode="inspect",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
        )
    else:
        plan = plan_dry_run(manifest, snapshot)
        report = build_report(
            mode="dry-run",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=read_objects,
        )

    write_json(report_dir / "dry-run-plan.json", {"operations": plan.operations, "blockers": plan.blockers})
    write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Ожидаемые фазовые blockers не являются сбоем CI: артефакты должны быть доступны владельцу/инженеру.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
