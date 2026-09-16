from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
    summarize_event,
)
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.history_runtime import validate_event_records
from scripts.stepik_uploader.learner_hygiene_recovery import (
    NormalizationRecoveryPlan,
    _operation_pairs,
    execute_normalization_recovery,
)
from scripts.stepik_uploader.learner_hygiene_writer import (
    _lesson_after_step,
    _lesson_after_title,
    _planned_operations,
)
from scripts.stepik_uploader.sync_state import empty_state


class FakeRecoveryClient:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = deepcopy(snapshot)
        self.title_writes = 0
        self.step_writes: list[int] = []

    def inspect_course(self, course_id: int) -> dict:
        if course_id != 299189:
            raise AssertionError(course_id)
        return deepcopy(self.snapshot)

    def _lesson(self) -> dict:
        return self.snapshot["sections"][0]["units"][0]["lesson"]

    def _request_write(self, method: str, path: str, payload: dict):
        self.title_writes += 1
        raise AssertionError("Recovery must not rewrite the already-confirmed title")

    def update_step_source(self, *, step_id: int, lesson_id: int, position: int, block: dict):
        if lesson_id != self._lesson()["id"]:
            raise AssertionError(lesson_id)
        self.step_writes.append(step_id)
        for item in self._lesson()["steps"]:
            source = item["step_source"]
            if source["id"] == step_id:
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


class LearnerHygieneNormalizationRecoveryTests(unittest.TestCase):
    legacy_title = "M02-L01 — Сформулируйте задачу и критерии результата"
    human_title = "Сформулируйте задачу и критерии результата"
    event_source_sha = "a" * 40
    current_source_sha = "b" * 40

    def _step(self, position: int, text: str) -> CompiledStep:
        return CompiledStep(
            position=position,
            block_name="text",
            text=text,
            source={},
            source_git_paths=("04_course/M02/M02-L01/lesson.md",),
        )

    def _steps(self, *, normalized: bool) -> list[CompiledStep]:
        separator = "" if normalized else "<hr />"
        return [
            self._step(1, "<p>one</p>"),
            self._step(2, f"<p>new two</p>{separator}<p>detail</p>"),
            self._step(3, f"<p>new three</p>{separator}<p>finish</p>"),
        ]

    def _baseline_lesson(self) -> dict:
        old_steps = [
            self._step(1, "<p>one</p>"),
            self._step(2, "<p>old two</p>"),
            self._step(3, "<p>old three</p>"),
        ]
        return {
            "id": 2591717,
            "title": self.legacy_title,
            "is_public": False,
            "language": "ru",
            "steps": [
                {
                    "id": 1000 + step.position,
                    "step": {"id": 1000 + step.position},
                    "step_source": {
                        "id": 1000 + step.position,
                        "position": step.position,
                        "block": step.block(),
                    },
                }
                for step in old_steps
            ],
        }

    def _snapshot(self, lesson: dict) -> dict:
        return {
            "course": {"id": 299189, "is_public": False, "language": "ru"},
            "sections": [
                {
                    "id": 755027,
                    "position": 3,
                    "title": "M02 — Постановка задачи",
                    "units": [
                        {
                            "id": 2631083,
                            "position": 1,
                            "lesson": deepcopy(lesson),
                        }
                    ],
                }
            ],
        }

    def _seed_incident(self):
        baseline_lesson = self._baseline_lesson()
        baseline_fp = live_lesson_fingerprint(baseline_lesson)
        legacy_steps = self._steps(normalized=False)
        normalized_steps = self._steps(normalized=True)
        legacy_desired = compiled_lesson_fingerprint(
            expected_title=self.human_title,
            expected_steps=legacy_steps,
        )
        normalized_desired = compiled_lesson_fingerprint(
            expected_title=self.human_title,
            expected_steps=normalized_steps,
        )
        identity = event_identity_from_environment(
            course_id=299189,
            object_id="M02-L01",
            kind="lesson",
            source_sha=self.event_source_sha,
            desired_fingerprint=legacy_desired,
            baseline_fingerprint=baseline_fp,
            pending_first_sha=None,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type="learner-facing-hygiene-sync",
            state_before={
                "canonical_id": "M02-L01",
                "stepik_lesson_id": 2591717,
                "applied_fingerprint": baseline_fp,
            },
            expected_state={
                "desired_fingerprint": legacy_desired,
                "source_sha": self.event_source_sha,
            },
            stepik_object_ids={"lesson_id": 2591717, "step_ids": [1001, 1002, 1003]},
            fingerprint_before=baseline_fp,
        )
        recorder._append(
            "BASELINE_SNAPSHOT_CAPTURED",
            {"recorded_at": "2026-09-16T06:40:00Z", "baseline_lesson_snapshot": deepcopy(baseline_lesson)},
            operation_id="baseline-snapshot",
        )

        legacy_operations, _legacy_final = _planned_operations(
            baseline_lesson,
            expected_title=self.human_title,
            expected_steps=legacy_steps,
        )
        normalized_operations, _normalized_final = _planned_operations(
            baseline_lesson,
            expected_title=self.human_title,
            expected_steps=normalized_steps,
        )
        pairs = _operation_pairs(legacy_operations, normalized_operations)
        self.assertEqual([item.operation_id for item in pairs], ["lesson-title", "step-0002-1002", "step-0003-1003"])

        for operation in legacy_operations[:1]:
            recorder.write_intent(
                operation_id=operation.operation_id,
                method="PUT",
                target="lessons/2591717",
                fingerprint_before=operation.fingerprint_before,
                expected_fingerprint_after=operation.fingerprint_after,
            )
            recorder.write_dispatch_started(operation_id=operation.operation_id)
            recorder.write_result(operation_id=operation.operation_id, status="COMPLETED")
            recorder.operation_readback(
                operation_id=operation.operation_id,
                expected_fingerprint_after=operation.fingerprint_after,
            )

        failed = legacy_operations[1]
        recorder.write_intent(
            operation_id=failed.operation_id,
            method="PUT",
            target="step-sources/1002",
            fingerprint_before=failed.fingerprint_before,
            expected_fingerprint_after=failed.fingerprint_after,
        )
        recorder.write_dispatch_started(operation_id=failed.operation_id)
        recorder.write_result(operation_id=failed.operation_id, status="COMPLETED")
        recorder.readback_failed(
            operation_id=failed.operation_id,
            reason_code="learner-hygiene-readback-unavailable-or-mismatch",
        )

        live = _lesson_after_title(baseline_lesson, self.human_title)
        live = _lesson_after_step(live, step_id=1002, expected=normalized_steps[1])
        self.assertEqual(live_lesson_fingerprint(live), pairs[1].normalized_fingerprint_after)

        state = empty_state(299189)
        state["lessons"]["M02-L01"] = {
            "canonical_id": "M02-L01",
            "stepik_lesson_id": 2591717,
            "applied_source_sha": "0" * 40,
            "applied_at": "2026-09-15T12:30:30Z",
            "applied_fingerprint": baseline_fp,
            "step_ids": [1001, 1002, 1003],
            "source_git_paths": ["04_course/M02/M02-L01/lesson.md"],
        }
        plan = NormalizationRecoveryPlan(
            event_id=identity.event_id,
            identity=identity,
            records=tuple(recorder.records(refresh=True)),
            baseline=deepcopy(state["lessons"]["M02-L01"]),
            baseline_lesson=deepcopy(baseline_lesson),
            normalized_expected_steps=tuple(normalized_steps),
            expected_title=self.human_title,
            lesson_id=2591717,
            module_position=3,
            lesson_position=1,
            unresolved_operation=pairs[1],
            remaining_operations=tuple(pairs[2:]),
            normalized_desired_fingerprint=normalized_desired,
            legacy_desired_fingerprint=legacy_desired,
            current_normalized_fingerprint=live_lesson_fingerprint(live),
            current_source_sha=self.current_source_sha,
            source_git_paths=("04_course/M02/M02-L01/lesson.md",),
        )
        return store, state, plan, live

    def test_recovery_confirms_normalized_prefix_without_rewriting_it_and_only_writes_remaining_step(self) -> None:
        store, state, plan, live = self._seed_incident()
        client = FakeRecoveryClient(self._snapshot(live))

        result = execute_normalization_recovery(
            client=client,
            plan=plan,
            store=store,
            state=state,
        )

        self.assertEqual(client.title_writes, 0)
        self.assertEqual(client.step_writes, [1003])
        self.assertEqual(result.stepik_writes, 1)
        self.assertEqual(
            result.state_record["applied_fingerprint"],
            plan.normalized_desired_fingerprint,
        )
        final_lesson = result.final_snapshot["sections"][0]["units"][0]["lesson"]
        self.assertEqual(live_lesson_fingerprint(final_lesson), plan.normalized_desired_fingerprint)

        records = store.load(plan.event_id)
        validate_event_records(records, expected_event_id=plan.event_id)
        summary = summarize_event(records)
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertEqual(summary["confirmed_operation_count"], 3)
        self.assertEqual(summary["writes_started"], 3)
        normalized_confirmation = [
            item for item in records
            if item.get("phase") == "OP_READBACK_CONFIRMED"
            and item.get("operation_id") == "step-0002-1002"
        ]
        self.assertEqual(len(normalized_confirmation), 1)
        self.assertEqual(normalized_confirmation[0]["read_back_result"], "CONFIRMED_NORMALIZED")
        self.assertEqual(
            normalized_confirmation[0]["actual_normalized_fingerprint"],
            plan.current_normalized_fingerprint,
        )


if __name__ == "__main__":
    unittest.main()
