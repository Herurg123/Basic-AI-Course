from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L01SourceCriterionLanguageTests(unittest.TestCase):
    def test_step5_reuses_plain_source_criterion(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )
        verification = steps[4].markdown

        self.assertIn(
            "выберите подходящий источник от того, кто отвечает за эту информацию",
            verification,
        )
        self.assertNotIn("официальный или первичный источник", verification)


if __name__ == "__main__":
    unittest.main()
