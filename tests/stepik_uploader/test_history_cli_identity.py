from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.deployment_history import stable_event_id
from scripts.stepik_uploader.history_cli import _baseline_from_state, _history_identity, _normalize_event_from_history


class HistoryCliIdentityTests(unittest.TestCase):
    def test_mislabeled_lesson_artifact_is_normalized_to_immutable_object_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_file = Path(tmp) / "event.json"
            event = {
                "event_id": "evt-123",
                "source_sha": "a" * 40,
                "kind": "lesson",
                "canonical_id": "M00-L02",
                "status": "APPLIED",
            }
            event_file.write_text(json.dumps(event), encoding="utf-8")
            identity = {
                "event_id": "evt-123",
                "source_sha": "a" * 40,
                "kind": "lesson",
                "object_id": "M00-L01",
            }
            normalized = _normalize_event_from_history(event, identity, event_file=event_file)
            self.assertEqual(normalized["canonical_id"], "M00-L01")
            persisted = json.loads(event_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["canonical_id"], "M00-L01")
            state = {
                "lessons": {
                    "M00-L01": {"canonical_id": "M00-L01", "stepik_lesson_id": 1},
                    "M00-L02": {"canonical_id": "M00-L02", "stepik_lesson_id": 2},
                }
            }
            self.assertEqual(
                _baseline_from_state(normalized, state)["canonical_id"],
                "M00-L01",
            )

    def test_golden_content_history_is_lesson_like_and_uses_immutable_object_id(self) -> None:
        for kind in ("golden-content-refresh", "golden-content-migration"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                event_file = Path(tmp) / "event.json"
                event = {
                    "event_id": "evt-golden",
                    "source_sha": "c" * 40,
                    "kind": "lesson",
                    "canonical_id": "WRONG",
                    "status": "APPLIED",
                }
                event_file.write_text(json.dumps(event), encoding="utf-8")
                identity = {
                    "event_id": "evt-golden",
                    "source_sha": "c" * 40,
                    "kind": kind,
                    "object_id": "M00-L02",
                }
                normalized = _normalize_event_from_history(event, identity, event_file=event_file)
                self.assertEqual(normalized["kind"], kind)
                self.assertEqual(normalized["canonical_id"], "M00-L02")
                state = {"lessons": {"M00-L02": {"canonical_id": "M00-L02", "stepik_lesson_id": 2}}}
                self.assertEqual(_baseline_from_state(normalized, state)["canonical_id"], "M00-L02")


    def test_history_identity_allows_same_event_across_workflow_runs(self) -> None:
        source_sha = "d" * 40
        desired = "sha256:" + "a" * 64
        baseline = "sha256:" + "b" * 64
        pending_first_sha = "e" * 40
        event_id = stable_event_id(
            course_id=299189,
            object_id="M00-L02",
            kind="golden-content-refresh",
            source_sha=source_sha,
            desired_fingerprint=desired,
            baseline_fingerprint=baseline,
            pending_first_sha=pending_first_sha,
        )

        def identity(run_id: str) -> dict:
            return {
                "event_id": event_id,
                "course_id": 299189,
                "object_id": "M00-L02",
                "kind": "golden-content-refresh",
                "source_sha": source_sha,
                "workflow": {"run_id": run_id, "run_attempt": "1", "run_url": None},
                "desired_fingerprint": desired,
                "baseline_fingerprint_before": baseline,
                "pending_first_sha": pending_first_sha,
                "retry_of_event_id": None,
                "continuation_of_event_id": None,
            }

        records = [
            {
                "history_schema_version": 1,
                "record_id": "r1",
                "phase": "EVENT_STARTED",
                "identity": identity("100"),
                "fingerprint_before": baseline,
            },
            {
                "history_schema_version": 1,
                "record_id": "r2",
                "phase": "RECOVERY_CLASSIFIED",
                "identity": identity("200"),
            },
        ]

        class Store:
            def load(self, value: str) -> list[dict]:
                self.assert_event = value
                return records

        resolved = _history_identity(Store(), {"event_id": event_id, "source_sha": source_sha})
        self.assertEqual(resolved["event_id"], event_id)
        self.assertEqual(resolved["object_id"], "M00-L02")

    def test_asset_identity_reconstructs_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_file = Path(tmp) / "event.json"
            event = {
                "event_id": "evt-asset",
                "source_sha": "b" * 40,
                "kind": "asset",
                "source_path": "wrong.png",
                "status": "APPLIED",
            }
            event_file.write_text(json.dumps(event), encoding="utf-8")
            identity = {
                "event_id": "evt-asset",
                "source_sha": "b" * 40,
                "kind": "asset",
                "object_id": "asset:05_assets/M05/M05-L01/M05-L01-A02.svg",
            }
            normalized = _normalize_event_from_history(event, identity, event_file=event_file)
            self.assertEqual(
                normalized["source_path"],
                "05_assets/M05/M05-L01/M05-L01-A02.svg",
            )
            self.assertNotIn("canonical_id", normalized)


if __name__ == "__main__":
    unittest.main()
