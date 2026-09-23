from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_lesson_source,
)


ROOT = Path(__file__).resolve().parents[2]


class LinearRecoveryRouteTests(unittest.TestCase):
    def _steps(self, lesson_id: str):
        return compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id=lesson_id,
        )

    def test_every_new_attempt_moves_to_a_later_self_review_without_old_answer_backlink(self) -> None:
        routes = (
            ("M03-L02", 6, 7, "/lesson/2591720/step/5"),
            ("M04-L02", 6, 7, None),
            ("M04-L03", 6, 7, None),
            ("M05-L02", 11, 12, "/lesson/2591725/step/9"),
            ("M06-L04", 5, 6, "/lesson/2591729/step/4"),
            ("M06-L04", 10, 11, "/lesson/2591729/step/9"),
            ("M07-L02", 7, 8, "/lesson/2591731/step/6"),
        )
        for lesson_id, recovery_position, review_position, forbidden_backlink in routes:
            with self.subTest(lesson_id=lesson_id, recovery_position=recovery_position):
                steps = self._steps(lesson_id)
                recovery = steps[recovery_position - 1]
                review = steps[review_position - 1]

                self.assertEqual(recovery.semantic_type, "RECOVERY")
                self.assertGreater(review.position, recovery.position)
                self.assertIn(review.semantic_type, {"COMPOSITE", "REFLECTION"})
                if forbidden_backlink is not None:
                    self.assertNotIn(forbidden_backlink, recovery.markdown)

                self.assertRegex(
                    review.markdown,
                    re.compile(
                        r"Прежн(?:ий|ие)\s+ответ(?:ы)?\s+в\s+Stepik\s+не\s+редактируйте",
                        re.IGNORECASE,
                    ),
                )

    def test_only_two_lessons_grow_to_add_physical_post_recovery_steps(self) -> None:
        self.assertEqual(len(self._steps("M04-L03")), 7)
        self.assertEqual(len(self._steps("M06-L04")), 11)

        unchanged_counts = {
            "M03-L02": 9,
            "M04-L02": 7,
            "M05-L02": 12,
            "M07-L02": 8,
        }
        for lesson_id, expected in unchanged_counts.items():
            with self.subTest(lesson_id=lesson_id):
                self.assertEqual(len(self._steps(lesson_id)), expected)


if __name__ == "__main__":
    unittest.main()
