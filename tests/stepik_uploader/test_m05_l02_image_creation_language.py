from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M05L02ImageCreationLanguageTests(unittest.TestCase):
    def test_lesson_uses_plain_language_for_created_images(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M05-L02",
        )
        full = "\n".join(step.markdown for step in steps)

        self.assertIn("два результата, которые вы получите сами", full)
        self.assertIn("Создайте первую версию изображения", full)
        self.assertIn("Зафиксируйте создание изображения в Stepik", full)
        self.assertIn("изображение, которое вы создали сами", full)
        self.assertNotIn("живых результатов", full)
        self.assertNotIn("живую первую версию", full)
        self.assertNotIn("первую живую версию", full)
        self.assertNotIn("живую генерацию", full)


if __name__ == "__main__":
    unittest.main()
