from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, EventIdentity, MemoryHistoryStore, stable_event_id
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source
from scripts.stepik_uploader.staging_normalization_recovery import (
    INCIDENT_EVENT_ID,
    INCIDENT_FAILED_OPERATION,
    INCIDENT_FIRST_OPERATION,
    INCIDENT_LEGACY_DESIRED,
    INCIDENT_LEGACY_STEP2_AFTER,
    INCIDENT_LESSON_ID,
    INCIDENT_PENDING_FIRST_SHA,
    INCIDENT_SOURCE_SHA,
    INCIDENT_STEP_IDS,
    RECOVERY_TARGET,
    _legacy_v1_steps,
    _normalized_v2_steps,
    build_staging_normalization_recovery_plan,
)
from scripts.stepik_uploader.sync_state import empty_state, with_pending_impact
from scripts.stepik_uploader.writer import ContentWriteError

CURRENT_SHA = "f" * 40


class FakeClient:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = copy.deepcopy(snapshot)
        self.create_positions: list[int] = []
        self.next_id = 11339676

    def _lesson(self) -> dict:
        return self.snapshot["sections"][0]["units"][0]["lesson"]

    def inspect_course(self, course_id: int) -> dict:
        if course_id != 299189:
            raise AssertionError(course_id)
        return copy.deepcopy(self.snapshot)

    def create_step_source(self, *, lesson_id: int, position: int, block: dict) -> dict:
        if lesson_id != INCIDENT_LESSON_ID:
            raise AssertionError(lesson_id)
        self.create_positions.append(position)
        step_id = self.next_id
        self.next_id += 1
        source = {
            "id": step_id,
            "lesson": lesson_id,
            "position": position,
            "block": copy.deepcopy(block),
        }
        self._lesson()["steps"].append({"id": step_id, "step_source": copy.deepcopy(source)})
        self._lesson()["steps"].sort(key=lambda item: int(item["step_source"]["position"]))
        return {"step-sources": [copy.deepcopy(source)]}

    def fetch_one(self, resource: str, object_id: int) -> dict:
        if resource != "step-sources":
            raise AssertionError(resource)
        for item in self._lesson()["steps"]:
            if int(item["step_source"]["id"]) == int(object_id):
                return copy.deepcopy(item["step_source"])
        raise AssertionError(object_id)


class StagingNormalizationRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.manifest = build_structural_manifest(cls.repo_root, source_sha=CURRENT_SHA)
        cls.module = None
        cls.lesson_manifest = None
        for module in cls.manifest["modules"]:
            for lesson in module["lessons"]:
                if lesson["canonical_id"] == RECOVERY_TARGET:
                    cls.module = module
                    cls.lesson_manifest = lesson
                    break
            if cls.lesson_manifest is not None:
                break
        if cls.module is None or cls.lesson_manifest is None:
            raise AssertionError("M06-L02 manifest target missing")
        cls.expected_title = str(cls.lesson_manifest["title"])
        cls.source_steps = compile_lesson_source(
            cls.repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id=RECOVERY_TARGET,
        )
        inventory = build_asset_inventory(cls.repo_root, cls.manifest)
        policy = load_asset_publication_policy(
            cls.repo_root / "04_course/stepik/automation/asset-publication.v1.json"
        )
        cls.asset_report = assess_asset_publication(
            repo_root=cls.repo_root,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )
        cls.legacy_steps = _legacy_v1_steps(
            repo_root=cls.repo_root,
            source_steps=cls.source_steps,
            asset_report=cls.asset_report,
        )
        cls.normalized_steps = _normalized_v2_steps(
            repo_root=cls.repo_root,
            source_steps=cls.source_steps,
            asset_report=cls.asset_report,
        )

    def _state(self) -> dict:
        return with_pending_impact(
            empty_state(299189),
            source_sha=INCIDENT_PENDING_FIRST_SHA,
            occurred_at="2026-09-16T00:00:00Z",
            paths_by_lesson={RECOVERY_TARGET: ["04_course/M06/M06-L02/lesson.md"]},
            reasons_by_lesson={RECOVERY_TARGET: ["canonical-learner-change"]},
        )

    def _snapshot(self) -> dict:
        steps = []
        for step_id, expected in zip(INCIDENT_STEP_IDS, self.normalized_steps[:2], strict=True):
            steps.append(
                {
                    "id": step_id,
                    "step_source": {
                        "id": step_id,
                        "lesson": INCIDENT_LESSON_ID,
                        "position": expected.position,
                        "block": copy.deepcopy(expected.block()),
                    },
                }
            )
        return {
            "course": {"id": 299189, "is_public": False, "language": "ru"},
            "sections": [
                {
                    "id": 700,
                    "position": int(self.module["position"]),
                    "units": [
                        {
                            "id": 702,
                            "position": int(self.lesson_manifest["position"]),
                            "lesson": {
                                "id": INCIDENT_LESSON_ID,
                                "title": self.expected_title,
                                "is_public": False,
                                "language": "ru",
                                "steps": steps,
                            },
                        }
                    ],
                }
            ],
        }

    def _history(self, snapshot: dict) -> MemoryHistoryStore:
        calculated = stable_event_id(
            course_id=299189,
            object_id=RECOVERY_TARGET,
            kind="lesson",
            source_sha=INCIDENT_SOURCE_SHA,
            desired_fingerprint=INCIDENT_LEGACY_DESIRED,
            baseline_fingerprint=None,
            pending_first_sha=INCIDENT_PENDING_FIRST_SHA,
        )
        self.assertEqual(calculated, INCIDENT_EVENT_ID)
        identity = EventIdentity(
            event_id=INCIDENT_EVENT_ID,
            course_id=299189,
            object_id=RECOVERY_TARGET,
            kind="lesson",
            source_sha=INCIDENT_SOURCE_SHA,
            workflow_run_id="35178499704",
            workflow_run_attempt="1",
            workflow_run_url=None,
            desired_fingerprint=INCIDENT_LEGACY_DESIRED,
            baseline_fingerprint_before=None,
            pending_first_sha=INCIDENT_PENDING_FIRST_SHA,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type="lesson-initial-upload",
            state_before=None,
            expected_state={
                "desired_fingerprint": INCIDENT_LEGACY_DESIRED,
                "source_sha": INCIDENT_SOURCE_SHA,
            },
            stepik_object_ids={"lesson_id": INCIDENT_LESSON_ID},
            fingerprint_before="sha256:" + "0" * 64,
            started_at="2026-09-17T03:57:05Z",
        )
        first_only = copy.deepcopy(snapshot["sections"][0]["units"][0]["lesson"])
        first_only["steps"] = first_only["steps"][:1]
        first_after = live_lesson_fingerprint(first_only)
        recorder.write_intent(
            operation_id=INCIDENT_FIRST_OPERATION,
            method="PUT",
            target=f"step-sources/{INCIDENT_STEP_IDS[0]}",
            fingerprint_before="sha256:" + "0" * 64,
            expected_fingerprint_after=first_after,
        )
        recorder.write_dispatch_started(operation_id=INCIDENT_FIRST_OPERATION)
        recorder.write_result(operation_id=INCIDENT_FIRST_OPERATION, status="COMPLETED")
        recorder.operation_readback(
            operation_id=INCIDENT_FIRST_OPERATION,
            expected_fingerprint_after=first_after,
        )
        recorder.write_intent(
            operation_id=INCIDENT_FAILED_OPERATION,
            method="POST",
            target="step-sources",
            fingerprint_before=first_after,
            expected_fingerprint_after=INCIDENT_LEGACY_STEP2_AFTER,
        )
        recorder.write_dispatch_started(operation_id=INCIDENT_FAILED_OPERATION)
        recorder.write_result(operation_id=INCIDENT_FAILED_OPERATION, status="COMPLETED")
        recorder.readback_failed(
            operation_id=INCIDENT_FAILED_OPERATION,
            reason_code="initial-create-step-readback-unavailable-or-mismatch",
        )
        return store

    def _build_plan(self, client: FakeClient, store: MemoryHistoryStore):
        return build_staging_normalization_recovery_plan(
            target_id=RECOVERY_TARGET,
            client=client,
            repo_root=self.repo_root,
            state=self._state(),
            store=store,
            current_source_sha=CURRENT_SHA,
            source_steps=self.source_steps,
            asset_report=self.asset_report,
            module_position=int(self.module["position"]),
            lesson_position=int(self.lesson_manifest["position"]),
            expected_title=self.expected_title,
        )

    def test_current_canonical_no_longer_matches_recorded_incident(self) -> None:
        legacy = compiled_lesson_fingerprint(
            expected_title=self.expected_title,
            expected_steps=self.legacy_steps,
        )
        normalized = compiled_lesson_fingerprint(
            expected_title=self.expected_title,
            expected_steps=self.normalized_steps,
        )
        self.assertNotEqual(legacy, INCIDENT_LEGACY_DESIRED)
        self.assertNotEqual(normalized, INCIDENT_LEGACY_DESIRED)

    def test_obsolete_incident_recovery_fails_closed_before_any_new_post(self) -> None:
        snapshot = self._snapshot()
        client = FakeClient(snapshot)
        store = self._history(snapshot)
        with self.assertRaisesRegex(ContentWriteError, "historical v1"):
            self._build_plan(client, store)
        self.assertEqual(client.create_positions, [])

    def test_live_step2_drift_also_never_creates_a_new_post(self) -> None:
        snapshot = self._snapshot()
        snapshot["sections"][0]["units"][0]["lesson"]["steps"][1]["step_source"]["block"]["text"] += "<p>drift</p>"
        client = FakeClient(snapshot)
        store = self._history(self._snapshot())
        with self.assertRaises(ContentWriteError):
            self._build_plan(client, store)
        self.assertEqual(client.create_positions, [])


if __name__ == "__main__":
    unittest.main()
