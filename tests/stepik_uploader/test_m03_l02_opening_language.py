from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M03L02OpeningLanguageTests(unittest.TestCase):
    def test_step1_describes_missing_support_in_plain_actions(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L02",
        )
        opening = steps[0].markdown

        self.assertIn(
            "курс не будет заранее подсказывать, на что обратить внимание и что делать дальше",
            opening,
        )
        self.assertNotIn("содержательной опоры", opening)


if __name__ == "__main__":
    unittest.main()
