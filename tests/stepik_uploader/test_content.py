from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.content import TEST_LESSON_ID, compile_test_lesson


class ContentCompilerTests(unittest.TestCase):
    def test_real_m02_l01_compiles_to_golden_compatible_shape(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        steps = compile_test_lesson(
            repo_root,
            free_answer_source={
                "is_attachments_enabled": False,
                "is_html_enabled": True,
                "manual_scoring": False,
            },
            lesson_id=TEST_LESSON_ID,
        )
        self.assertEqual([step.position for step in steps], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            [step.block_name for step in steps],
            ["text", "text", "text", "text", "free-answer", "text"],
        )
        self.assertIn("Ситуация 1 — с большей поддержкой", steps[1].text)
        self.assertIn("Ситуация 2 — с меньшей поддержкой", steps[3].text)
        self.assertIn('href="https://alice.yandex.ru/"', steps[1].text)
        self.assertNotIn("../../../05_assets/", "\n".join(step.text for step in steps))
        self.assertEqual(
            steps[4].source,
            {
                "is_attachments_enabled": False,
                "is_html_enabled": True,
                "manual_scoring": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
