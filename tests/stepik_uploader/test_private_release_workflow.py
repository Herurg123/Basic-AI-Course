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
        ordinary_preflight = raw.index("Preflight всех ordinary PENDING lessons без записи")
        ordinary_write = raw.index("Последовательно записать ordinary PENDING lessons")
        course_write = raw.index("Синхронизировать course page или закрыть доказанный commit-gap")
        golden_write = raw.index("Мигрировать M00-L02 с 7 на 8 шагов последним")
        self.assertLess(ordinary_preflight, ordinary_write)
        self.assertLess(ordinary_write, course_write)
        self.assertLess(course_write, golden_write)

    def test_course_page_recovery_probe_is_read_only_and_write_phase_is_confirmed(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        preflight = raw[raw.index("Preflight course page без записи"):raw.index("Preflight owner-approved M00-L02")]
        write = raw[raw.index("Синхронизировать course page или закрыть доказанный commit-gap"):raw.index("Мигрировать M00-L02")]
        self.assertIn("course_page_commit_gap_recovery.py", preflight)
        self.assertNotIn("--confirm-recovery", preflight)
        self.assertIn("course_page_commit_gap_recovery.py", write)
        self.assertIn("--confirm-recovery", write)
        self.assertIn("already closed", write)

    def test_golden_migration_is_last_and_never_uses_ordinary_target_flag(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        golden = raw[raw.index("Мигрировать M00-L02 с 7 на 8 шагов последним"):]
        self.assertIn("golden_content_migration.py", golden)
        self.assertIn("--confirm-write", golden)
        self.assertNotIn("--target-id M00-L02", raw)
        self.assertIn("golden-profile.next.json", golden)


if __name__ == "__main__":
    unittest.main()
