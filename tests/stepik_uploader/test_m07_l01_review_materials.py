from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M07L01ReviewMaterialsTests(unittest.TestCase):
    def test_step6_names_real_materials_instead_of_single_natural_trace_object(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L01",
        )
        review = steps[5].markdown

        self.assertIn("Учебная доска сообщений", review)
        self.assertIn("ИИ-чат, в котором выполняли задачу", review)
        self.assertIn("другие материалы, которые действительно использовали или сохраняли", review)
        self.assertIn("Специально создавать новые доказательства или отчёт сейчас не нужно", review)
        self.assertNotIn("откройте финальную заметку и свой естественный след", review)


if __name__ == "__main__":
    unittest.main()
