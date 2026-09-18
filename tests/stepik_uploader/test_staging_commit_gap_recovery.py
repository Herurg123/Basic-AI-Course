from __future__ import annotations

import unittest
from pathlib import Path


class StagingCommitGapWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.workflow = (self.repo_root / ".github/workflows/stepik-private-release.yml").read_text(encoding="utf-8")

    def test_commit_gap_probe_precedes_initial_runtime_in_unified_loop(self) -> None:
        block = self.workflow[
            self.workflow.index("Preflight всех PENDING lessons без записи"):
            self.workflow.index("Проверить неизменность source и scope перед write")
        ]
        recovery = "python scripts/stepik_uploader/staging_commit_gap_recovery.py"
        initial = "python scripts/stepik_uploader/staging_build_runtime.py"
        self.assertIn(recovery, block)
        self.assertIn(initial, block)
        self.assertLess(block.index(recovery), block.index(initial))

    def test_machine_state_patch_precedes_history_commit(self) -> None:
        block = self.workflow[
            self.workflow.index("Последовательно синхронизировать все PENDING lessons"):
            self.workflow.index("Синхронизировать course page")
        ]
        self.assertIn("sync_issue_state.py compare", block)
        self.assertIn("gh api --method PATCH", block)
        self.assertIn("history_cli.py mark-state-committed", block)
        self.assertLess(block.index("gh api --method PATCH"), block.index("history_cli.py mark-state-committed"))
        self.assertNotIn("continue-on-error: true", block)

    def test_pull_request_runs_offline_tests_only(self) -> None:
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)
        tests_index = self.workflow.index("  tests:\n")
        release_index = self.workflow.index("  release:\n")
        tests_block = self.workflow[tests_index:release_index]
        self.assertNotIn("STEPIC_CLIENT_ID", tests_block)
        self.assertNotIn("STEPIC_CLIENT_SECRET", tests_block)


if __name__ == "__main__":
    unittest.main()
