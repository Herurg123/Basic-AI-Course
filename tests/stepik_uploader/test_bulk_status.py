from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.stepik_uploader.bulk_status import build_bulk_status
from scripts.stepik_uploader.content import compile_test_lesson
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint

FREE = {
    "is_attachments_enabled": False,
    "is_html_enabled": True,
    "manual_scoring": False,
}


def _compiled_live_lesson(repo_root: Path) -> tuple[dict, str]:
    compiled = compile_test_lesson(repo_root, free_answer_source=FREE)
    title = "M02-L01 — Скажите, что получите и как это оцените"
    lesson = {
        "id": 301,
        "title": title,
        "language": "ru",
        "is_public": False,
        "steps": [
            {
                "id": 1000 + step.position,
                "step_source": {
                    "id": 1000 + step.position,
                    "position": step.position,
                    "block": step.block(),
                },
            }
            for step in compiled
        ],
    }
    fingerprint = compiled_lesson_fingerprint(expected_title=title, expected_steps=compiled)
    return lesson, fingerprint


def _placeholder(lesson_id: int, title: str) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "language": "ru",
        "is_public": False,
        "steps": [
            {
                "id": lesson_id * 10,
                "step_source": {
                    "id": lesson_id * 10,
                    "position": 1,
                    "block": {"name": "text", "source": {}, "text": "<p>Урок сгенерирован роботом ;)</p>"},
                },
            }
        ],
    }


class BulkStatusTests(unittest.TestCase):
    def test_all_course_status_keeps_golden_read_only_and_marks_placeholder_pending(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        m02, fingerprint = _compiled_live_lesson(repo_root)
        manifest = {
            "modules": [
                {
                    "canonical_id": "M00",
                    "position": 1,
                    "lessons": [
                        {
                            "canonical_id": "M00-L01",
                            "title": "Начните безопасный рабочий диалог",
                            "position": 1,
                            "golden_read_only": True,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        },
                        {
                            "canonical_id": "M00-L02",
                            "title": "Подготовьте и передайте безопасный учебный материал",
                            "position": 2,
                            "golden_read_only": True,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        },
                        {
                            "canonical_id": "M00-L03",
                            "title": "Откройте основание и вернитесь к работе",
                            "position": 3,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": ["M00-L03-A01"],
                            "steps": [{"position": 1}, {"position": 2}],
                        },
                    ],
                },
                {
                    "canonical_id": "M02",
                    "position": 3,
                    "lessons": [
                        {
                            "canonical_id": "M02-L01",
                            "title": "Скажите, что получите и как это оцените",
                            "position": 1,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": ["M02-L01-A01"],
                            "steps": [{"position": i} for i in range(1, 7)],
                        }
                    ],
                },
            ]
        }
        snapshot = {
            "course": {"id": 299189, "is_public": False},
            "sections": [
                {
                    "position": 1,
                    "units": [
                        {"position": 1, "lesson": _placeholder(101, "M00-L01 — Начните безопасный рабочий диалог")},
                        {"position": 2, "lesson": _placeholder(102, "M00-L02 — Подготовьте и передайте безопасный учебный материал")},
                        {"position": 3, "lesson": _placeholder(103, "M00-L03 — Откройте основание и вернитесь к работе")},
                    ],
                },
                {"position": 3, "units": [{"position": 1, "lesson": m02}]},
            ],
        }
        state = {
            "schema_version": 1,
            "course_id": 299189,
            "updated_at": "2026-09-14T00:00:00Z",
            "lessons": {
                "M02-L01": {
                    "canonical_id": "M02-L01",
                    "stepik_lesson_id": 301,
                    "applied_fingerprint": fingerprint,
                }
            },
        }
        profile = {"observed_conventions": {"free_answer_source": FREE}}
        plan = SimpleNamespace(
            operations=[
                {"lesson": "M00-L01", "action": "READ_ONLY_GOLDEN"},
                {"lesson": "M00-L02", "action": "READ_ONLY_GOLDEN"},
                {"lesson": "M00-L03", "action": "SKIP"},
                {"lesson": "M02-L01", "action": "SKIP"},
            ]
        )
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state=state,
            profile=profile,
            plan=plan,
        )
        by_id = {item["canonical_id"]: item for item in status["lessons"]}
        self.assertEqual(by_id["M00-L01"]["status"], "READ_ONLY_GOLDEN")
        self.assertEqual(by_id["M00-L02"]["status"], "READ_ONLY_GOLDEN")
        self.assertEqual(by_id["M00-L03"]["status"], "INITIAL_UPLOAD_REQUIRED")
        self.assertEqual(by_id["M02-L01"]["status"], "IN_SYNC")
        self.assertEqual(status["hard_blockers"], [])
        self.assertFalse(status["ready_for_bulk_write"])

    def test_stale_title_is_pending_not_duplicate_create(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = {
            "modules": [
                {
                    "canonical_id": "M06",
                    "position": 7,
                    "lessons": [
                        {
                            "canonical_id": "M06-L02",
                            "title": "Новый заголовок",
                            "position": 2,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        }
                    ],
                }
            ]
        }
        snapshot = {
            "course": {"id": 299189, "is_public": False},
            "sections": [
                {
                    "position": 7,
                    "units": [
                        {"position": 2, "lesson": _placeholder(602, "M06-L02 — Старый заголовок")}
                    ],
                }
            ],
        }
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state={"schema_version": 1, "course_id": 299189, "updated_at": None, "lessons": {}},
            profile={"observed_conventions": {"free_answer_source": FREE}},
            plan=SimpleNamespace(operations=[{"lesson": "M06-L02", "action": "SKIP_STALE_TITLE"}]),
        )
        record = status["lessons"][0]
        self.assertEqual(record["title_state"], "STALE_TITLE")
        self.assertEqual(record["status"], "INITIAL_UPLOAD_REQUIRED")
        self.assertIn("M06-L02:explicit-title-update-required", status["pending_requirements"])


if __name__ == "__main__":
    unittest.main()
