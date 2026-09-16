from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.course_page_sync import (
    CoursePageSyncError,
    _same_page,
    desired_fingerprint,
    parse_course_page,
)


class CoursePageSyncTests(unittest.TestCase):
    def test_parses_current_canonical_course_page(self) -> None:
        payload = parse_course_page(Path("04_course/stepik/course-page.md"))
        self.assertEqual(
            payload["title"],
            "ИИ с нуля: не коллекция промптов, а инструмент для реальных дел",
        )
        self.assertEqual(payload["workload"], "1–2 часа в неделю")
        self.assertIn("Формулировать реальные задачи для ИИ своими словами", payload["acquired_skills"])
        self.assertIn("После курса", payload["description"])
        self.assertIn("Техническая подготовка не требуется", payload["target_audience"])
        self.assertIn("Специальные знания не нужны", payload["requirements"])
        self.assertIn("практических действий", payload["course_format"])
        self.assertTrue(desired_fingerprint(payload).startswith("sha256:"))

    def test_missing_required_section_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "course-page.md"
            path.write_text("# Карточка\n\n## 1. Название\n\n**Тест**\n", encoding="utf-8")
            with self.assertRaises(CoursePageSyncError):
                parse_course_page(path)

    def test_html_readback_attributes_do_not_create_false_drift(self) -> None:
        desired = {
            "title": "Тест",
            "summary": "Коротко",
            "acquired_skills": "Навык 1\nНавык 2",
            "description": '<p><a href="https://example.com">Описание</a></p>',
            "target_audience": "<p>Для всех</p>",
            "requirements": "<p>Нет</p>",
            "course_format": "<p>Практика</p>",
            "workload": "1–2 часа в неделю",
        }
        live = dict(desired)
        live["description"] = '<p><a target="_blank" rel="noopener" href="https://example.com">Описание</a></p>'
        self.assertTrue(_same_page(live, desired))


if __name__ == "__main__":
    unittest.main()
