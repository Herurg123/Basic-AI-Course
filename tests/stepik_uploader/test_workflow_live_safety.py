from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowLiveSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.uploader = (self.repo_root / ".github/workflows/stepik-uploader.yml").read_text(encoding="utf-8")
        self.bulk = (self.repo_root / ".github/workflows/stepik-bulk-status.yml").read_text(encoding="utf-8")

    def test_both_live_workflows_use_same_course_mutex(self) -> None:
        shared = "group: stepik-live-course-299189"
        self.assertEqual(self.uploader.count(shared), 1)
        self.assertEqual(self.bulk.count(shared), 1)
        self.assertIn("cancel-in-progress: false", self.uploader)
        self.assertIn("cancel-in-progress: false", self.bulk)

    def test_mutex_is_not_derived_from_user_supplied_course_id(self) -> None:
        unsafe = "group: stepik-live-course-${{ inputs.course_id }}"
        self.assertNotIn(unsafe, self.uploader)
        self.assertNotIn(unsafe, self.bulk)

    def test_old_independent_live_concurrency_groups_are_removed(self) -> None:
        self.assertNotIn("stepik-uploader-${{ github.event_name }}-${{ github.ref }}", self.uploader)
        self.assertNotIn("stepik-bulk-status-${{ github.ref }}", self.bulk)

    def test_live_guard_runs_in_both_workflows(self) -> None:
        command = "python scripts/stepik_uploader/live_guard.py"
        self.assertEqual(self.uploader.count(command), 1)
        self.assertEqual(self.bulk.count(command), 1)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.uploader)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.bulk)

    def test_bulk_offline_tests_are_not_inside_live_mutex_job(self) -> None:
        tests_index = self.bulk.index("  tests:\n")
        bulk_index = self.bulk.index("  bulk_status:\n")
        tests_block = self.bulk[tests_index:bulk_index]
        self.assertNotIn("stepik-live-course-", tests_block)
        self.assertNotIn("STEPIC_CLIENT_ID", tests_block)
        self.assertNotIn("STEPIC_CLIENT_SECRET", tests_block)


if __name__ == "__main__":
    unittest.main()
