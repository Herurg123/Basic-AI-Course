from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LESSON_PATHS = sorted((ROOT / "04_course").glob("M*/M*-L*/lesson.md"))
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
CHECK_MARKER_RE = re.compile(r"<!--\s*Check:\s*M\d{2}-L\d{2}-C\d{2}\s*-->")


def _visible_markdown(text: str) -> str:
    without_comments = HTML_COMMENT_RE.sub("", text)
    return MARKDOWN_LINK_RE.sub(lambda match: match.group(1), without_comments)


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker)
    next_heading = text.find("\n## ", start + len(marker))
    return text[start:] if next_heading == -1 else text[start:next_heading]


class HumanReviewUxRegressionTests(unittest.TestCase):
    def test_all_21_lessons_are_present(self) -> None:
        self.assertEqual(len(LESSON_PATHS), 21)

    def test_no_stale_inline_material_promises_or_visible_md_extension(self) -> None:
        stale_patterns = (
            re.compile(r"будет показан[аоы]?\s+ниже", re.IGNORECASE),
            re.compile(r"будут показаны\s+ниже", re.IGNORECASE),
            re.compile(r"котор(?:ый|ая|ое|ые)\s+будет показан", re.IGNORECASE),
            re.compile(r"котор(?:ые|ая|ый|ое)\s+будут показаны", re.IGNORECASE),
            re.compile(r"(?<![\w.])\.md(?![\w.])", re.IGNORECASE),
        )
        offenders: list[str] = []
        for path in LESSON_PATHS:
            visible = _visible_markdown(path.read_text(encoding="utf-8"))
            for number, line in enumerate(visible.splitlines(), start=1):
                for pattern in stale_patterns:
                    if pattern.search(line):
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
                        )
        self.assertEqual(
            [],
            offenders,
            "Learner-facing stale inline-material wording survived:\n" + "\n".join(offenders),
        )

    def test_stepik_free_answer_headings_do_not_promise_external_check(self) -> None:
        offenders: list[str] = []
        for path in LESSON_PATHS:
            lines = path.read_text(encoding="utf-8").splitlines()
            for index, line in enumerate(lines):
                if not CHECK_MARKER_RE.search(line):
                    continue
                heading = ""
                for previous in range(index - 1, -1, -1):
                    if lines[previous].startswith("## "):
                        heading = lines[previous][3:].strip()
                        break
                if heading.lower().startswith("проверьте"):
                    offenders.append(
                        f"{path.relative_to(ROOT)}: {heading}"
                    )
        self.assertEqual(
            [],
            offenders,
            "Free-answer heading sounds like an external Stepik verdict:\n"
            + "\n".join(offenders),
        )

    def test_unaddressed_technical_help_phrase_is_absent(self) -> None:
        offenders: list[str] = []
        for path in LESSON_PATHS:
            visible = _visible_markdown(path.read_text(encoding="utf-8"))
            for number, line in enumerate(visible.splitlines(), start=1):
                if re.search(r"\bможно спросить\b", line, re.IGNORECASE):
                    has_addressee = any(
                        token in line.lower()
                        for token in ("преподавател", "куратор", "ии", "чат")
                    )
                    if not has_addressee:
                        offenders.append(
                            f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
                        )
        self.assertEqual(
            [],
            offenders,
            "Technical-help wording has no explicit addressee:\n" + "\n".join(offenders),
        )

    def test_source_only_material_cards_do_not_reabsorb_lesson_instructions(self) -> None:
        forbidden_by_path = {
            "05_assets/M01/M01-L01/M01-L01-A01.md": ("После ответа проверьте",),
            "05_assets/M01/M01-L01/M01-L01-A02.md": ("Откройте эту карточку", "Сравните текст с требованиями"),
            "05_assets/M01/M01-L02/M01-L02-A02.md": ("Сначала решите сами", "откройте предоставленный исходник"),
            "05_assets/M01/M01-L02/M01-L02-A03.md": ("Перечитайте исходник", "присвойте статус"),
            "05_assets/M02/M02-L01/M02-L01-A01.md": ("Сформулируйте своими словами",),
            "05_assets/M02/M02-L02/M02-L02-A01.md": ("Сначала отправьте ИИ", "Получите новую версию"),
            "05_assets/M03/M03-L01/M03-L01-A01.md": ("Сначала сами решите",),
            "05_assets/M03/M03-L02/M03-L02-A01.md": ("Используйте ИИ, чтобы решить",),
            "05_assets/M03/M03-L02/M03-L02-A02.md": ("Открывайте эту карточку", "Рассматривайте этот текст"),
            "05_assets/M04/M04-L02/M04-L02-A01.md": ("До передачи ИИ самостоятельно решите",),
            "05_assets/M05/M05-L02/M05-L02-A01-part1.md": ("Сформулируйте своё описание", "Сохраните свой запрос"),
            "05_assets/M05/M05-L02/M05-L02-A01-part2.md": ("Сами сравните", "Не создавайте новую похожую"),
            "05_assets/M06/M06-L01/M06-L01-A01.md": ("Сами решите, какое внешнее утверждение",),
            "05_assets/M06/M06-L02/M06-L02-A01.md": ("## Ваша задача", "По заданию урока сами решите"),
            "05_assets/M06/M06-L03/M06-L03-A01.md": ("Самостоятельно решите:",),
        }
        offenders: list[str] = []
        for relative, forbidden in forbidden_by_path.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase.lower() in text.lower():
                    offenders.append(f"{relative}: {phrase}")
        self.assertEqual([], offenders, "Lesson instructions leaked back into source-only material cards:\n" + "\n".join(offenders))

    def test_early_ai_work_names_the_expected_result(self) -> None:
        m01 = (ROOT / "04_course/M01/M01-L01/lesson.md").read_text(encoding="utf-8")
        m02 = (ROOT / "04_course/M02/M02-L02/lesson.md").read_text(encoding="utf-8")
        m03 = (ROOT / "04_course/M03/M03-L02/lesson.md").read_text(encoding="utf-8")
        self.assertIn("короткий текст-напоминание", m01)
        self.assertIn("короткий текст приглашения", m02)
        self.assertIn("пригодный порядок действий", m03)
        self.assertIn("Ничего делать с ИИ на этом шаге не нужно", m03)
        self.assertIn("Найдите общий принцип в интерфейсах различных ИИ-сервисов", m03)
        self.assertIn("[снимок Алисы AI](../../../05_assets/M03/M03-L02/M03-L02-A03-alice.png)", m03)
        self.assertIn("[снимок GigaChat](../../../05_assets/M03/M03-L02/M03-L02-A03.png)", m03)
        self.assertNotIn("откройте **только один**", m03.lower())



    def test_beginner_copyedit_makes_action_location_and_finish_explicit(self) -> None:
        m02 = (ROOT / "04_course/M02/M02-L02/lesson.md").read_text(encoding="utf-8")
        m03 = (ROOT / "04_course/M03/M03-L02/lesson.md").read_text(encoding="utf-8")
        m04 = (ROOT / "04_course/M04/M04-L03/lesson.md").read_text(encoding="utf-8")
        m05 = (ROOT / "04_course/M05/M05-L02/lesson.md").read_text(encoding="utf-8")
        m06 = (ROOT / "04_course/M06/M06-L01/lesson.md").read_text(encoding="utf-8")
        m07 = (ROOT / "04_course/M07/M07-L02/lesson.md").read_text(encoding="utf-8")
        form = (ROOT / "05_assets/M07/M07-L02/M07-L02-A03.md").read_text(encoding="utf-8")

        m02_step = _section(m02, "Получите первый вариант и сами решите, что уточнить")
        self.assertIn("Что делать:", m02_step)
        self.assertIn("Шаг завершён", m02_step)
        self.assertIn("одно осмысленное следующее сообщение", m02_step)

        m03_step = _section(m03, "Разберите уже выполненную попытку")
        self.assertIn("Ничего нового отправлять ИИ здесь не нужно", m03_step)
        self.assertIn("ИИ-чат", m03_step)
        self.assertIn("в поле Stepik", m03_step)
        self.assertNotIn("Артефакты", m03_step)
        self.assertNotIn("естественный след", m03_step.lower())

        m04_step = _section(m04, "Найдите в ответе один важный факт и проверьте его")
        self.assertIn("не нужно выбирать из готового списка", m04_step)
        self.assertIn("ИИ **не должен проверять сам себя вместо вас**", m04_step)
        self.assertIn("Шаг завершён", m04_step)

        m05_step = _section(m05, "Узнайте новое назначение и сами решите, что изменить")
        self.assertIn("пока ничего не редактируйте в ИИ-сервисе", m05_step)
        self.assertIn("в следующем шаге", m05_step)
        self.assertNotIn("Сама карточка останавливается", m05_step)

        m06_explain = _section(m06, "Сначала поймите, на что на самом деле опирается ответ ИИ")
        m06_practice = _section(m06, "Определите, на что можно опереться в трёх примерах")
        self.assertIn("слово **«основание»** означает", m06_explain)
        self.assertIn("ничего отправлять ии не нужно", m06_explain.lower())
        self.assertIn("ИИ открывать не нужно", m06_practice)
        self.assertIn("не проверяете сами факты", m06_practice)

        m07_step = _section(m07, "Разберите уже выполненную финальную работу")
        self.assertIn("не нужно снова работать с ИИ", m07_step)
        self.assertIn("не новый пример, не тренировка", m07_step)
        self.assertIn("ответьте в поле Stepik", m07_step)
        self.assertIn("Файлы, изображения и скриншоты в Stepik загружать не нужно", m07_step)

        self.assertTrue(form.startswith("# Вопросы для разбора финальной работы"))
        self.assertIn("не новый пример, не отдельное упражнение и не файл для заполнения", form)
        self.assertIn("Ничего отправлять ИИ здесь не нужно", form)
        self.assertNotIn("естественный след", form.lower())



if __name__ == "__main__":
    unittest.main()
