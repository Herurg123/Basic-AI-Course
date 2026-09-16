from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowLiveSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.uploader = (self.repo_root / ".github/workflows/stepik-uploader.yml").read_text(encoding="utf-8")
        self.bulk = (self.repo_root / ".github/workflows/stepik-bulk-status.yml").read_text(encoding="utf-8")
        self.hygiene = (self.repo_root / ".github/workflows/stepik-learner-hygiene.yml").read_text(encoding="utf-8")

    def test_all_live_workflows_use_same_course_mutex(self) -> None:
        shared = "group: stepik-live-course-299189"
        self.assertEqual(self.uploader.count(shared), 1)
        self.assertEqual(self.bulk.count(shared), 1)
        self.assertEqual(self.hygiene.count(shared), 1)
        self.assertIn("cancel-in-progress: false", self.uploader)
        self.assertIn("cancel-in-progress: false", self.bulk)
        self.assertIn("cancel-in-progress: false", self.hygiene)

    def test_mutex_is_not_derived_from_user_supplied_course_id(self) -> None:
        unsafe = "group: stepik-live-course-${{ inputs.course_id }}"
        self.assertNotIn(unsafe, self.uploader)
        self.assertNotIn(unsafe, self.bulk)
        self.assertNotIn(unsafe, self.hygiene)

    def test_old_independent_live_concurrency_groups_are_removed(self) -> None:
        self.assertNotIn("stepik-uploader-${{ github.event_name }}-${{ github.ref }}", self.uploader)
        self.assertNotIn("stepik-bulk-status-${{ github.ref }}", self.bulk)
        self.assertNotIn("stepik-learner-hygiene-${{ github.ref }}", self.hygiene)

    def test_live_guard_runs_before_every_live_runtime(self) -> None:
        command = "python scripts/stepik_uploader/live_guard.py"
        self.assertEqual(self.uploader.count(command), 1)
        self.assertEqual(self.bulk.count(command), 1)
        self.assertEqual(self.hygiene.count(command), 1)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.uploader)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.bulk)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.hygiene)
        live_index = self.hygiene.index("  live:\n")
        live_block = self.hygiene[live_index:]
        self.assertLess(
            live_block.index("python scripts/stepik_uploader/live_guard.py"),
            live_block.index("python scripts/stepik_uploader/learner_hygiene_entrypoint.py"),
        )

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

    def test_hygiene_live_job_is_manual_and_requires_explicit_confirmation(self) -> None:
        self.assertIn("workflow_dispatch:", self.hygiene)
        self.assertIn("confirm_write:", self.hygiene)
        self.assertIn("default: false", self.hygiene)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.hygiene)
        self.assertIn('"$COURSE_ID" != "299189"', self.hygiene)
        self.assertIn('if [[ "${CONFIRM_WRITE:-false}" == "true" ]]; then', self.hygiene)
        self.assertIn(
            'python scripts/stepik_uploader/learner_hygiene_entrypoint.py "${args[@]}" --confirm-write',
            self.hygiene,
        )
        self.assertIn(
            'python scripts/stepik_uploader/learner_hygiene_preflight.py "${args[@]}"',
            self.hygiene,
        )
        self.assertNotIn(
            'python scripts/stepik_uploader/learner_hygiene_entrypoint.py "${args[@]}"\n',
            self.hygiene,
        )

    def test_hygiene_pr_event_runs_tests_but_never_live_job(self) -> None:
        self.assertIn("pull_request:", self.hygiene)
        tests_index = self.hygiene.index("  tests:\n")
        live_index = self.hygiene.index("  live:\n")
        tests_block = self.hygiene[tests_index:live_index]
        self.assertNotIn("STEPIC_CLIENT_ID", tests_block)
        self.assertNotIn("STEPIC_CLIENT_SECRET", tests_block)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.hygiene[live_index:])

    def test_hygiene_machine_state_patch_precedes_history_commit(self) -> None:
        race_index = self.hygiene.index("Race-check и обновить Issue 54")
        history_index = self.hygiene.index("Commit durable history только после machine-state boundary")
        self.assertLess(race_index, history_index)
        block = self.hygiene[race_index:]
        self.assertIn("sync_issue_state.py compare", block)
        self.assertIn("state-update-required.flag", block)
        self.assertIn("sync_issue_state.py replace", block)
        self.assertIn("history_cli.py mark-state-committed", block)
        self.assertIn("sync-state.next.json", block)

    def test_hygiene_never_commits_history_when_runtime_or_state_race_fails(self) -> None:
        live_index = self.hygiene.index("  live:\n")
        live_block = self.hygiene[live_index:]
        runtime_index = live_block.index("python scripts/stepik_uploader/learner_hygiene_entrypoint.py")
        state_index = live_block.index("Race-check и обновить Issue 54")
        history_index = live_block.index("history_cli.py mark-state-committed")
        self.assertLess(runtime_index, state_index)
        self.assertLess(state_index, history_index)
        self.assertNotIn("continue-on-error: true", live_block)


if __name__ == "__main__":
    unittest.main()
