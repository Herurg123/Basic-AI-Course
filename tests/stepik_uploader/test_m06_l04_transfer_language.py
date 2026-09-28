from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L04TransferLanguageTests(unittest.TestCase):
    def test_steps_8_9_describe_new_topic_without_transfer_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L04",
        )
        task = steps[7].markdown
        check = steps[8].markdown

        self.assertIn("Решите новую задачу в другой теме", task)
        self.assertIn("Объясните, как вы действовали в новой теме", check)
        self.assertIn("использовали в этой новой теме", check)
        self.assertIn("использовать знакомый способ в новой ситуации", check)
        self.assertNotIn("Перенесите навык", task)
        self.assertNotIn("Объясните перенос", check)
        self.assertNotIn("не показывает перенос", check)


if __name__ == "__main__":
    unittest.main()
