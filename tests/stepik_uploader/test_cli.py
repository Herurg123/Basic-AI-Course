from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.stepik_uploader import main, parse_args


class CLITests(unittest.TestCase):
    def test_cli_exposes_only_read_only_modes(self) -> None:
        for mode in ("inspect", "dry-run"):
            with self.subTest(mode=mode):
                args = parse_args([mode])
                self.assertEqual(args.mode, mode)

    def test_dry_run_never_requires_write_confirmation(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "dry-run",
                    "--repo-root",
                    str(repo_root),
                    "--report-dir",
                    tmp,
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "platform-profile-check.json").is_file())


if __name__ == "__main__":
    unittest.main()
