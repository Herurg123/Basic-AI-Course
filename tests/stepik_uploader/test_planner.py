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


def snapshot(*, duplicate_third: bool = False, prefixed_titles: bool = False) -> dict:
    def title(canonical_id: str, text: str) -> str:
        return f"{canonical_id} — {text}" if prefixed_titles else text

    units = [
        {"id": 101, "position": 1, "lesson": {"id": 201, "title": title("M00-L01", "Первый"), "steps": []}},
        {"id": 102, "position": 2, "lesson": {"id": 202, "title": title("M00-L02", "Второй"), "steps": []}},
    ]
    if duplicate_third:
        units.extend(
            [
                {"id": 103, "position": 3, "lesson": {"id": 203, "title": "Третий", "steps": []}},
                {"id": 104, "position": 4, "lesson": {"id": 204, "title": "M00-L03 — Третий", "steps": []}},
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

    def test_prefixed_stepik_titles_are_recognized_without_planning_duplicates(self) -> None:
        live = snapshot(prefixed_titles=True)
        live["sections"][0]["units"].append(
            {"id": 103, "position": 3, "lesson": {"id": 203, "title": "M00-L03 — Третий", "steps": []}}
        )
        plan = plan_dry_run(manifest(), live)
        actions = {op["lesson"]: op["action"] for op in plan.operations}
        self.assertEqual(actions["M00-L01"], "READ_ONLY_GOLDEN")
        self.assertEqual(actions["M00-L02"], "READ_ONLY_GOLDEN")
        self.assertEqual(actions["M00-L03"], "SKIP")
        self.assertFalse(any(op["action"] == "PLANNED_CREATE" for op in plan.operations))

    def test_duplicate_existing_lesson_is_blocker_not_guess(self) -> None:
        plan = plan_dry_run(manifest(), snapshot(duplicate_third=True))
        self.assertTrue(any(blocker.startswith("duplicate:M00-L03") for blocker in plan.blockers))

    def test_golden_requires_exact_unique_title_and_position(self) -> None:
        bad = snapshot(prefixed_titles=True)
        bad["sections"][0]["units"][1]["position"] = 9
        golden, blockers = recognize_golden(manifest(), bad)
        self.assertNotIn("M00-L02", golden)
        self.assertTrue(blockers)

    def test_stable_id_with_title_drift_blocks_instead_of_planning_create(self) -> None:
        live = snapshot(prefixed_titles=True)
        live["sections"][0]["units"].append(
            {"id": 103, "position": 3, "lesson": {"id": 203, "title": "M00-L03 — Чужой заголовок", "steps": []}}
        )
        plan = plan_dry_run(manifest(), live)
        self.assertTrue(any(blocker.startswith("title-drift:M00-L03") for blocker in plan.blockers))
        self.assertFalse(any(op.get("lesson") == "M00-L03" and op["action"] == "PLANNED_CREATE" for op in plan.operations))

    def test_offline_dry_run_has_no_write_action(self) -> None:
        plan = plan_dry_run(manifest(), None)
        self.assertEqual(plan.write_count, 0)
        self.assertTrue(all(op["action"] != "CREATE" for op in plan.operations))
        self.assertIn("course-not-inspected", plan.blockers)


if __name__ == "__main__":
    unittest.main()
