from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L02TechnicalHelpTimingTests(unittest.TestCase):
    def test_calculator_help_appears_before_calculation_and_final_step_is_summary(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L02",
        )
        verification = steps[2].markdown
        final = steps[-1].markdown

        self.assertIn("как выполнить уже выбранное вычисление в калькуляторе", verification)
        self.assertIn("Как ввести это выражение в калькулятор?", verification)
        self.assertIn("Когда механика понятна, выполните расчёт самостоятельно", verification)
        self.assertIn("Что взять с собой дальше", final)
        self.assertIn("какие числа вообще должны попасть в расчёт", final)
        self.assertNotIn("Если нужна техническая помощь", final)


if __name__ == "__main__":
    unittest.main()
