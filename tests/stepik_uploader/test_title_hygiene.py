from __future__ import annotations

import unittest

from scripts.stepik_uploader.api import StepikWriteAmbiguousError
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, MemoryHistoryStore, event_identity_from_environment, summarize_event
from scripts.stepik_uploader.title_hygiene import (
    TitleHygieneError,
    TitleOperation,
    execute_title_only_operation,
    plan_title_hygiene,
    title_fingerprint,
)


class FakeTitleClient:
    def __init__(self, *, resource: str, object_id: int, title: str, ambiguous: bool = False) -> None:
        self.resource = resource
        self.object_id = object_id
        self.title = title
        self.ambiguous = ambiguous
        self.write_calls = 0

    def fetch_one(self, resource: str, object_id: int):
        if resource != self.resource or object_id != self.object_id:
            raise AssertionError((resource, object_id))
        return {"id": self.object_id, "title": self.title}

    def _request_write(self, method: str, path: str, payload: dict):
        self.write_calls += 1
        if method != "PUT" or not path.endswith(f"/{self.object_id}"):
            raise AssertionError((method, path))
        if self.ambiguous:
            raise StepikWriteAmbiguousError("synthetic ambiguous")
        key = "lesson" if self.resource == "lessons" else "section"
        self.title = payload[key]["title"]
        return {self.resource: [{"id": self.object_id, "title": self.title}]}


class TitleHygieneTests(unittest.TestCase):
    def _manifest(self):
        return {
            "modules": [
                {
                    "canonical_id": "M00",
                    "title": "Начните работать с ИИ",
                    "position": 1,
                    "lessons": [
                        {
                            "canonical_id": "M00-L01",
                            "title": "Получите первый полезный результат",
                            "position": 1,
                            "golden_read_only": True,
                        },
                        {
                            "canonical_id": "M00-L03",
                            "title": "Откройте основание и вернитесь к работе",
                            "position": 2,
                            "golden_read_only": False,
                        },
                    ],
                },
                {
                    "canonical_id": "M01",
                    "title": "Доведите ответ до пользы",
                    "position": 2,
                    "lessons": [
                        {
                            "canonical_id": "M01-L01",
                            "title": "Доведите первый ответ до небольшой пользы",
                            "position": 1,
                            "golden_read_only": False,
                        }
                    ],
                },
            ]
        }

    def _snapshot(self):
        return {
            "sections": [
                {
                    "id": 10,
                    "position": 1,
                    "title": "M00 — Начните работать с ИИ",
                    "units": [
                        {
                            "id": 101,
                            "position": 1,
                            "lesson": {
                                "id": 1001,
                                "title": "M00-L01 — Получите первый полезный результат",
                            },
                        },
                        {
                            "id": 102,
                            "position": 2,
                            "lesson": {
                                "id": 1003,
                                "title": "M00-L03 — Откройте основание и вернитесь к работе",
                            },
                        },
                    ],
                },
                {
                    "id": 20,
                    "position": 2,
                    "title": "Доведите ответ до пользы",
                    "units": [
                        {
                            "id": 201,
                            "position": 1,
                            "lesson": {
                                "id": 2001,
                                "title": "Доведите первый ответ до небольшой пользы",
                            },
                        }
                    ],
                },
            ]
        }

    def test_plan_updates_exact_legacy_only_and_keeps_golden_owner_only(self) -> None:
        plan = plan_title_hygiene(self._manifest(), self._snapshot())
        self.assertEqual(plan.blockers, [])
        self.assertEqual(
            [(op.kind, op.canonical_id) for op in plan.operations],
            [("section", "M00"), ("lesson", "M00-L03")],
        )
        self.assertEqual([item["canonical_id"] for item in plan.owner_required], ["M00-L01"])
        self.assertTrue(all(item.as_dict()["create_allowed"] is False for item in plan.operations))
        self.assertTrue(all(item.as_dict()["delete_allowed"] is False for item in plan.operations))

    def test_arbitrary_title_drift_blocks_instead_of_overwriting(self) -> None:
        snapshot = self._snapshot()
        snapshot["sections"][1]["units"][0]["lesson"]["title"] = "Ручное название владельца"
        plan = plan_title_hygiene(self._manifest(), snapshot)
        self.assertTrue(any("lesson:M01-L01" in item for item in plan.blockers))
        self.assertNotIn("M01-L01", [op.canonical_id for op in plan.operations])

    def test_title_only_write_has_wal_readback_and_final_commit(self) -> None:
        op = TitleOperation(
            kind="lesson",
            canonical_id="M01-L01",
            stepik_id=2001,
            position=1,
            live_title="M01-L01 — Доведите первый ответ до небольшой пользы",
            expected_title="Доведите первый ответ до небольшой пользы",
        )
        before_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.live_title)
        desired_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.expected_title)
        identity = event_identity_from_environment(
            course_id=299189,
            object_id=op.object_id,
            kind="title-metadata",
            source_sha="1" * 40,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=before_fp,
            pending_first_sha=None,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)
        client = FakeTitleClient(resource="lessons", object_id=2001, title=op.live_title)

        result = execute_title_only_operation(client, op, recorder)

        self.assertEqual(result["action"], "UPDATE_TITLE")
        self.assertEqual(client.write_calls, 1)
        self.assertEqual(client.title, op.expected_title)
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertTrue(summary["machine_state_committed"])
        self.assertEqual(summary["writes_started"], 1)
        self.assertEqual(summary["confirmed_operation_count"], 1)

    def test_ambiguous_title_write_is_never_blindly_retried(self) -> None:
        op = TitleOperation(
            kind="section",
            canonical_id="M04",
            stepik_id=40,
            position=5,
            live_title="M04 — Решите задачу по материалу",
            expected_title="Решите задачу по материалу",
        )
        before_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.live_title)
        desired_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.expected_title)
        identity = event_identity_from_environment(
            course_id=299189,
            object_id=op.object_id,
            kind="title-metadata",
            source_sha="2" * 40,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=before_fp,
            pending_first_sha=None,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)
        client = FakeTitleClient(resource="sections", object_id=40, title=op.live_title, ambiguous=True)

        with self.assertRaises(StepikWriteAmbiguousError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 1)

        client.ambiguous = False
        with self.assertRaises(TitleHygieneError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 1)


if __name__ == "__main__":
    unittest.main()
