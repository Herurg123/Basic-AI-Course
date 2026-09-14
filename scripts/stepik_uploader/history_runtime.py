from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deployment_history import (
    HISTORY_PREFIX,
    DeploymentHistoryError,
    DeploymentRecorder,
    EventIdentity,
    GitHubHistoryStore,
    MemoryHistoryStore,
    summarize_event,
)


def identity_from_records(records: list[dict[str, Any]]) -> EventIdentity:
    if not records:
        raise DeploymentHistoryError("Нельзя восстановить identity из пустой history")
    raw = records[0].get("identity")
    if not isinstance(raw, dict):
        raise DeploymentHistoryError("History event не содержит identity")
    workflow = raw.get("workflow") or {}
    if not isinstance(workflow, dict):
        raise DeploymentHistoryError("History identity.workflow повреждён")
    return EventIdentity(
        event_id=str(raw.get("event_id")),
        course_id=int(raw.get("course_id")),
        object_id=str(raw.get("object_id")),
        kind=str(raw.get("kind")),
        source_sha=str(raw.get("source_sha")),
        workflow_run_id=None if workflow.get("run_id") is None else str(workflow.get("run_id")),
        workflow_run_attempt=None if workflow.get("run_attempt") is None else str(workflow.get("run_attempt")),
        workflow_run_url=None if workflow.get("run_url") is None else str(workflow.get("run_url")),
        desired_fingerprint=str(raw.get("desired_fingerprint")),
        baseline_fingerprint_before=raw.get("baseline_fingerprint_before"),
        pending_first_sha=raw.get("pending_first_sha"),
        retry_of_event_id=raw.get("retry_of_event_id"),
        continuation_of_event_id=raw.get("continuation_of_event_id"),
    )


def find_object_events(store: Any, *, object_id: str) -> list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]]:
    """Find deployment events for one object without relying on a mutable active-event index."""
    event_ids: list[str] = []
    if isinstance(store, MemoryHistoryStore):
        event_ids = sorted(store.records)
    elif isinstance(store, GitHubHistoryStore):
        store.ensure_branch()
        response = store._request(
            "GET",
            f"/repos/{store.repository}/contents/{HISTORY_PREFIX}",
            params={"ref": store.branch},
        )
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            raise DeploymentHistoryError(f"Не удалось перечислить deployment events: HTTP {response.status_code}")
        listing = response.json()
        if not isinstance(listing, list):
            raise DeploymentHistoryError("Deployment history root имеет неожиданный формат")
        event_ids = sorted(
            str(item.get("name"))
            for item in listing
            if isinstance(item, dict)
            and item.get("type") == "dir"
            and str(item.get("name", "")).startswith("evt-")
        )
    else:
        raise DeploymentHistoryError("Неизвестный history store")

    found: list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]] = []
    for event_id in event_ids:
        records = store.load(event_id)
        if not records:
            continue
        identity = identity_from_records(records)
        if identity.object_id != object_id:
            continue
        found.append((identity, records, summarize_event(records)))
    return found


def find_incomplete_object_events(store: Any, *, object_id: str) -> list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]]:
    return [item for item in find_object_events(store, object_id=object_id) if not item[2].get("machine_state_committed")]


def final_confirmed_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in reversed(records):
        if record.get("phase") == "FINAL_READBACK_CONFIRMED":
            return record
    return None


def load_event_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentHistoryError(f"Не удалось прочитать deployment-event artifact: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("event_id"), str):
        raise DeploymentHistoryError("deployment-event artifact повреждён")
    return payload


def mark_machine_state_committed(
    store: Any,
    *,
    event_id: str,
    status: str,
    baseline_after: dict[str, Any] | None,
) -> None:
    records = store.load(event_id)
    identity = identity_from_records(records)
    summary = summarize_event(records)
    if not summary.get("final_readback_confirmed"):
        raise DeploymentHistoryError("Нельзя отметить machine state committed без FINAL_READBACK_CONFIRMED")
    if summary.get("machine_state_committed"):
        return
    recorder = DeploymentRecorder(store, identity)
    recorder.state_committed(baseline_after=baseline_after, status=status)
