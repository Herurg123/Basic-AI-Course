from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]
TASK_CARD = ROOT / "05_assets/M07/M07-L02/M07-L02-A01.md"


class RemainingProfessionalJargonTests(unittest.TestCase):
    def test_m07_l02_task_card_uses_plain_language(self) -> None:
        text = TASK_CARD.read_text(encoding="utf-8")
        self.assertIn("какие задачи подходят для финальной самостоятельной работы", text)
        self.assertIn("готовую учебную ситуацию", text)
        self.assertNotIn("класс задачи", text)
        self.assertNotIn("экзаменационный кейс", text)

    def test_m08_l01_final_reflection_uses_plain_objects(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M08-L01",
        )
        text = "\n".join(step.markdown for step in steps)
        self.assertIn("Это итоговое размышление", text)
        self.assertIn("Создавать новый файл или другой результат", text)
        self.assertNotIn("Новый артефакт", text)


if __name__ == "__main__":
    unittest.main()
