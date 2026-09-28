from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L01SourceLanguageTests(unittest.TestCase):
    def test_step4_uses_observable_source_search_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )
        source_search = steps[3].markdown

        self.assertIn("Найдите источник, который отвечает за нужную информацию", source_search)
        self.assertIn("страницу самого продукта", source_search)
        self.assertIn("короткому тексту, который поисковик показывает рядом со ссылкой", source_search)
        self.assertIn("формулировкой поискового запроса", source_search)
        self.assertNotIn("источник первого уровня", source_search)
        self.assertNotIn("официальный домен", source_search)
        self.assertNotIn("поисковым фрагментом", source_search)


if __name__ == "__main__":
    unittest.main()
