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



if __name__ == "__main__":
    unittest.main()
