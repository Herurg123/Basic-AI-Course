from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.stepik_uploader import main, parse_args


class CLITests(unittest.TestCase):
    def test_content_test_requires_explicit_confirmation_flag(self) -> None:
        args = parse_args(["content-test-one", "--course-id", "299189"])
        self.assertFalse(args.confirm_write)
        self.assertEqual(args.test_lesson, "M02-L01")

    def test_confirmation_is_explicit_and_target_remains_fixed_by_default(self) -> None:
        args = parse_args(["content-test-one", "--course-id", "299189", "--confirm-write"])
        self.assertTrue(args.confirm_write)
        self.assertEqual(args.test_lesson, "M02-L01")

    def test_default_safe_modes_do_not_enable_confirmation(self) -> None:
        for mode in ("inspect", "dry-run"):
            with self.subTest(mode=mode):
                args = parse_args([mode, "--course-id", "299189"])
                self.assertFalse(args.confirm_write)

    def test_unconfirmed_content_test_stops_before_credentials_or_write(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            code = main(
                [
                    "content-test-one",
                    "--repo-root",
                    str(repo_root),
                    "--report-dir",
                    str(report_dir),
                    "--course-id",
                    "299189",
                ]
            )
            self.assertEqual(code, 2)
            report = json.loads((report_dir / "run-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "BLOCKED")
            self.assertIn("explicit-confirm-write-required", report["blockers"])


if __name__ == "__main__":
    unittest.main()
