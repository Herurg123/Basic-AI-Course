from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.api import StepikAPIError
from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
    summarize_event,
)
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint
from scripts.stepik_uploader.writer import ContentWriteError, execute_content_sync_one

SHA = "1" * 40
TITLE = "M02-L01 — Test"
OLD_STEP = CompiledStep(1, "text", "<p>old</p>", {}, ("lesson.md",))
NEW_STEP = CompiledStep(1, "text", "<p>new</p>", {}, ("lesson.md",))


def snapshot(step: CompiledStep) -> dict:
    return {
        "course": {"id": 299189, "is_public": False},
        "sections": [
            {
                "id": 11,
                "position": 3,
                "units": [
                    {
                        "id": 12,
                        "position": 1,
                        "lesson": {
                            "id": 201,
                            "title": TITLE,
                            "is_public": False,
                            "language": "ru",
                            "steps": [
                                {
                                    "id": 101,
                                    "step_source": {
                                        "id": 101,
                                        "lesson": 201,
                                        "position": 1,
                                        "block": copy.deepcopy(step.block()),
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def baseline() -> dict:
    return {
        "canonical_id": "M02-L01",
        "stepik_lesson_id": 201,
        "applied_source_sha": "0" * 40,
        "applied_at": "2026-09-15T03:00:00Z",
        "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=[OLD_STEP]),
        "step_ids": [101],
        "source_git_paths": ["lesson.md"],
    }


def recorder() -> tuple[MemoryHistoryStore, DeploymentRecorder]:
    store = MemoryHistoryStore()
    desired = compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=[NEW_STEP])
    before = baseline()["applied_fingerprint"]
    event_id = stable_event_id(
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        desired_fingerprint=desired,
        baseline_fingerprint=before,
        pending_first_sha=SHA,
    )
    identity = EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        workflow_run_id="10",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/10",
        desired_fingerprint=desired,
        baseline_fingerprint_before=before,
        pending_first_sha=SHA,
    )
    rec = DeploymentRecorder(store, identity)
    rec.ensure_started(
        operation_type="lesson-content-sync",
        state_before=baseline(),
        expected_state={"desired_fingerprint": desired},
        stepik_object_ids={"lesson_id": 201, "step_ids": [101]},
        fingerprint_before=before,
        started_at="2026-09-15T03:01:00Z",
    )
    return store, rec


class RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.current = snapshot(OLD_STEP)

    def update_step_source(self, **kwargs):
        raise self.exc


class WriterExceptionClassificationTests(unittest.TestCase):
    def _run(self, exc: Exception):
        store, rec = recorder()
        client = RaisingClient(exc)
        with self.assertRaises(type(exc)):
            execute_content_sync_one(
                client,
                client.current,
                canonical_id="M02-L01",
                expected_steps=[NEW_STEP],
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
                baseline=baseline(),
                source_sha=SHA,
                recorder=rec,
            )
        return summarize_event(store.load(rec.identity.event_id))

    def test_proven_stepik_api_failure_is_known_failure(self) -> None:
        summary = self._run(StepikAPIError("HTTP 400"))
        self.assertEqual(summary["known_failed_writes"], 1)
        self.assertFalse(summary["ambiguous"])

    def test_unclassified_exception_after_dispatch_is_ambiguous(self) -> None:
        summary = self._run(ContentWriteError("unexpected client failure"))
        self.assertEqual(summary["known_failed_writes"], 0)
        self.assertTrue(summary["ambiguous"])


if __name__ == "__main__":
    unittest.main()
