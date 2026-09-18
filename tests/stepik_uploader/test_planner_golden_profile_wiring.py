from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]

PROFILE_AWARE_PLANNER_ROUTES = (
    "scripts/stepik_uploader/bulk_status.py",
    "scripts/stepik_uploader/first_upload_runtime.py",
    "scripts/stepik_uploader/staging_build_entrypoint.py",
    "scripts/stepik_uploader/staging_build_runtime.py",
    "scripts/stepik_uploader/staging_refresh_runtime.py",
    "scripts/stepik_uploader/stepik_uploader.py",
    "scripts/stepik_uploader/sync_runtime.py",
)


class PlannerGoldenProfileWiringTests(unittest.TestCase):
    def test_profile_aware_production_routes_pass_confirmed_profile_to_planner(self) -> None:
        for relative in PROFILE_AWARE_PLANNER_ROUTES:
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("golden_profile=profile", text)
                self.assertIn("load_golden_profile", text)


if __name__ == "__main__":
    unittest.main()
