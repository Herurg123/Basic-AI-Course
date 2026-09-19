from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import (
    HISTORY_SCHEMA_VERSION,
    DeploymentHistoryError,
    EventIdentity,
    GitHubHistoryStore,
    stable_event_id,
    stable_record_id,
)
from scripts.stepik_uploader.history_runtime import _anchor_identity_from_blob


class _Response:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _Session:
    def __init__(self, payload: dict | None = None, *, forbid_network: bool = False) -> None:
        self.payload = payload or {}
        self.forbid_network = forbid_network
        self.calls = 0

    def request(self, method: str, url: str, **kwargs):
        self.calls += 1
        if self.forbid_network:
            raise AssertionError("network request was not expected")
        return _Response(200, self.payload)


def _identity() -> EventIdentity:
    source_sha = "a" * 40
    desired = "sha256:" + "b" * 64
    baseline = "sha256:" + "c" * 64
    pending = "d" * 40
    event_id = stable_event_id(
        course_id=299189,
        object_id="M06-L01",
        kind="lesson",
        source_sha=source_sha,
        desired_fingerprint=desired,
        baseline_fingerprint=baseline,
        pending_first_sha=pending,
    )
    return EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M06-L01",
        kind="lesson",
        source_sha=source_sha,
        workflow_run_id="1",
        workflow_run_attempt="1",
        workflow_run_url="https://github.test/run/1",
        desired_fingerprint=desired,
        baseline_fingerprint_before=baseline,
        pending_first_sha=pending,
    )


def _blob_payload(identity: EventIdentity) -> dict:
    record = {
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "record_id": stable_record_id(identity.event_id, "EVENT_STARTED"),
        "phase": "EVENT_STARTED",
        "identity": identity.as_dict(),
    }
    raw = json.dumps(record, ensure_ascii=False).encode("utf-8")
    return {
        "encoding": "base64",
        "content": base64.b64encode(raw).decode("ascii"),
    }


class PersistentHistoryAnchorCacheTests(unittest.TestCase):
    def test_validated_immutable_anchor_is_reused_across_store_instances(self) -> None:
        identity = _identity()
        blob_sha = "e" * 40
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "anchors.json"
            with patch.dict(os.environ, {"STEPIK_HISTORY_ANCHOR_CACHE": str(cache_path)}, clear=False):
                first_session = _Session(_blob_payload(identity))
                first = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha=identity.source_sha,
                    session=first_session,
                )
                loaded = _anchor_identity_from_blob(
                    first,
                    event_id=identity.event_id,
                    blob_sha=blob_sha,
                )
                self.assertEqual(loaded, identity)
                self.assertEqual(first_session.calls, 1)
                self.assertTrue(cache_path.exists())

                second_session = _Session(forbid_network=True)
                second = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha=identity.source_sha,
                    session=second_session,
                )
                cached = _anchor_identity_from_blob(
                    second,
                    event_id=identity.event_id,
                    blob_sha=blob_sha,
                )
                self.assertEqual(cached, identity)
                self.assertEqual(second_session.calls, 0)

    def test_malformed_persistent_cache_fails_closed(self) -> None:
        identity = _identity()
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "anchors.json"
            cache_path.write_text("{not-json", encoding="utf-8")
            with patch.dict(os.environ, {"STEPIK_HISTORY_ANCHOR_CACHE": str(cache_path)}, clear=False):
                store = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha=identity.source_sha,
                    session=_Session(forbid_network=True),
                )
                with self.assertRaises(DeploymentHistoryError):
                    _anchor_identity_from_blob(
                        store,
                        event_id=identity.event_id,
                        blob_sha="e" * 40,
                    )


if __name__ == "__main__":
    unittest.main()
