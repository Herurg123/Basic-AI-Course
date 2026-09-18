from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.golden_content_refresh_m00_l01_6to6 as m00_l01
    from stepik_uploader.fingerprints import live_lesson_fingerprint
    from stepik_uploader.golden import load_golden_profile
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import baseline_for, load_state
else:
    from . import golden_content_refresh_m00_l01_6to6 as m00_l01
    from .fingerprints import live_lesson_fingerprint
    from .golden import load_golden_profile
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import baseline_for, load_state


COURSE_ID = 299189
EXPECTED_COUNTS = {"M00-L01": 6, "M00-L02": 8}


class GoldenProfileCaptureError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only capture of final live golden profile after private release")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    return parser.parse_args()


def _validated_baselines(state: dict) -> dict[str, dict]:
    pending_lessons = state.get("pending", {}).get("lessons", {})
    remaining = sorted(target for target in EXPECTED_COUNTS if target in pending_lessons)
    if remaining:
        raise GoldenProfileCaptureError("Golden capture запрещён при PENDING: " + ", ".join(remaining))

    baselines: dict[str, dict] = {}
    for target, count in EXPECTED_COUNTS.items():
        baseline = baseline_for(state, target)
        if not isinstance(baseline, dict):
            raise GoldenProfileCaptureError(f"{target}: отсутствует confirmed machine baseline")
        if len(baseline.get("step_ids", [])) != count:
            raise GoldenProfileCaptureError(f"{target}: baseline не подтверждает {count} step IDs")
        baselines[target] = baseline
    return baselines


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else repo_root / args.output
    report_path = args.report if args.report.is_absolute() else repo_root / args.report
    sha = source_sha(repo_root)
    report: dict = {
        "mode": "golden-profile-final-capture",
        "course_id": args.course_id,
        "source_main_sha": sha,
        "stepik_writes": 0,
    }
    try:
        if args.course_id != COURSE_ID:
            raise GoldenProfileCaptureError(f"capture разрешён только для course_id={COURSE_ID}")
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=COURSE_ID)
        baselines = _validated_baselines(state)

        profile = load_golden_profile(repo_root / m00_l01.GOLDEN_PROFILE_PATH)
        client_id, client_secret = m00_l01.legacy._credentials()
        client = m00_l01.legacy.StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(COURSE_ID)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False or course.get("language") not in {None, "ru"}:
            raise GoldenProfileCaptureError("Final golden capture разрешён только в private ru course")

        live_fingerprints: dict[str, str] = {}
        for target, baseline in baselines.items():
            profile_row = profile.get("golden_lessons", {}).get(target)
            if not isinstance(profile_row, dict):
                raise GoldenProfileCaptureError(f"{target}: отсутствует в canonical golden profile")
            lesson = m00_l01.legacy._live_target(snapshot, lesson_id=int(profile_row["stepik_lesson_id"]))
            if int(lesson.get("id", -1)) != int(baseline.get("stepik_lesson_id", -2)):
                raise GoldenProfileCaptureError(f"{target}: live lesson ID не совпадает с machine baseline")
            live_fp = live_lesson_fingerprint(lesson)
            proven_fp = baseline.get("confirmed_live_fingerprint") or baseline.get("applied_fingerprint")
            if live_fp != proven_fp:
                raise GoldenProfileCaptureError(f"{target}: live fingerprint не совпадает с final machine baseline")
            live_fingerprints[target] = live_fp

        proposed = m00_l01._next_profile_all(profile, snapshot, sha=sha)
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, proposed)
        report.update(
            {
                "verdict": "PASS",
                "golden_lessons": EXPECTED_COUNTS,
                "live_fingerprints": live_fingerprints,
                "output": str(output),
                "blockers": [],
            }
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        GoldenProfileCaptureError,
        m00_l01.GoldenM00L01RefreshError,
        m00_l01.legacy.GoldenProfileError,
        m00_l01.legacy.StepikAPIError,
        m00_l01.legacy.SyncStateError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        report.update({"verdict": "BLOCKED", "blockers": [str(exc)]})
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
