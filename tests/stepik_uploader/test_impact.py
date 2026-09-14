from __future__ import annotations

import unittest

from scripts.stepik_uploader.impact import assess_paths


class ImpactTests(unittest.TestCase):
    def test_maps_lesson_and_asset_changes_to_canonical_lesson(self) -> None:
        result = assess_paths(
            [
                "04_course/M03/M03-L02/lesson.md",
                "05_assets/M03/M03-L02/M03-L02-A03.png",
                "04_course/M03/M03-L02/author-notes.md",
            ]
        )
        self.assertEqual(result["affected_lessons"], ["M03-L02"])
        self.assertFalse(result["course_page_changed"])
        self.assertTrue(result["stepik_content_impact"])
        self.assertNotIn("04_course/M03/M03-L02/author-notes.md", result["paths_by_lesson"]["M03-L02"])

    def test_course_page_is_tracked_separately(self) -> None:
        result = assess_paths(["04_course/stepik/course-page.md"])
        self.assertEqual(result["affected_lessons"], [])
        self.assertTrue(result["course_page_changed"])
        self.assertTrue(result["stepik_content_impact"])

    def test_tooling_only_change_does_not_mark_course_content_pending(self) -> None:
        result = assess_paths(["scripts/stepik_uploader/writer.py"])
        self.assertFalse(result["stepik_content_impact"])


if __name__ == "__main__":
    unittest.main()
