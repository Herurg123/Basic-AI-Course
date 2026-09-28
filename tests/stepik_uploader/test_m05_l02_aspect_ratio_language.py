from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M05L02AspectRatioLanguageTests(unittest.TestCase):
    def test_recovery_explains_16x9_in_plain_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M05-L02",
        )
        recovery = steps[9].markdown

        self.assertIn("формата 16:9", recovery)
        self.assertIn("широкую прямоугольную картинку", recovery)


if __name__ == "__main__":
    unittest.main()
