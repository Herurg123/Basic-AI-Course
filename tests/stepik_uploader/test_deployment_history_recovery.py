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
from scripts.stepik_uploader.history_runtime import find_incomplete_object_events, mark_machine_state_committed
from scripts.stepik_uploader.reconcile import classify_reconcile

SHA1 = "1" * 40
SHA2 = "2" * 40
OLD = "sha256:" + "a" * 64
DESIRED = "sha256:" + "b" * 64
PARTIAL = "sha256:" + "c" * 64
MANUAL = "sha256:" + "d" * 64


def identity(*, source_sha: str = SHA1, desired: str = DESIRED, baseline: str | None = OLD) -> EventIdentity:
    event_id = stable_event_id(
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=source_sha,
        desired_fingerprint=desired,
        baseline_fingerprint=baseline,
        pending_first_sha=SHA1,
    )
    return EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=source_sha,
        workflow_run_id="100",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/100",
        desired_fingerprint=desired,
        baseline_fingerprint_before=baseline,
        pending_first_sha=SHA1,
    )


def started(recorder: DeploymentRecorder) -> None:
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before={"applied_fingerprint": OLD},
        expected_state={"desired_fingerprint": DESIRED},
        stepik_object_ids={"lesson_id": 10, "step_ids": [101, 102]},
        fingerprint_before=OLD,
        started_at="2026-09-14T20:00:00Z",
    )


def dispatch_one(recorder: DeploymentRecorder, *, expected_after: str = PARTIAL) -> None:
    recorder.write_intent(
        operation_id="step-0001-101",
        method="PUT",
        target="step-sources/101",
        fingerprint_before=OLD,
        expected_fingerprint_after=expected_after,
    )
    recorder.write_dispatch_started(operation_id="step-0001-101")


def confirm_one_write(recorder: DeploymentRecorder, *, expected_after: str = DESIRED) -> None:
    dispatch_one(recorder, expected_after=expected_after)
    recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
    recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after=expected_after)


class DeploymentHistoryRecoveryTests(unittest.TestCase):
    def test_event_id_is_stable_for_logical_retry(self) -> None:
        first = identity().event_id
        second = identity().event_id
        self.assertEqual(first, second)

    def test_retry_does_not_duplicate_started_event(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        started(recorder)
        records = recorder.records(refresh=True)
        self.assertEqual([r["phase"] for r in records].count("EVENT_STARTED"), 1)

    def test_history_conflict_cannot_rewrite_existing_record(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        with self.assertRaises(DeploymentHistoryError):
            recorder.ensure_started(
                operation_type="different-operation",
                state_before={"applied_fingerprint": OLD},
                expected_state={"desired_fingerprint": DESIRED},
                stepik_object_ids={"lesson_id": 10, "step_ids": [101, 102]},
                fingerprint_before=OLD,
                started_at="2026-09-14T20:00:00Z",
            )

    def test_failure_before_first_write_is_explicit(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        recorder.failure(reason_code="pre-write-guard", before_any_write=True)
        summary = summarize_event(recorder.records(refresh=True))
        self.assertFalse(summary["external_write_started"])
        self.assertIn("FAILED_BEFORE_WRITE", summary["phases"])

    def test_failed_before_write_event_is_terminal_not_incomplete(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        recorder.failure(reason_code="pre-write-guard", before_any_write=True)

        self.assertEqual(find_incomplete_object_events(store, object_id="M02-L01"), [])

    def test_started_event_without_terminal_outcome_remains_incomplete(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)

        incomplete = find_incomplete_object_events(store, object_id="M02-L01")

        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0][0].event_id, identity().event_id)

    def test_failed_after_write_started_remains_incomplete(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        dispatch_one(recorder)
        recorder.failure(reason_code="post-dispatch-guard", before_any_write=False)

        incomplete = find_incomplete_object_events(store, object_id="M02-L01")

        self.assertEqual(len(incomplete), 1)
        self.assertTrue(incomplete[0][2]["external_write_started"])

    def test_intent_without_dispatch_is_safe_to_retry(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=PARTIAL,
        )
        summary = summarize_event(recorder.records(refresh=True))
        self.assertEqual(summary["write_intents"], 1)
        self.assertEqual(summary["writes_started"], 0)
        self.assertFalse(summary["external_write_started"])
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=OLD,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.action, "NORMAL_SYNC_ROUTE")
        self.assertTrue(decision.auto_allowed)

    def test_ambiguous_api_result_forbids_blind_retry(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        dispatch_one(recorder)
        recorder.write_result(operation_id="step-0001-101", status="AMBIGUOUS", reason_code="timeout")
        summary = summarize_event(recorder.records(refresh=True))
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=OLD,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.classification, "AMBIGUOUS_WRITE_RESULT")
        self.assertFalse(decision.auto_allowed)
        self.assertTrue(decision.owner_approval_required)

    def test_failed_readback_is_not_confirmed(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        dispatch_one(recorder)
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.readback_failed(operation_id="step-0001-101", reason_code="network")
        summary = summarize_event(recorder.records(refresh=True))
        self.assertFalse(summary["final_readback_confirmed"])
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=PARTIAL,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.classification, "UNCONFIRMED_WRITE_READBACK_FAILED")
        self.assertFalse(decision.auto_allowed)

    def test_confirmed_partial_state_can_continue_only_when_live_matches(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        dispatch_one(recorder)
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after=PARTIAL)
        summary = summarize_event(recorder.records(refresh=True))
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=PARTIAL,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.action, "AUTO_CONTINUE_FROM_CONFIRMED_PREFIX")
        self.assertTrue(decision.auto_allowed)

    def test_manual_drift_after_confirmed_partial_requires_owner(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        dispatch_one(recorder)
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after=PARTIAL)
        summary = summarize_event(recorder.records(refresh=True))
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=MANUAL,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.classification, "PARTIAL_WRITE_WITH_SUBSEQUENT_DRIFT")
        self.assertTrue(decision.owner_approval_required)

    def test_verified_write_plus_state_patch_failure_recovers_without_write(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        confirm_one_write(recorder)
        baseline_after = {
            "canonical_id": "M02-L01",
            "stepik_lesson_id": 10,
            "applied_source_sha": SHA1,
            "applied_at": "2026-09-14T20:01:00Z",
            "applied_fingerprint": DESIRED,
            "step_ids": [101, 102],
            "source_git_paths": ["04_course/M02/M02-L01/lesson.md"],
        }
        recorder.final_readback(
            fingerprint_after=DESIRED,
            stepik_object_ids={"lesson_id": 10, "step_ids": [101, 102]},
            status="APPLIED",
            baseline_after=baseline_after,
        )
        summary = summarize_event(recorder.records(refresh=True))
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=DESIRED,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=summary,
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.action, "AUTO_RECOVER_MACHINE_STATE")
        self.assertTrue(decision.auto_allowed)

        mark_machine_state_committed(
            store,
            event_id=identity().event_id,
            status="APPLIED",
            baseline_after=baseline_after,
        )
        first_count = len(store.load(identity().event_id))
        mark_machine_state_committed(
            store,
            event_id=identity().event_id,
            status="APPLIED",
            baseline_after=baseline_after,
        )
        self.assertEqual(len(store.load(identity().event_id)), first_count)
        self.assertTrue(summarize_event(store.load(identity().event_id))["machine_state_committed"])

    def test_machine_state_commit_must_equal_final_readback(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        started(recorder)
        confirm_one_write(recorder)
        baseline_after = {"applied_fingerprint": DESIRED}
        recorder.final_readback(
            fingerprint_after=DESIRED,
            stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
            status="APPLIED",
            baseline_after=baseline_after,
        )
        with self.assertRaises(DeploymentHistoryError):
            mark_machine_state_committed(
                store,
                event_id=identity().event_id,
                status="APPLIED",
                baseline_after={"applied_fingerprint": MANUAL},
            )
        with self.assertRaises(DeploymentHistoryError):
            mark_machine_state_committed(
                store,
                event_id=identity().event_id,
                status="NOOP_CONFIRMED",
                baseline_after=baseline_after,
            )

    def test_noop_confirmed_is_a_real_history_event_with_zero_writes(self) -> None:
        same = identity(desired=OLD, baseline=OLD)
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, same)
        recorder.ensure_started(
            operation_type="lesson-content-sync",
            state_before={"applied_fingerprint": OLD},
            expected_state={"desired_fingerprint": OLD},
            stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
            fingerprint_before=OLD,
            started_at="2026-09-14T20:00:00Z",
        )
        recorder.final_readback(
            fingerprint_after=OLD,
            stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
            status="NOOP_CONFIRMED",
            baseline_after={"applied_fingerprint": OLD},
        )
        records = recorder.records(refresh=True)
        summary = summarize_event(records)
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertEqual(summary["writes_started"], 0)
        final = next(r for r in records if r["phase"] == "FINAL_READBACK_CONFIRMED")
        self.assertEqual(final["status"], "NOOP_CONFIRMED")

    def test_newer_main_blocks_old_event_even_if_live_matches_old_intermediate(self) -> None:
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA2,
            live_fingerprint=PARTIAL,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary={"external_write_started": True, "last_confirmed_operation_fingerprint": PARTIAL},
            event_source_sha=SHA1,
        )
        self.assertEqual(decision.classification, "STALE_SOURCE_SHA")
        self.assertFalse(decision.auto_allowed)

    def test_committed_history_live_match_exposes_stale_machine_baseline(self) -> None:
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=DESIRED,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=None,
            event_source_sha=None,
            committed_history_live_match=True,
        )
        self.assertEqual(decision.classification, "STALE_MACHINE_BASELINE")
        self.assertFalse(decision.auto_allowed)
        self.assertTrue(decision.owner_approval_required)

    def test_live_equals_canonical_without_proven_event_is_not_auto_adopted(self) -> None:
        decision = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=DESIRED,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=None,
            event_source_sha=None,
        )
        self.assertEqual(decision.classification, "UNPROVEN_LIVE_EQUALS_CANONICAL")
        self.assertTrue(decision.owner_approval_required)

    def test_reconcile_only_observation_is_not_incomplete_deployment(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
        recorder.reconcile_classified(
            classification="IN_SYNC",
            action="NOOP",
            reason_codes=["baseline-live-canonical-match"],
            live_fingerprint=OLD,
            baseline_fingerprint=OLD,
            current_main_sha=SHA1,
            owner_approval_required=False,
        )
        self.assertEqual(find_incomplete_object_events(store, object_id="M02-L01"), [])

    def test_retry_or_reconcile_records_current_workflow_relationship(self) -> None:
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity())
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
            record = recorder.reconcile_classified(
                classification="IN_SYNC",
                action="NOOP",
                reason_codes=["baseline-live-canonical-match"],
                live_fingerprint=OLD,
                baseline_fingerprint=OLD,
                current_main_sha=SHA1,
                owner_approval_required=False,
            )
        self.assertEqual(record["recorded_by_workflow"]["run_id"], "200")
        self.assertEqual(record["event_relationship"]["type"], "RETRY_OR_CONTINUATION_OF_EVENT")
        self.assertEqual(record["event_relationship"]["origin_run_id"], "100")

    def test_structural_and_metadata_divergence_never_auto_reconcile(self) -> None:
        structural = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=OLD,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=None,
            event_source_sha=None,
            structural_divergence=True,
        )
        metadata = classify_reconcile(
            source_sha=SHA1,
            current_main_sha=SHA1,
            live_fingerprint=OLD,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=OLD,
            event_summary=None,
            event_source_sha=None,
            metadata_divergence=True,
        )
        self.assertFalse(structural.auto_allowed)
        self.assertFalse(metadata.auto_allowed)
        self.assertTrue(structural.owner_approval_required)
        self.assertTrue(metadata.owner_approval_required)


if __name__ == "__main__":
    unittest.main()
