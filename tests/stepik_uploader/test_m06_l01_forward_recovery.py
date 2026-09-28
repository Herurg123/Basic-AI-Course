from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L01ForwardRecoveryTests(unittest.TestCase):
    def test_step8_recovery_does_not_rewrite_step7(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )
        self.assertEqual(len(steps), 8)
        recovery = steps[7].markdown

        self.assertIn("Этот шаг нужен **не всем**", recovery)
        self.assertIn("прежний ответ не переписывайте", recovery)
        self.assertIn("не возвращайтесь к ответу в шаге 7", recovery)
        self.assertIn("Дополнительно отвечать в Stepik по новой попытке не нужно", recovery)
        self.assertIn("данных недостаточно", recovery)
        self.assertNotIn("ответьте в шаге 7 уже по фактически проверенной работе", recovery)


if __name__ == "__main__":
    unittest.main()
