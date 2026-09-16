from __future__ import annotations

import unittest
from pathlib import Path


class StagingCommitGapWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.workflow = (self.repo_root / ".github/workflows/stepik-staging-build.yml").read_text(encoding="utf-8")

    def test_commit_gap_probe_runs_before_initial_runtime(self) -> None:
        recovery = "python scripts/stepik_uploader/staging_commit_gap_recovery.py"
        initial = "python scripts/stepik_uploader/staging_build_runtime.py"
        self.assertIn(recovery, self.workflow)
        self.assertIn(initial, self.workflow)
        self.assertLess(self.workflow.index(recovery), self.workflow.index(initial))
        self.assertIn("if: steps.recovery.outputs.applicable != 'true'", self.workflow)

    def test_commit_gap_recovery_never_bypasses_owner_confirmation_for_history_write(self) -> None:
        commit_step = self.workflow.index("Зафиксировать confirmed state и durable history")
        block = self.workflow[commit_step:]
        self.assertIn("if: inputs.confirm_write == true && success()", block)
        self.assertIn("sync_issue_state.py compare", block)
        self.assertIn("history_cli.py mark-state-committed", block)
        self.assertNotIn("continue-on-error: true", block)

    def test_pull_request_runs_offline_tests_only(self) -> None:
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)
        tests_index = self.workflow.index("  tests:\n")
        live_index = self.workflow.index("  staging-build:\n")
        tests_block = self.workflow[tests_index:live_index]
        self.assertNotIn("STEPIC_CLIENT_ID", tests_block)
        self.assertNotIn("STEPIC_CLIENT_SECRET", tests_block)


if __name__ == "__main__":
    unittest.main()
