from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_resolution_report import build_asset_resolution_report


class AssetResolutionReportTests(unittest.TestCase):
    def test_current_course_report_closes_route_gate_without_unlocking_bulk_write(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        report = build_asset_resolution_report(repo_root, course_id=299189)

        self.assertTrue(report["route_gate_passed"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["unresolved_sources"], [])
        self.assertEqual(report["decision"], "D-2026-09-15-STEPIK-ATTACHMENTS")
        self.assertEqual(report["summary"]["resolved_occurrences"], 49)
        self.assertEqual(report["summary"]["resolved_unique_source_files"], 43)
        self.assertEqual(report["summary"]["materialization_required_unique_files"], 5)
        self.assertEqual(report["stepik_writes"], 0)
        self.assertFalse(report["ready_for_bulk_write"])
        self.assertEqual(report["next_gate"], "verified-rendering-and-first-upload")
        self.assertEqual(
            report["topology_fingerprint"],
            "sha256:ecbb9f9b8426c5bd4bba9f07816ab0e647022c13c0f38b4c29d9debd6096c20d",
        )


if __name__ == "__main__":
    unittest.main()
