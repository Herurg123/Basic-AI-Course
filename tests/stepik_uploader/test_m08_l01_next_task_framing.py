from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M08L01NextTaskFramingTests(unittest.TestCase):
    def test_step3_uses_plain_language_instead_of_framework_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M08-L01",
        )
        framing = steps[2].markdown

        self.assertIn("что пригодится в следующей задаче и насколько она сложна", framing)
        self.assertIn("чтобы спокойно обдумать будущую задачу", framing)
        self.assertNotIn("рамку переноса и сложности", framing)
        self.assertNotIn("рамку размышления", framing)


if __name__ == "__main__":
    unittest.main()
