from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L04ReviewLanguageTests(unittest.TestCase):
    def test_step4_uses_plain_post_action_language(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L04",
        )
        review = steps[3].markdown

        self.assertIn("откройте сохранённые материалы своей работы", review)
        self.assertIn("что в исходном ответе, переданном материале или видимых действиях сервиса", review)
        self.assertIn("к какому выводу пришли", review)
        self.assertIn("позднее объяснение не превращает в выполненное действие", review)
        self.assertIn("до или во время работы", review)
        self.assertNotIn("наблюдаемо", review)
        self.assertNotIn("существующий ранний след", review)
        self.assertNotIn("подтвердить фактической предыдущей работой", review)


if __name__ == "__main__":
    unittest.main()
