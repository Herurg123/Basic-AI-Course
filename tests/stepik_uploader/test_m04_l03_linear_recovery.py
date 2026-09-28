from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_lesson_source,
)


ROOT = Path(__file__).resolve().parents[2]


class M04L03LinearRecoveryTests(unittest.TestCase):
    def _steps(self):
        return compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M04-L03",
        )

    def test_route_has_seven_forward_steps(self) -> None:
        steps = self._steps()
        self.assertEqual(len(steps), 7)
        self.assertEqual([step.position for step in steps], list(range(1, 8)))
        self.assertEqual(steps[4].semantic_type, "CHECK")
        self.assertEqual(steps[5].semantic_type, "RECOVERY")
        self.assertEqual(steps[6].semantic_type, "REFLECTION")

    def test_recovery_does_not_send_learner_back_to_old_stepik_answers(self) -> None:
        steps = self._steps()
        recovery = steps[5].markdown
        reflection = steps[6].markdown

        self.assertIn("К прежним ответам в Stepik не возвращайтесь", recovery)
        self.assertIn("После завершения переходите только к следующему шагу", recovery)
        self.assertIn("К прежним ответам в Stepik не возвращайтесь", reflection)
        self.assertNotIn("/lesson/2591723/step/4", recovery)
        self.assertNotIn("/lesson/2591723/step/5", recovery)

    def test_post_recovery_reflection_is_local_and_conditional(self) -> None:
        reflection = self._steps()[6].markdown
        self.assertIn("Если новая попытка", reflection)
        self.assertIn("не нужно снова работать с ИИ", reflection)
        self.assertIn("что-либо писать в Stepik", reflection)
        self.assertIn("обычной учебной заметке", reflection)
        self.assertIn("Что взять с собой дальше", reflection)


if __name__ == "__main__":
    unittest.main()
