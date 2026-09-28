from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M05L02PromptLanguageTests(unittest.TestCase):
    def test_step4_uses_plain_russian_term_before_prompt(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M05-L02",
        )
        generation = steps[3].markdown

        self.assertIn("«идеального запроса» (промпта)", generation)
        self.assertNotIn("«идеального промпта»", generation)


if __name__ == "__main__":
    unittest.main()
