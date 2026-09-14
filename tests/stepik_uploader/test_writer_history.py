from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, EventIdentity, MemoryHistoryStore, stable_event_id, summarize_event
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.writer import ContentWriteError, execute_content_sync_one

TITLE = "M02-L01 — Test"
SHA = "1" * 40
OLD_STEPS = [
    CompiledStep(1, "text", "<p>old-1</p>", {}, ("lesson.md",)),
    CompiledStep(2, "text", "<p>old-2</p>", {}, ("lesson.md",)),
]
NEW_STEPS = [
    CompiledStep(1, "text", "<p>new-1</p>", {}, ("lesson.md",)),
    CompiledStep(2, "text", "<p>new-2</p>", {}, ("lesson.md",)),
]


def lesson_from(steps: list[CompiledStep]) -> dict:
    return {
        "id": 201,
        "title": TITLE,
        "is_public": False,
        "language": "ru",
        "steps": [
            {
                "id": 100 + step.position,
                "step_source": {
                    "id": 100 + step.position,
                    "lesson": 201,
                    "position": step.position,
                    "block": copy.deepcopy(step.block()),
                },
            }
            for step in steps
        ],
    }


def snapshot_from(steps: list[CompiledStep]) -> dict:
    return {
        "course": {"id": 299189, "is_public": False},
        "sections": [
            {
                "id": 11,
                "position": 3,
                "units": [{"id": 12, "position": 1, "lesson": lesson_from(steps)}],
            }
        ],
    }


def baseline(steps: list[CompiledStep]) -> dict:
    return {
        "canonical_id": "M02-L01",
        "stepik_lesson_id": 201,
        "applied_source_sha": "0" * 40,
        "applied_at": "2026-09-14T10:00:00Z",
        "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=steps),
        "step_ids": [101, 102],
        "source_git_paths": ["lesson.md"],
    }


def recorder_for(store: MemoryHistoryStore) -> DeploymentRecorder:
    desired = compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=NEW_STEPS)
    old = baseline(OLD_STEPS)["applied_fingerprint"]
    event_id = stable_event_id(
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        desired_fingerprint=desired,
        baseline_fingerprint=old,
        pending_first_sha=SHA,
    )
    identity = EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=SHA,
        workflow_run_id="10",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/10",
        desired_fingerprint=desired,
        baseline_fingerprint_before=old,
        pending_first_sha=SHA,
    )
    recorder = DeploymentRecorder(store, identity)
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before=baseline(OLD_STEPS),
        expected_state={"desired_fingerprint": desired},
        stepik_object_ids={"lesson_id": 201, "step_ids": [101, 102]},
        fingerprint_before=old,
        started_at="2026-09-14T10:01:00Z",
    )
    return recorder


class FakeClient:
    def __init__(self, steps: list[CompiledStep], *, fail_update_number: int | None = None, fail_readback_id: int | None = None) -> None:
        self.snapshot = snapshot_from(steps)
        self.fail_update_number = fail_update_number
        self.fail_readback_id = fail_readback_id
        self.update_count = 0
        self.trace: list[str] = []

    def _lesson(self) -> dict:
        return self.snapshot["sections"][0]["units"][0]["lesson"]

    def update_step_source(self, *, step_id: int, lesson_id: int, position: int, block: dict) -> dict:
        self.update_count += 1
        self.trace.append(f"write:{step_id}")
        if self.fail_update_number == self.update_count:
            raise ContentWriteError("simulated write failure")
        item = next(value for value in self._lesson()["steps"] if value["id"] == step_id)
        item["step_source"]["position"] = position
        item["step_source"]["block"] = copy.deepcopy(block)
        return {"step-sources": [copy.deepcopy(item["step_source"])]}

    def fetch_one(self, resource: str, object_id: int) -> dict:
        self.trace.append(f"read:{object_id}")
        if self.fail_readback_id == object_id:
            raise ContentWriteError("simulated readback failure")
        item = next(value for value in self._lesson()["steps"] if value["id"] == object_id)
        return copy.deepcopy(item["step_source"])

    def inspect_course(self, course_id: int) -> dict:
        self.trace.append("read:course")
        return copy.deepcopy(self.snapshot)


class TraceRecorder:
    def __init__(self, inner: DeploymentRecorder, trace: list[str]) -> None:
        self.inner = inner
        self.trace = trace

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def write_intent(self, *, operation_id: str, **kwargs):
        self.trace.append(f"intent:{operation_id}")
        return self.inner.write_intent(operation_id=operation_id, **kwargs)


class WriterHistoryTests(unittest.TestCase):
    def test_write_intent_is_durable_before_each_stepik_write(self) -> None:
        store = MemoryHistoryStore()
        client = FakeClient(OLD_STEPS)
        recorder = TraceRecorder(recorder_for(store), client.trace)
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=NEW_STEPS,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=baseline(OLD_STEPS),
            source_sha=SHA,
            recorder=recorder,
        )
        self.assertTrue(result.verified)
        self.assertLess(client.trace.index("intent:step-0001-101"), client.trace.index("write:101"))
        self.assertLess(client.trace.index("intent:step-0002-102"), client.trace.index("write:102"))
        summary = summarize_event(store.load(recorder.inner.identity.event_id))
        self.assertEqual(summary["writes_started"], 2)
        self.assertTrue(summary["final_readback_confirmed"])

    def test_partial_multi_step_failure_preserves_confirmed_prefix_without_final_confirmation(self) -> None:
        store = MemoryHistoryStore()
        client = FakeClient(OLD_STEPS, fail_update_number=2)
        recorder = recorder_for(store)
        with self.assertRaises(ContentWriteError):
            execute_content_sync_one(
                client,
                client.inspect_course(299189),
                canonical_id="M02-L01",
                expected_steps=NEW_STEPS,
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
                baseline=baseline(OLD_STEPS),
                source_sha=SHA,
                recorder=recorder,
            )
        summary = summarize_event(recorder.records(refresh=True))
        self.assertEqual(summary["writes_started"], 2)
        self.assertEqual(summary["confirmed_operation_count"], 1)
        self.assertFalse(summary["final_readback_confirmed"])
        self.assertNotEqual(live_lesson_fingerprint(client._lesson()), compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=NEW_STEPS))

    def test_failed_operation_readback_never_creates_final_confirmation(self) -> None:
        store = MemoryHistoryStore()
        client = FakeClient(OLD_STEPS, fail_readback_id=101)
        recorder = recorder_for(store)
        with self.assertRaises(ContentWriteError):
            execute_content_sync_one(
                client,
                client.inspect_course(299189),
                canonical_id="M02-L01",
                expected_steps=NEW_STEPS,
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
                baseline=baseline(OLD_STEPS),
                source_sha=SHA,
                recorder=recorder,
            )
        summary = summarize_event(recorder.records(refresh=True))
        self.assertTrue(summary["readback_failed"])
        self.assertFalse(summary["final_readback_confirmed"])

    def test_recovery_after_all_step_writes_still_records_applied_not_noop(self) -> None:
        store = MemoryHistoryStore()
        recorder = recorder_for(store)
        desired_snapshot = snapshot_from(NEW_STEPS)
        desired_live_fp = live_lesson_fingerprint(desired_snapshot["sections"][0]["units"][0]["lesson"])
        recorder.write_intent(
            operation_id="step-0001-101",
            method="PUT",
            target="step-sources/101",
            fingerprint_before=baseline(OLD_STEPS)["applied_fingerprint"],
            expected_fingerprint_after="sha256:" + "c" * 64,
        )
        recorder.write_result(operation_id="step-0001-101", status="COMPLETED")
        recorder.operation_readback(operation_id="step-0001-101", expected_fingerprint_after="sha256:" + "c" * 64)
        recorder.write_intent(
            operation_id="step-0002-102",
            method="PUT",
            target="step-sources/102",
            fingerprint_before="sha256:" + "c" * 64,
            expected_fingerprint_after=desired_live_fp,
        )
        recorder.write_result(operation_id="step-0002-102", status="COMPLETED")
        recorder.operation_readback(operation_id="step-0002-102", expected_fingerprint_after=desired_live_fp)

        client = FakeClient(NEW_STEPS)
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=NEW_STEPS,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=baseline(OLD_STEPS),
            source_sha=SHA,
            recorder=recorder,
            recovery_expected_live_fingerprint=desired_live_fp,
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.operations, [])
        final = next(record for record in recorder.records(refresh=True) if record["phase"] == "FINAL_READBACK_CONFIRMED")
        self.assertEqual(final["status"], "APPLIED")


if __name__ == "__main__":
    unittest.main()
