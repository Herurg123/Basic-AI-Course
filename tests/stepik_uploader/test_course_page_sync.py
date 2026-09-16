from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.stepik_uploader.course_page_sync import (
    CoursePageSyncError,
    REQUIRED_FIELDS,
    _same_page,
    assert_preserved_course_state,
    course_page_write_payload,
    desired_fingerprint,
    parse_course_page,
    preserved_course_state,
)


class CoursePageSyncTests(unittest.TestCase):
    def test_parses_current_canonical_course_page(self) -> None:
        payload = parse_course_page(Path("04_course/stepik/course-page.md"))
        self.assertEqual(
            payload["title"],
            "ИИ с нуля: не коллекция промптов, а инструмент для реальных дел",
        )
        self.assertEqual(payload["workload"], "1–2 часа в неделю.")
        self.assertEqual(payload["difficulty"], "easy")
        self.assertIsInstance(payload["acquired_skills"], list)
        self.assertIsInstance(payload["acquired_assets"], list)
        self.assertIn("Формулировать реальные задачи для ИИ своими словами", payload["acquired_skills"])
        self.assertIn("Практический навык работы с современным ИИ с нулевого уровня", payload["acquired_assets"])
        self.assertIn("После курса", payload["description"])
        self.assertIn("Техническая подготовка не требуется", payload["target_audience"])
        self.assertIn("Специальные знания не нужны", payload["requirements"])
        self.assertIn("практических действий", payload["learning_format"])
        self.assertNotIn("course_format", payload)
        self.assertTrue(desired_fingerprint(payload).startswith("sha256:"))

    def test_write_payload_is_full_raw_get_read_modify_write(self) -> None:
        desired = parse_course_page(Path("04_course/stepik/course-page.md"))
        live = deepcopy(desired)
        live.update(
            {
                "id": 299189,
                "title": "Старое название",
                "sections": [101, 102],
                "owner": 7,
                "authors": [7],
                "instructors": [7],
                "tags": [10, 11],
                "language": "ru",
                "is_public": False,
                "is_paid": False,
                "course_format": "legacy Stepik field",
                "update_date": "server-managed-value",
                "custom_returned_field": {"must": "survive"},
            }
        )
        payload = course_page_write_payload(live, desired)
        self.assertEqual(set(payload), set(live))
        for field in REQUIRED_FIELDS:
            self.assertEqual(payload[field], desired[field])
        self.assertIsInstance(payload["acquired_skills"], list)
        self.assertIsInstance(payload["acquired_assets"], list)
        self.assertIn("learning_format", payload)
        self.assertEqual(payload["course_format"], "legacy Stepik field")
        self.assertEqual(payload["sections"], [101, 102])
        self.assertEqual(payload["custom_returned_field"], {"must": "survive"})

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
            "acquired_skills": ["Навык 1", "Навык 2"],
            "acquired_assets": ["Результат 1", "Результат 2"],
            "description": '<p><a href="https://example.com">Описание</a></p>',
            "target_audience": "<p>Для всех</p>",
            "requirements": "<p>Нет</p>",
            "learning_format": "<p>Практика</p>",
            "workload": "1–2 часа в неделю",
            "difficulty": "easy",
        }
        live = dict(desired)
        live["description"] = '<p><a target="_blank" rel="noopener" href="https://example.com">Описание</a></p>'
        self.assertTrue(_same_page(live, desired))

    def test_preserved_metadata_detects_scope_escape_and_protects_legacy_course_format(self) -> None:
        before = {
            "sections": [1, 2],
            "owner": 7,
            "authors": [7],
            "instructors": [7],
            "tags": [10, 11],
            "language": "ru",
            "is_public": False,
            "is_paid": False,
            "course_format": "legacy Stepik field",
            "cover": "https://example.test/cover.png",
        }
        after = dict(before)
        self.assertEqual(preserved_course_state(before), preserved_course_state(after))
        assert_preserved_course_state(before, after)
        after["course_format"] = "changed unexpectedly"
        with self.assertRaises(CoursePageSyncError):
            assert_preserved_course_state(before, after)

    def test_preserved_metadata_detects_structure_escape(self) -> None:
        before = {
            "sections": [1, 2],
            "owner": 7,
            "authors": [7],
            "instructors": [7],
            "tags": [10, 11],
            "language": "ru",
            "is_public": False,
            "is_paid": False,
            "course_format": "legacy",
        }
        after = dict(before)
        after["sections"] = [1]
        with self.assertRaises(CoursePageSyncError):
            assert_preserved_course_state(before, after)

    def test_required_preserved_metadata_must_be_exposed(self) -> None:
        with self.assertRaises(CoursePageSyncError):
            preserved_course_state({"language": "ru", "is_public": False, "is_paid": False})


if __name__ == "__main__":
    unittest.main()
