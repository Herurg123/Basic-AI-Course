from __future__ import annotations

import unittest

from scripts.stepik_uploader.stepik_uploader import parse_args


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


if __name__ == "__main__":
    unittest.main()
