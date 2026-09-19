from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.platform_profile import PLATFORM_PROFILE_PATH, PlatformProfileError, load_platform_profile
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reporting import build_report, write_json
else:
    from .api import StepikAPIError, StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .platform_profile import PLATFORM_PROFILE_PATH, PlatformProfileError, load_platform_profile
    from .planner import plan_dry_run
    from .reporting import build_report, write_json


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
            "Для live inspect нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в environment/GitHub Actions Secrets."
        )
    return client_id, client_secret


def count_snapshot(snapshot: dict) -> int:
    sections = snapshot.get("sections", [])
    units = [unit for section in sections for unit in section.get("units", [])]
    lessons = [unit.get("lesson", {}) for unit in units]
    steps = [step for lesson in lessons for step in lesson.get("steps", [])]
    return 1 + len(sections) + len(units) + len(lessons) + (2 * len(steps))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Stepik inspection for project «ИИ с нуля». Writes use the private-release workflow."
    )
    parser.add_argument("mode", choices=["inspect", "dry-run"])
    parser.add_argument("--course-id", type=int, default=None)
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
        platform_profile = load_platform_profile(repo_root / PLATFORM_PROFILE_PATH)
    except (CanonicalBuildError, PlatformProfileError) as exc:
        print(f"READ-ONLY BLOCKER: {exc}", file=sys.stderr)
        return 2

    write_json(report_dir / "build-manifest.structural.json", manifest)
    write_json(
        report_dir / "platform-profile-check.json",
        {
            "status": "confirmed",
            "course_id": platform_profile["course_id"],
            "schema_version": platform_profile["schema_version"],
        },
    )

    snapshot = None
    read_objects = 0
    if args.mode == "inspect":
        if args.course_id is None:
            print("LIVE INSPECT BLOCKER: inspect требует --course-id", file=sys.stderr)
            return 2
        try:
            client_id, client_secret = require_credentials()
            client = StepikClient(client_id, client_secret, api_host=args.api_host)
            snapshot = client.inspect_course(args.course_id)
            read_objects = count_snapshot(snapshot)
            write_json(report_dir / "course-snapshot.json", snapshot)
        except (RuntimeError, StepikAPIError) as exc:
            print(f"LIVE INSPECT BLOCKER: {exc}", file=sys.stderr)
            return 2

    plan = plan_dry_run(manifest, snapshot)
    write_json(
        report_dir / "dry-run-plan.json",
        {
            "operations": plan.operations,
            "blockers": plan.blockers,
            "notices": plan.notices,
        },
    )
    report = build_report(
        mode=args.mode,
        source_sha=sha,
        course_id=args.course_id,
        manifest=manifest,
        plan=plan,
        read_objects=read_objects,
    )
    report["platform_profile_status"] = "confirmed"
    write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.mode == "inspect" and plan.blockers:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
