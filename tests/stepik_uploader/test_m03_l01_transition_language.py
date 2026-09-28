from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M03L01TransitionLanguageTests(unittest.TestCase):
    def test_final_transition_uses_plain_next_action_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L01",
        )
        final = steps[-1].markdown

        self.assertIn("самостоятельно решить, что делать дальше", final)
        self.assertNotIn("содержательный ход", final)


if __name__ == "__main__":
    unittest.main()
