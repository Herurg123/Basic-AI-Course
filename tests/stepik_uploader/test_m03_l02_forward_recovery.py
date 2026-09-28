from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_lesson_source,
)


ROOT = Path(__file__).resolve().parents[2]


class M03L02ForwardRecoveryTests(unittest.TestCase):
    def test_recovery_transition_does_not_promise_missing_review(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L02",
        )
        self.assertEqual(len(steps), 9)
        recovery = steps[5].markdown
        transfer = steps[6].markdown

        self.assertIn("переходите дальше", recovery)
        self.assertIn("не возвращайтесь", recovery)
        self.assertIn("Дополнительно отвечать о ней в Stepik сейчас не нужно", recovery)
        self.assertIn("в следующем шаге вы сравните интерфейсы двух ИИ-сервисов", recovery)
        self.assertNotIn("отдельно разберёте именно её", recovery)

        self.assertIn("сравните два подготовленных снимка", transfer)
        self.assertIn("снимок Алисы AI", transfer)
        self.assertIn("снимок GigaChat", transfer)


if __name__ == "__main__":
    unittest.main()
