from __future__ import annotations

import copy
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import scripts.stepik_uploader.golden_content_migration as migration
from scripts.stepik_uploader.deployment_history import DeploymentHistoryError, DeploymentRecorder, MemoryHistoryStore, event_identity_from_environment
from scripts.stepik_uploader.fingerprints import canonical_hash
from scripts.stepik_uploader.golden_content_migration import (
    TARGET_ID,
    _fixture_fingerprint,
    _history_state,
    _next_profile,
)


SHA = "2" * 40
DESIRED = "sha256:" + "3" * 64


def profile() -> dict:
    return {
        "schema_version": "1.0",
        "status": "confirmed-read-only",
        "course_id": 299189,
        "course_state": {"language": "ru", "is_public": False},
        "golden_lessons": {
            "M00-L01": {
                "stepik_section_id": 11,
                "stepik_unit_id": 101,
                "stepik_lesson_id": 201,
                "lesson_title": "Первый",
                "section_position": 1,
                "unit_position": 1,
                "language": "ru",
                "is_public": False,
                "step_count": 1,
                "block_sequence": ["text"],
                "step_text_sha256": [],
            },
            TARGET_ID: {
                "stepik_section_id": 11,
                "stepik_unit_id": 102,
                "stepik_lesson_id": 202,
                "lesson_title": "Второй",
                "section_position": 1,
                "unit_position": 2,
                "language": "ru",
                "is_public": False,
                "plan_rows": 7,
                "step_count": 7,
                "block_sequence": ["text"] * 7,
                "step_text_sha256": [],
                "free_answer_positions": [],
            },
        },
        "observed_conventions": {"free_answer_source": {}},
    }


def snapshot(step_count: int = 8) -> dict:
    steps = [
        {
            "id": 1000 + pos,
            "step_source": {
                "id": 1000 + pos,
                "position": pos,
                "block": {"name": "text", "source": {}, "text": f"<p>Шаг {pos}</p>"},
            },
        }
        for pos in range(1, step_count + 1)
    ]
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
                            "title": "Первый",
                            "language": "ru",
                            "is_public": False,
                            "steps": [{"step_source": {"position": 1, "block": {"name": "text", "source": {}, "text": ""}}}],
                        },
                    },
                    {
                        "id": 102,
                        "position": 2,
                        "lesson": {
                            "id": 202,
                            "title": "Второй",
                            "language": "ru",
                            "is_public": False,
                            "steps": steps,
                        },
                    },
                ],
            }
        ],
    }


class GoldenContentMigrationTests(unittest.TestCase):
    def test_fixture_fingerprint_changes_when_old_contract_changes(self) -> None:
        first = profile()
        second = copy.deepcopy(first)
        second["golden_lessons"][TARGET_ID]["step_count"] = 6
        self.assertNotEqual(_fixture_fingerprint(first), _fixture_fingerprint(second))

    def test_history_without_records_is_new(self) -> None:
        state, baseline = _history_state([], "sha256:" + "1" * 64, DESIRED)
        self.assertEqual(state, "NEW")
        self.assertIsNone(baseline)

    def test_partial_history_requires_exact_last_confirmed_fingerprint(self) -> None:
        store = MemoryHistoryStore()
        identity = event_identity_from_environment(
            course_id=299189,
            object_id=TARGET_ID,
            kind="golden-content-migration",
            source_sha=SHA,
            desired_fingerprint=DESIRED,
            baseline_fingerprint=canonical_hash({"old": 7}),
            pending_first_sha=None,
        )
        recorder = DeploymentRecorder(store, identity)
        before = "sha256:" + "4" * 64
        after = "sha256:" + "5" * 64
        recorder.ensure_started(
            operation_type="golden-content-7-to-8",
            state_before={"fixture": 7},
            expected_state={"desired": 8},
            stepik_object_ids={"lesson_id": 202},
            fingerprint_before=before,
        )
        recorder.write_intent(
            operation_id="update-0001-1001",
            method="PUT",
            target="step-sources/1001",
            fingerprint_before=before,
            expected_fingerprint_after=after,
        )
        recorder.write_dispatch_started(operation_id="update-0001-1001")
        recorder.write_result(operation_id="update-0001-1001", status="COMPLETED")
        recorder.operation_readback(operation_id="update-0001-1001", expected_fingerprint_after=after)
        records = store.load(identity.event_id)
        state, _ = _history_state(records, after, DESIRED)
        self.assertEqual(state, "PARTIAL_CONFIRMED")
        with self.assertRaises(DeploymentHistoryError):
            _history_state(records, before, DESIRED)

    def test_next_profile_rebaselines_only_from_final_live(self) -> None:
        p = profile()
        live = snapshot(8)
        # M00-L01 must remain valid for whole-profile validation.
        import hashlib
        p["golden_lessons"]["M00-L01"]["step_text_sha256"] = [hashlib.sha256(b"").hexdigest()]
        proposed = _next_profile(p, live, sha=SHA)
        row = proposed["golden_lessons"][TARGET_ID]
        self.assertEqual(row["plan_rows"], 8)
        self.assertEqual(row["step_count"], 8)
        self.assertEqual(len(row["step_text_sha256"]), 8)
        self.assertEqual(proposed["observed_source_sha"], SHA)

    def test_entrypoint_routes_accepted_8_step_fixture_to_noop_path(self) -> None:
        args = Namespace(
            course_id=299189,
            repo_root=Path("."),
            report_dir=Path("artifacts/test"),
            sync_state=Path("state.json"),
            api_host="https://stepik.org",
            confirm_write=False,
        )
        accepted = profile()
        accepted["golden_lessons"][TARGET_ID]["step_count"] = 8
        with (
            patch.object(migration.legacy, "parse_args", return_value=args),
            patch.object(migration.legacy, "load_golden_profile", return_value=accepted),
            patch.object(migration, "_current_fixture_noop", return_value=0) as noop,
            patch.object(migration.legacy, "main", return_value=99) as old_route,
        ):
            self.assertEqual(migration.main(), 0)
        noop.assert_called_once_with(args, accepted)
        old_route.assert_not_called()

    def test_entrypoint_keeps_7_step_fixture_on_proven_writer(self) -> None:
        args = Namespace(
            course_id=299189,
            repo_root=Path("."),
            report_dir=Path("artifacts/test"),
            sync_state=Path("state.json"),
            api_host="https://stepik.org",
            confirm_write=False,
        )
        old = profile()
        with (
            patch.object(migration.legacy, "parse_args", return_value=args),
            patch.object(migration.legacy, "load_golden_profile", return_value=old),
            patch.object(migration.legacy, "main", return_value=0) as old_route,
            patch.object(migration, "_current_fixture_noop", return_value=99) as noop,
        ):
            self.assertEqual(migration.main(), 0)
        old_route.assert_called_once_with()
        noop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
