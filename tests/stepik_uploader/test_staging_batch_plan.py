from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
)
from scripts.stepik_uploader.staging_batch_plan import (
    add_history_recovery_targets,
    select_targets,
)


class StagingBatchPlanTests(unittest.TestCase):
    SOURCE_SHA = "a" * 40
    DESIRED_FP = "sha256:" + "1" * 64
    BEFORE_FP = "sha256:" + "0" * 64

    def manifest(self):
        return {
            "modules": [
                {
                    "lessons": [
                        {"canonical_id": "M00-L01", "golden_read_only": True},
                        {"canonical_id": "M00-L02", "golden_read_only": True},
                        {"canonical_id": "M00-L03"},
                    ]
                },
                {
                    "lessons": [
                        {"canonical_id": "M01-L01"},
                        {"canonical_id": "M01-L02"},
                    ]
                },
            ]
        }

    def pending(self, *ids: str, course_page: bool = False):
        return {
            "lessons": {
                canonical_id: {"status": "PENDING"}
                for canonical_id in ids
            },
            "course_page": {"status": "PENDING"} if course_page else None,
        }

    def committed_baseline(self, canonical_id: str):
        return {
            "canonical_id": canonical_id,
            "stepik_lesson_id": 100,
            "applied_fingerprint": self.DESIRED_FP,
            "step_ids": [1],
        }

    def add_uncommitted_final_history(self, store: MemoryHistoryStore, canonical_id: str, *, source_sha: str):
        identity = event_identity_from_environment(
            course_id=299189,
            object_id=canonical_id,
            kind="lesson",
            source_sha=source_sha,
            desired_fingerprint=self.DESIRED_FP,
            baseline_fingerprint=None,
            pending_first_sha="b" * 40,
        )
        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type="INITIAL_UPLOAD",
            state_before=None,
            expected_state=None,
            stepik_object_ids={"lesson_id": 100, "step_ids": [1]},
            fingerprint_before=self.BEFORE_FP,
        )
        recorder.write_intent(
            operation_id="step-0001",
            method="PUT",
            target="step:1",
            fingerprint_before=self.BEFORE_FP,
            expected_fingerprint_after=self.DESIRED_FP,
        )
        recorder.write_dispatch_started(operation_id="step-0001")
        recorder.write_result(operation_id="step-0001", status="COMPLETED")
        recorder.operation_readback(
            operation_id="step-0001",
            expected_fingerprint_after=self.DESIRED_FP,
        )
        recorder.final_readback(
            fingerprint_after=self.DESIRED_FP,
            stepik_object_ids={"lesson_id": 100, "step_ids": [1]},
            status="APPLIED",
            baseline_after=self.committed_baseline(canonical_id),
        )

    def test_selects_only_ordinary_pending_in_manifest_order(self):
        state = {
            "lessons": {},
            "pending": self.pending("M01-L02", "M00-L02", "M01-L01", course_page=True),
        }
        plan = select_targets(self.manifest(), state)
        self.assertEqual(plan["target_ids"], ["M01-L01", "M01-L02"])
        self.assertEqual(plan["excluded_golden_pending"], ["M00-L02"])
        self.assertTrue(plan["course_page_pending"])
        self.assertEqual(plan["blockers"], [])
        self.assertTrue(plan["write_allowed"])

    def test_existing_baseline_for_pending_lesson_blocks_initial_batch(self):
        state = {
            "lessons": {"M01-L01": {"canonical_id": "M01-L01"}},
            "pending": self.pending("M01-L01", "M01-L02"),
        }
        plan = select_targets(self.manifest(), state)
        self.assertEqual(plan["target_ids"], ["M01-L02"])
        self.assertFalse(plan["write_allowed"])
        self.assertIn("M01-L01", plan["blockers"][0])

    def test_unknown_pending_lesson_blocks_batch(self):
        state = {
            "lessons": {},
            "pending": self.pending("M99-L99", "M01-L01"),
        }
        plan = select_targets(self.manifest(), state)
        self.assertEqual(plan["target_ids"], ["M01-L01"])
        self.assertFalse(plan["write_allowed"])
        self.assertIn("M99-L99", plan["blockers"][0])

    def test_no_pending_targets_is_valid_noop(self):
        state = {"lessons": {}, "pending": self.pending("M00-L02")}
        plan = select_targets(self.manifest(), state)
        self.assertEqual(plan["target_ids"], [])
        self.assertEqual(plan["target_count"], 0)
        self.assertEqual(plan["excluded_golden_pending"], ["M00-L02"])
        self.assertTrue(plan["write_allowed"])

    def test_incomplete_current_source_history_with_baseline_becomes_recovery_target(self):
        store = MemoryHistoryStore()
        self.add_uncommitted_final_history(store, "M01-L01", source_sha=self.SOURCE_SHA)
        state = {
            "lessons": {"M01-L01": self.committed_baseline("M01-L01")},
            "pending": self.pending("M01-L02"),
        }
        selected = select_targets(self.manifest(), state)
        plan = add_history_recovery_targets(
            selection=selected,
            manifest=self.manifest(),
            state=state,
            source_main_sha=self.SOURCE_SHA,
            store=store,
            course_id=299189,
        )
        self.assertEqual(plan["target_ids"], ["M01-L01", "M01-L02"])
        self.assertEqual(plan["recovery_target_ids"], ["M01-L01"])
        self.assertTrue(plan["write_allowed"])

    def test_stale_source_incomplete_history_blocks_batch(self):
        store = MemoryHistoryStore()
        self.add_uncommitted_final_history(store, "M01-L01", source_sha="c" * 40)
        state = {
            "lessons": {"M01-L01": self.committed_baseline("M01-L01")},
            "pending": self.pending("M01-L02"),
        }
        selected = select_targets(self.manifest(), state)
        plan = add_history_recovery_targets(
            selection=selected,
            manifest=self.manifest(),
            state=state,
            source_main_sha=self.SOURCE_SHA,
            store=store,
            course_id=299189,
        )
        self.assertFalse(plan["write_allowed"])
        self.assertTrue(any("source_sha=" in blocker for blocker in plan["blockers"]))


if __name__ == "__main__":
    unittest.main()
