from __future__ import annotations

import base64
import json
import unittest

from scripts.stepik_uploader.deployment_history import (
    HISTORY_SCHEMA_VERSION,
    DeploymentHistoryError,
    EventIdentity,
    GitHubHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import find_object_events


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class IndexedFakeStore(GitHubHistoryStore):
    def __init__(self, *, tree: list[dict], anchors: dict[str, dict], records: dict[str, list[dict]]) -> None:
        super().__init__(
            repository="owner/repo",
            token="token",
            source_sha="a" * 40,
        )
        self._branch_ready = True
        self.tree = tree
        self.anchors = anchors
        self.records_map = records
        self.tree_calls = 0
        self.blob_calls: list[str] = []
        self.load_calls: list[str] = []
        self.truncated = False

    def _request(self, method: str, path: str, **kwargs):
        if method == "GET" and "/git/trees/" in path:
            self.tree_calls += 1
            return FakeResponse(200, {"tree": list(self.tree), "truncated": self.truncated})
        if method == "GET" and "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            self.blob_calls.append(sha)
            payload = self.anchors[sha]
            encoded = base64.b64encode(
                (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            ).decode("ascii")
            return FakeResponse(200, {"encoding": "base64", "content": encoded})
        raise AssertionError((method, path, kwargs))

    def load(self, event_id: str) -> list[dict]:
        self.load_calls.append(event_id)
        return [dict(item) for item in self.records_map.get(event_id, [])]


def identity_for(*, object_id: str, digit: str) -> EventIdentity:
    source_sha = digit * 40
    desired = "sha256:" + digit * 64
    event_id = stable_event_id(
        course_id=299189,
        object_id=object_id,
        kind="title-metadata",
        source_sha=source_sha,
        desired_fingerprint=desired,
        baseline_fingerprint=None,
        pending_first_sha=None,
    )
    return EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id=object_id,
        kind="title-metadata",
        source_sha=source_sha,
        workflow_run_id="1",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/1",
        desired_fingerprint=desired,
        baseline_fingerprint_before=None,
        pending_first_sha=None,
    )


def started_record(identity: EventIdentity, suffix: str) -> dict:
    return {
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "record_id": f"event-started-{suffix}",
        "phase": "EVENT_STARTED",
        "identity": identity.as_dict(),
    }


class HistoryObjectIndexTests(unittest.TestCase):
    def _store(self) -> tuple[IndexedFakeStore, EventIdentity, EventIdentity]:
        first = identity_for(object_id="title:section:M00", digit="a")
        second = identity_for(object_id="title:lesson:M01-L01", digit="b")
        first_anchor = started_record(first, "111111111111")
        second_anchor = started_record(second, "222222222222")
        tree = [
            {
                "path": f".stepik-deployment-history/events/{first.event_id}/event-started-111111111111.json",
                "type": "blob",
                "sha": "blob-first",
            },
            {
                "path": f".stepik-deployment-history/events/{first.event_id}/write-intent-title-put-aaaaaaaaaaaa.json",
                "type": "blob",
                "sha": "blob-first-other",
            },
            {
                "path": f".stepik-deployment-history/events/{second.event_id}/event-started-222222222222.json",
                "type": "blob",
                "sha": "blob-second",
            },
        ]
        store = IndexedFakeStore(
            tree=tree,
            anchors={"blob-first": first_anchor, "blob-second": second_anchor},
            records={first.event_id: [first_anchor], second.event_id: [second_anchor]},
        )
        return store, first, second

    def test_object_lookup_reads_one_anchor_per_event_and_caches_blob_identity(self) -> None:
        store, first, second = self._store()

        result_first = find_object_events(store, object_id=first.object_id)
        self.assertEqual([item[0].event_id for item in result_first], [first.event_id])
        self.assertEqual(store.tree_calls, 1)
        self.assertCountEqual(store.blob_calls, ["blob-first", "blob-second"])
        self.assertEqual(store.load_calls, [first.event_id])

        result_second = find_object_events(store, object_id=second.object_id)
        self.assertEqual([item[0].event_id for item in result_second], [second.event_id])
        self.assertEqual(store.tree_calls, 2)
        self.assertCountEqual(store.blob_calls, ["blob-first", "blob-second"])
        self.assertEqual(store.load_calls, [first.event_id, second.event_id])

    def test_new_event_is_discovered_without_refetching_old_anchor_blobs(self) -> None:
        store, first, second = self._store()
        find_object_events(store, object_id=first.object_id)

        third = identity_for(object_id="title:lesson:M07-L02", digit="c")
        third_anchor = started_record(third, "333333333333")
        store.tree.append(
            {
                "path": f".stepik-deployment-history/events/{third.event_id}/event-started-333333333333.json",
                "type": "blob",
                "sha": "blob-third",
            }
        )
        store.anchors["blob-third"] = third_anchor
        store.records_map[third.event_id] = [third_anchor]

        result = find_object_events(store, object_id=third.object_id)
        self.assertEqual([item[0].event_id for item in result], [third.event_id])
        self.assertEqual(store.tree_calls, 2)
        self.assertCountEqual(store.blob_calls, ["blob-first", "blob-second", "blob-third"])
        self.assertEqual(store.load_calls, [first.event_id, third.event_id])

    def test_truncated_recursive_tree_fails_closed(self) -> None:
        store, first, _second = self._store()
        store.truncated = True
        with self.assertRaises(DeploymentHistoryError):
            find_object_events(store, object_id=first.object_id)
        self.assertEqual(store.load_calls, [])


if __name__ == "__main__":
    unittest.main()
