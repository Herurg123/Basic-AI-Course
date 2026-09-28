from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M03L02SummaryLanguageTests(unittest.TestCase):
    def test_final_summary_describes_independence_without_internal_term(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L02",
        )
        final = steps[-1].markdown

        self.assertIn("самостоятельно решить новую задачу", final)
        self.assertIn("курс заранее не говорит, что именно делать", final)
        self.assertNotIn("без содержательного ведения", final)


if __name__ == "__main__":
    unittest.main()
