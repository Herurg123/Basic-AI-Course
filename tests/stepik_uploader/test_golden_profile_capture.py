from __future__ import annotations

import unittest

from scripts.stepik_uploader.golden_profile_capture import GoldenProfileCaptureError, _validated_baselines


class GoldenProfileCaptureTests(unittest.TestCase):
    def test_unchanged_golden_baselines_may_come_from_older_source_sha(self) -> None:
        state = {
            "course_id": 299189,
            "pending": {"lessons": {}, "course_page": None},
            "lessons": {
                "M00-L01": {
                    "canonical_id": "M00-L01",
                    "stepik_lesson_id": 1,
                    "step_ids": [1, 2, 3, 4, 5, 6],
                    "applied_source_sha": "a" * 40,
                },
                "M00-L02": {
                    "canonical_id": "M00-L02",
                    "stepik_lesson_id": 2,
                    "step_ids": list(range(10, 18)),
                    "applied_source_sha": "b" * 40,
                },
            },
        }
        baselines = _validated_baselines(state)
        self.assertEqual(set(baselines), {"M00-L01", "M00-L02"})

    def test_pending_golden_blocks_final_capture(self) -> None:
        state = {
            "course_id": 299189,
            "pending": {"lessons": {"M00-L01": {"status": "PENDING"}}},
            "lessons": {},
        }
        with self.assertRaises(GoldenProfileCaptureError):
            _validated_baselines(state)


if __name__ == "__main__":
    unittest.main()
