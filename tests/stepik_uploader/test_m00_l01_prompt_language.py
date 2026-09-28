from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M00L01PromptLanguageTests(unittest.TestCase):
    def test_opening_introduces_prompt_after_plain_russian_term(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M00-L01",
        )
        opening = steps[0].markdown

        self.assertIn("«идеальный запрос» (промпт)", opening)
        self.assertNotIn("«идеальный промпт»", opening)


if __name__ == "__main__":
    unittest.main()
