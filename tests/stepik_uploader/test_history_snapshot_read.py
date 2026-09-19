from __future__ import annotations

import base64
import json
import unittest

from scripts.stepik_uploader.deployment_history import DeploymentHistoryError, GitHubHistoryStore


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


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
