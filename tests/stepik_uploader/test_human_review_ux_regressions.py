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


if __name__ == "__main__":
    unittest.main()
