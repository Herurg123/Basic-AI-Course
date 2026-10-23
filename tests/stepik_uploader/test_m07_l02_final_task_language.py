from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M07L02FinalTaskLanguageTests(unittest.TestCase):
    def test_step1_uses_plain_task_language_instead_of_case_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L02",
        )
        opening = steps[0].markdown

        self.assertIn("Готовой задачи с заранее заданной ситуацией", opening)
        self.assertNotIn("экзаменационного кейса", opening)

    def test_final_check_has_one_complete_set_of_seven_questions(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L02",
        )
        check = steps[5].markdown
        self.assertIn("**Ответьте в Stepik на семь вопросов:**", check)
        self.assertEqual(7, sum(
            line.startswith(f"{n}. **") for n in range(1, 8)
            for line in check.splitlines()
        ))
        for meaning in (
            "где действительно использовали результат",
            "ещё до проверки первой версии",
            "как изменился результат",
            "1–3 важных решения",
            "как это повлияло на результат",
            "что это безопасно и нужно для задачи",
            "техническими действиями",
            "если по ним видно, что вы определились с ними ещё тогда",
            "первая попытка остаётся тренировочной",
        ):
            self.assertIn(meaning, check)
        # A03 does not duplicate the questions: no second list of evaluation prompts.
        preamble = check.split("**Ответьте в Stepik на семь вопросов:**", 1)[0]
        self.assertIn("Памятка перед ответом", preamble)
        self.assertNotIn("## Что вы сделали", preamble)



if __name__ == "__main__":
    unittest.main()
