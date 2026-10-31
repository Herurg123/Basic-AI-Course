from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import (
    DeploymentHistoryError, DeploymentRecorder, EventIdentity, MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import find_incomplete_object_events
from scripts.stepik_uploader.reconcile_m06_l04 import (
    BASELINE_FP, BASELINE_LIVE_FP, EVENT_ID, EXPECTED_STEP2, EXPECTED_STEP9,
    FINAL_DESIRED, LESSON_ID, OBJECT_ID, ORIGIN_SHA, OWNER_APPROVAL,
    PENDING_FIRST_SHA, STEP2_ID, STEP9_ID, STEP_IDS,
    proposed_state, verify_wal, verify_observed_partial,
)
from scripts.stepik_uploader.sync_state import SCHEMA_VERSION


def identity() -> EventIdentity:
    actual = stable_event_id(
        course_id=299189, object_id=OBJECT_ID, kind="lesson",
        source_sha=ORIGIN_SHA, desired_fingerprint=FINAL_DESIRED,
        baseline_fingerprint=BASELINE_FP, pending_first_sha=PENDING_FIRST_SHA,
    )
    assert actual == EVENT_ID
    return EventIdentity(
        event_id=actual, course_id=299189, object_id=OBJECT_ID,
        kind="lesson", source_sha=ORIGIN_SHA, desired_fingerprint=FINAL_DESIRED,
        baseline_fingerprint_before=BASELINE_FP, pending_first_sha=PENDING_FIRST_SHA,
        workflow_run_id="40094692532", workflow_run_attempt="1",
        workflow_run_url="https://github.com/Herurg123/Basic-AI-Course/actions/runs/40094692532",
    )


def interrupted() -> tuple[MemoryHistoryStore, EventIdentity]:
    store = MemoryHistoryStore()
    idn = identity()
    rec = DeploymentRecorder(store, idn)
    rec.ensure_started(
        operation_type="lesson-content-refresh",
        state_before={"applied_fingerprint": BASELINE_FP},
        expected_state={"desired_fingerprint": FINAL_DESIRED},
        stepik_object_ids={"lesson_id": LESSON_ID, "step_ids": STEP_IDS},
        fingerprint_before=BASELINE_LIVE_FP,
    )
    op2 = f"step-0002-{STEP2_ID}"
    rec.write_intent(
        operation_id=op2, method="PUT", target=f"step-sources/{STEP2_ID}",
        fingerprint_before=BASELINE_LIVE_FP, expected_fingerprint_after=EXPECTED_STEP2,
    )
    rec.write_dispatch_started(operation_id=op2)
    rec.write_result(operation_id=op2, status="COMPLETED")
    rec.operation_readback(operation_id=op2, expected_fingerprint_after=EXPECTED_STEP2,
                           observed_live_fingerprint=EXPECTED_STEP2)
    op9 = f"step-0009-{STEP9_ID}"
    rec.write_intent(
        operation_id=op9, method="PUT", target=f"step-sources/{STEP9_ID}",
        fingerprint_before=EXPECTED_STEP2, expected_fingerprint_after=EXPECTED_STEP9,
    )
    rec.write_dispatch_started(operation_id=op9)
    rec.write_result(operation_id=op9, status="AMBIGUOUS", reason_code="stepik-write-ambiguous")
    rec.failure(reason_code="refresh-runtime-stepikwriteambiguouserror", before_any_write=False)
    return store, idn


def example_state() -> dict:
    old = {
        "canonical_id": OBJECT_ID, "stepik_lesson_id": LESSON_ID,
        "step_ids": STEP_IDS, "source_git_paths": ["04_course/M06/M06-L04/lesson.md"],
        "applied_fingerprint": BASELINE_FP, "confirmed_live_fingerprint": BASELINE_LIVE_FP,
        "applied_source_sha": "7a5557381ea01c2627087595b3fb256f0a75c36d",
        "applied_at": "2026-09-29T03:52:45Z",
    }
    ref = {
        "state_path": f"lessons.{OBJECT_ID}", "stepik_lesson_id": LESSON_ID,
        "applied_source_sha": old["applied_source_sha"], "applied_at": old["applied_at"],
        "applied_fingerprint": BASELINE_FP, "confirmed_live_fingerprint": BASELINE_LIVE_FP,
    }
    return {
        "schema_version": SCHEMA_VERSION, "course_id": 299189, "lessons": {OBJECT_ID: old},
        "assets": {}, "updated_at": "2026-10-24T13:12:05Z",
        "pending": {"course_page": None, "lessons": {OBJECT_ID: {
            "object_id": OBJECT_ID, "kind": "lesson", "status": "PENDING",
            "reason_codes": ["direct-lesson-source"], "source_paths": ["04_course/M06/M06-L04/lesson.md"],
            "first_pending_sha": PENDING_FIRST_SHA, "latest_pending_sha": ORIGIN_SHA,
            "first_pending_at": "2026-10-23T06:11:15Z", "latest_pending_at": "2026-10-24T08:58:25Z",
            "confirmed_baseline_ref": ref,
        }}},
    }


def snapshot() -> dict:
    lesson = {
        "id": LESSON_ID, "title": "Проверьте новые ситуации без готового маршрута",
        "language": "ru", "is_public": False,
        "steps": [{"step_source": {
            "id": step_id, "position": pos, "block": {
                "name": "free-answer" if pos == 9 else "text",
                "text": "<p>Фрагмент</p>", "source": {},
            }
        }} for pos, step_id in enumerate(STEP_IDS, start=1)],
    }
    return {"course": {"id": 299189, "is_public": False},
            "sections": [{"position": 7, "units": [{"position": 4, "lesson": lesson}]}]}


class AmbiguousPutOwnerReconciliationTests(unittest.TestCase):
    def test_exact_wal_is_detected(self):
        store, _ = interrupted()
        self.assertEqual(verify_wal(store.load(EVENT_ID)).event_id, EVENT_ID)
        self.assertEqual(len(find_incomplete_object_events(store, object_id=OBJECT_ID)), 1)

    def test_exact_owner_terminal_unlocks_only_incident(self):
        store, idn = interrupted()
        DeploymentRecorder(store, idn)._append("RECONCILE_COMMITTED", {
            "reconciliation_mode": OWNER_APPROVAL, "owner_approved": True,
            "old_expected_intermediate": EXPECTED_STEP9,
            "observed_live_fingerprint": EXPECTED_STEP9, "baseline_before": BASELINE_FP,
        }, operation_id="step-0009-owner-reconciliation")
        self.assertEqual(find_incomplete_object_events(store, object_id=OBJECT_ID), [])

    def test_wrong_owner_terminal_blocks_history(self):
        for field, wrong in (
            ("owner_approved", False),
            ("observed_live_fingerprint", EXPECTED_STEP2),
            ("old_expected_intermediate", EXPECTED_STEP2),
            ("baseline_before", BASELINE_LIVE_FP),
            ("reconciliation_mode", "WRONG"),
        ):
            with self.subTest(field=field):
                store, idn = interrupted()
                record = {
                    "reconciliation_mode": OWNER_APPROVAL, "owner_approved": True,
                    "old_expected_intermediate": EXPECTED_STEP9,
                    "observed_live_fingerprint": EXPECTED_STEP9, "baseline_before": BASELINE_FP,
                }
                record[field] = wrong
                DeploymentRecorder(store, idn)._append("RECONCILE_COMMITTED", record,
                                                       operation_id="step-0009-owner-reconciliation")
                with self.assertRaises(DeploymentHistoryError):
                    find_incomplete_object_events(store, object_id=OBJECT_ID)

    def test_different_wal_transition_is_blocked(self):
        store, idn = interrupted()
        rec = DeploymentRecorder(store, idn)
        rec._append("WRITE_AMBIGUOUS", {"operation_id": f"step-0009-{STEP9_ID}",
                                       "reason_code": "stepik-write-ambiguous"},
                    operation_id="not-the-original-operation")
        with self.assertRaises(DeploymentHistoryError):
            verify_wal(store.load(EVENT_ID))

    def test_observed_intermediate_requires_exact_live_hash_and_ids(self):
        ss = snapshot()
        with patch("scripts.stepik_uploader.reconcile_m06_l04.live_lesson_fingerprint",
                   return_value=EXPECTED_STEP9):
            self.assertEqual(verify_observed_partial(ss, example_state()["lessons"][OBJECT_ID]), EXPECTED_STEP9)
        with patch("scripts.stepik_uploader.reconcile_m06_l04.live_lesson_fingerprint",
                   return_value=EXPECTED_STEP2):
            with self.assertRaises(DeploymentHistoryError):
                verify_observed_partial(ss, example_state()["lessons"][OBJECT_ID])
        ss["sections"][0]["units"][0]["lesson"]["steps"][8]["step_source"]["id"] = 0
        with self.assertRaises(DeploymentHistoryError):
            verify_observed_partial(ss, example_state()["lessons"][OBJECT_ID])

    def test_wrong_course_visibility_or_lesson_id_blocks(self):
        for mode in ("public_course", "wrong_lesson", "wrong_section"):
            ss = snapshot()
            if mode == "public_course":
                ss["course"]["is_public"] = True
            elif mode == "wrong_lesson":
                ss["sections"][0]["units"][0]["lesson"]["id"] = 1
            else:
                ss["sections"][0]["position"] = 8
            with self.assertRaises(DeploymentHistoryError):
                verify_observed_partial(ss, example_state()["lessons"][OBJECT_ID])

    def test_reconciled_baseline_preserves_pending_and_other_lessons(self):
        st = example_state()
        other = deepcopy(st["lessons"][OBJECT_ID])
        other["canonical_id"] = "M07-L01"
        st["lessons"]["M07-L01"] = other
        old = deepcopy(st)
        nxt = proposed_state(st, live_fp=EXPECTED_STEP9)
        self.assertEqual(nxt["lessons"][OBJECT_ID]["applied_fingerprint"], EXPECTED_STEP9)
        self.assertEqual(nxt["lessons"][OBJECT_ID]["confirmed_live_fingerprint"], EXPECTED_STEP9)
        self.assertEqual(nxt["pending"]["lessons"][OBJECT_ID]["status"], "PENDING")
        self.assertEqual(nxt["pending"]["lessons"][OBJECT_ID]["confirmed_baseline_ref"]["applied_fingerprint"], EXPECTED_STEP9)
        self.assertEqual(nxt["lessons"]["M07-L01"], st["lessons"]["M07-L01"])
        self.assertEqual(st, old)
        self.assertEqual(proposed_state(nxt, live_fp=EXPECTED_STEP9), nxt)

    def test_baseline_manual_drift_blocks(self):
        st = example_state()
        st["lessons"][OBJECT_ID]["confirmed_live_fingerprint"] = "sha256:" + "0" * 64
        with self.assertRaises(DeploymentHistoryError):
            proposed_state(st, live_fp=EXPECTED_STEP9)


if __name__ == "__main__":
    unittest.main()
