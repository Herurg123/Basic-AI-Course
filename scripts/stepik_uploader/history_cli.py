from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from stepik_uploader.history_runtime import load_event_artifact, mark_machine_state_committed
else:
    from .deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from .history_runtime import load_event_artifact, mark_machine_state_committed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commit durable Stepik deployment history after machine-state PATCH")
    parser.add_argument("mark-state-committed", nargs="?")
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        event = load_event_artifact(args.event_file)
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise DeploymentHistoryError("state-file должен содержать JSON object")
        canonical_id = str(event.get("canonical_id"))
        baseline_after = state.get("lessons", {}).get(canonical_id)
        store = GitHubHistoryStore(
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            token=os.environ.get("GITHUB_TOKEN", ""),
            source_sha=str(event.get("source_sha")),
        )
        mark_machine_state_committed(
            store,
            event_id=str(event["event_id"]),
            status=str(event.get("status")),
            baseline_after=baseline_after if isinstance(baseline_after, dict) else None,
        )
        return 0
    except (DeploymentHistoryError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
