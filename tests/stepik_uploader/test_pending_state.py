from __future__ import annotations

import unittest

from scripts.stepik_uploader.sync_state import close_lesson_pending, empty_state, with_pending_impact

SHA1 = "1" * 40
SHA2 = "2" * 40
T1 = "2026-09-14T10:00:00Z"
T2 = "2026-09-14T11:00:00Z"


class PendingStateTests(unittest.TestCase):
    def test_first_pending_lesson_captures_baseline_reference(self) -> None:
        state = empty_state(299189)
        state["lessons"]["M02-L01"] = {
            "canonical_id": "M02-L01",
            "stepik_lesson_id": 2591717,
            "applied_source_sha": "a" * 40,
            "applied_at": "2026-09-14T08:37:09Z",
            "applied_fingerprint": "sha256:" + "b" * 64,
            "step_ids": [1],
            "source_git_paths": ["04_course/M02/M02-L01/lesson.md"],
        }
        next_state = with_pending_impact(
            state,
            source_sha=SHA1,
            occurred_at=T1,
            paths_by_lesson={"M02-L01": ["04_course/M02/M02-L01/lesson.md"]},
            reasons_by_lesson={"M02-L01": ["direct-lesson-source"]},
        )
        pending = next_state["pending"]["lessons"]["M02-L01"]
        self.assertEqual(pending["first_pending_sha"], SHA1)
        self.assertEqual(pending["latest_pending_sha"], SHA1)
        self.assertEqual(pending["confirmed_baseline_ref"]["state_path"], "lessons.M02-L01")

    def test_second_merge_updates_same_pending_record(self) -> None:
        state = with_pending_impact(
            empty_state(299189),
            source_sha=SHA1,
            occurred_at=T1,
            paths_by_lesson={"M03-L02": ["04_course/M03/M03-L02/lesson.md"]},
            reasons_by_lesson={"M03-L02": ["direct-lesson-source"]},
        )
        state = with_pending_impact(
            state,
            source_sha=SHA2,
            occurred_at=T2,
            paths_by_lesson={"M03-L02": ["05_assets/M03/M03-L02/M03-L02-A03.md"]},
            reasons_by_lesson={"M03-L02": ["lesson-asset"]},
        )
        self.assertEqual(list(state["pending"]["lessons"]), ["M03-L02"])
        pending = state["pending"]["lessons"]["M03-L02"]
        self.assertEqual(pending["first_pending_sha"], SHA1)
        self.assertEqual(pending["latest_pending_sha"], SHA2)
        self.assertEqual(len(pending["source_paths"]), 2)

    def test_two_lessons_are_independent_pending_objects(self) -> None:
        state = with_pending_impact(
            empty_state(299189),
            source_sha=SHA1,
            occurred_at=T1,
            paths_by_lesson={
                "M03-L02": ["04_course/M03/M03-L02/lesson.md"],
                "M05-L02": ["04_course/M05/M05-L02/lesson.md"],
            },
            reasons_by_lesson={
                "M03-L02": ["direct-lesson-source"],
                "M05-L02": ["direct-lesson-source"],
            },
        )
        self.assertEqual(set(state["pending"]["lessons"]), {"M03-L02", "M05-L02"})

    def test_applied_closes_only_target_pending(self) -> None:
        state = self._two_pending()
        state = close_lesson_pending(state, canonical_id="M03-L02", confirmed_at=T2, confirmation_status="APPLIED")
        self.assertNotIn("M03-L02", state["pending"]["lessons"])
        self.assertIn("M05-L02", state["pending"]["lessons"])

    def test_noop_confirmed_closes_only_target_pending(self) -> None:
        state = self._two_pending()
        state = close_lesson_pending(state, canonical_id="M05-L02", confirmed_at=T2, confirmation_status="NOOP_CONFIRMED")
        self.assertIn("M03-L02", state["pending"]["lessons"])
        self.assertNotIn("M05-L02", state["pending"]["lessons"])

    def test_course_page_pending_is_separate(self) -> None:
        state = with_pending_impact(
            empty_state(299189),
            source_sha=SHA1,
            occurred_at=T1,
            paths_by_lesson={},
            reasons_by_lesson={},
            course_page_paths=["04_course/stepik/course-page.md"],
            course_page_reason_codes=["course-page-source"],
        )
        self.assertEqual(state["pending"]["lessons"], {})
        self.assertEqual(state["pending"]["course_page"]["object_id"], "course-page")

    def _two_pending(self) -> dict:
        return with_pending_impact(
            empty_state(299189),
            source_sha=SHA1,
            occurred_at=T1,
            paths_by_lesson={
                "M03-L02": ["04_course/M03/M03-L02/lesson.md"],
                "M05-L02": ["04_course/M05/M05-L02/lesson.md"],
            },
            reasons_by_lesson={
                "M03-L02": ["direct-lesson-source"],
                "M05-L02": ["direct-lesson-source"],
            },
        )


if __name__ == "__main__":
    unittest.main()
