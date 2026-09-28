from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M04L03OwnMaterialVerificationTests(unittest.TestCase):
    def test_step3_verifies_against_own_source_material(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L03",
        )
        verification = steps[2].markdown

        self.assertIn("сверьте её со своим материалом", verification)
        self.assertIn("Откройте свой исходный материал", verification)
        self.assertIn("недостаточно информации", verification)
        self.assertIn("ИИ **не проверяет собственный ответ вместо вас**", verification)
        self.assertNotIn("официальный источник", verification)
        self.assertNotIn("другой способ, которому вы уже научились", verification)


if __name__ == "__main__":
    unittest.main()
