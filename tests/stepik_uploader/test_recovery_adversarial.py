from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import (
    DeploymentHistoryError,
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
    summarize_event,
)
from scripts.stepik_uploader.reconcile import classify_reconcile

SHA = "1" * 40
OLD = "sha256:" + "a" * 64
DESIRED = "sha256:" + "b" * 64
MANUAL = "sha256:" + "c" * 64


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


def start(recorder: DeploymentRecorder) -> None:
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before={"applied_fingerprint": OLD},
        expected_state={"desired_fingerprint": DESIRED},
        stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
        fingerprint_before=OLD,
        started_at="2026-09-14T20:00:00Z",
    )


class RecoveryAdversarialTests(unittest.TestCase):
    def test_intent_only_retry_reuses_semantic_record_across_workflow_runs(self) -> None:
        store = MemoryHistoryStore()
        first = DeploymentRecorder(store, identity())
        start(first)
        original = first.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        count_before = len(store.load(identity().event_id))

        with patch.dict(
            "os.environ",
            {
                "GITHUB_RUN_ID": "200",
                "GITHUB_RUN_ATTEMPT": "2",
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_REPOSITORY": "Herurg123/Basic-AI-Course",
            },
            clear=False,
        ):
            retry = DeploymentRecorder(store, identity())
            repeated = retry.write_intent(
                operation_id="step-0001-101",
                method="PUT",
                target="step-sources/101",
                fingerprint_before=OLD,
                expected_fingerprint_after=DESIRED,
            )

        self.assertEqual(repeated, original)
        self.assertEqual(len(store.load(identity().event_id)), count_before)
        self.assertFalse(summarize_event(store.load(identity().event_id))["external_write_started"])

    def test_intent_retry_with_different_semantics_is_blocked(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        start(recorder)
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        with self.assertRaises(DeploymentHistoryError):
            recorder.write_intent(
                operation_id="step-0001-101",
                method="PUT",
                target="step-sources/999",
                fingerprint_before=OLD,
                expected_fingerprint_after=DESIRED,
            )

    def test_known_write_failure_is_retry_safe_only_when_live_still_matches_baseline(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        start(recorder)
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0001-101")
        recorder.write_result(
            operation_id="step-0001-101",
            status="FAILED_KNOWN",
            reason_code="http-400",
        )
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["all_dispatched_writes_failed_known"])

        safe = classify_reconcile(
            source_sha=SHA,
            current_main_sha=SHA,
            live_fingerprint=OLD,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA,
        )
        self.assertEqual(safe.classification, "KNOWN_WRITE_FAILURE_RETRY_SAFE")
        self.assertEqual(safe.action, "NORMAL_SYNC_ROUTE")
        self.assertTrue(safe.auto_allowed)

        drifted = classify_reconcile(
            source_sha=SHA,
            current_main_sha=SHA,
            live_fingerprint=MANUAL,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA,
        )
        self.assertEqual(drifted.classification, "KNOWN_WRITE_FAILURE_WITH_LIVE_DIVERGENCE")
        self.assertFalse(drifted.auto_allowed)
        self.assertTrue(drifted.owner_approval_required)


if __name__ == "__main__":
    unittest.main()
