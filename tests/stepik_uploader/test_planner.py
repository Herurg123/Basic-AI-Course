from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.planner import plan_dry_run


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


def snapshot(*, include_third: bool = False, prefixed_titles: bool = False) -> dict:
    def title(canonical_id: str, text: str) -> str:
        return f"{canonical_id} — {text}" if prefixed_titles else text

    units = [
        {"id": 101, "position": 1, "lesson": {"id": 201, "title": title("M00-L01", "Первый"), "steps": []}},
        {"id": 102, "position": 2, "lesson": {"id": 202, "title": title("M00-L02", "Второй"), "steps": []}},
    ]
    if include_third:
        units.append(
            {"id": 103, "position": 3, "lesson": {"id": 203, "title": title("M00-L03", "Третий"), "steps": []}}
        )
    return {"sections": [{"id": 11, "title": "M00", "position": 1, "units": units}]}


class PlannerTests(unittest.TestCase):
    def test_all_existing_lessons_use_same_skip_class_and_missing_is_planned(self) -> None:
        plan = plan_dry_run(manifest(), snapshot())
        actions = {op["lesson"]: op["action"] for op in plan.operations}
        self.assertEqual(actions["M00-L01"], "SKIP")
        self.assertEqual(actions["M00-L02"], "SKIP")
        self.assertEqual(actions["M00-L03"], "PLANNED_CREATE")
        self.assertEqual(plan.blockers, [])

    def test_prefixed_titles_are_accepted_for_every_lesson(self) -> None:
        plan = plan_dry_run(manifest(), snapshot(include_third=True, prefixed_titles=True))
        self.assertEqual({op["action"] for op in plan.operations}, {"SKIP"})
        self.assertEqual(plan.blockers, [])

    def test_title_difference_at_canonical_position_is_notice_not_special_class(self) -> None:
        live = snapshot(include_third=True)
        live["sections"][0]["units"][0]["lesson"]["title"] = "Старый первый заголовок"

        plan = plan_dry_run(manifest(), live)

        first = next(op for op in plan.operations if op["lesson"] == "M00-L01")
        self.assertEqual(first["action"], "SKIP_STALE_TITLE")
        notice = next(item for item in plan.notices if item["canonical_id"] == "M00-L01")
        self.assertEqual(notice["classification"], "TITLE_DIFFERS_AT_CANONICAL_POSITION")
        self.assertFalse(notice["automatic_write_allowed"])
        self.assertEqual(plan.blockers, [])

    def test_identity_found_outside_canonical_position_blocks(self) -> None:
        live = snapshot()
        live["sections"][0]["units"].append(
            {"id": 104, "position": 4, "lesson": {"id": 204, "title": "M00-L03 — Третий", "steps": []}}
        )

        plan = plan_dry_run(manifest(), live)

        self.assertTrue(any(item.startswith("position-drift:M00-L03") for item in plan.blockers))

    def test_duplicate_position_blocks_instead_of_guessing(self) -> None:
        live = snapshot(include_third=True)
        live["sections"][0]["units"].append(
            {"id": 104, "position": 3, "lesson": {"id": 204, "title": "Другой", "steps": []}}
        )

        plan = plan_dry_run(manifest(), live)

        self.assertTrue(any(item.startswith("duplicate-position:M00-L03") for item in plan.blockers))

    def test_identity_collision_outside_position_blocks(self) -> None:
        live = snapshot(include_third=True)
        live["sections"][0]["units"].append(
            {"id": 104, "position": 4, "lesson": {"id": 204, "title": "M00-L03 — Третий", "steps": []}}
        )

        plan = plan_dry_run(manifest(), live)

        self.assertTrue(any(item.startswith("ambiguous-identity:M00-L03") for item in plan.blockers))

    def test_offline_plan_is_read_only_and_requires_live_inspection(self) -> None:
        plan = plan_dry_run(manifest(), None)
        self.assertEqual(len(plan.operations), 3)
        self.assertTrue(all(op["action"] == "PLANNED_AFTER_LIVE_GUARDS" for op in plan.operations))
        self.assertEqual(plan.blockers, ["course-not-inspected"])


if __name__ == "__main__":
    unittest.main()
