from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L04SafetyLanguageTests(unittest.TestCase):
    def test_step1_uses_plain_language_for_real_world_risk_boundary(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L04",
        )
        opening = steps[0].markdown

        self.assertNotIn("high-stakes", opening)
        self.assertIn("важных реальных решений", opening)
        self.assertIn("здоровья, безопасности, денег или прав человека", opening)


if __name__ == "__main__":
    unittest.main()
