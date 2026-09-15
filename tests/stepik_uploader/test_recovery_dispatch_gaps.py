from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
    summarize_event,
)
from scripts.stepik_uploader.reconcile import classify_reconcile

SHA = "1" * 40
OLD = "sha256:" + "a" * 64
PARTIAL = "sha256:" + "b" * 64
DESIRED = "sha256:" + "c" * 64


def identity() -> EventIdentity:
    event_id = stable_event_id(
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        desired_fingerprint=DESIRED,
        baseline_fingerprint=OLD,
        pending_first_sha=SHA,
    )
    return EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        workflow_run_id="100",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/100",
        desired_fingerprint=DESIRED,
        baseline_fingerprint_before=OLD,
        pending_first_sha=SHA,
    )


def recorder_with_confirmed_first_step() -> DeploymentRecorder:
    store = MemoryHistoryStore()
    recorder = DeploymentRecorder(store, identity())
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before={"applied_fingerprint": OLD},
        expected_state={"desired_fingerprint": DESIRED},
        stepik_object_ids={"lesson_id": 10, "step_ids": [101, 102]},
        fingerprint_before=OLD,
        started_at="2026-09-14T20:00:00Z",
    )
    recorder.write_intent(
        operation_id="step-0001-101",
        method="PUT",
        target="step-sources/101",
        fingerprint_before=OLD,
        expected_fingerprint_after=PARTIAL,
    )
    recorder.write_dispatch_started(operation_id="step-0001-101")
    recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
    recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after=PARTIAL)
    return recorder


def decision_for(recorder: DeploymentRecorder):
    return classify_reconcile(
        source_sha=SHA,
        current_main_sha=SHA,
        live_fingerprint=PARTIAL,
        desired_fingerprint=DESIRED,
        baseline_fingerprint=OLD,
        event_summary=summarize_event(recorder.records(refresh=True)),
        event_source_sha=SHA,
        event_baseline_fingerprint_before=OLD,
        event_baseline_known=True,
    )


class RecoveryDispatchGapTests(unittest.TestCase):
    def test_crash_after_second_dispatch_before_result_never_auto_continues(self) -> None:
        recorder = recorder_with_confirmed_first_step()
        recorder.write_intent(
            operation_id="step-0002-102",
            method="PUT",
            target="step-sources/102",
            fingerprint_before=PARTIAL,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0002-102")

        decision = decision_for(recorder)
        self.assertEqual(decision.classification, "WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX")
        self.assertFalse(decision.auto_allowed)
        self.assertTrue(decision.owner_approval_required)
        self.assertIn("unconfirmed-dispatch-remains", decision.reason_codes)

    def test_completed_second_write_without_readback_never_auto_continues(self) -> None:
        recorder = recorder_with_confirmed_first_step()
        recorder.write_intent(
            operation_id="step-0002-102",
            method="PUT",
            target="step-sources/102",
            fingerprint_before=PARTIAL,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0002-102")
        recorder.write_result(operation_id="step-0002-102", status="COMPLETED")

        decision = decision_for(recorder)
        self.assertEqual(decision.classification, "WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX")
        self.assertFalse(decision.auto_allowed)
        self.assertTrue(decision.owner_approval_required)

    def test_known_failure_after_confirmed_prefix_requires_owner_retry_route(self) -> None:
        recorder = recorder_with_confirmed_first_step()
        recorder.write_intent(
            operation_id="step-0002-102",
            method="PUT",
            target="step-sources/102",
            fingerprint_before=PARTIAL,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0002-102")
        recorder.write_result(operation_id="step-0002-102", status="FAILED_KNOWN", reason_code="http-400")

        decision = decision_for(recorder)
        self.assertEqual(decision.classification, "KNOWN_WRITE_FAILURE_OWNER_RETRY_REQUIRED")
        self.assertFalse(decision.auto_allowed)
        self.assertTrue(decision.owner_approval_required)

    def test_fully_confirmed_prefix_still_allows_continuation(self) -> None:
        recorder = recorder_with_confirmed_first_step()
        decision = decision_for(recorder)
        self.assertEqual(decision.classification, "CONFIRMED_PARTIAL_AUTOMATION_STATE")
        self.assertEqual(decision.action, "AUTO_CONTINUE_FROM_CONFIRMED_PREFIX")
        self.assertTrue(decision.auto_allowed)


if __name__ == "__main__":
    unittest.main()
