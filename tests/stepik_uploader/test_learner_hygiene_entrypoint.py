from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import DeploymentRecorder, MemoryHistoryStore, event_identity_from_environment
from scripts.stepik_uploader.learner_hygiene_entrypoint import stale_history_commit_only_events
from scripts.stepik_uploader.sync_state import empty_state

OLD_SHA = "1" * 40
NEW_SHA = "2" * 40
BEFORE_FP = "sha256:" + "a" * 64
AFTER_FP = "sha256:" + "b" * 64


def proven_event(store: MemoryHistoryStore, source_sha: str) -> dict:
    identity = event_identity_from_environment(
        course_id=299189,
        object_id="M04-L01",
        kind="lesson",
        source_sha=source_sha,
        desired_fingerprint=AFTER_FP,
        baseline_fingerprint=BEFORE_FP,
        pending_first_sha=None,
    )
    recorder = DeploymentRecorder(store, identity)
    after = {
        "canonical_id": "M04-L01",
        "stepik_lesson_id": 2591721,
        "applied_source_sha": source_sha,
        "applied_at": "2026-09-15T12:30:30Z",
        "applied_fingerprint": AFTER_FP,
        "step_ids": [1],
        "source_git_paths": ["04_course/M04/M04-L01/lesson.md"],
    }
    recorder.ensure_started(
        operation_type="learner-facing-hygiene-sync",
        state_before={"applied_fingerprint": BEFORE_FP},
        expected_state={"desired_fingerprint": AFTER_FP},
        stepik_object_ids={"lesson_id": 2591721, "step_ids": [1]},
        fingerprint_before=BEFORE_FP,
    )
    recorder.write_intent(
        operation_id="lesson-title",
        method="PUT",
        target="lessons/2591721",
        fingerprint_before=BEFORE_FP,
        expected_fingerprint_after=AFTER_FP,
    )
    recorder.write_dispatch_started(operation_id="lesson-title")
    recorder.write_result(operation_id="lesson-title", status="COMPLETED")
    recorder.operation_readback(operation_id="lesson-title", expected_fingerprint_after=AFTER_FP)
    recorder.final_readback(
        fingerprint_after=AFTER_FP,
        stepik_object_ids={"lesson_id": 2591721, "step_ids": [1]},
        status="APPLIED",
        baseline_after=after,
    )
    return after


class LearnerHygieneEntrypointTests(unittest.TestCase):
    def test_old_source_with_matching_issue_state_requires_history_commit_only(self) -> None:
        store = MemoryHistoryStore()
        after = proven_event(store, OLD_SHA)
        state = empty_state(299189)
        state["lessons"]["M04-L01"] = after
        events = stale_history_commit_only_events(store=store, state=state, current_source_sha=NEW_SHA)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["canonical_id"], "M04-L01")
        self.assertEqual(events[0]["source_sha"], OLD_SHA)

    def test_same_source_is_left_to_normal_runtime(self) -> None:
        store = MemoryHistoryStore()
        after = proven_event(store, NEW_SHA)
        state = empty_state(299189)
        state["lessons"]["M04-L01"] = after
        self.assertEqual(
            stale_history_commit_only_events(store=store, state=state, current_source_sha=NEW_SHA),
            [],
        )

    def test_mismatching_issue_state_is_not_adopted(self) -> None:
        store = MemoryHistoryStore()
        proven_event(store, OLD_SHA)
        state = empty_state(299189)
        state["lessons"]["M04-L01"] = {
            "canonical_id": "M04-L01",
            "stepik_lesson_id": 2591721,
            "applied_fingerprint": BEFORE_FP,
        }
        self.assertEqual(
            stale_history_commit_only_events(store=store, state=state, current_source_sha=NEW_SHA),
            [],
        )


if __name__ == "__main__":
    unittest.main()
