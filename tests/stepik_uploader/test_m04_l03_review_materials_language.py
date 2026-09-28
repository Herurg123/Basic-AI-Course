from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M04L03ReviewMaterialsLanguageTests(unittest.TestCase):
    def test_step4_names_concrete_work_materials_instead_of_artifacts(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L03",
        )
        review = steps[3].markdown

        self.assertIn("Свой материал, ИИ-чат и другие материалы", review)
        self.assertIn("полученный результат, изменённая версия материала или ваша заметка", review)
        self.assertNotIn("другие артефакты", review)


if __name__ == "__main__":
    unittest.main()
