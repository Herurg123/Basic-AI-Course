from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M03L02InterfacePrincipleLanguageTests(unittest.TestCase):
    def test_step8_uses_plain_common_principle_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M03-L02",
        )
        check = steps[7].markdown

        self.assertIn("Опишите общий принцип своими словами", check)
        self.assertIn("по смыслу одинаково в обоих ИИ-сервисах", check)
        self.assertNotIn("Ответьте о переносе", check)
        self.assertNotIn("перенос навыка", check)


if __name__ == "__main__":
    unittest.main()
