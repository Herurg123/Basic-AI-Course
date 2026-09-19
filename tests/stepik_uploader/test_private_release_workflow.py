from __future__ import annotations

import unittest
from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/stepik-private-release.yml")


class PrivateReleaseWorkflowTests(unittest.TestCase):
    def test_pr_runs_tests_only_and_release_is_manual(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        jobs = data["jobs"]
        self.assertIn("tests", jobs)
        self.assertIn("release", jobs)
        self.assertEqual(jobs["release"]["if"], "github.event_name == 'workflow_dispatch'")
        self.assertIn("confirm_write", raw)

    def test_live_job_uses_fixed_course_mutex_and_current_main_guard(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: stepik-live-course-299189", raw)
        self.assertNotIn("group: stepik-live-course-${{ inputs.course_id }}", raw)
        self.assertGreaterEqual(raw.count("live_guard.py"), 3)
        self.assertIn('if [[ "$COURSE_ID" != "299189" ]]', raw)

    def test_private_release_reuses_immutable_history_anchor_cache(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "STEPIK_HISTORY_ANCHOR_CACHE: artifacts/stepik-private-release/history-anchor-cache.json",
            raw,
        )

    def test_every_lesson_uses_one_preflight_and_write_loop(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Preflight всех PENDING lessons без записи", raw)
        self.assertIn("Последовательно синхронизировать все PENDING lessons", raw)
        self.assertIn("refresh_target_ids", raw)
        self.assertIn("initial_target_ids", raw)
        self.assertIn("recovery_target_ids", raw)
        self.assertIn("staging_refresh_runtime.py", raw)
        self.assertIn("staging_build_runtime.py", raw)
        self.assertIn("staging_commit_gap_recovery.py", raw)

    def test_no_special_lesson_runtime_remains(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8").lower()
        self.assertNotIn("golden", raw)
        self.assertNotIn("owner-approved m00", raw)
        self.assertNotIn("6→6", raw)
        self.assertNotIn("8→8", raw)
        self.assertNotIn("m00-l01 6", raw)
        self.assertNotIn("m00-l02 content", raw)

    def test_all_preflights_precede_any_mutating_route(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        lesson_preflight = raw.index("Preflight всех PENDING lessons без записи")
        course_preflight = raw.index("Preflight course page без записи")
        scope_recheck = raw.index("Проверить неизменность source и scope перед write")
        lesson_write = raw.index("Последовательно синхронизировать все PENDING lessons")
        course_write = raw.index("Синхронизировать course page")
        self.assertLess(lesson_preflight, course_preflight)
        self.assertLess(course_preflight, scope_recheck)
        self.assertLess(scope_recheck, lesson_write)
        self.assertLess(lesson_write, course_write)

    def test_lesson_state_patch_precedes_history_commit(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        block = raw[
            raw.index("Последовательно синхронизировать все PENDING lessons"):
            raw.index("Синхронизировать course page")
        ]
        patch = block.index("gh api --method PATCH")
        history = block.index("history_cli.py mark-state-committed")
        self.assertLess(patch, history)

    def test_course_page_recovery_probe_is_read_only_and_write_phase_confirmed(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        preflight = raw[
            raw.index("Preflight course page без записи"):
            raw.index("Проверить неизменность source и scope перед write")
        ]
        write = raw[
            raw.index("Синхронизировать course page"):
            raw.index("Проверить финальный zero-PENDING")
        ]
        self.assertIn("course_page_commit_gap_recovery.py", preflight)
        self.assertNotIn("--confirm-recovery", preflight)
        self.assertIn("course_page_commit_gap_recovery.py", write)
        self.assertIn("--confirm-recovery", write)

    def test_final_gate_requires_zero_pending_and_all_21_baselines(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        final = raw[raw.index("Проверить финальный zero-PENDING"):]
        self.assertIn("pending.get('lessons')", final)
        self.assertIn("pending.get('course_page')", final)
        self.assertIn("expected-baselines", final)
        self.assertIn("len(expected) != 21", final)
        self.assertIn("missing Stepik lesson ID", final)
        self.assertIn("missing confirmed step IDs", final)


if __name__ == "__main__":
    unittest.main()
