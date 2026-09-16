from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.deployment_history import DeploymentHistoryError, DeploymentRecorder, MemoryHistoryStore
from scripts.stepik_uploader.golden import GoldenProfileError
from scripts.stepik_uploader.golden_title_migration import (
    _assess_snapshot,
    _event_identity,
    build_golden_title_operations,
)
from scripts.stepik_uploader.title_hygiene import execute_title_only_operation


SHA = "1" * 40


PROFILE = {
    "schema_version": "1.0",
    "status": "confirmed-read-only",
    "course_id": 299189,
    "course_state": {"language": "ru", "is_public": False},
    "golden_lessons": {
        "M00-L01": {
            "stepik_section_id": 11,
            "stepik_unit_id": 101,
            "stepik_lesson_id": 201,
            "lesson_title": "M00-L01 — Первый урок",
            "section_position": 1,
            "unit_position": 1,
            "step_count": 1,
            "block_sequence": ["text"],
            "language": "ru",
            "is_public": False,
        },
        "M00-L02": {
            "stepik_section_id": 11,
            "stepik_unit_id": 102,
            "stepik_lesson_id": 202,
            "lesson_title": "M00-L02 — Второй урок",
            "section_position": 1,
            "unit_position": 2,
            "step_count": 1,
            "block_sequence": ["text"],
            "language": "ru",
            "is_public": False,
        },
    },
    "observed_conventions": {"free_answer_source": {}},
}


MANIFEST = {
    "modules": [
        {
            "canonical_id": "M00",
            "position": 1,
            "lessons": [
                {
                    "canonical_id": "M00-L01",
                    "title": "Первый урок",
                    "position": 1,
                    "golden_read_only": True,
                },
                {
                    "canonical_id": "M00-L02",
                    "title": "Второй урок",
                    "position": 2,
                    "golden_read_only": True,
                },
            ],
        }
    ]
}


def snapshot() -> dict:
    return {
        "course": {"id": 299189, "language": "ru", "is_public": False},
        "sections": [
            {
                "id": 11,
                "position": 1,
                "units": [
                    {
                        "id": 101,
                        "position": 1,
                        "lesson": {
                            "id": 201,
                            "title": "M00-L01 — Первый урок",
                            "language": "ru",
                            "is_public": False,
                            "steps": [{"step_source": {"position": 1, "block": {"name": "text", "source": {}}}}],
                        },
                    },
                    {
                        "id": 102,
                        "position": 2,
                        "lesson": {
                            "id": 202,
                            "title": "M00-L02 — Второй урок",
                            "language": "ru",
                            "is_public": False,
                            "steps": [{"step_source": {"position": 1, "block": {"name": "text", "source": {}}}}],
                        },
                    },
                ],
            }
        ],
    }


class FakeLessonClient:
    def __init__(self, *, lesson_id: int, title: str) -> None:
        self.lesson_id = lesson_id
        self.title = title
        self.write_calls = 0

    def fetch_one(self, resource: str, object_id: int):
        if resource != "lessons" or object_id != self.lesson_id:
            raise AssertionError((resource, object_id))
        return {"id": object_id, "title": self.title}

    def _request_write(self, method: str, path: str, payload: dict):
        if method != "PUT" or path != f"/api/lessons/{self.lesson_id}":
            raise AssertionError((method, path))
        self.write_calls += 1
        self.title = payload["lesson"]["title"]
        return {"lessons": [{"id": self.lesson_id, "title": self.title}]}


class GoldenTitleMigrationTests(unittest.TestCase):
    def test_builds_only_two_exact_owner_targets(self) -> None:
        operations = build_golden_title_operations(PROFILE, MANIFEST)
        self.assertEqual([op.canonical_id for op in operations], ["M00-L01", "M00-L02"])
        self.assertEqual([op.stepik_id for op in operations], [201, 202])
        self.assertEqual([op.expected_title for op in operations], ["Первый урок", "Второй урок"])
        self.assertTrue(all(op.kind == "lesson" for op in operations))

    def test_fixture_must_equal_exact_legacy_title(self) -> None:
        profile = copy.deepcopy(PROFILE)
        profile["golden_lessons"]["M00-L01"]["lesson_title"] = "Ручной заголовок"
        with self.assertRaisesRegex(Exception, "exact legacy"):
            build_golden_title_operations(profile, MANIFEST)

    def test_initial_legacy_state_is_ready_without_history(self) -> None:
        operations = build_golden_title_operations(PROFILE, MANIFEST)
        assessed = _assess_snapshot(PROFILE, snapshot(), MemoryHistoryStore(), operations, sha=SHA)
        self.assertEqual([row["state"] for row in assessed], ["LEGACY_READY", "LEGACY_READY"])
        self.assertTrue(all(row["stepik_write_required"] for row in assessed))

    def test_target_title_without_exact_history_is_blocked(self) -> None:
        live = snapshot()
        live["sections"][0]["units"][0]["lesson"]["title"] = "Первый урок"
        operations = build_golden_title_operations(PROFILE, MANIFEST)
        with self.assertRaises(DeploymentHistoryError):
            _assess_snapshot(PROFILE, live, MemoryHistoryStore(), operations, sha=SHA)

    def test_non_title_golden_drift_remains_blocker(self) -> None:
        live = snapshot()
        live["sections"][0]["units"][1]["position"] = 9
        operations = build_golden_title_operations(PROFILE, MANIFEST)
        with self.assertRaises(GoldenProfileError):
            _assess_snapshot(PROFILE, live, MemoryHistoryStore(), operations, sha=SHA)

    def test_proven_target_title_is_recovery_safe(self) -> None:
        operations = build_golden_title_operations(PROFILE, MANIFEST)
        operation = operations[0]
        store = MemoryHistoryStore()
        identity = _event_identity(operation, sha=SHA)
        recorder = DeploymentRecorder(store, identity)
        client = FakeLessonClient(lesson_id=operation.stepik_id, title=operation.live_title)

        result = execute_title_only_operation(client, operation, recorder)
        self.assertEqual(result["action"], "UPDATE_TITLE")
        self.assertEqual(client.write_calls, 1)

        live = snapshot()
        live["sections"][0]["units"][0]["lesson"]["title"] = operation.expected_title
        assessed = _assess_snapshot(PROFILE, live, store, operations, sha=SHA)
        first = next(row for row in assessed if row["canonical_id"] == "M00-L01")
        self.assertEqual(first["state"], "TARGET_PROVEN_HISTORY")
        self.assertFalse(first["stepik_write_required"])


if __name__ == "__main__":
    unittest.main()
