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


LESSON_HISTORY_KINDS = {"lesson", "golden-content-refresh", "golden-content-migration"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commit durable Stepik deployment history after machine-state PATCH")
    parser.add_argument("command", choices=["mark-state-committed"])
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    return parser.parse_args()


def _history_identity(store: GitHubHistoryStore, event: dict) -> dict:
    event_id = str(event.get("event_id") or "")
    if not event_id:
        raise DeploymentHistoryError("Deployment event artifact не содержит event_id")
    records = store.load(event_id)
    if not records:
        raise DeploymentHistoryError("Deployment event artifact не имеет immutable history records")
    identities = [row.get("identity") for row in records if isinstance(row.get("identity"), dict)]
    if not identities:
        raise DeploymentHistoryError("Immutable history не содержит event identity")
    first = identities[0]
    if any(identity != first for identity in identities[1:]):
        raise DeploymentHistoryError("Immutable history содержит конфликтующие event identities")
    if first.get("event_id") != event_id:
        raise DeploymentHistoryError("History identity event_id не совпадает с event artifact")
    if str(first.get("source_sha") or "") != str(event.get("source_sha") or ""):
        raise DeploymentHistoryError("History identity source_sha не совпадает с event artifact")
    return first


def _normalize_event_from_history(event: dict, identity: dict, *, event_file: Path) -> dict:
    """Bind routing metadata to immutable history identity before state commit.

    Event artifact fields are transport metadata. The append-only history identity is
    authoritative for object_id/kind. Golden content routes intentionally use their
    own immutable ``kind`` values but still commit a lesson baseline; ordinary lesson
    and asset events keep the same rule. This prevents a mislabeled helper artifact
    from committing another object's baseline.
    """
    normalized = dict(event)
    kind = str(identity.get("kind") or "")
    object_id = str(identity.get("object_id") or "")
    if kind not in LESSON_HISTORY_KINDS | {"asset"} or not object_id:
        raise DeploymentHistoryError("History identity имеет неподдерживаемый kind/object_id")
    normalized["kind"] = kind
    if kind == "asset":
        if not object_id.startswith("asset:"):
            raise DeploymentHistoryError("Asset history identity не имеет prefix asset:")
        normalized["source_path"] = object_id.removeprefix("asset:")
        normalized.pop("canonical_id", None)
    else:
        normalized["canonical_id"] = object_id
        normalized.pop("source_path", None)
    if normalized != event:
        event_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def _baseline_from_state(event: dict, state: dict) -> dict | None:
    kind = str(event.get("kind") or "lesson")
    if kind == "asset":
        source_path = event.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            raise DeploymentHistoryError("Asset deployment event не содержит source_path")
        baseline = state.get("assets", {}).get(source_path)
        return baseline if isinstance(baseline, dict) else None
    if kind not in LESSON_HISTORY_KINDS:
        raise DeploymentHistoryError(f"Неподдерживаемый lesson-like history kind: {kind}")
    canonical_id = str(event.get("canonical_id"))
    baseline = state.get("lessons", {}).get(canonical_id)
    return baseline if isinstance(baseline, dict) else None


def main() -> int:
    args = parse_args()
    try:
        event = load_event_artifact(args.event_file)
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise DeploymentHistoryError("state-file должен содержать JSON object")
        store = GitHubHistoryStore(
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            token=os.environ.get("GITHUB_TOKEN", ""),
            source_sha=str(event.get("source_sha")),
        )
        identity = _history_identity(store, event)
        event = _normalize_event_from_history(event, identity, event_file=args.event_file)
        baseline_after = _baseline_from_state(event, state)
        if not isinstance(baseline_after, dict):
            raise DeploymentHistoryError("Machine state не содержит baseline для immutable event identity")
        mark_machine_state_committed(
            store,
            event_id=str(event["event_id"]),
            status=str(event.get("status")),
            baseline_after=baseline_after,
        )
        return 0
    except (DeploymentHistoryError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
