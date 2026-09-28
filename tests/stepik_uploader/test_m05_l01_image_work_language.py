from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M05L01ImageWorkLanguageTests(unittest.TestCase):
    def test_lesson_uses_plain_language_for_future_image_work(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M05-L01",
        )
        full = "\n".join(step.markdown for step in steps)

        self.assertIn("сами начнёте создавать изображение в ИИ-сервисе", full)
        self.assertIn("Что пригодится в следующем уроке", full)
        self.assertIn("До первого самостоятельного создания изображения", full)
        self.assertNotIn("живая генерация", full)
        self.assertNotIn("Живая работа", full)
        self.assertNotIn("живую работу", full)


if __name__ == "__main__":
    unittest.main()
