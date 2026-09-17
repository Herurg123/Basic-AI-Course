from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.staging_build_runtime import _learner_step_count


class StagingBuildAuthorOnlyCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.manifest = build_structural_manifest(cls.repo_root)

    def _lesson(self, canonical_id: str) -> dict:
        return next(
            lesson
            for module in self.manifest["modules"]
            for lesson in module["lessons"]
            if lesson["canonical_id"] == canonical_id
        )

    def test_real_author_only_lessons_count_only_learner_steps_for_stepik(self) -> None:
        m06 = self._lesson("M06-L02")
        m07 = self._lesson("M07-L02")

        self.assertEqual(len(m06["steps"]), 7)
        self.assertEqual(_learner_step_count(m06), 6)
        self.assertEqual([row["position"] for row in m06["steps"] if row["author_only"]], [6])

        self.assertEqual(len(m07["steps"]), 8)
        self.assertEqual(_learner_step_count(m07), 7)
        self.assertEqual([row["position"] for row in m07["steps"] if row["author_only"]], [7])

    def test_non_author_only_lesson_keeps_existing_count_contract(self) -> None:
        lesson = self._lesson("M06-L01")
        self.assertFalse(any(row["author_only"] for row in lesson["steps"]))
        self.assertEqual(_learner_step_count(lesson), len(lesson["steps"]))

    def test_runtime_uses_learner_count_in_both_preflight_and_write_gates(self) -> None:
        runtime_source = (self.repo_root / "scripts/stepik_uploader/staging_build_runtime.py").read_text(encoding="utf-8")
        self.assertIn("len(preflight_steps) != _learner_step_count(lesson_manifest)", runtime_source)
        self.assertIn("len(rendered_steps) != _learner_step_count(lesson_manifest)", runtime_source)
        self.assertNotIn("len(preflight_steps) != len(lesson_manifest.get(\"steps\", []))", runtime_source)
        self.assertNotIn("len(rendered_steps) != len(lesson_manifest.get(\"steps\", []))", runtime_source)


if __name__ == "__main__":
    unittest.main()
