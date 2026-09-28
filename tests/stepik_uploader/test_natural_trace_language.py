from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]
LESSONS = ("M03-L02", "M06-L04", "M07-L01", "M07-L02")


class NaturalTraceLanguageTests(unittest.TestCase):
    def test_learner_lessons_do_not_use_natural_trace_jargon(self) -> None:
        for lesson_id in LESSONS:
            with self.subTest(lesson_id=lesson_id):
                steps = compile_lesson_source(
                    ROOT,
                    free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                    lesson_id=lesson_id,
                )
                learner_text = "\n".join(step.markdown for step in steps)
                self.assertNotIn("естественный след", learner_text.lower())

    def test_plain_material_language_remains(self) -> None:
        m03 = "\n".join(
            step.markdown
            for step in compile_lesson_source(
                ROOT,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id="M03-L02",
            )
        )
        m06 = "\n".join(
            step.markdown
            for step in compile_lesson_source(
                ROOT,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id="M06-L04",
            )
        )
        m07a = "\n".join(
            step.markdown
            for step in compile_lesson_source(
                ROOT,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id="M07-L01",
            )
        )
        m07b = "\n".join(
            step.markdown
            for step in compile_lesson_source(
                ROOT,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id="M07-L02",
            )
        )

        self.assertIn("то, что и так появляется при решении задачи", m03)
        self.assertIn("материалы, которые появляются во время работы", m06)
        self.assertIn("то, что появляется во время работы", m07a)
        self.assertIn("Сохраняйте материалы по ходу работы, а не отдельный отчёт", m07b)


if __name__ == "__main__":
    unittest.main()
