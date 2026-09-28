from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M03L02RecoveryLanguageTests(unittest.TestCase):
    def test_step6_uses_observable_entry_conditions(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L02",
        )
        recovery = steps[5].markdown

        self.assertIn("Этот шаг нужен **не всем**", recovery)
        self.assertIn("до или во время работы", recovery)
        self.assertIn("вы открыли вопросы предыдущего шага", recovery)
        self.assertIn("существует только в вашем объяснении сейчас", recovery)
        self.assertIn("Если ничего из этого не произошло", recovery)
        self.assertNotIn("попытка стала тренировочной", recovery)
        self.assertNotIn("предыдущая попытка подтверждена", recovery)
        self.assertNotIn("загрязнена подсказкой", recovery)


if __name__ == "__main__":
    unittest.main()
