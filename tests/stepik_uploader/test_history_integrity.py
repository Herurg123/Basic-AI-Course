from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentHistoryError,
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import find_object_events, validate_event_records

SHA = "1" * 40
OLD = "sha256:" + "a" * 64
DESIRED = "sha256:" + "b" * 64


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


def started_recorder() -> tuple[MemoryHistoryStore, DeploymentRecorder]:
    store = MemoryHistoryStore()
    recorder = DeploymentRecorder(store, identity())
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before={"applied_fingerprint": OLD},
        expected_state={"desired_fingerprint": DESIRED},
        stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
        fingerprint_before=OLD,
        started_at="2026-09-15T03:00:00Z",
    )
    return store, recorder


class HistoryIntegrityTests(unittest.TestCase):
    def test_valid_partial_event_passes_integrity_validation(self) -> None:
        store, recorder = started_recorder()
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0001-101")
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after=DESIRED)
        records = recorder.records(refresh=True)
        resolved = validate_event_records(records, expected_event_id=identity().event_id)
        self.assertEqual(resolved.event_id, identity().event_id)

    def test_tampered_logical_identity_fails_closed(self) -> None:
        store, recorder = started_recorder()
        records = recorder.records(refresh=True)
        tampered = copy.deepcopy(records[0])
        tampered["record_id"] = "reconcile-classified-tampered-000000000000"
        tampered["phase"] = "RECONCILE_CLASSIFIED"
        tampered["identity"]["object_id"] = "M99-L99"
        store.records[identity().event_id][tampered["record_id"]] = tampered
        with self.assertRaises(DeploymentHistoryError):
            find_object_events(store, object_id="M02-L01")

    def test_result_without_dispatch_fails_closed(self) -> None:
        store, recorder = started_recorder()
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        with self.assertRaises(DeploymentHistoryError):
            find_object_events(store, object_id="M02-L01")

    def test_conflicting_write_results_fail_closed(self) -> None:
        store, recorder = started_recorder()
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=OLD,
            expected_fingerprint_after=DESIRED,
        )
        recorder.write_dispatch_started(operation_id="step-0001-101")
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.write_result(operation_id="step-0001-101", status="AMBIGUOUS", reason_code="tampered")
        with self.assertRaises(DeploymentHistoryError):
            find_object_events(store, object_id="M02-L01")

    def test_applied_final_without_write_evidence_fails_closed(self) -> None:
        store, recorder = started_recorder()
        recorder.final_readback(
            fingerprint_after=DESIRED,
            stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
            status="APPLIED",
            baseline_after={"applied_fingerprint": DESIRED},
        )
        with self.assertRaises(DeploymentHistoryError):
            find_object_events(store, object_id="M02-L01")

    def test_directory_event_id_mismatch_fails_closed(self) -> None:
        _store, recorder = started_recorder()
        with self.assertRaises(DeploymentHistoryError):
            validate_event_records(
                recorder.records(refresh=True),
                expected_event_id="evt-" + "0" * 32,
            )


if __name__ == "__main__":
    unittest.main()
