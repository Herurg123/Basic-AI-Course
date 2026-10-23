from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M06L01ForwardRecoveryTests(unittest.TestCase):
    def test_step8_recovery_does_not_rewrite_step7(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )
        self.assertEqual(len(steps), 8)
        recovery = steps[7].markdown

        # Повтор нужен при неоткрытом источнике или несделанной сверке,
        # но не при честной нехватке данных в прочитанном источнике.
        self.assertIn("**Новая попытка не нужна**", recovery)
        self.assertIn("**Новая попытка нужна**", recovery)
        self.assertIn("не нашли подходящий источник", recovery)
        self.assertIn("не смогли его открыть", recovery)
        self.assertIn("открыли источник, но так и не сравнили", recovery)
        self.assertIn("Даже если нужных сведений оказалось мало", recovery)
        self.assertIn("Неважно, когда вы обнаружили проблему", recovery)
        self.assertIn("Прежний ответ в Stepik не меняйте", recovery)
        self.assertIn("не возвращайтесь к ответу в шаге 7", recovery)
        self.assertIn("Дополнительно отвечать в Stepik по новой попытке не нужно", recovery)
        self.assertNotIn("ответьте в шаге 7 уже по фактически проверенной работе", recovery)

    def test_no_source_is_reported_honestly_before_recovery(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M06-L01",
        )
        self.assertEqual(len(steps), 8)
        search, verification, check = steps[3].markdown, steps[4].markdown, steps[6].markdown

        self.assertIn("Не нашли подходящий источник или он не открывается?", search)
        self.assertIn("Повторять задание только из-за этого не нужно", search)
        self.assertIn("Если источник найти или открыть не удалось, сравнивать пока нечего", verification)
        self.assertIn("Не смогли найти или открыть источник?", check)
        self.assertIn("Не придумывайте ссылку, цитату или сведения", check)
        self.assertIn("После ответа переходите к шагу 8", check)
        self.assertNotIn("во втором выделенном блоке", search)


if __name__ == "__main__":
    unittest.main()
