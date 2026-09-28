from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M07L02HelpBoundaryLanguageTests(unittest.TestCase):
    def test_step3_uses_concrete_help_boundary_without_internal_attempt_labels(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L02",
        )
        help_step = steps[2].markdown

        self.assertIn("Какая помощь допустима во время самостоятельной работы", help_step)
        self.assertIn("что делать дальше", help_step)
        self.assertIn("что именно проверять", help_step)
        self.assertIn("что изменить в результате", help_step)
        self.assertIn("После разбора курс объяснит, как поступить дальше", help_step)
        self.assertNotIn("содержательный следующий ход", help_step)
        self.assertNotIn("делает затронутую попытку тренировочной", help_step)


if __name__ == "__main__":
    unittest.main()
