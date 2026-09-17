from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.stepik_uploader.staging_refresh_runtime import (
    _assessment_or_history_gate,
    _refresh_materialization_plan,
    _version_suffix,
)
from scripts.stepik_uploader.writer import ContentWriteError


class StagingRefreshRuntimeTests(unittest.TestCase):
    def assessment(self, status: str):
        return SimpleNamespace(
            status=status,
            reasons=("reason",),
            live_fingerprint="sha256:" + "1" * 64,
            desired_fingerprint="sha256:" + "2" * 64,
            baseline_fingerprint="sha256:" + "1" * 64,
        )

    def test_fresh_update_required_is_allowed(self) -> None:
        state, identity, records, summary = _assessment_or_history_gate(
            target_id="M01-L01",
            assessment=self.assessment("UPDATE_REQUIRED"),
            incomplete=[],
            desired_fp="sha256:" + "2" * 64,
            sha="a" * 40,
        )
        self.assertEqual(state, "FRESH")
        self.assertIsNone(identity)
        self.assertEqual(records, [])
        self.assertIsNone(summary)

    def test_fresh_drift_is_blocked(self) -> None:
        with self.assertRaises(ContentWriteError):
            _assessment_or_history_gate(
                target_id="M01-L01",
                assessment=self.assessment("DRIFT_BLOCKED"),
                incomplete=[],
                desired_fp="sha256:" + "2" * 64,
                sha="a" * 40,
            )

    def test_version_suffix_uses_source_sha_prefix(self) -> None:
        source_sha = "sha256:" + "abcdef123456" + "0" * 52
        self.assertEqual(_version_suffix(source_sha), "abcdef123456")

    def test_changed_existing_visual_gets_versioned_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "asset.svg"
            asset.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                '<rect width="20" height="20" fill="#ddd"/></svg>',
                encoding="utf-8",
            )
            from scripts.stepik_uploader.attachment_materialization import file_sha256

            current_sha = file_sha256(asset)
            rows = [
                {
                    "source_path": "asset.svg",
                    "source_sha256": current_sha,
                    "mode": "rasterize-png-stepik-image",
                }
            ]
            state = {
                "assets": {
                    "asset.svg": {
                        "source_sha256": "sha256:" + "0" * 64,
                        "materialization_mode": "rasterize-png-stepik-image",
                        "stepik_attachment_id": 42,
                    }
                }
            }
            plan = _refresh_materialization_plan(
                repo_root=root,
                report_dir=root / "report",
                rows=rows,
                state=state,
            )
            self.assertEqual(len(plan), 1)
            self.assertTrue(plan[0]["replacement"])
            self.assertEqual(plan[0]["filename_suffix"], current_sha.removeprefix("sha256:")[:12])
            self.assertIn(plan[0]["filename_suffix"], plan[0]["materialized_filename"])
            self.assertEqual(plan[0]["previous_attachment_id"], 42)

    def test_unchanged_existing_visual_reuses_unversioned_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "asset.svg"
            asset.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                '<rect width="20" height="20" fill="#ddd"/></svg>',
                encoding="utf-8",
            )
            from scripts.stepik_uploader.attachment_materialization import file_sha256

            current_sha = file_sha256(asset)
            rows = [
                {
                    "source_path": "asset.svg",
                    "source_sha256": current_sha,
                    "mode": "rasterize-png-stepik-image",
                }
            ]
            state = {
                "assets": {
                    "asset.svg": {
                        "source_sha256": current_sha,
                        "materialization_mode": "rasterize-png-stepik-image",
                        "stepik_attachment_id": 42,
                    }
                }
            }
            plan = _refresh_materialization_plan(
                repo_root=root,
                report_dir=root / "report",
                rows=rows,
                state=state,
            )
            self.assertFalse(plan[0]["replacement"])
            self.assertIsNone(plan[0]["filename_suffix"])
            self.assertEqual(plan[0]["materialized_filename"], "asset.png")


if __name__ == "__main__":
    unittest.main()
