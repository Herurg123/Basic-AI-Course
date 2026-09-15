from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.compiler_report import build_report


class CompilerReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.report = build_report(cls.repo_root)

    def test_real_course_report_matches_closed_source_compiler_gate(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(summary["lessons"], 21)
        self.assertEqual(summary["structural_plan_rows"], 150)
        self.assertEqual(summary["author_only_rows_excluded"], 2)
        self.assertEqual(summary["compiled_learner_steps"], 148)
        self.assertEqual(len(self.report["lessons"]), 21)
        self.assertEqual(
            {item["canonical_id"] for item in self.report["lessons"]},
            {f"M{module:02d}-L{lesson:02d}" for module, lesson_count in ((0, 3), (1, 2), (2, 2), (3, 2), (4, 3), (5, 2), (6, 4), (7, 2), (8, 1)) for lesson in range(1, lesson_count + 1)},
        )

    def test_report_cannot_claim_bulk_write_readiness(self) -> None:
        self.assertEqual(self.report["stepik_writes"], 0)
        self.assertFalse(self.report["writer_enabled"])
        self.assertEqual(self.report["next_gate"], "asset-publication-resolution")
        self.assertGreater(
            self.report["summary"]["repo_relative_links_pending_asset_route"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
