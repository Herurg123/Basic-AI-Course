from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, EventIdentity, MemoryHistoryStore, stable_event_id
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.history_runtime import validate_event_records
from scripts.stepik_uploader.initial_upload_writer import execute_initial_upload_one

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


def complete_snapshot() -> dict:
    return {
        "course": {"id": 299189, "is_public": False},
        "sections": [
            {
                "position": 5,
                "units": [
                    {
                        "position": 1,
                        "lesson": {
                            "id": 204,
                            "title": TITLE,
                            "is_public": False,
                            "language": "ru",
                            "steps": [
                                {
                                    "id": index,
                                    "step_source": {
                                        "id": index,
                                        "lesson": 204,
                                        "position": index,
                                        "block": copy.deepcopy(step.block()),
                                    },
                                }
                                for index, step in enumerate(EXPECTED, start=1)
                            ],
                        },
                    }
                ],
            }
        ],
    }


class ReadOnlyCompleteClient:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self.update_calls = 0
        self.create_calls = 0

    def inspect_course(self, course_id: int) -> dict:
        self.assert_course(course_id)
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def assert_course(course_id: int) -> None:
        if course_id != 299189:
            raise AssertionError(course_id)

    def update_step_source(self, **_kwargs):
        self.update_calls += 1
        raise AssertionError("recovery must not PUT")

    def create_step_source(self, **_kwargs):
        self.create_calls += 1
        raise AssertionError("recovery must not POST")


def proven_recorder(snapshot: dict) -> DeploymentRecorder:
    desired = compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED)
    identity = EventIdentity(
        event_id=stable_event_id(
            course_id=299189,
            object_id="M04-L01",
            kind="lesson",
            source_sha=SOURCE_SHA,
            desired_fingerprint=desired,
            baseline_fingerprint=None,
            pending_first_sha=None,
        ),
        course_id=299189,
        object_id="M04-L01",
        kind="lesson",
        source_sha=SOURCE_SHA,
        workflow_run_id="test-origin",
        workflow_run_attempt="1",
        workflow_run_url=None,
        desired_fingerprint=desired,
        baseline_fingerprint_before=None,
        pending_first_sha=None,
    )
    recorder = DeploymentRecorder(MemoryHistoryStore(), identity)
    live = snapshot["sections"][0]["units"][0]["lesson"]
    recorder.ensure_started(
        operation_type="lesson-initial-upload",
        state_before=None,
        expected_state={"desired_fingerprint": desired, "source_sha": SOURCE_SHA},
        stepik_object_ids={"lesson_id": 204},
        fingerprint_before=live_lesson_fingerprint(live),
        started_at="2026-09-15T11:00:00Z",
    )
    for index, operation_id in enumerate(("step-0001-1", "step-create-0002"), start=1):
        recorder.write_intent(
            operation_id=operation_id,
            method="PUT" if index == 1 else "POST",
            target="step-sources/1" if index == 1 else "step-sources",
            fingerprint_before="sha256:" + "a" * 64,
            expected_fingerprint_after=desired,
        )
        recorder.write_dispatch_started(operation_id=operation_id)
        recorder.write_result(operation_id=operation_id, status="COMPLETED")
        recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=desired)
    return recorder


class FirstUploadRuntimeRecoveryGateTests(unittest.TestCase):
    def test_runtime_resume_flag_can_finish_proven_complete_event_without_new_write(self) -> None:
        snapshot = complete_snapshot()
        client = ReadOnlyCompleteClient(snapshot)
        recorder = proven_recorder(snapshot)
        result = execute_initial_upload_one(
            client,
            snapshot,
            canonical_id="M04-L01",
            expected_steps=EXPECTED,
            module_position=5,
            lesson_position=1,
            expected_title=TITLE,
            source_sha=SOURCE_SHA,
            recorder=recorder,
            # first_upload_runtime derives this same flag from the latest confirmed fingerprint.
            allow_partial_resume=True,
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)
        self.assertEqual(result.operations, [{"action": "RESUME_PROVEN_COMPLETE", "steps": 2}])
        records = recorder.records(refresh=True)
        validate_event_records(records, expected_event_id=recorder.identity.event_id)
        final = next(item for item in records if item.get("phase") == "FINAL_READBACK_CONFIRMED")
        self.assertEqual(final["status"], "APPLIED")


if __name__ == "__main__":
    unittest.main()
