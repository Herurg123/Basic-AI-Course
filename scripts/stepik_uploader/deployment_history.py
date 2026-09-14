from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

HISTORY_SCHEMA_VERSION = 1
HISTORY_BRANCH = "stepik-deployment-history-v1"
HISTORY_PREFIX = ".stepik-deployment-history/events"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FP_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DeploymentHistoryError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _safe_token(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "unknown"


def _workflow_context() -> dict[str, str | None]:
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None
    return {
        "run_id": run_id,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "run_url": run_url,
    }


def _attempt_token() -> str:
    workflow = _workflow_context()
    run_id = workflow.get("run_id") or "local"
    attempt = workflow.get("run_attempt") or "1"
    return _safe_token(f"run-{run_id}-attempt-{attempt}")


def stable_event_id(
    *,
    course_id: int,
    object_id: str,
    kind: str,
    source_sha: str,
    desired_fingerprint: str,
    baseline_fingerprint: str | None,
    pending_first_sha: str | None,
) -> str:
    if not SHA_RE.fullmatch(source_sha):
        raise DeploymentHistoryError("source_sha должен быть полным Git SHA")
    if not FP_RE.fullmatch(desired_fingerprint):
        raise DeploymentHistoryError("desired_fingerprint имеет неверный формат")
    if baseline_fingerprint is not None and not FP_RE.fullmatch(baseline_fingerprint):
        raise DeploymentHistoryError("baseline_fingerprint имеет неверный формат")
    if pending_first_sha is not None and not SHA_RE.fullmatch(pending_first_sha):
        raise DeploymentHistoryError("pending_first_sha должен быть полным Git SHA")
    payload = "|".join(
        [
            str(int(course_id)),
            kind,
            object_id,
            source_sha,
            desired_fingerprint,
            baseline_fingerprint or "none",
            pending_first_sha or "none",
        ]
    )
    return "evt-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def stable_record_id(event_id: str, phase: str, operation_id: str | None = None) -> str:
    suffix = f"-{operation_id}" if operation_id else ""
    raw = f"{event_id}|{phase}|{operation_id or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    safe_phase = _safe_token(phase)
    return f"{safe_phase}{suffix}-{digest}"


@dataclass(frozen=True)
class EventIdentity:
    event_id: str
    course_id: int
    object_id: str
    kind: str
    source_sha: str
    workflow_run_id: str | None
    workflow_run_attempt: str | None
    workflow_run_url: str | None
    desired_fingerprint: str
    baseline_fingerprint_before: str | None
    pending_first_sha: str | None
    retry_of_event_id: str | None = None
    continuation_of_event_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "course_id": self.course_id,
            "object_id": self.object_id,
            "kind": self.kind,
            "source_sha": self.source_sha,
            "workflow": {
                "run_id": self.workflow_run_id,
                "run_attempt": self.workflow_run_attempt,
                "run_url": self.workflow_run_url,
            },
            "desired_fingerprint": self.desired_fingerprint,
            "baseline_fingerprint_before": self.baseline_fingerprint_before,
            "pending_first_sha": self.pending_first_sha,
            "retry_of_event_id": self.retry_of_event_id,
            "continuation_of_event_id": self.continuation_of_event_id,
        }


def event_identity_from_environment(
    *,
    course_id: int,
    object_id: str,
    kind: str,
    source_sha: str,
    desired_fingerprint: str,
    baseline_fingerprint: str | None,
    pending_first_sha: str | None,
) -> EventIdentity:
    event_id = stable_event_id(
        course_id=course_id,
        object_id=object_id,
        kind=kind,
        source_sha=source_sha,
        desired_fingerprint=desired_fingerprint,
        baseline_fingerprint=baseline_fingerprint,
        pending_first_sha=pending_first_sha,
    )
    workflow = _workflow_context()
    return EventIdentity(
        event_id=event_id,
        course_id=int(course_id),
        object_id=object_id,
        kind=kind,
        source_sha=source_sha,
        workflow_run_id=workflow["run_id"],
        workflow_run_attempt=workflow["run_attempt"],
        workflow_run_url=workflow["run_url"],
        desired_fingerprint=desired_fingerprint,
        baseline_fingerprint_before=baseline_fingerprint,
        pending_first_sha=pending_first_sha,
    )


class MemoryHistoryStore:
    """Offline/idempotency test store with the same append-only contract as GitHub."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, dict[str, Any]]] = {}

    def append(self, event_id: str, record_id: str, payload: dict[str, Any]) -> None:
        event = self.records.setdefault(event_id, {})
        normalized = deepcopy(payload)
        if record_id in event:
            if event[record_id] != normalized:
                raise DeploymentHistoryError(f"history conflict: {event_id}/{record_id} уже существует с другим payload")
            return
        event[record_id] = normalized

    def load(self, event_id: str) -> list[dict[str, Any]]:
        return [deepcopy(self.records[event_id][key]) for key in sorted(self.records.get(event_id, {}))]


class GitHubHistoryStore:
    """Append-only operational history in a dedicated derived Git branch."""

    def __init__(
        self,
        *,
        repository: str,
        token: str,
        source_sha: str,
        branch: str = HISTORY_BRANCH,
        api_url: str = "https://api.github.com",
        session: requests.Session | None = None,
    ) -> None:
        if not repository or "/" not in repository:
            raise DeploymentHistoryError("GITHUB_REPOSITORY должен иметь вид owner/repo")
        if not token:
            raise DeploymentHistoryError("Для durable deployment history нужен GITHUB_TOKEN")
        if not SHA_RE.fullmatch(source_sha):
            raise DeploymentHistoryError("source_sha должен быть полным Git SHA")
        self.repository = repository
        self.token = token
        self.source_sha = source_sha
        self.branch = branch
        self.api_url = api_url.rstrip("/")
        self.session = session or requests.Session()
        self._branch_ready = False

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        try:
            return self.session.request(
                method,
                f"{self.api_url}{path}",
                headers=self.headers,
                timeout=30,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise DeploymentHistoryError(f"GitHub history API недоступен: {exc.__class__.__name__}") from exc

    def ensure_branch(self) -> None:
        if self._branch_ready:
            return
        ref_path = f"/repos/{self.repository}/git/ref/heads/{self.branch}"
        response = self._request("GET", ref_path)
        if response.status_code == 200:
            self._branch_ready = True
            return
        if response.status_code != 404:
            raise DeploymentHistoryError(f"Не удалось проверить history branch: HTTP {response.status_code}")
        created = self._request(
            "POST",
            f"/repos/{self.repository}/git/refs",
            json={"ref": f"refs/heads/{self.branch}", "sha": self.source_sha},
        )
        if created.status_code not in {201, 422}:
            raise DeploymentHistoryError(f"Не удалось создать history branch: HTTP {created.status_code}")
        verify = self._request("GET", ref_path)
        if verify.status_code != 200:
            raise DeploymentHistoryError("History branch не подтверждён после create/race")
        self._branch_ready = True

    def _path(self, event_id: str, record_id: str) -> str:
        if not re.fullmatch(r"evt-[0-9a-f]{32}", event_id):
            raise DeploymentHistoryError("Некорректный event_id")
        if not re.fullmatch(r"[a-z0-9-]{8,180}", record_id):
            raise DeploymentHistoryError("Некорректный record_id")
        return f"{HISTORY_PREFIX}/{event_id}/{record_id}.json"

    def _read_existing(self, path: str) -> tuple[str, str] | None:
        response = self._request(
            "GET",
            f"/repos/{self.repository}/contents/{path}",
            params={"ref": self.branch},
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise DeploymentHistoryError(f"Не удалось прочитать history record: HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("content"), str) or not isinstance(data.get("sha"), str):
            raise DeploymentHistoryError("GitHub history record имеет неожиданный формат")
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise DeploymentHistoryError("GitHub history record повреждён") from exc
        return content, data["sha"]

    def append(self, event_id: str, record_id: str, payload: dict[str, Any]) -> None:
        self.ensure_branch()
        path = self._path(event_id, record_id)
        content = _canonical_json(payload)
        existing = self._read_existing(path)
        if existing is not None:
            if existing[0] != content:
                raise DeploymentHistoryError(f"history conflict: {event_id}/{record_id} нельзя переписать")
            return
        response = self._request(
            "PUT",
            f"/repos/{self.repository}/contents/{path}",
            json={
                "message": f"Stepik history {event_id}: {record_id}",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            },
        )
        if response.status_code in {200, 201}:
            return
        if response.status_code in {409, 422}:
            raced = self._read_existing(path)
            if raced is not None and raced[0] == content:
                return
        raise DeploymentHistoryError(f"Не удалось append history record: HTTP {response.status_code}")

    def load(self, event_id: str) -> list[dict[str, Any]]:
        self.ensure_branch()
        response = self._request(
            "GET",
            f"/repos/{self.repository}/contents/{HISTORY_PREFIX}/{event_id}",
            params={"ref": self.branch},
        )
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            raise DeploymentHistoryError(f"Не удалось прочитать event history: HTTP {response.status_code}")
        listing = response.json()
        if not isinstance(listing, list):
            raise DeploymentHistoryError("Event history directory имеет неожиданный формат")
        records: list[dict[str, Any]] = []
        for item in sorted(listing, key=lambda value: str(value.get("name", ""))):
            if not isinstance(item, dict) or not str(item.get("name", "")).endswith(".json"):
                continue
            raw = self._read_existing(str(item.get("path")))
            if raw is None:
                raise DeploymentHistoryError("History listing изменился во время чтения")
            try:
                payload = json.loads(raw[0])
            except json.JSONDecodeError as exc:
                raise DeploymentHistoryError("History record содержит некорректный JSON") from exc
            if not isinstance(payload, dict):
                raise DeploymentHistoryError("History record должен быть JSON object")
            records.append(payload)
        return records


class DeploymentRecorder:
    def __init__(self, store: Any, identity: EventIdentity) -> None:
        self.store = store
        self.identity = identity
        self._records_cache: list[dict[str, Any]] | None = None

    def records(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._records_cache is None or refresh:
            self._records_cache = self.store.load(self.identity.event_id)
        return deepcopy(self._records_cache)

    def _append(self, phase: str, payload: dict[str, Any], *, operation_id: str | None = None) -> dict[str, Any]:
        record_id = stable_record_id(self.identity.event_id, phase, operation_id)
        current_workflow = _workflow_context()
        relationship = None
        if current_workflow.get("run_id") and current_workflow.get("run_id") != self.identity.workflow_run_id:
            relationship = {
                "type": "RETRY_OR_CONTINUATION_OF_EVENT",
                "event_id": self.identity.event_id,
                "origin_run_id": self.identity.workflow_run_id,
            }
        record = {
            "history_schema_version": HISTORY_SCHEMA_VERSION,
            "record_id": record_id,
            "phase": phase,
            "identity": self.identity.as_dict(),
            "recorded_by_workflow": current_workflow,
            "event_relationship": relationship,
            **payload,
        }
        self.store.append(self.identity.event_id, record_id, record)
        self._records_cache = None
        return record

    def ensure_started(
        self,
        *,
        operation_type: str,
        state_before: dict[str, Any] | None,
        expected_state: dict[str, Any] | None,
        stepik_object_ids: dict[str, Any],
        fingerprint_before: str,
        started_at: str | None = None,
    ) -> dict[str, Any]:
        existing = [record for record in self.records() if record.get("phase") == "EVENT_STARTED"]
        if existing:
            first = existing[0]
            expected_core = {
                "operation_type": operation_type,
                "state_before": state_before,
                "expected_state": expected_state,
                "stepik_object_ids": stepik_object_ids,
                "fingerprint_before": fingerprint_before,
            }
            for key, value in expected_core.items():
                if first.get(key) != value:
                    raise DeploymentHistoryError(f"Существующий event {self.identity.event_id} конфликтует по {key}")
            return first
        return self._append(
            "EVENT_STARTED",
            {
                "started_at": started_at or utc_now(),
                "operation_type": operation_type,
                "state_before": state_before,
                "expected_state": expected_state,
                "stepik_object_ids": stepik_object_ids,
                "fingerprint_before": fingerprint_before,
                "desired_fingerprint": self.identity.desired_fingerprint,
                "external_write_started": False,
            },
        )

    def write_intent(
        self,
        *,
        operation_id: str,
        method: str,
        target: str,
        fingerprint_before: str,
        expected_fingerprint_after: str,
    ) -> dict[str, Any]:
        semantic = {
            "operation_id": operation_id,
            "method": method,
            "target": target,
            "fingerprint_before": fingerprint_before,
            "expected_fingerprint_after": expected_fingerprint_after,
            "external_write_started": False,
        }
        existing = [
            record
            for record in self.records()
            if record.get("phase") == "WRITE_INTENT" and record.get("operation_id") == operation_id
        ]
        if existing:
            if len(existing) != 1:
                raise DeploymentHistoryError(f"{operation_id}: найдено несколько WRITE_INTENT records")
            first = existing[0]
            for key, value in semantic.items():
                if first.get(key) != value:
                    raise DeploymentHistoryError(f"{operation_id}: существующий WRITE_INTENT конфликтует по {key}")
            return first
        return self._append(
            "WRITE_INTENT",
            {"recorded_at": utc_now(), **semantic},
            operation_id=operation_id,
        )

    def write_dispatch_started(self, *, operation_id: str) -> dict[str, Any]:
        return self._append(
            "WRITE_DISPATCH_STARTED",
            {
                "recorded_at": utc_now(),
                "operation_id": operation_id,
                "external_write_started": True,
            },
            operation_id=operation_id,
        )

    def write_result(self, *, operation_id: str, status: str, reason_code: str | None = None) -> dict[str, Any]:
        if status not in {"COMPLETED", "FAILED_KNOWN", "AMBIGUOUS"}:
            raise DeploymentHistoryError(f"Некорректный write result status: {status}")
        return self._append(
            f"WRITE_{status}",
            {
                "recorded_at": utc_now(),
                "operation_id": operation_id,
                "write_status": status,
                "reason_code": reason_code,
            },
            operation_id=operation_id,
        )

    def operation_readback(self, *, operation_id: str, expected_fingerprint_after: str) -> dict[str, Any]:
        return self._append(
            "OP_READBACK_CONFIRMED",
            {
                "confirmed_at": utc_now(),
                "operation_id": operation_id,
                "fingerprint_after": expected_fingerprint_after,
                "read_back_result": "CONFIRMED",
            },
            operation_id=operation_id,
        )

    def readback_failed(self, *, operation_id: str | None, reason_code: str) -> dict[str, Any]:
        suffix = operation_id or _attempt_token()
        return self._append(
            "READBACK_FAILED",
            {"recorded_at": utc_now(), "operation_id": operation_id, "read_back_result": "UNAVAILABLE", "reason_code": reason_code},
            operation_id=suffix,
        )

    def final_readback(
        self,
        *,
        fingerprint_after: str,
        stepik_object_ids: dict[str, Any],
        status: str,
        baseline_after: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if status not in {"APPLIED", "NOOP_CONFIRMED"}:
            raise DeploymentHistoryError("final read-back поддерживает только APPLIED/NOOP_CONFIRMED")
        return self._append(
            "FINAL_READBACK_CONFIRMED",
            {
                "confirmed_at": utc_now(),
                "fingerprint_after": fingerprint_after,
                "actual_confirmed_state": baseline_after,
                "stepik_object_ids": stepik_object_ids,
                "read_back_result": "CONFIRMED",
                "status": status,
            },
        )

    def failure(self, *, reason_code: str, before_any_write: bool) -> dict[str, Any]:
        return self._append(
            "FAILED_BEFORE_WRITE" if before_any_write else "FAILED_AFTER_WRITE_STARTED",
            {
                "recorded_at": utc_now(),
                "reason_code": reason_code,
                "external_write_started": not before_any_write,
                "status": "FAILED",
            },
            operation_id=_attempt_token(),
        )

    def recovery_classified(self, *, classification: str, reason_codes: Iterable[str]) -> dict[str, Any]:
        token = f"{_safe_token(classification)}-{_attempt_token()}"
        return self._append(
            "RECOVERY_CLASSIFIED",
            {
                "recorded_at": utc_now(),
                "recovery_status": classification,
                "reason_codes": sorted(set(str(value) for value in reason_codes)),
            },
            operation_id=token,
        )

    def reconcile_classified(
        self,
        *,
        classification: str,
        action: str,
        reason_codes: Iterable[str],
        live_fingerprint: str,
        baseline_fingerprint: str | None,
        current_main_sha: str,
        owner_approval_required: bool,
    ) -> dict[str, Any]:
        token = f"{_safe_token(classification)}-{_attempt_token()}"
        return self._append(
            "RECONCILE_CLASSIFIED",
            {
                "recorded_at": utc_now(),
                "reconcile_status": classification,
                "action": action,
                "reason_codes": sorted(set(str(value) for value in reason_codes)),
                "live_fingerprint": live_fingerprint,
                "baseline_fingerprint": baseline_fingerprint,
                "current_main_sha": current_main_sha,
                "owner_approval_required": owner_approval_required,
            },
            operation_id=token,
        )

    def state_committed(self, *, baseline_after: dict[str, Any] | None, status: str, committed_at: str | None = None) -> dict[str, Any]:
        if status not in {"APPLIED", "NOOP_CONFIRMED"}:
            raise DeploymentHistoryError(f"Некорректный committed status: {status}")
        if not isinstance(baseline_after, dict):
            raise DeploymentHistoryError("MACHINE_STATE_COMMITTED требует baseline_after")
        return self._append(
            "MACHINE_STATE_COMMITTED",
            {
                "confirmed_at": committed_at or utc_now(),
                "status": status,
                "baseline_after": baseline_after,
                "reconcile_status": "COMMITTED",
            },
        )


def summarize_event(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered = list(records)
    phases = [str(record.get("phase")) for record in ordered]
    intents = [record for record in ordered if record.get("phase") == "WRITE_INTENT"]
    dispatches = [record for record in ordered if record.get("phase") == "WRITE_DISPATCH_STARTED"]
    ambiguous = [record for record in ordered if record.get("phase") == "WRITE_AMBIGUOUS"]
    readback_failed = [record for record in ordered if record.get("phase") == "READBACK_FAILED"]
    final = next((record for record in ordered if record.get("phase") == "FINAL_READBACK_CONFIRMED"), None)
    committed = next((record for record in ordered if record.get("phase") == "MACHINE_STATE_COMMITTED"), None)
    confirmed_ops = sorted(
        (record for record in ordered if record.get("phase") == "OP_READBACK_CONFIRMED"),
        key=lambda record: str(record.get("operation_id") or ""),
    )
    last_confirmed = confirmed_ops[-1] if confirmed_ops else None
    return {
        "phases": phases,
        "external_write_started": bool(dispatches),
        "write_intents": len(intents),
        "writes_started": len(dispatches),
        "ambiguous": bool(ambiguous),
        "readback_failed": bool(readback_failed),
        "final_readback_confirmed": final is not None,
        "final_fingerprint": None if final is None else final.get("fingerprint_after"),
        "final_status": None if final is None else final.get("status"),
        "machine_state_committed": committed is not None,
        "committed_baseline_after": None if committed is None else committed.get("baseline_after"),
        "last_confirmed_operation_fingerprint": None if last_confirmed is None else last_confirmed.get("fingerprint_after"),
        "confirmed_operation_count": len(confirmed_ops),
    }
