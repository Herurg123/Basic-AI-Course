from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import DeploymentHistoryError, GitHubHistoryStore


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: object,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class SequenceSession:
    def __init__(self, responses: list[FakeResponse], *, forbid_network: bool = False) -> None:
        self.responses = list(responses)
        self.forbid_network = forbid_network
        self.calls = 0

    def request(self, method: str, url: str, **kwargs):
        self.calls += 1
        if self.forbid_network:
            raise AssertionError("network request was not expected")
        if not self.responses:
            raise AssertionError("unexpected extra network request")
        return self.responses.pop(0)


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def blob_response(raw: bytes) -> FakeResponse:
    return FakeResponse(
        200,
        {
            "encoding": "base64",
            "content": base64.b64encode(raw).decode("ascii"),
        },
    )


class SnapshotHistoryStore(GitHubHistoryStore):
    def __init__(self, *, listing: list[dict], blobs: dict[str, dict]) -> None:
        super().__init__(
            repository="owner/repo",
            token="token",
            source_sha="a" * 40,
        )
        self._branch_ready = True
        self.listing = listing
        self.blobs = blobs
        self.branch_path_reads = 0
        self.blob_reads: list[str] = []

    def _request(self, method: str, path: str, **kwargs):
        if method == "GET" and "/contents/.stepik-deployment-history/events/" in path:
            suffix = path.split("/contents/", 1)[1]
            if suffix.count("/") == 2:
                return FakeResponse(200, list(self.listing))
            self.branch_path_reads += 1
            return FakeResponse(404, {})

        if method == "GET" and "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            self.blob_reads.append(sha)
            payload = self.blobs[sha]
            raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            return FakeResponse(
                200,
                {
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode("ascii"),
                },
            )

        raise AssertionError((method, path, kwargs))


class DeploymentHistorySnapshotReadTests(unittest.TestCase):
    def test_git_blob_sha_matches_known_git_object_vector(self) -> None:
        self.assertEqual(
            GitHubHistoryStore._git_blob_sha(b"test\n"),
            "9daeafb9864cf43055ae93beb0afd6c7d144bfa4",
        )

    def test_load_reads_exact_blobs_from_listing_not_moving_branch_paths(self) -> None:
        event_id = "evt-" + "1" * 32
        records = [
            {
                "history_schema_version": 1,
                "record_id": "event-started-111111111111",
                "phase": "EVENT_STARTED",
            },
            {
                "history_schema_version": 1,
                "record_id": "write-intent-step-222222222222",
                "phase": "WRITE_INTENT",
            },
        ]
        listing = [
            {
                "name": "event-started-111111111111.json",
                "path": f".stepik-deployment-history/events/{event_id}/event-started-111111111111.json",
                "sha": "blob-started",
            },
            {
                "name": "write-intent-step-222222222222.json",
                "path": f".stepik-deployment-history/events/{event_id}/write-intent-step-222222222222.json",
                "sha": "blob-intent",
            },
        ]
        store = SnapshotHistoryStore(
            listing=listing,
            blobs={"blob-started": records[0], "blob-intent": records[1]},
        )

        loaded = store.load(event_id)

        self.assertEqual(loaded, records)
        self.assertEqual(store.branch_path_reads, 0)
        self.assertEqual(store.blob_reads, ["blob-started", "blob-intent"])

    def test_persistent_blob_cache_is_reused_across_store_instances(self) -> None:
        raw = b'{"history_schema_version":1,"phase":"EVENT_STARTED"}\n'
        blob_sha = git_blob_sha(raw)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"STEPIK_HISTORY_BLOB_CACHE_DIR": tmp}, clear=False):
                first_session = SequenceSession([blob_response(raw)])
                first = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha="a" * 40,
                    session=first_session,
                    sleep=lambda _seconds: None,
                )
                self.assertEqual(first._read_blob(blob_sha), raw.decode("utf-8"))
                self.assertEqual(first_session.calls, 1)
                self.assertTrue((Path(tmp) / f"{blob_sha}.blob").exists())

                second_session = SequenceSession([], forbid_network=True)
                second = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha="a" * 40,
                    session=second_session,
                    sleep=lambda _seconds: None,
                )
                self.assertEqual(second._read_blob(blob_sha), raw.decode("utf-8"))
                self.assertEqual(second_session.calls, 0)

    def test_tampered_persistent_blob_cache_fails_closed(self) -> None:
        raw = b'{"history_schema_version":1}\n'
        blob_sha = git_blob_sha(raw)
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / f"{blob_sha}.blob"
            cache.write_bytes(b"tampered")
            with patch.dict(os.environ, {"STEPIK_HISTORY_BLOB_CACHE_DIR": tmp}, clear=False):
                store = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha="a" * 40,
                    session=SequenceSession([], forbid_network=True),
                    sleep=lambda _seconds: None,
                )
                with self.assertRaisesRegex(DeploymentHistoryError, "cache повреждён"):
                    store._read_blob(blob_sha)

    def test_explicit_rate_limit_is_retried_then_cached(self) -> None:
        raw = b'{"history_schema_version":1,"phase":"EVENT_STARTED"}\n'
        blob_sha = git_blob_sha(raw)
        delays: list[float] = []
        session = SequenceSession(
            [
                FakeResponse(
                    403,
                    {"message": "You have exceeded a secondary rate limit."},
                    headers={"X-RateLimit-Remaining": "4999"},
                ),
                blob_response(raw),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"STEPIK_HISTORY_BLOB_CACHE_DIR": tmp}, clear=False):
                store = GitHubHistoryStore(
                    repository="owner/repo",
                    token="token",
                    source_sha="a" * 40,
                    session=session,
                    sleep=delays.append,
                )
                self.assertEqual(store._read_blob(blob_sha), raw.decode("utf-8"))
        self.assertEqual(session.calls, 2)
        self.assertEqual(delays, [60.0])

    def test_permission_403_is_not_retried_and_reports_sanitized_details(self) -> None:
        raw = b'{"history_schema_version":1}\n'
        blob_sha = git_blob_sha(raw)
        delays: list[float] = []
        session = SequenceSession(
            [
                FakeResponse(
                    403,
                    {"message": "Resource not accessible by integration"},
                    headers={"X-RateLimit-Remaining": "4999"},
                )
            ]
        )
        store = GitHubHistoryStore(
            repository="owner/repo",
            token="token",
            source_sha="a" * 40,
            session=session,
            sleep=delays.append,
        )
        with self.assertRaisesRegex(
            DeploymentHistoryError,
            "Resource not accessible by integration",
        ):
            store._read_blob(blob_sha)
        self.assertEqual(session.calls, 1)
        self.assertEqual(delays, [])

    def test_missing_blob_sha_fails_closed(self) -> None:
        event_id = "evt-" + "2" * 32
        store = SnapshotHistoryStore(
            listing=[
                {
                    "name": "event-started-111111111111.json",
                    "path": f".stepik-deployment-history/events/{event_id}/event-started-111111111111.json",
                }
            ],
            blobs={},
        )

        with self.assertRaisesRegex(DeploymentHistoryError, "immutable blob SHA"):
            store.load(event_id)


if __name__ == "__main__":
    unittest.main()
