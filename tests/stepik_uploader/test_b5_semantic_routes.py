from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_lesson_source,
)


ROOT = Path(__file__).resolve().parents[2]


class B5SemanticRouteTests(unittest.TestCase):
    def _steps(self, lesson_id: str):
        return compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id=lesson_id,
        )

    def test_m06_l03_stages_cards_without_inline_scope_spill(self) -> None:
        steps = self._steps("M06-L03")
        self.assertEqual(len(steps), 6)

        first = steps[1]
        second = steps[3]

        self.assertEqual(
            first.unresolved_repo_links,
            ("../../../05_assets/M06/M06-L03/M06-L03-A01.md",),
        )
        self.assertNotIn("школьной мастерской «Куб»", first.markdown)
        self.assertEqual(second.unresolved_repo_links, ())
        self.assertIn("школьной мастерской «Куб»", second.markdown)

    def test_m06_l04_keeps_forward_recovery_eleven_step_route_shape(self) -> None:
        steps = self._steps("M06-L04")
        self.assertEqual(len(steps), 11)
        self.assertEqual(
            [step.block_name for step in steps],
            [
                "text",
                "text",
                "text",
                "free-answer",
                "text",
                "text",
                "free-answer",
                "text",
                "free-answer",
                "text",
                "text",
            ],
        )
        self.assertEqual(steps[2].exercise_ids, ("M06-L04-E01",))
        self.assertEqual(steps[3].check_ids, ("M06-L04-C01",))
        self.assertEqual(steps[5].exercise_ids, ("M06-L04-E02",))
        self.assertEqual(steps[6].check_ids, ("M06-L04-C02",))
        self.assertEqual(steps[8].check_ids, ("M06-L04-C03",))

    def test_m06_l04_hides_post_action_rubric_before_e01(self) -> None:
        steps = self._steps("M06-L04")
        pre_action = "\n".join(step.markdown for step in steps[:3])
        post_check = steps[3].markdown

        for leaked in (
            "наблюдаемо",
            "не установлено",
            "какое основание для проверки",
            "что именно сопоставили",
            "какой статус выбрали",
        ):
            self.assertNotIn(leaked, pre_action, leaked)

        self.assertIn("не установлено", post_check)
        self.assertIn("какое основание для проверки", post_check)
        self.assertIn("какой статус выбрали", post_check)

    def test_m06_l04_application_form_and_recovery_targets_are_post_action(self) -> None:
        steps = self._steps("M06-L04")

        a03 = "../../../05_assets/M06/M06-L04/M06-L04-A03.md"
        self.assertTrue(all(a03 not in step.unresolved_repo_links for step in steps[:6]))
        self.assertIn(a03, steps[6].unresolved_repo_links)

        self.assertNotIn("/lesson/2591729/step/4", steps[4].markdown)
        self.assertNotIn("/lesson/2591729/step/9", steps[9].markdown)
        self.assertIn("Прежний ответ в Stepik не редактируйте", steps[5].markdown)
        self.assertNotIn("Win + V", "\n".join(step.markdown for step in steps[:9]))
        self.assertIn("Win + V", steps[9].markdown)
        self.assertIn("Прежний ответ в Stepik не редактируйте", steps[10].markdown)


if __name__ == "__main__":
    unittest.main()
