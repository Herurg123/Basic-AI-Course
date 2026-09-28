from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M04L02CompletionRouteTests(unittest.TestCase):
    def test_independent_privacy_task_has_one_explicit_completion(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L02",
        )
        practice = steps[3].markdown
        check = steps[4].markdown

        self.assertIn("Задание закончено, когда у вас есть", practice)
        self.assertIn("короткая нейтральная запись для общего списка встреч", practice)
        self.assertIn("Сохраните оба результата у себя", practice)
        self.assertIn("если вы решили вообще не передавать материал", practice.lower())
        self.assertIn("два результата предыдущего шага", check)
        self.assertIn("готовую короткую запись для общего списка встреч", check)


if __name__ == "__main__":
    unittest.main()
