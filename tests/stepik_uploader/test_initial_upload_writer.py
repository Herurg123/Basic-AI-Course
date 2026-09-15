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

    def make_complete(self) -> None:
        self._steps()[0]["step_source"]["block"] = copy.deepcopy(EXPECTED[0].block())
        self._steps().append(
            {
                "id": 2,
                "step_source": {
                    "id": 2,
                    "lesson": 204,
                    "position": 2,
                    "block": copy.deepcopy(EXPECTED[1].block()),
                },
            }
        )
        self.next_id = 3

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


def add_confirmed_first_step(recorder: DeploymentRecorder, live_fingerprint: str) -> None:
    operation_id = "step-0001-1"
    recorder.write_intent(
        operation_id=operation_id,
        method="PUT",
        target="step-sources/1",
        fingerprint_before="sha256:" + "a" * 64,
        expected_fingerprint_after=live_fingerprint,
    )
    recorder.write_dispatch_started(operation_id=operation_id)
    recorder.write_result(operation_id=operation_id, status="COMPLETED")
    recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=live_fingerprint)


def add_fully_confirmed_write_evidence(recorder: DeploymentRecorder) -> None:
    desired = compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED)
    for operation_id in ("step-0001-1", "step-create-0002"):
        recorder.write_intent(
            operation_id=operation_id,
            method="PUT" if operation_id == "step-0001-1" else "POST",
            target="step-sources/1" if operation_id == "step-0001-1" else "step-sources",
            fingerprint_before="sha256:" + "a" * 64,
            expected_fingerprint_after=desired,
        )
        recorder.write_dispatch_started(operation_id=operation_id)
        recorder.write_result(operation_id=operation_id, status="COMPLETED")
        recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=desired)


class InitialUploadWriterTests(unittest.TestCase):
    def test_skeleton_upload_has_wal_readbacks_and_final_baseline(self) -> None:
        client = FakeClient()
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
        final = next(item for item in records if item.get("phase") == "FINAL_READBACK_CONFIRMED")
        self.assertEqual(final["status"], "APPLIED")

    def test_unproven_partial_prefix_is_blocked_without_write(self) -> None:
        client = FakeClient()
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = EXPECTED[0].block()
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
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = EXPECTED[0].block()
        _store, recorder = recorder_for(client.inspect_course(299189))
        partial_fp = live_lesson_fingerprint(lesson)
        add_confirmed_first_step(recorder, partial_fp)
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

    def test_dispatch_gap_blocks_partial_resume_without_new_write(self) -> None:
        client = FakeClient()
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = EXPECTED[0].block()
        _store, recorder = recorder_for(client.inspect_course(299189))
        add_confirmed_first_step(recorder, live_lesson_fingerprint(lesson))
        recorder.write_intent(
            operation_id="step-create-0002",
            method="POST",
            target="step-sources",
            fingerprint_before=live_lesson_fingerprint(lesson),
            expected_fingerprint_after=compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        )
        recorder.write_dispatch_started(operation_id="step-create-0002")
        with self.assertRaisesRegex(ContentWriteError, "blind retry/continuation запрещён"):
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
                allow_partial_resume=True,
            )
        self.assertEqual(client.create_calls, 0)

    def test_known_failed_dispatch_blocks_partial_resume_without_new_write(self) -> None:
        client = FakeClient()
        lesson = client.snapshot["sections"][0]["units"][0]["lesson"]
        lesson["steps"][0]["step_source"]["block"] = EXPECTED[0].block()
        _store, recorder = recorder_for(client.inspect_course(299189))
        add_confirmed_first_step(recorder, live_lesson_fingerprint(lesson))
        recorder.write_intent(
            operation_id="step-create-0002",
            method="POST",
            target="step-sources",
            fingerprint_before=live_lesson_fingerprint(lesson),
            expected_fingerprint_after=compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        )
        recorder.write_dispatch_started(operation_id="step-create-0002")
        recorder.write_result(operation_id="step-create-0002", status="FAILED_KNOWN", reason_code="test-known-failure")
        with self.assertRaisesRegex(ContentWriteError, "blind retry/continuation запрещён"):
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
                allow_partial_resume=True,
            )
        self.assertEqual(client.create_calls, 0)

    def test_complete_matching_live_without_proven_history_is_blocked(self) -> None:
        client = FakeClient()
        client.make_complete()
        _store, recorder = recorder_for(client.inspect_course(299189))
        with self.assertRaisesRegex(ContentWriteError, "automatic adoption запрещён"):
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
        self.assertFalse(any(item.get("phase") == "FINAL_READBACK_CONFIRMED" for item in recorder.records(refresh=True)))

    def test_proven_complete_recovery_adds_final_applied_without_new_write(self) -> None:
        client = FakeClient()
        _store, recorder = recorder_for(client.inspect_course(299189))
        add_fully_confirmed_write_evidence(recorder)
        client.make_complete()
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
            allow_complete_recovery=True,
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)
        self.assertEqual(result.operations, [{"action": "RESUME_PROVEN_COMPLETE", "steps": 2}])
        records = recorder.records(refresh=True)
        validate_event_records(records, expected_event_id=recorder.identity.event_id)
        final = next(item for item in records if item.get("phase") == "FINAL_READBACK_CONFIRMED")
        self.assertEqual(final["status"], "APPLIED")

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
