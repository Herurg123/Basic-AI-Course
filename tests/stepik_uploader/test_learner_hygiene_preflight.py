from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.fingerprints import live_lesson_fingerprint
from scripts.stepik_uploader.learner_hygiene_preflight import plan_tracked_lesson
from scripts.stepik_uploader.writer import ContentWriteError


class LearnerHygienePreflightTests(unittest.TestCase):
    canonical_id = "M04-L01"
    legacy_title = "M04-L01 — Получите ответ по безопасному исходнику"
    human_title = "Получите ответ по безопасному исходнику"

    def _steps(self, *, second_text: str) -> list[CompiledStep]:
        return [
            CompiledStep(
                position=1,
                block_name="text",
                text="<p>Первый шаг</p>",
                source={},
                source_git_paths=("04_course/M04/M04-L01/lesson.md",),
            ),
            CompiledStep(
                position=2,
                block_name="text",
                text=second_text,
                source={},
                source_git_paths=("04_course/M04/M04-L01/lesson.md",),
            ),
        ]

    def _live_lesson(self) -> dict:
        old_steps = self._steps(second_text="<p>Служебный M04-L01-A01</p>")
        return {
            "id": 2591721,
            "title": self.legacy_title,
            "is_public": False,
            "language": "ru",
            "steps": [
                {
                    "id": 7001,
                    "step": {"id": 7001},
                    "step_source": {
                        "id": 7001,
                        "position": 1,
                        "block": old_steps[0].block(),
                    },
                },
                {
                    "id": 7002,
                    "step": {"id": 7002},
                    "step_source": {
                        "id": 7002,
                        "position": 2,
                        "block": old_steps[1].block(),
                    },
                },
            ],
        }

    def _baseline(self, live_lesson: dict) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "stepik_lesson_id": live_lesson["id"],
            "applied_source_sha": "a" * 40,
            "applied_at": "2026-09-15T12:30:30Z",
            "applied_fingerprint": live_lesson_fingerprint(live_lesson),
            "step_ids": [7001, 7002],
            "source_git_paths": ["04_course/M04/M04-L01/lesson.md"],
        }

    def test_plan_is_read_only_and_lists_exact_title_and_step_writes(self) -> None:
        live = self._live_lesson()
        before = deepcopy(live)
        desired_steps = self._steps(second_text="<p>Учебный файл</p>")

        plan = plan_tracked_lesson(
            live,
            canonical_id=self.canonical_id,
            expected_title=self.human_title,
            expected_steps=desired_steps,
            baseline=self._baseline(live),
        )

        self.assertEqual(live, before)
        self.assertEqual(plan["stepik_lesson_id"], 2591721)
        self.assertEqual(plan["stepik_writes_planned"], 2)
        self.assertEqual(
            [item["action"] for item in plan["operations"]],
            ["UPDATE_TITLE", "UPDATE_STEP"],
        )
        self.assertEqual(plan["operations"][0]["target"], "lessons/2591721")
        self.assertEqual(plan["operations"][1]["target"], "step-sources/7002")
        self.assertEqual(plan["operations"][1]["expected_block"], desired_steps[1].block())

    def test_live_drift_blocks_preflight_before_any_write(self) -> None:
        live = self._live_lesson()
        baseline = self._baseline(live)
        live["steps"][0]["step_source"]["block"] = {"name": "text", "text": "<p>manual drift</p>"}

        with self.assertRaises(ContentWriteError):
            plan_tracked_lesson(
                live,
                canonical_id=self.canonical_id,
                expected_title=self.human_title,
                expected_steps=self._steps(second_text="<p>Учебный файл</p>"),
                baseline=baseline,
            )

    def test_preflight_source_contains_no_stepik_write_calls(self) -> None:
        source = Path("scripts/stepik_uploader/learner_hygiene_preflight.py").read_text(encoding="utf-8")
        self.assertNotIn("execute_title_only_operation(", source)
        self.assertNotIn("execute_tracked_learner_hygiene(", source)
        self.assertNotIn("execute_normalization_recovery(", source)
        self.assertNotIn("update_step_source(", source)
        self.assertNotIn("_request_write(", source)

    def test_workflow_separates_preflight_from_mutating_followup_steps(self) -> None:
        workflow = Path(".github/workflows/stepik-learner-hygiene.yml").read_text(encoding="utf-8")
        self.assertIn("learner_hygiene_preflight.py", workflow)
        self.assertIn("learner_hygiene_recovery_entrypoint.py", workflow)
        self.assertIn('if [[ "${CONFIRM_WRITE:-false}" == "true" ]]', workflow)
        self.assertGreaterEqual(workflow.count("success() && inputs.confirm_write == true"), 3)


if __name__ == "__main__":
    unittest.main()
