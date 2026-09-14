from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import find_object_events, latest_committed_history_evidence

SHA1 = "1" * 40
SHA2 = "2" * 40
FP1 = "sha256:" + "a" * 64
FP2 = "sha256:" + "b" * 64


def identity(source_sha: str, desired: str, baseline: str) -> EventIdentity:
    event_id = stable_event_id(
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=source_sha,
        desired_fingerprint=desired,
        baseline_fingerprint=baseline,
        pending_first_sha=source_sha,
    )
    return EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id="M02-L01",
        kind="lesson",
        source_sha=source_sha,
        workflow_run_id="1",
        workflow_run_attempt="1",
        workflow_run_url="https://example.invalid/run/1",
        desired_fingerprint=desired,
        baseline_fingerprint_before=baseline,
        pending_first_sha=source_sha,
    )


def committed_event(store: MemoryHistoryStore, ident: EventIdentity, fingerprint: str, committed_at: str) -> None:
    recorder = DeploymentRecorder(store, ident)
    baseline_after = {
        "canonical_id": "M02-L01",
        "stepik_lesson_id": 10,
        "applied_source_sha": ident.source_sha,
        "applied_at": committed_at,
        "applied_fingerprint": fingerprint,
        "step_ids": [101],
        "source_git_paths": ["lesson.md"],
    }
    recorder.ensure_started(
        operation_type="lesson-content-sync",
        state_before={"applied_fingerprint": ident.baseline_fingerprint_before},
        expected_state={"desired_fingerprint": ident.desired_fingerprint},
        stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
        fingerprint_before=ident.baseline_fingerprint_before or fingerprint,
        started_at=committed_at,
    )
    recorder.final_readback(
        fingerprint_after=fingerprint,
        stepik_object_ids={"lesson_id": 10, "step_ids": [101]},
        status="APPLIED",
        baseline_after=baseline_after,
    )
    recorder.state_committed(baseline_after=baseline_after, status="APPLIED", committed_at=committed_at)


class LatestCommittedHistoryTests(unittest.TestCase):
    def test_old_matching_event_does_not_make_current_baseline_stale(self) -> None:
        store = MemoryHistoryStore()
        old = identity(SHA1, FP1, FP1)
        new = identity(SHA2, FP2, FP1)
        committed_event(store, old, FP1, "2026-09-14T10:00:00Z")
        committed_event(store, new, FP2, "2026-09-14T11:00:00Z")

        evidence = latest_committed_history_evidence(
            find_object_events(store, object_id="M02-L01"),
            live_fingerprint=FP1,
        )
        self.assertFalse(evidence["ambiguous"])
        self.assertFalse(evidence["live_match"])
        self.assertEqual(evidence["fingerprints"], [FP2])
        self.assertEqual(evidence["event_ids"], [new.event_id])

    def test_latest_matching_event_is_accepted_as_stale_baseline_evidence(self) -> None:
        store = MemoryHistoryStore()
        old = identity(SHA1, FP1, FP1)
        new = identity(SHA2, FP2, FP1)
        committed_event(store, old, FP1, "2026-09-14T10:00:00Z")
        committed_event(store, new, FP2, "2026-09-14T11:00:00Z")

        evidence = latest_committed_history_evidence(
            find_object_events(store, object_id="M02-L01"),
            live_fingerprint=FP2,
        )
        self.assertTrue(evidence["live_match"])
        self.assertFalse(evidence["ambiguous"])

    def test_equal_latest_timestamps_with_different_fingerprints_are_ambiguous(self) -> None:
        store = MemoryHistoryStore()
        first = identity(SHA1, FP1, FP1)
        second = identity(SHA2, FP2, FP1)
        committed_event(store, first, FP1, "2026-09-14T11:00:00Z")
        committed_event(store, second, FP2, "2026-09-14T11:00:00Z")

        evidence = latest_committed_history_evidence(
            find_object_events(store, object_id="M02-L01"),
            live_fingerprint=FP2,
        )
        self.assertTrue(evidence["ambiguous"])
        self.assertFalse(evidence["live_match"])
        self.assertEqual(set(evidence["fingerprints"]), {FP1, FP2})


if __name__ == "__main__":
    unittest.main()
