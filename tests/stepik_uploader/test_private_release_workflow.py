from __future__ import annotations

import unittest
from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/stepik-private-release.yml")


class PrivateReleaseWorkflowTests(unittest.TestCase):
    def test_pr_runs_tests_only_and_live_job_is_manual(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        jobs = data["jobs"]
        self.assertIn("tests", jobs)
        self.assertIn("release", jobs)
        self.assertEqual(jobs["release"]["if"], "github.event_name == 'workflow_dispatch'")
        self.assertIn("workflow_dispatch", raw)
        self.assertIn("confirm_write", raw)

    def test_live_job_uses_fixed_course_mutex_and_current_main_guard(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: stepik-live-course-299189", raw)
        self.assertNotIn("group: stepik-live-course-${{ inputs.course_id }}", raw)
        self.assertGreaterEqual(raw.count("live_guard.py"), 4)
        self.assertIn('if [[ "$COURSE_ID" != "299189" ]]', raw)

    def test_all_preflights_precede_any_mutating_route(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        course_preflight = raw.index("Preflight course page без записи")
        m00_l02_preflight = raw.index("Preflight owner-approved M00-L02 content refresh без записи")
        m00_l01_preflight = raw.index("Preflight owner-approved M00-L01 6→6 без записи")
        ordinary_preflight = raw.index("Preflight всех ordinary PENDING lessons без записи")
        ordinary_write = raw.index("Последовательно записать ordinary PENDING lessons")
        course_write = raw.index("Синхронизировать course page или закрыть доказанный commit-gap")
        m00_l02_write = raw.index("Обновить owner-approved M00-L02 перед M00-L01")
        m00_l01_write = raw.index("Обновить owner-approved M00-L01 6→6 последним")
        self.assertLess(course_preflight, ordinary_write)
        self.assertLess(m00_l02_preflight, ordinary_write)
        self.assertLess(m00_l01_preflight, ordinary_write)
        self.assertLess(ordinary_preflight, ordinary_write)
        self.assertLess(ordinary_write, course_write)
        self.assertLess(course_write, m00_l02_write)
        self.assertLess(m00_l02_write, m00_l01_write)

    def test_course_page_recovery_probe_is_read_only_and_write_phase_is_confirmed(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        preflight = raw[raw.index("Preflight course page без записи"):raw.index("Preflight owner-approved M00-L02")]
        write = raw[raw.index("Синхронизировать course page или закрыть доказанный commit-gap"):raw.index("Обновить owner-approved M00-L02")]
        self.assertIn("course_page_commit_gap_recovery.py", preflight)
        self.assertNotIn("--confirm-recovery", preflight)
        self.assertIn("course_page_commit_gap_recovery.py", write)
        self.assertIn("--confirm-recovery", write)
        self.assertIn("already closed", write)

    def test_ordinary_scope_splits_initial_refresh_and_recovery_modes(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("refresh_target_ids", raw)
        self.assertIn("initial_target_ids", raw)
        self.assertIn("recovery_target_ids", raw)
        self.assertIn("staging_refresh_runtime.py", raw)
        self.assertIn("staging_build_entrypoint.py", raw)
        self.assertIn("staging_commit_gap_recovery.py", raw)
        self.assertGreaterEqual(raw.count("target in plan.get('refresh_target_ids', [])"), 2)

    def test_ordinary_write_commits_machine_state_before_history(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        block = raw[raw.index("Последовательно записать ordinary PENDING lessons"):raw.index("Синхронизировать course page")]
        patch = block.index("gh api --method PATCH")
        asset_history = block.index("history_cli.py mark-state-committed --event-file \"$event\"")
        lesson_history = block.index("history_cli.py mark-state-committed --event-file \"$lesson_event\"")
        self.assertLess(patch, asset_history)
        self.assertLess(asset_history, lesson_history)

    def test_golden_refresh_order_preserves_old_fixture_until_m00_l02_is_done(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        l02 = raw.index("Обновить owner-approved M00-L02 перед M00-L01")
        l01 = raw.index("Обновить owner-approved M00-L01 6→6 последним")
        self.assertLess(l02, l01)
        l02_block = raw[l02:l01]
        l01_block = raw[l01:]
        self.assertIn("golden_content_migration.py", l02_block)
        self.assertIn("golden_content_refresh_m00_l01_6to6.py", l01_block)
        self.assertIn("--confirm-write", l02_block)
        self.assertIn("--confirm-write", l01_block)
        self.assertGreaterEqual(raw.count("--target-id M00-L02"), 2)
        self.assertGreaterEqual(raw.count("--target-id M00-L01"), 2)
        self.assertIn("golden_commit_gap_recovery.py", l02_block)
        self.assertIn("golden_commit_gap_recovery.py", l01_block)

    def test_closed_golden_routes_recover_commit_gap_without_stepik_write(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(raw.count("golden_commit_gap_recovery.py"), 4)
        l02 = raw[raw.index("Обновить owner-approved M00-L02 перед M00-L01"):raw.index("Обновить owner-approved M00-L01 6→6 последним")]
        l01 = raw[raw.index("Обновить owner-approved M00-L01 6→6 последним"):raw.index("Проверить финальный machine backlog")]
        for block, target in ((l02, "M00-L02"), (l01, "M00-L01")):
            self.assertIn(f"--target-id {target}", block)
            self.assertIn("lesson-deployment-event.json", block)
            self.assertIn("history_cli.py mark-state-committed", block)
            self.assertIn("commit-gap recovered without Stepik write", block)

    def test_final_gate_requires_zero_pending_both_golden_baselines_and_fresh_capture(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        final = raw[raw.index("Проверить финальный machine backlog"):]
        self.assertIn("if lessons:", final)
        self.assertIn("pending.get('course_page')", final)
        self.assertIn("('M00-L01', 6)", final)
        self.assertIn("('M00-L02', 8)", final)
        self.assertIn("golden_profile_capture.py", final)
        self.assertIn("golden-profile.final.next.json", final)
        self.assertIn("golden-profile-final-capture.json", final)


if __name__ == "__main__":
    unittest.main()
