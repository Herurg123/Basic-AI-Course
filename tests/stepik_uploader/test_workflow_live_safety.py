from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowLiveSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.uploader_path = self.repo_root / ".github/workflows/stepik-uploader.yml"
        self.release_path = self.repo_root / ".github/workflows/stepik-private-release.yml"
        self.uploader = self.uploader_path.read_text(encoding="utf-8")
        self.release = self.release_path.read_text(encoding="utf-8")

    def test_only_current_stepik_workflows_remain(self) -> None:
        workflows = {path.name for path in (self.repo_root / ".github/workflows").glob("stepik-*.yml")}
        self.assertEqual(workflows, {"stepik-uploader.yml", "stepik-private-release.yml"})

    def test_all_live_stepik_jobs_share_fixed_course_mutex(self) -> None:
        shared = "group: stepik-live-course-299189"
        self.assertEqual(self.uploader.count(shared), 1)
        self.assertEqual(self.release.count(shared), 1)
        self.assertNotIn("group: stepik-live-course-${{ inputs.course_id }}", self.uploader)
        self.assertNotIn("group: stepik-live-course-${{ inputs.course_id }}", self.release)
        self.assertIn("cancel-in-progress: false", self.uploader)
        self.assertIn("cancel-in-progress: false", self.release)

    def test_uploader_manual_mode_is_read_only(self) -> None:
        self.assertIn("- dry-run", self.uploader)
        self.assertIn("- inspect", self.uploader)
        self.assertIn("- target-preflight", self.uploader)

        inspect = self.uploader[self.uploader.index("  inspect:"):]
        self.assertNotIn("--confirm-write", inspect)
        self.assertNotIn("--confirm-recovery", inspect)
        self.assertNotIn("contents: write", inspect)
        self.assertNotIn("issues: write", inspect)
        self.assertNotIn("gh api --method PATCH", inspect)
        self.assertNotIn("history_cli.py mark-state-committed", inspect)
        self.assertNotIn("special_history_commit.py", inspect)
        self.assertNotIn("gh issue comment", inspect)

        # Read-only target-preflight may reuse the exact production runtime in
        # preflight mode. Write authority is controlled by explicit confirmation
        # flags and permissions, not by merely importing/invoking the runtime.
        self.assertIn("staging_refresh_runtime.py", inspect)
        self.assertIn("staging_build_runtime.py", inspect)
        self.assertIn("course_page_sync.py", inspect)

        self.assertNotIn("first_upload_runtime.py", self.uploader)
        self.assertNotIn("sync_runtime.py", self.uploader)

    def test_private_release_is_only_stepik_write_entry_point(self) -> None:
        self.assertIn("confirm_write", self.release)
        self.assertIn("staging_refresh_runtime.py", self.release)
        self.assertIn("staging_build_runtime.py", self.release)
        self.assertIn("course_page_sync.py", self.release)
        self.assertNotIn("golden", self.release.lower())
        self.assertNotIn("learner_hygiene", self.release)
        self.assertNotIn("section_position_recovery", self.release)

    def test_current_main_guard_runs_before_live_api_routes(self) -> None:
        self.assertIn("python scripts/stepik_uploader/live_guard.py", self.uploader)
        self.assertIn("python scripts/stepik_uploader/live_guard.py", self.release)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.uploader)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.release)

    def test_pending_impact_update_does_not_call_stepik_api(self) -> None:
        impact_start = self.uploader.index("  impact:")
        inspect_start = self.uploader.index("  inspect:")
        impact = self.uploader[impact_start:inspect_start]
        self.assertNotIn("STEPIC_CLIENT_ID", impact)
        self.assertNotIn("STEPIC_CLIENT_SECRET", impact)
        self.assertIn("impact.py", impact)
        self.assertIn("sync_issue_state.py apply-impact", impact)

    def test_no_retired_workflow_files_exist(self) -> None:
        retired = [
            "stepik-bulk-status.yml",
            "stepik-golden-title-migration.yml",
            "stepik-learner-hygiene.yml",
            "stepik-section-position-recovery.yml",
            "stepik-staging-batch.yml",
            "stepik-staging-build.yml",
        ]
        for name in retired:
            with self.subTest(name=name):
                self.assertFalse((self.repo_root / ".github/workflows" / name).exists())


if __name__ == "__main__":
    unittest.main()
