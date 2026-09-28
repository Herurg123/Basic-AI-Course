from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class ObservableHelpBoundaryLanguageTests(unittest.TestCase):
    def test_m06_l04_uses_observable_help_events(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L04",
        )
        text = "\n".join(step.markdown for step in steps)
        self.assertIn("что именно делать, что проверять, какой вариант выбрать или какой вывод сделать", text)
        self.assertIn("не будет говорить, что именно делать в каждой ситуации", text)
        self.assertNotIn("содержательный ход", text)
        self.assertNotIn("содержательная подсказка", text)
        self.assertNotIn("содержательный маршрут", text)

    def test_m07_l01_avoids_substantive_route_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L01",
        )
        text = "\n".join(step.markdown for step in steps)
        self.assertIn("не нужно начинать новую задачу или придумывать другой способ решения", text)
        self.assertIn("сами решите, как действовать", text)
        self.assertNotIn("содержательный приём", text)
        self.assertNotIn("содержательный маршрут", text)


if __name__ == "__main__":
    unittest.main()
