from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
    summarize_event,
)
from scripts.stepik_uploader.learner_hygiene_entrypoint import (
    HygieneEntrypointError,
    commit_proven_title_history_boundaries,
    stale_history_commit_only_events,
    title_history_object_ids,
)
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


def title_event(store: MemoryHistoryStore, *, with_final: bool = True, object_id: str = "title:lesson:M01-L01") -> str:
    identity = event_identity_from_environment(
        course_id=299189,
        object_id=object_id,
        kind="title-metadata",
        source_sha=OLD_SHA,
        desired_fingerprint=AFTER_FP,
        baseline_fingerprint=BEFORE_FP,
        pending_first_sha=None,
    )
    recorder = DeploymentRecorder(store, identity)
    before = {"kind": "lesson", "stepik_id": 1001, "title": "M01-L01 — Старое название"}
    after = {"kind": "lesson", "stepik_id": 1001, "title": "Старое название"}
    recorder.ensure_started(
        operation_type="title-hygiene",
        state_before=before,
        expected_state=after,
        stepik_object_ids={"lesson_id": 1001},
        fingerprint_before=BEFORE_FP,
    )
    recorder.write_intent(
        operation_id="title-put",
        method="PUT",
        target="lessons/1001",
        fingerprint_before=BEFORE_FP,
        expected_fingerprint_after=AFTER_FP,
    )
    recorder.write_dispatch_started(operation_id="title-put")
    recorder.write_result(operation_id="title-put", status="COMPLETED")
    recorder.operation_readback(operation_id="title-put", expected_fingerprint_after=AFTER_FP)
    if with_final:
        recorder.final_readback(
            fingerprint_after=AFTER_FP,
            stepik_object_ids={"lesson_id": 1001},
            status="APPLIED",
            baseline_after=after,
        )
    return identity.event_id


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

    def test_proven_old_source_title_final_is_committed_without_new_write(self) -> None:
        store = MemoryHistoryStore()
        event_id = title_event(store, with_final=True)

        recovered = commit_proven_title_history_boundaries(
            store=store,
            object_ids=["title:lesson:M01-L01"],
        )

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["event_id"], event_id)
        self.assertEqual(recovered[0]["source_sha"], OLD_SHA)
        self.assertEqual(recovered[0]["stepik_writes"], 0)
        summary = summarize_event(store.load(event_id))
        self.assertTrue(summary["final_readback_confirmed"])
        self.assertTrue(summary["machine_state_committed"])

    def test_title_event_without_final_is_not_auto_committed(self) -> None:
        store = MemoryHistoryStore()
        event_id = title_event(store, with_final=False)

        recovered = commit_proven_title_history_boundaries(
            store=store,
            object_ids=["title:lesson:M01-L01"],
        )

        self.assertEqual(recovered, [])
        self.assertFalse(summarize_event(store.load(event_id))["machine_state_committed"])

    def test_multiple_incomplete_title_events_for_one_object_fail_closed(self) -> None:
        store = MemoryHistoryStore()
        title_event(store, with_final=False)
        second_identity = event_identity_from_environment(
            course_id=299189,
            object_id="title:lesson:M01-L01",
            kind="title-metadata",
            source_sha=NEW_SHA,
            desired_fingerprint="sha256:" + "c" * 64,
            baseline_fingerprint=AFTER_FP,
            pending_first_sha=None,
        )
        DeploymentRecorder(store, second_identity).ensure_started(
            operation_type="title-hygiene",
            state_before={"title": "old"},
            expected_state={"title": "new"},
            stepik_object_ids={"lesson_id": 1001},
            fingerprint_before=AFTER_FP,
        )

        with self.assertRaises(HygieneEntrypointError):
            commit_proven_title_history_boundaries(
                store=store,
                object_ids=["title:lesson:M01-L01"],
            )

    def test_title_object_ids_cover_modules_and_lessons(self) -> None:
        manifest = {
            "modules": [
                {
                    "canonical_id": "M00",
                    "lessons": [
                        {"canonical_id": "M00-L01"},
                        {"canonical_id": "M00-L02"},
                    ],
                }
            ]
        }
        self.assertEqual(
            title_history_object_ids(manifest),
            ["title:lesson:M00-L01", "title:lesson:M00-L02", "title:section:M00"],
        )


if __name__ == "__main__":
    unittest.main()
