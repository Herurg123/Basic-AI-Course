from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/stepik-golden-title-migration.yml"
SCRIPT = ROOT / "scripts/stepik_uploader/golden_title_migration.py"


class GoldenTitleWorkflowSafetyTests(unittest.TestCase):
    def test_workflow_is_manual_for_live_and_defaults_to_read_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("confirm_write:", text)
        self.assertIn("default: false", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn("group: stepik-live-course-299189", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("scripts/stepik_uploader/live_guard.py", text)
        self.assertIn("golden_title_migration.py", text)

    def test_script_has_fixed_targets_and_no_create_delete_routes(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('COURSE_ID = 299189', text)
        self.assertIn('TARGET_IDS = ("M00-L01", "M00-L02")', text)
        self.assertNotIn('client._request_write("POST"', text)
        self.assertNotIn('client._request_write("DELETE"', text)
        self.assertIn('"structural_writes_allowed": False', text)
        self.assertIn('"golden_profile_update_required_after_write": True', text)


if __name__ == "__main__":
    unittest.main()
