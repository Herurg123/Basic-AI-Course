from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.history_runtime import validate_event_records
from scripts.stepik_uploader.initial_upload_writer import execute_initial_upload_one
from scripts.stepik_uploader.writer import ContentWriteError

TITLE = "M04-L01 — Получите ответ по безопасному исходнику"
SOURCE_SHA = "1" * 40
EXPECTED = [
    CompiledStep(1, "text", "<p>Первый</p>", {}, ("04_course/M04/M04-L01/lesson.md",)),
    CompiledStep(
        2,
        "free-answer",
        "<p>Проверка</p>",
        {"is_attachments_enabled": False, "is_html_enabled": True, "manual_scoring": False},
        ("04_course/M04/M04-L01/lesson.md",),
    ),
]


def skeleton() -> dict:
    return {
        "course": {"id": 299189, "is_public": False},
        "sections": [
            {
                "id": 14,
                "position": 5,
                "units": [
                    {
                        "id": 104,
                        "position": 1,
                        "lesson": {
                            "id": 204,
                            "title": TITLE,
                            "is_public": False,
                            "language": "ru",
                            "steps": [
                                {
                                    "id": 1,
                                    "step_source": {
                                        "id": 1,
                                        "lesson": 204,
                                        "position": 1,
                                        "block": {
                                            "name": "text",
                                            "text": "Урок сгенерирован роботом ;)",
                                            "source": {},
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


class FakeClient:
    def __init__(self) -> None:
        self.snapshot = skeleton()
        self.update_calls = 0
        self.create_calls = 0
        self.next_id = 2

    def _steps(self) -> list[dict]:
        return self.snapshot["sections"][0]["units"][0]["lesson"]["steps"]

    def update_step_source(self, *, step_id: int, lesson_id: int, position: int, block: dict) -> dict:
        self.update_calls += 1
        item = next(value for value in self._steps() if value["id"] == step_id)
        item["step_source"] = {
            "id": step_id,
            "lesson": lesson_id,
            "position": position,
            "block": copy.deepcopy(block),
        }
        return {"step-sources": [copy.deepcopy(item["step_source"])]}

    def create_step_source(self, *, lesson_id: int, position: int, block: dict) -> dict:
        self.create_calls += 1
        step_id = self.next_id
        self.next_id += 1
        source = {
            "id": step_id,
            "lesson": lesson_id,
            "position": position,
            "block": copy.deepcopy(block),
        }
        self._steps().append({"id": step_id, "step_source": source})
        return {"step-sources": [copy.deepcopy(source)]}

    def fetch_one(self, resource: str, object_id: int) -> dict:
        if resource != "step-sources":
            raise AssertionError(resource)
        return copy.deepcopy(next(value["step_source"] for value in self._steps() if value["id"] == object_id))

    def inspect_course(self, course_id: int) -> dict:
        if course_id != 299189:
            raise AssertionError(course_id)
        return copy.deepcopy(self.snapshot)


def recorder_for(snapshot: dict) -> tuple[MemoryHistoryStore, DeploymentRecorder]:
    desired = compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED)
    event_id = stable_event_id(
        course_id=299189,
        object_id="M04-L01",
        kind="lesson",
        source_sha=SOURCE_SHA,
        desired_fingerprint=desired,
        baseline_fingerprint=None,
        pending_first_sha=None,
    )
    identity = EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M04-L01",
        kind="lesson",
        source_sha=SOURCE_SHA,
        workflow_run_id="test",
        workflow_run_attempt="1",
        workflow_run_url=None,
        desired_fingerprint=desired,
        baseline_fingerprint_before=None,
        pending_first_sha=None,
    )
    store = MemoryHistoryStore()
    recorder = DeploymentRecorder(store, identity)
    live = snapshot["sections"][0]["units"][0]["lesson"]
    recorder.ensure_started(
        operation_type="lesson-initial-upload",
        state_before=None,
        expected_state={"desired_fingerprint": desired, "source_sha": SOURCE_SHA},
        stepik_object_ids={"lesson_id": 204},
        fingerprint_before=live_lesson_fingerprint(live),
        started_at="2026-09-15T11:00:00Z",
    )
    return store, recorder


class InitialUploadWriterTests(unittest.TestCase):
    def test_skeleton_upload_has_wal_readbacks_and_final_baseline(self) -> None:
        client = FakeClient()
        store, recorder = recorder_for(client.inspect_course(299189))
        result = execute_initial_upload_one(
            client,
            client.inspect_course(299189),
            canonical_id="M04-L01",
            expected_steps=EXPECTED,
            module_position=5,
            lesson_position=1,
            expected_title=TITLE,
            source_sha=SOURCE_SHA,
            recorder=recorder,
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, 1)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual([op["action"] for op in result.operations], ["UPDATE_PLACEHOLDER", "CREATE_STEP"])
        self.assertEqual(result.state_record["canonical_id"], "M04-L01")
        records = recorder.records(refresh=True)
        validate_event_records(records, expected_event_id=recorder.identity.event_id)
        self.assertEqual(sum(item.get("phase") == "WRITE_INTENT" for item in records), 2)
        self.assertEqual(sum(item.get("phase") == "OP_READBACK_CONFIRMED" for item in records), 2)
        self.assertTrue(any(item.get("phase") == "FINAL_READBACK_CONFIRMED" for item in records))

    def test_unproven_partial_prefix_is_blocked_without_write(self) -> None:
        client = FakeClient()
        first = EXPECTED[0]
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = first.block()
        _store, recorder = recorder_for(client.inspect_course(299189))
        with self.assertRaisesRegex(ContentWriteError, "partial matching prefix"):
            execute_initial_upload_one(
                client,
                client.inspect_course(299189),
                canonical_id="M04-L01",
                expected_steps=EXPECTED,
                module_position=5,
                lesson_position=1,
                expected_title=TITLE,
                source_sha=SOURCE_SHA,
                recorder=recorder,
                allow_partial_resume=False,
            )
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)

    def test_proven_partial_prefix_can_resume_only_remaining_step(self) -> None:
        client = FakeClient()
        first = EXPECTED[0]
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = first.block()
        _store, recorder = recorder_for(client.inspect_course(299189))
        result = execute_initial_upload_one(
            client,
            client.inspect_course(299189),
            canonical_id="M04-L01",
            expected_steps=EXPECTED,
            module_position=5,
            lesson_position=1,
            expected_title=TITLE,
            source_sha=SOURCE_SHA,
            recorder=recorder,
            allow_partial_resume=True,
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(result.operations[0]["action"], "RESUME_PROVEN_PARTIAL")
        self.assertEqual(result.operations[1]["action"], "CREATE_STEP")

    def test_unexpected_existing_content_fails_before_any_write(self) -> None:
        client = FakeClient()
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"]["text"] = "<p>ручной контент</p>"
        _store, recorder = recorder_for(client.inspect_course(299189))
        with self.assertRaises(ContentWriteError):
            execute_initial_upload_one(
                client,
                client.inspect_course(299189),
                canonical_id="M04-L01",
                expected_steps=EXPECTED,
                module_position=5,
                lesson_position=1,
                expected_title=TITLE,
                source_sha=SOURCE_SHA,
                recorder=recorder,
            )
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)


if __name__ == "__main__":
    unittest.main()
