from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.golden_content_current_8 as current
    import stepik_uploader.golden_content_migration_7to8 as legacy
    import stepik_uploader.golden_content_refresh_8to8 as refresh
else:
    from . import golden_content_current_8 as current
    from . import golden_content_migration_7to8 as legacy
    from . import golden_content_refresh_8to8 as refresh


# Public/test surface retained for existing callers and regression tests.
COURSE_ID = legacy.COURSE_ID
TARGET_ID = legacy.TARGET_ID
GOLDEN_PROFILE_PATH = legacy.GOLDEN_PROFILE_PATH
ASSET_POLICY_PATH = legacy.ASSET_POLICY_PATH
GoldenContentMigrationError = legacy.GoldenContentMigrationError
_fixture_fingerprint = legacy._fixture_fingerprint
_history_state = legacy._history_state
_next_profile = legacy._next_profile


# The original 7→8 writer reads records[0] while reopening a partial event.
# GitHub history storage order is not semantic phase order, so keep the proven
# writer unchanged and harden only its adapter by presenting EVENT_STARTED first.
_ORIGINAL_LEGACY_HISTORY_STORE = legacy._history_store


def _event_started_first(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    started = [record for record in records if record.get("phase") == "EVENT_STARTED"]
    rest = [record for record in records if record.get("phase") != "EVENT_STARTED"]
    return [*started, *rest]


def _legacy_history_store_started_first(sha: str) -> Any:
    store = _ORIGINAL_LEGACY_HISTORY_STORE(sha)
    raw_load = store.load

    def load(event_id: str) -> list[dict[str, Any]]:
        return _event_started_first(raw_load(event_id))

    store.load = load
    return store


legacy._history_store = _legacy_history_store_started_first


def _current_fixture_noop(args: Any, profile: dict[str, Any]) -> int:
    return current.run(args, profile)


def _current_fixture_route(args: Any, profile: dict[str, Any]) -> int:
    """Route accepted 8-step golden to no-op or guarded content refresh.

    PENDING is the only permission boundary for the refresh path. The refresh
    itself independently proves accepted fixture == pre-write live, confirmed
    machine baseline, eight stable step ids/positions and private course state.
    """
    repo_root = args.repo_root.resolve()
    state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
    try:
        state = legacy.load_state(state_path, course_id=COURSE_ID)
    except (legacy.SyncStateError, OSError, ValueError, TypeError):
        # Let the no-op path emit its normal fail-closed report for invalid state.
        return _current_fixture_noop(args, profile)
    pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
    if pending is not None:
        return refresh.run(args, profile)
    return _current_fixture_noop(args, profile)


def main() -> int:
    args = legacy.parse_args()
    repo_root = args.repo_root.resolve()
    try:
        profile = legacy.load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        step_count = int(observed.get("step_count", -1)) if isinstance(observed, dict) else -1
    except (legacy.GoldenProfileError, OSError, ValueError, TypeError):
        # Preserve the historical fail-closed report for malformed/old fixture state.
        return legacy.main()

    if step_count == 7:
        return legacy.main()
    if step_count == 8:
        return _current_fixture_route(args, profile)

    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "golden-content-migration",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": legacy.source_sha(repo_root),
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
        "verdict": "BLOCKED",
        "blockers": [
            f"{TARGET_ID}: supported golden fixture step_count is only 7 (migration) or 8 (current/refresh), got {step_count}"
        ],
    }
    legacy.write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
