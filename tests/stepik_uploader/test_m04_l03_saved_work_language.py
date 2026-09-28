from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M04L03SavedWorkLanguageTests(unittest.TestCase):
    def test_step2_names_concrete_saved_objects_without_extra_report(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L03",
        )
        practice = steps[1].markdown

        self.assertIn("сообщения в ИИ-чате", practice)
        self.assertIn("полученный результат", practice)
        self.assertIn("Специальный отчёт для этого создавать не нужно", practice)
        self.assertNotIn("сохраните естественный след своей работы", practice)


if __name__ == "__main__":
    unittest.main()
