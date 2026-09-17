from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
)
from scripts.stepik_uploader.transport_equivalence import normalize_stepik_transport_html


EXPECTED = "sha256:" + "a" * 64


def _identity() -> EventIdentity:
    return EventIdentity(
        event_id="evt-" + "1" * 32,
        course_id=299189,
        object_id="M99-L01",
        kind="lesson",
        source_sha="1" * 40,
        workflow_run_id=None,
        workflow_run_attempt=None,
        workflow_run_url=None,
        desired_fingerprint=EXPECTED,
        baseline_fingerprint_before=None,
        pending_first_sha="1" * 40,
    )


class TransportHistoryCompatibilityTests(unittest.TestCase):
    def test_transport_normalization_is_idempotent_for_break_and_multiline_paragraph(self) -> None:
        raw = '<p>Первая строка\nВторая строка<br /></p><p>Третья\nЧетвёртая</p>'
        once = normalize_stepik_transport_html(raw)
        twice = normalize_stepik_transport_html(once)
        self.assertEqual(twice, once)
        self.assertIn("<br>", once)

    def test_old_operation_readback_record_without_observed_field_remains_idempotent(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, _identity())
        record = recorder.operation_readback(
            operation_id="step-create-0001",
            expected_fingerprint_after=EXPECTED,
        )
        stored = store.records[_identity().event_id][record["record_id"]]
        stored.pop("observed_live_fingerprint", None)
        recorder.operation_readback(
            operation_id="step-create-0001",
            expected_fingerprint_after=EXPECTED,
        )

    def test_old_final_readback_record_without_observed_field_remains_idempotent(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, _identity())
        baseline = {"applied_fingerprint": EXPECTED}
        record = recorder.final_readback(
            fingerprint_after=EXPECTED,
            stepik_object_ids={"lesson_id": 1, "step_ids": [2]},
            status="NOOP_CONFIRMED",
            baseline_after=baseline,
        )
        stored = store.records[_identity().event_id][record["record_id"]]
        stored.pop("observed_live_fingerprint", None)
        recorder.final_readback(
            fingerprint_after=EXPECTED,
            stepik_object_ids={"lesson_id": 1, "step_ids": [2]},
            status="NOOP_CONFIRMED",
            baseline_after=baseline,
        )


if __name__ == "__main__":
    unittest.main()
