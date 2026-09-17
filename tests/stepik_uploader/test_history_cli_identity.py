from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.history_cli import _baseline_from_state, _normalize_event_from_history


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
