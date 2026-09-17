from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.staging_commit_gap_recovery as ordinary
    from stepik_uploader.history_runtime import find_incomplete_object_events
    from stepik_uploader.reporting import write_json
    from stepik_uploader.sync_state import baseline_for, load_state
else:
    from . import staging_commit_gap_recovery as ordinary
    from .history_runtime import find_incomplete_object_events
    from .reporting import write_json
    from .sync_state import baseline_for, load_state


GOLDEN_IDS = {"M00-L01", "M00-L02"}


def main() -> int:
    args = ordinary.parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    target_id = str(args.target_id).strip()
    probe = report_dir / "commit-gap-recovery.json"

    try:
        if args.course_id != 299189:
            raise ordinary.ContentWriteError("Golden commit-gap recovery разрешён только для course_id=299189")
        if target_id not in GOLDEN_IDS:
            raise ordinary.ContentWriteError("Golden commit-gap recovery разрешён только для M00-L01/M00-L02")
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        pending = state.get("pending", {}).get("lessons", {}).get(target_id)
        baseline = baseline_for(state, target_id)
        if pending is not None or not isinstance(baseline, dict):
            write_json(
                probe,
                {
                    "applicable": False,
                    "target_lesson": target_id,
                    "reason": "golden-still-pending-or-baseline-absent",
                    "stepik_writes": 0,
                },
            )
            return 0

        sha = ordinary.source_sha(repo_root)
        store = ordinary._history_store(sha)
        incomplete = find_incomplete_object_events(store, object_id=target_id)
        current = [item for item in incomplete if item[0].source_sha == sha]
        if not current:
            write_json(
                probe,
                {
                    "applicable": False,
                    "target_lesson": target_id,
                    "reason": "no-current-source-history-gap",
                    "stepik_writes": 0,
                },
            )
            return 0
        if len(current) != len(incomplete):
            raise ordinary.DeploymentHistoryError(
                f"{target_id}: одновременно существуют current и stale incomplete golden events"
            )

        # Reuse the proven ordinary commit-gap verifier. The only ordinary-specific
        # restriction is the explicit READ_ONLY_GOLDEN rejection; recovery performs
        # zero Stepik writes and merely proves live == current baseline == final WAL.
        ordinary.GOLDEN_IDS = set()
        return ordinary.main()
    except (
        ordinary.ContentWriteError,
        ordinary.DeploymentHistoryError,
        ordinary.SyncStateError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        write_json(
            probe,
            {
                "applicable": True,
                "target_lesson": target_id,
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "stepik_writes": 0,
            },
        )
        print(f"GOLDEN RECOVERY BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
