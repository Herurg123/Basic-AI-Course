from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M07L02FinalTaskLanguageTests(unittest.TestCase):
    def test_step1_uses_plain_task_language_instead_of_case_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L02",
        )
        opening = steps[0].markdown

        self.assertIn("Готовой задачи с заранее заданной ситуацией", opening)
        self.assertNotIn("экзаменационного кейса", opening)


if __name__ == "__main__":
    unittest.main()
