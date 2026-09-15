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

    def test_bulk_workflow_changes_trigger_regular_pr_ci(self) -> None:
        self.assertGreaterEqual(
            self.uploader.count("'.github/workflows/stepik-bulk-status.yml'"),
            2,
        )

    def test_first_upload_is_explicit_owner_mode_with_confirmation(self) -> None:
        self.assertIn("- first-upload-m04-l01", self.uploader)
        self.assertIn('[[ "$MODE" == "first-upload-m04-l01" ]]', self.uploader)
        self.assertIn("python scripts/stepik_uploader/first_upload_runtime.py", self.uploader)
        self.assertIn("--confirm-write", self.uploader)
        self.assertIn("inputs.mode == 'first-upload-m04-l01' && success()", self.uploader)

    def test_first_upload_reads_and_race_checks_machine_state(self) -> None:
        read_condition = (
            "inputs.mode == 'sync-status' || inputs.mode == 'sync-reconcile' || "
            "inputs.mode == 'sync-changed' || inputs.mode == 'first-upload-m04-l01'"
        )
        self.assertIn(read_condition, self.uploader)
        first_commit = self.uploader.index("Зафиксировать first upload")
        first_block = self.uploader[first_commit:]
        self.assertIn("sync-state.previous.json", first_block)
        self.assertIn("sync_issue_state.py compare", first_block)
        self.assertIn("sync_issue_state.py replace", first_block)
        self.assertIn("asset-deployment-event.json", first_block)
        self.assertIn("lesson-deployment-event.json", first_block)
        self.assertGreaterEqual(first_block.count("history_cli.py mark-state-committed"), 2)

    def test_first_upload_cannot_bypass_current_main_guard_or_mutex(self) -> None:
        live_index = self.uploader.index("  live:\n")
        live_block = self.uploader[live_index:]
        self.assertIn("group: stepik-live-course-299189", live_block)
        self.assertIn("python scripts/stepik_uploader/live_guard.py", live_block)
        self.assertLess(
            live_block.index("python scripts/stepik_uploader/live_guard.py"),
            live_block.index("python scripts/stepik_uploader/first_upload_runtime.py"),
        )


if __name__ == "__main__":
    unittest.main()
