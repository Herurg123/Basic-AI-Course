from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L04UnavailableSourceRecoveryTests(unittest.TestCase):
    def test_recovery_does_not_allow_second_ai_to_replace_source(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L04",
        )
        recovery = steps[4].markdown

        self.assertIn(
            "не заменяйте его ответом другого ИИ",
            recovery,
        )
        self.assertIn(
            "Для каждой такой ситуации используйте соответствующий новый случай ниже",
            recovery,
        )


if __name__ == "__main__":
    unittest.main()
