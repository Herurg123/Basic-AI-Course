from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L01RecoveryObjectTests(unittest.TestCase):
    def test_route_never_requires_nonexistent_other_fact(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )

        search_step = steps[3].markdown
        recovery = steps[7].markdown

        self.assertNotIn("другой безопасный внешний факт из учебной задачи", search_step)
        self.assertNotIn("другой безопасный внешний факт из учебной ситуации", recovery)
        self.assertIn("данных недостаточно", search_step)
        self.assertIn("Win + L", recovery)
        self.assertIn("самостоятельно найдите подходящую страницу или документ", recovery)
        self.assertIn("не возвращайтесь к ответу в шаге 7", recovery)


if __name__ == "__main__":
    unittest.main()
