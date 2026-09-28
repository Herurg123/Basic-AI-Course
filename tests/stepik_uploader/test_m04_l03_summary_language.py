from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M04L03SummaryLanguageTests(unittest.TestCase):
    def test_summary_uses_plain_observable_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L03",
        )
        text = "\n".join(step.markdown for step in steps)

        self.assertIn(
            "сами выбрали безопасный материал и небольшую задачу",
            text,
        )
        self.assertIn(
            "какой материал выбрать, какую задачу решить, что проверить и что делать с результатом",
            text,
        )
        self.assertNotIn("самостоятельная проверка существенного", text)
        self.assertNotIn("содержательного следующего хода", text)
        self.assertNotIn("Содержательный выбор", text)


if __name__ == "__main__":
    unittest.main()
