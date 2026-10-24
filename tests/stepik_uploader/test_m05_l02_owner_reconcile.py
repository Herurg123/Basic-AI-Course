from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from scripts.stepik_uploader.deployment_history import (
    DeploymentHistoryError, DeploymentRecorder, EventIdentity, MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import find_incomplete_object_events
from scripts.stepik_uploader.reconcile_m05_l02 import (
    BASELINE_FP, EVENT_ID, EXPECTED_INTERMEDIATE, OBSERVED_INTERMEDIATE,
    ORIGIN_SHA, OBJECT_ID, OWNER_APPROVAL, STEP_ID,
    proposed_state, verify_wal, verify_observed_partial,
)
from scripts.stepik_uploader.sync_state import SCHEMA_VERSION


PENDING_SHA = "b775cf533e0600dbf8060bcff67c862594a08eff"
OLD_DESIRED_FP = "sha256:98563f52fc0acb6049812090a3a4d6064d7d74057b93ad35ebcbf4f24f586f50"
OLD_IDS = [11291310,11339649,11339650,11339651,11339653,11339654,
           11339655,11339656,11339657,11339658,11339660,11339662]


def make_identity() -> EventIdentity:
    event_id = stable_event_id(
        course_id=299189, object_id=OBJECT_ID, kind="lesson",
        source_sha=ORIGIN_SHA, desired_fingerprint=OLD_DESIRED_FP,
        baseline_fingerprint=BASELINE_FP, pending_first_sha=PENDING_SHA,
    )
    assert event_id == EVENT_ID
    return EventIdentity(
        event_id=event_id,course_id=299189,object_id=OBJECT_ID,kind="lesson",
        source_sha=ORIGIN_SHA,workflow_run_id="40086031794",
        workflow_run_attempt="1",workflow_run_url="https://example.invalid",
        desired_fingerprint=OLD_DESIRED_FP,baseline_fingerprint_before=BASELINE_FP,
        pending_first_sha=PENDING_SHA,
    )


def interrupted_store() -> tuple[MemoryHistoryStore, EventIdentity]:
    store = MemoryHistoryStore()
    identity = make_identity()
    rec = DeploymentRecorder(store,identity)
    rec.ensure_started(
        operation_type="lesson-content-refresh",
        state_before={"applied_fingerprint":BASELINE_FP},
        expected_state={"desired_fingerprint":OLD_DESIRED_FP},
        stepik_object_ids={"lesson_id":2591725,"step_ids":OLD_IDS},
        fingerprint_before=BASELINE_FP,
    )
    op=f"step-0002-{STEP_ID}"
    rec.write_intent(operation_id=op,method="PUT",target=f"step-sources/{STEP_ID}",
                     fingerprint_before=BASELINE_FP,expected_fingerprint_after=EXPECTED_INTERMEDIATE)
    rec.write_dispatch_started(operation_id=op)
    rec.write_result(operation_id=op,status="COMPLETED")
    rec.readback_failed(operation_id=op,reason_code="operation-readback-unavailable-or-mismatch")
    rec.failure(reason_code="refresh-runtime-contentwriteerror",before_any_write=False)
    return store,identity


def example_state() -> dict:
    base={"canonical_id":OBJECT_ID,"stepik_lesson_id":2591725,
          "step_ids":OLD_IDS,"source_git_paths":["04_course/M05/M05-L02/lesson.md"],
          "applied_fingerprint":BASELINE_FP,"confirmed_live_fingerprint":BASELINE_FP,
          "applied_source_sha":"7a5557381ea01c2627087595b3fb256f0a75c36d",
          "applied_at":"2026-09-29T03:47:29Z"}
    return {
        "schema_version":SCHEMA_VERSION,"course_id":299189,
        "lessons":{OBJECT_ID:base},"assets":{},"updated_at":"2026-10-24T11:14:58Z",
        "pending":{"course_page":None,"lessons":{OBJECT_ID:{
            "object_id":OBJECT_ID,"kind":"lesson","status":"PENDING",
            "reason_codes":["canonical-learner-change"],"source_paths":["04_course/M05/M05-L02/lesson.md"],
            "first_pending_sha":PENDING_SHA,"latest_pending_sha":ORIGIN_SHA,
            "first_pending_at":"2026-10-24T10:00:00Z","latest_pending_at":"2026-10-24T11:00:00Z",
            "confirmed_baseline_ref":{
                "state_path":f"lessons.{OBJECT_ID}",
                "stepik_lesson_id":2591725,"applied_source_sha":base["applied_source_sha"],
                "applied_at":base["applied_at"],"applied_fingerprint":BASELINE_FP,
                "confirmed_live_fingerprint":BASELINE_FP,
            }
        }}}
    }


def example_snapshot() -> dict:
    steps=[]
    for position, sid in enumerate(OLD_IDS,start=1):
        text="<p>Другой шаг</p>"
        if position==2:
            text=("<p>Теперь попробуйте изменить эту же картинку.</p>\n<ol>"
                  "<li>Шаг 1</li></ol>")
        steps.append({"step_source":{"id":sid,"position":position,
                                      "block":{"name":"text","source":{},"text":text}}})
    return {"course":{"id":299189,"is_public":False},
            "sections":[{"position":6,"units":[{"position":2,"lesson":{
                "id":2591725,"title":"Создайте изображение и затем измените именно его",
                "language":"ru","is_public":False,"steps":steps
            }}]}]}


class SingleStepOwnerReconciliationTests(unittest.TestCase):
    def test_exact_wal_identity_and_failure(self):
        store,_=interrupted_store()
        self.assertEqual(verify_wal(store.load(EVENT_ID)).event_id,EVENT_ID)
        self.assertEqual(len(find_incomplete_object_events(store,object_id=OBJECT_ID)),1)

    def test_terminal_only_after_exact_explicit_owner_evidence(self):
        store, identity=interrupted_store()
        rec=DeploymentRecorder(store,identity)
        rec._append("RECONCILE_COMMITTED",{
            "reconciliation_mode":OWNER_APPROVAL,
            "old_expected_intermediate":EXPECTED_INTERMEDIATE,
            "observed_live_fingerprint":OBSERVED_INTERMEDIATE,
            "baseline_before":BASELINE_FP,"owner_approved":True,
        },operation_id="step-0002-owner-reconciliation")
        self.assertEqual(find_incomplete_object_events(store,object_id=OBJECT_ID),[])

    def test_terminal_wrong_evidence_fails_closed(self):
        store,identity=interrupted_store()
        DeploymentRecorder(store,identity)._append("RECONCILE_COMMITTED",{
            "reconciliation_mode":OWNER_APPROVAL,
            "old_expected_intermediate":EXPECTED_INTERMEDIATE,
            "observed_live_fingerprint":"sha256:"+ "0"*64,
            "baseline_before":BASELINE_FP,"owner_approved":True,
        },operation_id="step-0002-owner-reconciliation")
        with self.assertRaises(DeploymentHistoryError):
            find_incomplete_object_events(store,object_id=OBJECT_ID)

    def test_other_unconfirmed_events_still_block(self):
        store,identity=interrupted_store()
        # No terminal certification. Nothing about the owner command weakens this gate.
        self.assertEqual(len(find_incomplete_object_events(store,object_id=OBJECT_ID)),1)

    def test_partial_baseline_update_preserves_pending_and_all_steps(self):
        state=example_state()
        new=proposed_state(state,live_fp=OBSERVED_INTERMEDIATE)
        self.assertEqual(new["lessons"][OBJECT_ID]["step_ids"], OLD_IDS)
        self.assertEqual(new["lessons"][OBJECT_ID]["applied_fingerprint"],OBSERVED_INTERMEDIATE)
        self.assertEqual(new["pending"]["lessons"][OBJECT_ID]["status"],"PENDING")
        self.assertEqual(new["pending"]["lessons"][OBJECT_ID]["confirmed_baseline_ref"]["applied_fingerprint"],OBSERVED_INTERMEDIATE)
        self.assertEqual(state["lessons"][OBJECT_ID]["applied_fingerprint"],BASELINE_FP)
        self.assertEqual(proposed_state(new,live_fp=OBSERVED_INTERMEDIATE),new)

    def test_changed_or_unknown_machine_baseline_is_blocked(self):
        state=example_state()
        state["lessons"][OBJECT_ID]["applied_fingerprint"]="sha256:"+"a"*64
        with self.assertRaises(DeploymentHistoryError):
            proposed_state(state,live_fp=OBSERVED_INTERMEDIATE)

    def test_exact_one_html_transport_change_and_identity_guard(self):
        snapshot=example_snapshot()
        with patch("scripts.stepik_uploader.reconcile_m05_l02.live_lesson_fingerprint",
                   side_effect=[OBSERVED_INTERMEDIATE,EXPECTED_INTERMEDIATE]):
            self.assertEqual(verify_observed_partial(snapshot,example_state()["lessons"][OBJECT_ID]),OBSERVED_INTERMEDIATE)

    def test_another_lesson_id_is_blocked_even_with_matching_fingerprint(self):
        snapshot=example_snapshot()
        snapshot["sections"][0]["units"][0]["lesson"]["id"]=9999
        with self.assertRaises(DeploymentHistoryError):
            verify_observed_partial(snapshot,example_state()["lessons"][OBJECT_ID])

    def test_wrong_step_identifiers_block(self):
        snapshot=example_snapshot()
        snapshot["sections"][0]["units"][0]["lesson"]["steps"][1]["step_source"]["id"]=1
        with self.assertRaises(DeploymentHistoryError):
            verify_observed_partial(snapshot,example_state()["lessons"][OBJECT_ID])

    def test_other_live_html_change_blocks_before_reconstruction(self):
        snapshot=example_snapshot()
        with patch("scripts.stepik_uploader.reconcile_m05_l02.live_lesson_fingerprint",
                   return_value="sha256:"+"0"*64):
            with self.assertRaises(DeploymentHistoryError):
                verify_observed_partial(snapshot,example_state()["lessons"][OBJECT_ID])


if __name__ == "__main__":
    unittest.main()
