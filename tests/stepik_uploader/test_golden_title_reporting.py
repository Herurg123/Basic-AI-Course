from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import DeploymentRecorder, MemoryHistoryStore
from scripts.stepik_uploader.golden_title_migration import _event_identity, _history_counters
from scripts.stepik_uploader.title_hygiene import TitleOperation, execute_title_only_operation


SHA = "2" * 40


class FakeLessonClient:
    def __init__(self, *, lesson_id: int, title: str) -> None:
        self.lesson_id = lesson_id
        self.title = title

    def fetch_one(self, resource: str, object_id: int):
        if resource != "lessons" or object_id != self.lesson_id:
            raise AssertionError((resource, object_id))
        return {"id": object_id, "title": self.title}

    def _request_write(self, method: str, path: str, payload: dict):
        if method != "PUT" or path != f"/api/lessons/{self.lesson_id}":
            raise AssertionError((method, path))
        self.title = payload["lesson"]["title"]
        return {"lessons": [{"id": self.lesson_id, "title": self.title}]}


class GoldenTitleReportingTests(unittest.TestCase):
    def test_history_counters_expose_completed_dispatch_after_partial_run(self) -> None:
        operation = TitleOperation(
            kind="lesson",
            canonical_id="M00-L01",
            stepik_id=2591708,
            position=1,
            live_title="M00-L01 — Начните безопасный рабочий диалог",
            expected_title="Начните безопасный рабочий диалог",
        )
        store = MemoryHistoryStore()
        identity = _event_identity(operation, sha=SHA)
        execute_title_only_operation(
            FakeLessonClient(lesson_id=operation.stepik_id, title=operation.live_title),
            operation,
            DeploymentRecorder(store, identity),
        )

        counters = _history_counters(store, [operation], sha=SHA)
        self.assertEqual(counters["write_dispatches_started"], 1)
        self.assertEqual(counters["write_readbacks_confirmed"], 1)


if __name__ == "__main__":
    unittest.main()
