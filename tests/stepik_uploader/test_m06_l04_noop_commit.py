from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import (
    DeploymentHistoryError, DeploymentRecorder, EventIdentity, MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import mark_machine_state_committed
from scripts.stepik_uploader.reconcile_m06_l04 import BASELINE_FP
from scripts.stepik_uploader.repair_m06_l04_noop_commit import (
    COURSE_ID, DESIRED_FP, EVENT_ID, EXPECTED_SOURCE_PATHS,
    FIRST_PENDING_SHA, INTERMEDIATE_FP, LESSON_ID, OBJECT_ID, PREVIOUS_SHA,
    RECONCILED_EVENT_ID, STEP_IDS, planned_state, proven_final, verified_live,
)
from scripts.stepik_uploader.sync_state import SCHEMA_VERSION


def exact_final() -> dict:
    return {
        "canonical_id": OBJECT_ID, "stepik_lesson_id": LESSON_ID, "step_ids": STEP_IDS,
        "source_git_paths": EXPECTED_SOURCE_PATHS, "applied_fingerprint": DESIRED_FP,
        "confirmed_live_fingerprint": INTERMEDIATE_FP, "applied_source_sha": PREVIOUS_SHA,
        "applied_at": "2026-10-24T14:35:18Z",
    }


def old_state() -> dict:
    old = dict(exact_final())
    old.update({
        "applied_fingerprint": INTERMEDIATE_FP,
        "confirmed_live_fingerprint": INTERMEDIATE_FP,
        "applied_source_sha": "bcf20b6ce0c5ca921247cba209a7a375f1bb72a2",
        "applied_at": "2026-10-24T14:12:31Z",
        "partial_reconciliation": RECONCILED_EVENT_ID,
    })
    other = dict(old, canonical_id="M07-L01", stepik_lesson_id=2591730)
    return {
        "schema_version": SCHEMA_VERSION, "course_id": COURSE_ID,
        "updated_at": "2026-10-24T14:35:20Z",
        "lessons": {OBJECT_ID: old, "M07-L01": other}, "assets": {},
        "pending": {"course_page": None, "lessons": {}},
    }


def wal():
    identity = EventIdentity(
        event_id=EVENT_ID, course_id=COURSE_ID, kind="lesson", object_id=OBJECT_ID,
        source_sha=PREVIOUS_SHA, desired_fingerprint=DESIRED_FP,
        baseline_fingerprint_before=INTERMEDIATE_FP, pending_first_sha=FIRST_PENDING_SHA,
        workflow_run_id="40101570460", workflow_run_attempt="1",
        workflow_run_url="https://github.com/Herurg123/Basic-AI-Course/actions/runs/40101570460",
    )
    assert stable_event_id(
        course_id=COURSE_ID, object_id=OBJECT_ID, kind="lesson",
        source_sha=PREVIOUS_SHA, desired_fingerprint=DESIRED_FP,
        baseline_fingerprint=INTERMEDIATE_FP, pending_first_sha=FIRST_PENDING_SHA,
    ) == EVENT_ID
    store = MemoryHistoryStore()
    recorder = DeploymentRecorder(store, identity)
    recorder.ensure_started(
        operation_type="lesson-content-refresh",
        state_before=old_state()["lessons"][OBJECT_ID],
        expected_state={"desired_fingerprint": DESIRED_FP},
        stepik_object_ids={"lesson_id": LESSON_ID, "step_ids": STEP_IDS},
        fingerprint_before=INTERMEDIATE_FP,
    )
    recorder.final_readback(
        fingerprint_after=DESIRED_FP, observed_live_fingerprint=INTERMEDIATE_FP,
        stepik_object_ids={"lesson_id": LESSON_ID, "step_ids": STEP_IDS},
        status="NOOP_CONFIRMED", baseline_after=exact_final(),
    )
    return store


def example_snapshot() -> dict:
    steps = [{
        "step_source": {"id": sid, "position": index,
                        "block": {"name": "text", "text": "<p>Пример</p>", "source": {}}},
    } for index, sid in enumerate(STEP_IDS, start=1)]
    lesson = {
        "id": LESSON_ID, "title": "Проверьте новые ситуации без готового маршрута",
        "language": "ru", "is_public": False, "steps": steps,
    }
    return {
        "course": {"id": COURSE_ID, "is_public": False},
        "sections": [{"position": 7, "units": [{"position": 4, "lesson": lesson}]}],
    }


class M06L04NoopCommitGapTests(unittest.TestCase):
    def test_proven_final_is_exact_and_has_no_stepik_write_records(self):
        store = wal()
        self.assertEqual(proven_final(store.load(EVENT_ID)), exact_final())

    def test_machine_baseline_catches_up_and_other_objects_untouched(self):
        old = old_state()
        snapshot = deepcopy(old)
        nxt = planned_state(old, exact_final())
        self.assertEqual(nxt["lessons"][OBJECT_ID], exact_final())
        self.assertEqual(nxt["lessons"]["M07-L01"], snapshot["lessons"]["M07-L01"])
        self.assertEqual(nxt["pending"], snapshot["pending"])
        self.assertEqual(old, snapshot)
        self.assertEqual(planned_state(nxt, exact_final()), nxt)

    def test_final_wal_cannot_commit_before_machine_patch(self):
        store = wal()
        with self.assertRaises(DeploymentHistoryError):
            mark_machine_state_committed(
                store, event_id=EVENT_ID, status="NOOP_CONFIRMED",
                baseline_after=old_state()["lessons"][OBJECT_ID],
            )
        mark_machine_state_committed(
            store, event_id=EVENT_ID, status="NOOP_CONFIRMED",
            baseline_after=exact_final(),
        )
        mark_machine_state_committed(
            store, event_id=EVENT_ID, status="NOOP_CONFIRMED",
            baseline_after=exact_final(),
        )
        self.assertEqual(proven_final(store.load(EVENT_ID)), exact_final())

    def test_machine_state_drift_and_new_pending_block(self):
        old = old_state()
        old["lessons"][OBJECT_ID]["applied_fingerprint"] = BASELINE_FP
        with self.assertRaises(DeploymentHistoryError):
            planned_state(old, exact_final())
        old = old_state()
        old["pending"]["lessons"][OBJECT_ID] = {
            "object_id": OBJECT_ID, "kind": "lesson", "status": "PENDING",
        }
        with self.assertRaises(RuntimeError):
            planned_state(old, exact_final())

    def test_live_exact_hash_and_topology(self):
        snapshot = example_snapshot()
        with patch("scripts.stepik_uploader.repair_m06_l04_noop_commit.live_lesson_fingerprint",
                   return_value=INTERMEDIATE_FP):
            self.assertEqual(verified_live(snapshot, old_state()["lessons"][OBJECT_ID]), INTERMEDIATE_FP)
        with patch("scripts.stepik_uploader.repair_m06_l04_noop_commit.live_lesson_fingerprint",
                   return_value=DESIRED_FP):
            with self.assertRaises(DeploymentHistoryError):
                verified_live(snapshot, old_state()["lessons"][OBJECT_ID])
        snapshot["sections"][0]["units"][0]["lesson"]["steps"][8]["step_source"]["id"] = 9999
        with self.assertRaises(DeploymentHistoryError):
            verified_live(snapshot, old_state()["lessons"][OBJECT_ID])

    def test_new_wal_operations_or_altered_state_block(self):
        store = wal()
        records = store.load(EVENT_ID)
        records.append({"phase": "WRITE_DISPATCH_STARTED"})
        with self.assertRaises(DeploymentHistoryError):
            proven_final(records)
        store = wal()
        records = store.load(EVENT_ID)
        for row in records:
            if row.get("phase") == "FINAL_READBACK_CONFIRMED":
                row["actual_confirmed_state"]["applied_source_sha"] = "0" * 40
        with self.assertRaises(DeploymentHistoryError):
            proven_final(records)


if __name__ == "__main__":
    unittest.main()
