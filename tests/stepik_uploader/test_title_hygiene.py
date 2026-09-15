from __future__ import annotations

import unittest

from scripts.stepik_uploader.api import StepikWriteAmbiguousError
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
    summarize_event,
)
from scripts.stepik_uploader.title_hygiene import (
    TitleHygieneError,
    TitleOperation,
    execute_title_only_operation,
    plan_title_hygiene,
    title_fingerprint,
)


class FakeTitleClient:
    def __init__(
        self,
        *,
        resource: str,
        object_id: int,
        title: str,
        position: int = 1,
        course: int = 299189,
        ambiguous: bool = False,
        drift_position_after_write: int | None = None,
    ) -> None:
        self.resource = resource
        self.object_id = object_id
        self.title = title
        self.position = position
        self.course = course
        self.ambiguous = ambiguous
        self.drift_position_after_write = drift_position_after_write
        self.write_calls = 0
        self.options_calls = 0
        self.call_order: list[str] = []

    def fetch_one(self, resource: str, object_id: int):
        if resource != self.resource or object_id != self.object_id:
            raise AssertionError((resource, object_id))
        self.call_order.append("GET")
        result = {"id": self.object_id, "title": self.title}
        if self.resource == "sections":
            result.update({"position": self.position, "course": self.course, "exam": False})
        else:
            result.update({"language": "ru", "is_public": False})
        return result

    def _request_options(self, path: str):
        self.options_calls += 1
        self.call_order.append("OPTIONS")
        if self.resource == "sections":
            fields = {
                "title": {"required": True},
                "position": {"required": True},
                "course": {"required": True},
                "exam": {"required": False},
                "id": {"read_only": True},
            }
        else:
            fields = {
                "title": {"required": True},
                "language": {"required": False},
                "is_public": {"required": False},
                "id": {"read_only": True},
            }
        return {"actions": {"PUT": fields}}, "GET, PUT, OPTIONS"

    def _request_write(self, method: str, path: str, payload: dict):
        self.write_calls += 1
        self.call_order.append("PUT")
        if method != "PUT" or not path.endswith(f"/{self.object_id}"):
            raise AssertionError((method, path))
        if self.ambiguous:
            raise StepikWriteAmbiguousError("synthetic ambiguous")
        key = "lesson" if self.resource == "lessons" else "section"
        self.title = payload[key]["title"]
        if self.resource == "sections":
            # Имитируем replacement semantics: если position забыли, Stepik сбрасывает его в 1.
            self.position = int(payload[key].get("position", 1))
            if self.drift_position_after_write is not None:
                self.position = self.drift_position_after_write
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
                        {"id": 101, "position": 1, "lesson": {"id": 1001, "title": "M00-L01 — Получите первый полезный результат"}},
                        {"id": 102, "position": 2, "lesson": {"id": 1003, "title": "M00-L03 — Откройте основание и вернитесь к работе"}},
                    ],
                },
                {
                    "id": 20,
                    "position": 2,
                    "title": "Доведите ответ до пользы",
                    "units": [
                        {"id": 201, "position": 1, "lesson": {"id": 2001, "title": "Доведите первый ответ до небольшой пользы"}}
                    ],
                },
            ]
        }

    @staticmethod
    def _recorder(op: TitleOperation, source_digit: str = "1"):
        before_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.live_title)
        desired_fp = title_fingerprint(kind=op.kind, stepik_id=op.stepik_id, title=op.expected_title)
        identity = event_identity_from_environment(
            course_id=299189,
            object_id=op.object_id,
            kind="title-metadata",
            source_sha=source_digit * 40,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=before_fp,
            pending_first_sha=None,
        )
        store = MemoryHistoryStore()
        return store, DeploymentRecorder(store, identity)

    def test_plan_updates_exact_legacy_only_and_keeps_golden_owner_only(self) -> None:
        plan = plan_title_hygiene(self._manifest(), self._snapshot())
        self.assertEqual(plan.blockers, [])
        self.assertEqual([(op.kind, op.canonical_id) for op in plan.operations], [("section", "M00"), ("lesson", "M00-L03")])
        self.assertEqual([item["canonical_id"] for item in plan.owner_required], ["M00-L01"])
        self.assertTrue(all(item.as_dict()["create_allowed"] is False for item in plan.operations))
        self.assertTrue(all(item.as_dict()["delete_allowed"] is False for item in plan.operations))

    def test_arbitrary_title_drift_blocks_instead_of_overwriting(self) -> None:
        snapshot = self._snapshot()
        snapshot["sections"][1]["units"][0]["lesson"]["title"] = "Ручное название владельца"
        plan = plan_title_hygiene(self._manifest(), snapshot)
        self.assertTrue(any("lesson:M01-L01" in item for item in plan.blockers))
        self.assertNotIn("M01-L01", [op.canonical_id for op in plan.operations])

    def test_lesson_title_write_has_wal_readback_and_final_commit(self) -> None:
        op = TitleOperation(
            kind="lesson", canonical_id="M01-L01", stepik_id=2001, position=1,
            live_title="M01-L01 — Доведите первый ответ до небольшой пользы",
            expected_title="Доведите первый ответ до небольшой пользы",
        )
        store, recorder = self._recorder(op)
        client = FakeTitleClient(resource="lessons", object_id=2001, title=op.live_title)
        result = execute_title_only_operation(client, op, recorder)
        self.assertEqual(result["action"], "UPDATE_TITLE")
        self.assertEqual(client.write_calls, 1)
        self.assertLess(client.call_order.index("OPTIONS"), client.call_order.index("PUT"))
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertTrue(summary["machine_state_committed"])
        self.assertEqual(summary["writes_started"], 1)
        self.assertEqual(summary["confirmed_operation_count"], 1)

    def test_section_title_update_preserves_position_and_commits_structural_state(self) -> None:
        op = TitleOperation(
            kind="section", canonical_id="M04", stepik_id=40, position=5,
            live_title="M04 — Решите задачу по материалу", expected_title="Решите задачу по материалу",
        )
        _store, recorder = self._recorder(op, "2")
        client = FakeTitleClient(resource="sections", object_id=40, title=op.live_title, position=5)
        result = execute_title_only_operation(client, op, recorder)
        self.assertEqual(result["action"], "UPDATE_TITLE")
        self.assertEqual(client.position, 5)
        self.assertEqual(client.write_calls, 1)
        records = recorder.records(refresh=True)
        final = next(record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED")
        committed = next(record for record in records if record.get("phase") == "MACHINE_STATE_COMMITTED")
        self.assertEqual(final["actual_confirmed_state"]["position"], 5)
        self.assertEqual(committed["baseline_after"]["position"], 5)

    def test_section_position_drift_blocks_before_write(self) -> None:
        op = TitleOperation(
            kind="section", canonical_id="M04", stepik_id=40, position=5,
            live_title="M04 — Решите задачу по материалу", expected_title="Решите задачу по материалу",
        )
        _store, recorder = self._recorder(op, "3")
        client = FakeTitleClient(resource="sections", object_id=40, title=op.live_title, position=1)
        with self.assertRaises(TitleHygieneError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 0)
        self.assertEqual(recorder.records(refresh=True), [])

    def test_section_position_readback_mismatch_fails_closed_after_single_write(self) -> None:
        op = TitleOperation(
            kind="section", canonical_id="M04", stepik_id=40, position=5,
            live_title="M04 — Решите задачу по материалу", expected_title="Решите задачу по материалу",
        )
        _store, recorder = self._recorder(op, "4")
        client = FakeTitleClient(
            resource="sections", object_id=40, title=op.live_title, position=5,
            drift_position_after_write=1,
        )
        with self.assertRaises(TitleHygieneError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 1)
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["readback_failed"])
        self.assertFalse(summary["final_readback_confirmed"])

    def test_ambiguous_title_write_is_never_blindly_retried(self) -> None:
        op = TitleOperation(
            kind="section", canonical_id="M04", stepik_id=40, position=5,
            live_title="M04 — Решите задачу по материалу", expected_title="Решите задачу по материалу",
        )
        _store, recorder = self._recorder(op, "5")
        client = FakeTitleClient(resource="sections", object_id=40, title=op.live_title, position=5, ambiguous=True)
        with self.assertRaises(StepikWriteAmbiguousError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 1)
        client.ambiguous = False
        with self.assertRaises(TitleHygieneError):
            execute_title_only_operation(client, op, recorder)
        self.assertEqual(client.write_calls, 1)


if __name__ == "__main__":
    unittest.main()
