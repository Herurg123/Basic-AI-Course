from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, MemoryHistoryStore, event_identity_from_environment, summarize_event
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.learner_hygiene_writer import (
    _planned_operations,
    execute_tracked_learner_hygiene,
)
from scripts.stepik_uploader.writer import ContentWriteError


class FakeHygieneClient:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = deepcopy(snapshot)
        self.title_writes = 0
        self.step_writes = 0

    def inspect_course(self, course_id: int) -> dict:
        if course_id != int(self.snapshot["course"]["id"]):
            raise AssertionError(course_id)
        return deepcopy(self.snapshot)

    def _lesson(self) -> dict:
        return self.snapshot["sections"][0]["units"][0]["lesson"]

    def _request_write(self, method: str, path: str, payload: dict):
        if method != "PUT" or not path.endswith(f"/{self._lesson()['id']}"):
            raise AssertionError((method, path))
        self.title_writes += 1
        self._lesson()["title"] = payload["lesson"]["title"]
        return {"lessons": [{"id": self._lesson()["id"], "title": self._lesson()["title"]}]}

    def update_step_source(self, *, step_id: int, lesson_id: int, position: int, block: dict):
        if lesson_id != self._lesson()["id"]:
            raise AssertionError(lesson_id)
        for item in self._lesson()["steps"]:
            source = item["step_source"]
            if source["id"] == step_id:
                self.step_writes += 1
                source["position"] = position
                source["block"] = deepcopy(block)
                return {"step-sources": [deepcopy(source)]}
        raise AssertionError(step_id)

    def fetch_one(self, resource: str, object_id: int) -> dict:
        if resource != "step-sources":
            raise AssertionError(resource)
        for item in self._lesson()["steps"]:
            source = item["step_source"]
            if source["id"] == object_id:
                return deepcopy(source)
        raise AssertionError(object_id)


class LearnerHygieneWriterTests(unittest.TestCase):
    legacy_title = "M04-L01 — Получите ответ по безопасному исходнику"
    human_title = "Получите ответ по безопасному исходнику"

    def _steps(self, *, second_text: str) -> list[CompiledStep]:
        return [
            CompiledStep(
                position=1,
                block_name="text",
                text="<p>Первый шаг</p>",
                source={},
                source_git_paths=("04_course/M04/M04-L01/lesson.md",),
            ),
            CompiledStep(
                position=2,
                block_name="text",
                text=second_text,
                source={},
                source_git_paths=("04_course/M04/M04-L01/lesson.md",),
            ),
        ]

    def _snapshot(self) -> dict:
        old_steps = self._steps(second_text="<p>Служебный M04-L01-A01</p>")
        return {
            "course": {"id": 299189, "is_public": False, "language": "ru"},
            "sections": [
                {
                    "id": 400,
                    "position": 5,
                    "title": "M04 — Решите задачу по материалу",
                    "units": [
                        {
                            "id": 401,
                            "position": 1,
                            "lesson": {
                                "id": 2591721,
                                "title": self.legacy_title,
                                "is_public": False,
                                "language": "ru",
                                "steps": [
                                    {
                                        "id": 7001,
                                        "step": {"id": 7001},
                                        "step_source": {
                                            "id": 7001,
                                            "position": 1,
                                            "block": old_steps[0].block(),
                                        },
                                    },
                                    {
                                        "id": 7002,
                                        "step": {"id": 7002},
                                        "step_source": {
                                            "id": 7002,
                                            "position": 2,
                                            "block": old_steps[1].block(),
                                        },
                                    },
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    def _baseline(self, snapshot: dict) -> dict:
        lesson = snapshot["sections"][0]["units"][0]["lesson"]
        return {
            "canonical_id": "M04-L01",
            "stepik_lesson_id": lesson["id"],
            "applied_source_sha": "a" * 40,
            "applied_at": "2026-09-15T12:30:30Z",
            "applied_fingerprint": live_lesson_fingerprint(lesson),
            "step_ids": [7001, 7002],
            "source_git_paths": ["04_course/M04/M04-L01/lesson.md"],
        }

    def _recorder(self, baseline: dict, desired_steps: list[CompiledStep]) -> DeploymentRecorder:
        desired_fp = compiled_lesson_fingerprint(
            expected_title=self.human_title,
            expected_steps=desired_steps,
        )
        identity = event_identity_from_environment(
            course_id=299189,
            object_id="M04-L01",
            kind="lesson",
            source_sha="b" * 40,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=baseline["applied_fingerprint"],
            pending_first_sha="c" * 40,
        )
        return DeploymentRecorder(MemoryHistoryStore(), identity)

    def test_title_and_changed_step_are_one_tracked_event(self) -> None:
        snapshot = self._snapshot()
        baseline = self._baseline(snapshot)
        desired_steps = self._steps(second_text="<p>Учебный файл</p>")
        recorder = self._recorder(baseline, desired_steps)
        client = FakeHygieneClient(snapshot)

        result = execute_tracked_learner_hygiene(
            client,
            snapshot,
            canonical_id="M04-L01",
            expected_steps=desired_steps,
            module_position=5,
            lesson_position=1,
            expected_title=self.human_title,
            legacy_title=self.legacy_title,
            baseline=baseline,
            source_sha="b" * 40,
            recorder=recorder,
        )

        self.assertTrue(result.verified)
        self.assertEqual(client.title_writes, 1)
        self.assertEqual(client.step_writes, 1)
        self.assertEqual([item["action"] for item in result.operations], ["UPDATE_TITLE", "UPDATE_STEP"])
        self.assertEqual(result.state_record["applied_fingerprint"], compiled_lesson_fingerprint(
            expected_title=self.human_title,
            expected_steps=desired_steps,
        ))
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertFalse(summary["machine_state_committed"])
        self.assertEqual(summary["writes_started"], 2)
        self.assertEqual(summary["confirmed_operation_count"], 2)

    def test_proven_title_prefix_resumes_only_remaining_step(self) -> None:
        snapshot = self._snapshot()
        baseline = self._baseline(snapshot)
        desired_steps = self._steps(second_text="<p>Учебный файл</p>")
        recorder = self._recorder(baseline, desired_steps)
        client = FakeHygieneClient(snapshot)
        lesson = snapshot["sections"][0]["units"][0]["lesson"]
        operations, _desired = _planned_operations(
            lesson,
            expected_title=self.human_title,
            expected_steps=desired_steps,
        )
        title_op = operations[0]

        recorder.ensure_started(
            operation_type="learner-facing-hygiene-sync",
            state_before={
                "canonical_id": "M04-L01",
                "stepik_lesson_id": lesson["id"],
                "applied_fingerprint": baseline["applied_fingerprint"],
            },
            expected_state={
                "desired_fingerprint": recorder.identity.desired_fingerprint,
                "source_sha": "b" * 40,
            },
            stepik_object_ids={"lesson_id": lesson["id"], "step_ids": [7001, 7002]},
            fingerprint_before=baseline["applied_fingerprint"],
        )
        recorder._append(
            "BASELINE_SNAPSHOT_CAPTURED",
            {"recorded_at": "2026-09-15T14:00:00Z", "baseline_lesson_snapshot": deepcopy(lesson)},
            operation_id="baseline-snapshot",
        )
        recorder.write_intent(
            operation_id=title_op.operation_id,
            method="PUT",
            target=f"lessons/{lesson['id']}",
            fingerprint_before=title_op.fingerprint_before,
            expected_fingerprint_after=title_op.fingerprint_after,
        )
        recorder.write_dispatch_started(operation_id=title_op.operation_id)
        recorder.write_result(operation_id=title_op.operation_id, status="COMPLETED")
        recorder.operation_readback(
            operation_id=title_op.operation_id,
            expected_fingerprint_after=title_op.fingerprint_after,
        )
        client.snapshot["sections"][0]["units"][0]["lesson"]["title"] = self.human_title
        intermediate = client.inspect_course(299189)

        result = execute_tracked_learner_hygiene(
            client,
            intermediate,
            canonical_id="M04-L01",
            expected_steps=desired_steps,
            module_position=5,
            lesson_position=1,
            expected_title=self.human_title,
            legacy_title=self.legacy_title,
            baseline=baseline,
            source_sha="b" * 40,
            recorder=recorder,
        )

        self.assertTrue(result.verified)
        self.assertEqual(client.title_writes, 0)
        self.assertEqual(client.step_writes, 1)
        self.assertEqual(result.operations[0]["action"], "RESUME_PROVEN_PREFIX")

    def test_dispatch_gap_blocks_without_new_write(self) -> None:
        snapshot = self._snapshot()
        baseline = self._baseline(snapshot)
        desired_steps = self._steps(second_text="<p>Учебный файл</p>")
        recorder = self._recorder(baseline, desired_steps)
        client = FakeHygieneClient(snapshot)
        lesson = snapshot["sections"][0]["units"][0]["lesson"]
        operations, _desired = _planned_operations(
            lesson,
            expected_title=self.human_title,
            expected_steps=desired_steps,
        )
        title_op = operations[0]
        recorder.ensure_started(
            operation_type="learner-facing-hygiene-sync",
            state_before={
                "canonical_id": "M04-L01",
                "stepik_lesson_id": lesson["id"],
                "applied_fingerprint": baseline["applied_fingerprint"],
            },
            expected_state={
                "desired_fingerprint": recorder.identity.desired_fingerprint,
                "source_sha": "b" * 40,
            },
            stepik_object_ids={"lesson_id": lesson["id"], "step_ids": [7001, 7002]},
            fingerprint_before=baseline["applied_fingerprint"],
        )
        recorder._append(
            "BASELINE_SNAPSHOT_CAPTURED",
            {"recorded_at": "2026-09-15T14:00:00Z", "baseline_lesson_snapshot": deepcopy(lesson)},
            operation_id="baseline-snapshot",
        )
        recorder.write_intent(
            operation_id=title_op.operation_id,
            method="PUT",
            target=f"lessons/{lesson['id']}",
            fingerprint_before=title_op.fingerprint_before,
            expected_fingerprint_after=title_op.fingerprint_after,
        )
        recorder.write_dispatch_started(operation_id=title_op.operation_id)

        with self.assertRaisesRegex(ContentWriteError, "dispatch"):
            execute_tracked_learner_hygiene(
                client,
                snapshot,
                canonical_id="M04-L01",
                expected_steps=desired_steps,
                module_position=5,
                lesson_position=1,
                expected_title=self.human_title,
                legacy_title=self.legacy_title,
                baseline=baseline,
                source_sha="b" * 40,
                recorder=recorder,
            )
        self.assertEqual(client.title_writes, 0)
        self.assertEqual(client.step_writes, 0)

    def test_manual_live_drift_before_event_blocks(self) -> None:
        snapshot = self._snapshot()
        baseline = self._baseline(snapshot)
        desired_steps = self._steps(second_text="<p>Учебный файл</p>")
        recorder = self._recorder(baseline, desired_steps)
        drifted = deepcopy(snapshot)
        drifted["sections"][0]["units"][0]["lesson"]["steps"][0]["step_source"]["block"]["text"] = "<p>manual</p>"
        client = FakeHygieneClient(drifted)

        with self.assertRaisesRegex(ContentWriteError, "отличается от baseline"):
            execute_tracked_learner_hygiene(
                client,
                drifted,
                canonical_id="M04-L01",
                expected_steps=desired_steps,
                module_position=5,
                lesson_position=1,
                expected_title=self.human_title,
                legacy_title=self.legacy_title,
                baseline=baseline,
                source_sha="b" * 40,
                recorder=recorder,
            )
        self.assertEqual(client.title_writes, 0)
        self.assertEqual(client.step_writes, 0)


if __name__ == "__main__":
    unittest.main()
