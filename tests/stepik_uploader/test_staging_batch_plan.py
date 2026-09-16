from __future__ import annotations

import unittest

from scripts.stepik_uploader.staging_batch_plan import select_targets


class StagingBatchPlanTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
