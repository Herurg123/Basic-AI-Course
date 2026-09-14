from __future__ import annotations

import unittest

from scripts.stepik_uploader.planner import plan_dry_run, recognize_golden


def manifest() -> dict:
    return {
        "modules": [
            {
                "canonical_id": "M00",
                "position": 1,
                "lessons": [
                    {"canonical_id": "M00-L01", "title": "Первый", "position": 1},
                    {"canonical_id": "M00-L02", "title": "Второй", "position": 2},
                    {"canonical_id": "M00-L03", "title": "Третий", "position": 3},
                ],
            }
        ]
    }


def snapshot(*, duplicate_third: bool = False) -> dict:
    units = [
        {"id": 101, "position": 1, "lesson": {"id": 201, "title": "Первый", "steps": []}},
        {"id": 102, "position": 2, "lesson": {"id": 202, "title": "Второй", "steps": []}},
    ]
    if duplicate_third:
        units.extend(
            [
                {"id": 103, "position": 3, "lesson": {"id": 203, "title": "Третий", "steps": []}},
                {"id": 104, "position": 4, "lesson": {"id": 204, "title": "Третий", "steps": []}},
            ]
        )
    return {"sections": [{"id": 11, "title": "M00", "position": 1, "units": units}]}


class PlannerTests(unittest.TestCase):
    def test_golden_are_read_only_and_missing_lesson_is_only_planned(self) -> None:
        plan = plan_dry_run(manifest(), snapshot())
        actions = {op["lesson"]: op["action"] for op in plan.operations}
        self.assertEqual(actions["M00-L01"], "READ_ONLY_GOLDEN")
        self.assertEqual(actions["M00-L02"], "READ_ONLY_GOLDEN")
        self.assertEqual(actions["M00-L03"], "PLANNED_CREATE")
        self.assertIn("needs-golden-profile", plan.blockers)

    def test_duplicate_existing_lesson_is_blocker_not_guess(self) -> None:
        plan = plan_dry_run(manifest(), snapshot(duplicate_third=True))
        self.assertTrue(any(blocker.startswith("duplicate:M00-L03") for blocker in plan.blockers))

    def test_golden_requires_exact_unique_title_and_position(self) -> None:
        bad = snapshot()
        bad["sections"][0]["units"][1]["position"] = 9
        golden, blockers = recognize_golden(manifest(), bad)
        self.assertNotIn("M00-L02", golden)
        self.assertTrue(blockers)

    def test_offline_dry_run_has_no_write_action(self) -> None:
        plan = plan_dry_run(manifest(), None)
        self.assertEqual(plan.write_count, 0)
        self.assertTrue(all(op["action"] != "CREATE" for op in plan.operations))
        self.assertIn("course-not-inspected", plan.blockers)


if __name__ == "__main__":
    unittest.main()
