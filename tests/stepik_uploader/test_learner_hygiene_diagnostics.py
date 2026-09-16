from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
)
from scripts.stepik_uploader.fingerprints import live_lesson_fingerprint, live_lesson_payload
from scripts.stepik_uploader.learner_hygiene_writer import _record_readback_diagnostic


class LearnerHygieneReadbackDiagnosticTests(unittest.TestCase):
    def test_diagnostic_persists_actual_semantic_lesson_state(self) -> None:
        lesson = {
            "id": 2591717,
            "title": "Сформулируйте задачу и критерии результата",
            "language": "ru",
            "is_public": False,
            "steps": [
                {
                    "id": 11297091,
                    "step_source": {
                        "id": 11297091,
                        "position": 1,
                        "block": {
                            "name": "text",
                            "text": "<p>Stepik normalized body</p>",
                            "source": {},
                        },
                    },
                }
            ],
        }
        identity = event_identity_from_environment(
            course_id=299189,
            object_id="M02-L01",
            kind="lesson",
            source_sha="a" * 40,
            desired_fingerprint="sha256:" + "1" * 64,
            baseline_fingerprint="sha256:" + "2" * 64,
            pending_first_sha=None,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)

        _record_readback_diagnostic(
            recorder,
            operation_id="step-0001-11297091",
            expected_fingerprint="sha256:" + "3" * 64,
            actual_lesson=lesson,
            reason_code="test-readback-mismatch",
        )

        records = store.load(identity.event_id)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["phase"], "READBACK_DIAGNOSTIC")
        self.assertEqual(record["actual_fingerprint"], live_lesson_fingerprint(lesson))
        self.assertEqual(record["actual_lesson_payload"], live_lesson_payload(lesson))
        self.assertNotIn("id", record["actual_lesson_payload"])
        self.assertEqual(record["reason_code"], "test-readback-mismatch")


if __name__ == "__main__":
    unittest.main()
