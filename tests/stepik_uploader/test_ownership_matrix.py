from __future__ import annotations

import json
import unittest
from pathlib import Path

MATRIX = Path("04_course/stepik/automation/ownership-matrix.v1.json")
REQUIRED_CLASSES = {
    "direct_learner_content_change",
    "shared_learner_dependency_change",
    "lesson_asset_change",
    "course_page",
    "golden_lesson",
    "normal_lesson_with_baseline",
    "normal_lesson_without_baseline",
    "metadata_change",
    "structural_step_change",
    "manual_stepik_drift",
    "partial_write",
    "ambiguous_api_result",
    "failed_readback",
    "machine_state_patch_failure",
    "stale_machine_baseline",
    "state_race",
    "tooling_only_change",
    "author_only_change",
    "recovery",
    "reconcile",
    "rebaseline_adoption",
    "new_git_merge_during_deployment_recovery",
}
REQUIRED_FIELDS = {
    "detect",
    "initiate",
    "execute",
    "owner_approval",
    "auto_retry",
    "auto_continue_partial",
    "auto_reconcile",
    "auto_rebaseline",
    "stop",
    "evidence",
    "state_change",
    "history_event",
}


class OwnershipMatrixTests(unittest.TestCase):
    def test_all_mandatory_event_classes_are_present_and_complete(self) -> None:
        payload = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["course_id"], 299189)
        classes = payload["classes"]
        self.assertEqual(REQUIRED_CLASSES - set(classes), set())
        for name in REQUIRED_CLASSES:
            with self.subTest(event_class=name):
                self.assertEqual(REQUIRED_FIELDS - set(classes[name]), set())
                self.assertIsInstance(classes[name]["evidence"], list)
                self.assertTrue(classes[name]["evidence"])

    def test_matrix_preserves_non_destructive_defaults(self) -> None:
        payload = json.loads(MATRIX.read_text(encoding="utf-8"))
        defaults = payload["defaults"]
        self.assertFalse(defaults["automatic_retry"])
        self.assertFalse(defaults["destructive_recovery"])
        self.assertFalse(defaults["delete_allowed"])
        self.assertEqual(defaults["unknown_state"], "STOP")


if __name__ == "__main__":
    unittest.main()
