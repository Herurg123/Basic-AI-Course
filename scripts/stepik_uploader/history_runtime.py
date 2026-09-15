from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .deployment_history import (
    HISTORY_PREFIX,
    HISTORY_SCHEMA_VERSION,
    DeploymentHistoryError,
    DeploymentRecorder,
    EventIdentity,
    GitHubHistoryStore,
    MemoryHistoryStore,
    stable_event_id,
    summarize_event,
)


def _parse_identity(raw: Any) -> EventIdentity:
    if not isinstance(raw, dict):
        raise DeploymentHistoryError("History record не содержит корректный identity")
    workflow = raw.get("workflow") or {}
    if not isinstance(workflow, dict):
        raise DeploymentHistoryError("History identity.workflow повреждён")
    required_strings = ("event_id", "object_id", "kind", "source_sha", "desired_fingerprint")
    for key in required_strings:
        if not isinstance(raw.get(key), str) or not raw.get(key):
            raise DeploymentHistoryError(f"History identity.{key} отсутствует или повреждён")
    try:
        course_id = int(raw.get("course_id"))
    except (TypeError, ValueError) as exc:
        raise DeploymentHistoryError("History identity.course_id повреждён") from exc
    baseline = raw.get("baseline_fingerprint_before")
    pending_first_sha = raw.get("pending_first_sha")
    if baseline is not None and not isinstance(baseline, str):
        raise DeploymentHistoryError("History identity.baseline_fingerprint_before повреждён")
    if pending_first_sha is not None and not isinstance(pending_first_sha, str):
        raise DeploymentHistoryError("History identity.pending_first_sha повреждён")
    return EventIdentity(
        event_id=raw["event_id"],
        course_id=course_id,
        object_id=raw["object_id"],
        kind=raw["kind"],
        source_sha=raw["source_sha"],
        workflow_run_id=None if workflow.get("run_id") is None else str(workflow.get("run_id")),
        workflow_run_attempt=None if workflow.get("run_attempt") is None else str(workflow.get("run_attempt")),
        workflow_run_url=None if workflow.get("run_url") is None else str(workflow.get("run_url")),
        desired_fingerprint=raw["desired_fingerprint"],
        baseline_fingerprint_before=baseline,
        pending_first_sha=pending_first_sha,
        retry_of_event_id=raw.get("retry_of_event_id"),
        continuation_of_event_id=raw.get("continuation_of_event_id"),
    )


def _identity_core(identity: EventIdentity) -> tuple[Any, ...]:
    return (
        identity.event_id,
        identity.course_id,
        identity.object_id,
        identity.kind,
        identity.source_sha,
        identity.desired_fingerprint,
        identity.baseline_fingerprint_before,
        identity.pending_first_sha,
    )


def validate_event_records(records: list[dict[str, Any]], *, expected_event_id: str | None = None) -> EventIdentity:
    """Fail closed on tampered or internally contradictory operational history."""
    if not records:
        raise DeploymentHistoryError("Нельзя проверить пустую deployment history")

    started_records = [record for record in records if record.get("phase") == "EVENT_STARTED"]
    if len(started_records) > 1:
        raise DeploymentHistoryError("History event содержит несколько EVENT_STARTED")
    anchor_record = started_records[0] if started_records else records[0]
    anchor = _parse_identity(anchor_record.get("identity"))

    calculated_event_id = stable_event_id(
        course_id=anchor.course_id,
        object_id=anchor.object_id,
        kind=anchor.kind,
        source_sha=anchor.source_sha,
        desired_fingerprint=anchor.desired_fingerprint,
        baseline_fingerprint=anchor.baseline_fingerprint_before,
        pending_first_sha=anchor.pending_first_sha,
    )
    if anchor.event_id != calculated_event_id:
        raise DeploymentHistoryError("History identity.event_id не соответствует stable event identity")
    if expected_event_id is not None and anchor.event_id != expected_event_id:
        raise DeploymentHistoryError("History directory event_id не совпадает с identity.event_id")

    core = _identity_core(anchor)
    record_ids: set[str] = set()
    for record in records:
        if record.get("history_schema_version") != HISTORY_SCHEMA_VERSION:
            raise DeploymentHistoryError("History record имеет неподдерживаемую schema version")
        record_id = record.get("record_id")
        phase = record.get("phase")
        if not isinstance(record_id, str) or not record_id:
            raise DeploymentHistoryError("History record не содержит record_id")
        if record_id in record_ids:
            raise DeploymentHistoryError("History event содержит duplicate record_id")
        record_ids.add(record_id)
        if not isinstance(phase, str) or not phase:
            raise DeploymentHistoryError("History record не содержит phase")
        current = _parse_identity(record.get("identity"))
        if _identity_core(current) != core:
            raise DeploymentHistoryError("History event содержит records с разной logical identity")

    singular = ("FINAL_READBACK_CONFIRMED", "MACHINE_STATE_COMMITTED")
    for phase in singular:
        if sum(record.get("phase") == phase for record in records) > 1:
            raise DeploymentHistoryError(f"History event содержит несколько {phase}")

    intents: dict[str, dict[str, Any]] = {}
    dispatches: dict[str, dict[str, Any]] = {}
    results: dict[str, list[dict[str, Any]]] = {}
    confirmed: dict[str, dict[str, Any]] = {}
    for record in records:
        phase = record.get("phase")
        if phase not in {
            "WRITE_INTENT",
            "WRITE_DISPATCH_STARTED",
            "WRITE_COMPLETED",
            "WRITE_FAILED_KNOWN",
            "WRITE_AMBIGUOUS",
            "OP_READBACK_CONFIRMED",
        }:
            continue
        operation_id = record.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise DeploymentHistoryError(f"{phase} не содержит operation_id")
        if phase == "WRITE_INTENT":
            if operation_id in intents:
                raise DeploymentHistoryError(f"{operation_id}: несколько WRITE_INTENT")
            intents[operation_id] = record
        elif phase == "WRITE_DISPATCH_STARTED":
            if operation_id in dispatches:
                raise DeploymentHistoryError(f"{operation_id}: несколько WRITE_DISPATCH_STARTED")
            dispatches[operation_id] = record
        elif phase in {"WRITE_COMPLETED", "WRITE_FAILED_KNOWN", "WRITE_AMBIGUOUS"}:
            results.setdefault(operation_id, []).append(record)
        elif phase == "OP_READBACK_CONFIRMED":
            if operation_id in confirmed:
                raise DeploymentHistoryError(f"{operation_id}: несколько OP_READBACK_CONFIRMED")
            confirmed[operation_id] = record

    for operation_id in dispatches:
        if operation_id not in intents:
            raise DeploymentHistoryError(f"{operation_id}: dispatch существует без WRITE_INTENT")
    for operation_id, operation_results in results.items():
        if operation_id not in dispatches:
            raise DeploymentHistoryError(f"{operation_id}: write result существует без dispatch")
        if len(operation_results) != 1:
            raise DeploymentHistoryError(f"{operation_id}: несколько взаимоисключающих write results")
    for operation_id in confirmed:
        operation_results = results.get(operation_id, [])
        if len(operation_results) != 1 or operation_results[0].get("phase") != "WRITE_COMPLETED":
            raise DeploymentHistoryError(f"{operation_id}: read-back подтверждён без единственного WRITE_COMPLETED")

    finals = [record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED"]
    commits = [record for record in records if record.get("phase") == "MACHINE_STATE_COMMITTED"]
    if commits and not finals:
        raise DeploymentHistoryError("MACHINE_STATE_COMMITTED существует без FINAL_READBACK_CONFIRMED")
    if finals:
        final = finals[0]
        final_status = final.get("status")
        if final_status not in {"APPLIED", "NOOP_CONFIRMED"}:
            raise DeploymentHistoryError("FINAL_READBACK_CONFIRMED содержит неизвестный status")
        if not isinstance(final.get("actual_confirmed_state"), dict):
            raise DeploymentHistoryError("FINAL_READBACK_CONFIRMED не содержит baseline-after")
        if final.get("fingerprint_after") != anchor.desired_fingerprint:
            raise DeploymentHistoryError("Final fingerprint не совпадает с desired fingerprint event")
        if final_status == "NOOP_CONFIRMED" and dispatches:
            raise DeploymentHistoryError("NOOP_CONFIRMED несовместим с начатым Stepik write")
        if final_status == "APPLIED" and not dispatches:
            raise DeploymentHistoryError("APPLIED не подтверждён ни одним write dispatch")
        if set(dispatches) != set(confirmed):
            raise DeploymentHistoryError("Final read-back существует при незавершённой per-operation evidence")

    if commits:
        committed = commits[0]
        final = finals[0]
        if committed.get("status") != final.get("status"):
            raise DeploymentHistoryError("Committed status не совпадает с final read-back")
        if committed.get("baseline_after") != final.get("actual_confirmed_state"):
            raise DeploymentHistoryError("Committed baseline-after не совпадает с final read-back")

    return anchor


def identity_from_records(records: list[dict[str, Any]], *, expected_event_id: str | None = None) -> EventIdentity:
    return validate_event_records(records, expected_event_id=expected_event_id)


def _anchor_identity_from_blob(store: GitHubHistoryStore, *, event_id: str, blob_sha: str) -> EventIdentity:
    cache = getattr(store, "_history_anchor_identity_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(store, "_history_anchor_identity_cache", cache)
    cached = cache.get(blob_sha)
    if isinstance(cached, EventIdentity):
        if cached.event_id != event_id:
            raise DeploymentHistoryError("History anchor cache конфликтует с event directory")
        return cached

    response = store._request("GET", f"/repos/{store.repository}/git/blobs/{blob_sha}")
    if response.status_code != 200:
        raise DeploymentHistoryError(f"Не удалось прочитать history anchor blob: HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict) or data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
        raise DeploymentHistoryError("History anchor blob имеет неожиданный формат")
    try:
        raw = base64.b64decode(data["content"]).decode("utf-8")
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeploymentHistoryError("History anchor blob повреждён") from exc
    if not isinstance(record, dict):
        raise DeploymentHistoryError("History anchor должен быть JSON object")
    if record.get("history_schema_version") != HISTORY_SCHEMA_VERSION:
        raise DeploymentHistoryError("History anchor имеет неподдерживаемую schema version")
    if not isinstance(record.get("record_id"), str) or not isinstance(record.get("phase"), str):
        raise DeploymentHistoryError("History anchor не содержит record_id/phase")
    identity = _parse_identity(record.get("identity"))
    calculated_event_id = stable_event_id(
        course_id=identity.course_id,
        object_id=identity.object_id,
        kind=identity.kind,
        source_sha=identity.source_sha,
        desired_fingerprint=identity.desired_fingerprint,
        baseline_fingerprint=identity.baseline_fingerprint_before,
        pending_first_sha=identity.pending_first_sha,
    )
    if identity.event_id != event_id or calculated_event_id != event_id:
        raise DeploymentHistoryError("History anchor identity не соответствует event directory")
    cache[blob_sha] = identity
    return identity


def _github_event_ids_for_object(store: GitHubHistoryStore, *, object_id: str) -> list[str]:
    """Индексирует history по одному immutable anchor blob на event, а не перечитывает все records.

    Recursive tree перечитывается на каждый lookup, поэтому events, созданные текущим write-run,
    появляются сразу. Содержимое уже известных anchors кэшируется по immutable blob SHA.
    Полный event загружается ниже только если anchor относится к нужному object_id.
    """
    store.ensure_branch()
    response = store._request(
        "GET",
        f"/repos/{store.repository}/git/trees/{store.branch}",
        params={"recursive": "1"},
    )
    if response.status_code != 200:
        raise DeploymentHistoryError(f"Не удалось построить history object index: HTTP {response.status_code}")
    data = response.json()
    tree = data.get("tree") if isinstance(data, dict) else None
    if not isinstance(tree, list):
        raise DeploymentHistoryError("History recursive tree имеет неожиданный формат")
    if data.get("truncated") is True:
        raise DeploymentHistoryError("History recursive tree truncated; object index недоказуем")

    prefix = f"{HISTORY_PREFIX}/"
    by_event: dict[str, list[dict[str, Any]]] = {}
    for item in tree:
        if not isinstance(item, dict) or item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        if not path.startswith(prefix) or not path.endswith(".json"):
            continue
        relative = path[len(prefix):]
        if "/" not in relative:
            continue
        event_id, filename = relative.split("/", 1)
        if "/" in filename or not event_id.startswith("evt-"):
            continue
        if not isinstance(item.get("sha"), str) or not item.get("sha"):
            raise DeploymentHistoryError("History tree blob не содержит SHA")
        by_event.setdefault(event_id, []).append(item)

    event_ids: list[str] = []
    for event_id, items in sorted(by_event.items()):
        started = [item for item in items if str(item.get("path", "")).rsplit("/", 1)[-1].startswith("event-started-")]
        anchor_item = min(started or items, key=lambda item: str(item.get("path", "")))
        identity = _anchor_identity_from_blob(
            store,
            event_id=event_id,
            blob_sha=str(anchor_item["sha"]),
        )
        if identity.object_id == object_id:
            event_ids.append(event_id)
    return event_ids


def find_object_events(store: Any, *, object_id: str) -> list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]]:
    """Find deployment/reconcile events for one object without a mutable active-event index."""
    event_ids: list[str] = []
    github_indexed = False
    if isinstance(store, MemoryHistoryStore):
        event_ids = sorted(store.records)
    elif isinstance(store, GitHubHistoryStore):
        github_indexed = True
        event_ids = _github_event_ids_for_object(store, object_id=object_id)
    else:
        raise DeploymentHistoryError("Неизвестный history store")

    found: list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]] = []
    for event_id in event_ids:
        records = store.load(event_id)
        if not records:
            continue
        identity = identity_from_records(records, expected_event_id=event_id)
        if identity.object_id != object_id:
            if github_indexed:
                raise DeploymentHistoryError("History object index не совпадает с полным event identity")
            continue
        found.append((identity, records, summarize_event(records)))
    return found


def find_incomplete_object_events(store: Any, *, object_id: str) -> list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]]:
    """Return only started deployment events, not reconcile-only observations."""
    result = []
    for item in find_object_events(store, object_id=object_id):
        _identity, records, summary = item
        if not any(record.get("phase") == "EVENT_STARTED" for record in records):
            continue
        if not summary.get("machine_state_committed"):
            result.append(item)
    return result


def latest_committed_history_evidence(
    object_events: list[tuple[EventIdentity, list[dict[str, Any]], dict[str, Any]]],
    *,
    live_fingerprint: str,
) -> dict[str, Any]:
    """Resolve only the latest provable committed deployment state for stale-baseline evidence.

    Older committed events that happen to match current live content are not sufficient proof that
    the current Issue baseline is stale. Equal latest timestamps with different fingerprints are
    intentionally ambiguous because second-level timestamps cannot prove ordering.
    """
    candidates: list[tuple[str, str, str]] = []
    for identity, records, summary in object_events:
        committed_baseline = summary.get("committed_baseline_after")
        if not summary.get("machine_state_committed") or not isinstance(committed_baseline, dict):
            continue
        committed_records = [record for record in records if record.get("phase") == "MACHINE_STATE_COMMITTED"]
        if len(committed_records) != 1:
            continue
        committed_at = committed_records[0].get("confirmed_at")
        fingerprint = committed_baseline.get("applied_fingerprint")
        if isinstance(committed_at, str) and isinstance(fingerprint, str):
            candidates.append((committed_at, identity.event_id, fingerprint))

    if not candidates:
        return {
            "has_evidence": False,
            "live_match": False,
            "ambiguous": False,
            "committed_at": None,
            "event_ids": [],
            "fingerprints": [],
        }

    latest_time = max(value[0] for value in candidates)
    latest = [value for value in candidates if value[0] == latest_time]
    event_ids = sorted(value[1] for value in latest)
    fingerprints = sorted({value[2] for value in latest})
    ambiguous = len(fingerprints) != 1
    return {
        "has_evidence": True,
        "live_match": False if ambiguous else fingerprints[0] == live_fingerprint,
        "ambiguous": ambiguous,
        "committed_at": latest_time,
        "event_ids": event_ids,
        "fingerprints": fingerprints,
    }


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
    identity = identity_from_records(records, expected_event_id=event_id)
    summary = summarize_event(records)
    if not summary.get("final_readback_confirmed"):
        raise DeploymentHistoryError("Нельзя отметить machine state committed без FINAL_READBACK_CONFIRMED")
    final = final_confirmed_record(records)
    if final is None:
        raise DeploymentHistoryError("FINAL_READBACK_CONFIRMED не найден")
    expected_status = final.get("status")
    expected_baseline = final.get("actual_confirmed_state")
    if status != expected_status:
        raise DeploymentHistoryError(
            f"MACHINE_STATE_COMMITTED status={status!r} не совпадает с final read-back status={expected_status!r}"
        )
    if not isinstance(expected_baseline, dict) or baseline_after != expected_baseline:
        raise DeploymentHistoryError("Machine state baseline после PATCH не совпадает с подтверждённым final read-back")
    if summary.get("machine_state_committed"):
        committed = summary.get("committed_baseline_after")
        if committed != expected_baseline:
            raise DeploymentHistoryError("Существующий MACHINE_STATE_COMMITTED конфликтует с final read-back")
        return
    recorder = DeploymentRecorder(store, identity)
    recorder.state_committed(baseline_after=baseline_after, status=status)
