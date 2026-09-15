from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.section_position_recovery import (
    build_recovery_plan,
    snapshot_content_fingerprint,
)


class SectionPositionRecoveryTests(unittest.TestCase):
    def _baseline(self):
        rows = []
        for index in range(9):
            canonical_id = f"M{index:02d}"
            title = f"Module {index}"
            rows.append(
                {
                    "canonical_id": canonical_id,
                    "section_id": 100 + index,
                    "canonical_title": title,
                    "expected_live_title": f"{canonical_id} — {title}" if index == 8 else title,
                    "expected_position": index + 1,
                    "unit_ids": [1000 + index],
                    "recover": 1 <= index <= 7,
                }
            )
        return {
            "schema_version": 1,
            "course_id": 299189,
            "sections": rows,
        }

    def _manifest(self):
        return {
            "modules": [
                {
                    "canonical_id": f"M{index:02d}",
                    "title": f"Module {index}",
                    "position": index + 1,
                    "lessons": [],
                }
                for index in range(9)
            ]
        }

    def _snapshot(self):
        sections = []
        for index in range(9):
            canonical_id = f"M{index:02d}"
            title = f"Module {index}"
            live_position = 9 if index == 8 else 1
            sections.append(
                {
                    "id": 100 + index,
                    "position": live_position,
                    "title": f"{canonical_id} — {title}" if index == 8 else title,
                    "units": [
                        {
                            "id": 1000 + index,
                            "position": 1,
                            "lesson": {
                                "id": 2000 + index,
                                "title": f"Lesson {index}",
                                "is_public": False,
                                "language": "ru",
                                "steps": [
                                    {
                                        "id": 3000 + index,
                                        "step_source": {
                                            "id": 3000 + index,
                                            "lesson": 2000 + index,
                                            "position": 1,
                                            "block": {
                                                "name": "text",
                                                "text": f"<p>{index}</p>",
                                                "source": {},
                                            },
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            )
        return {
            "course": {
                "id": 299189,
                "title": "Course",
                "language": "ru",
                "is_public": False,
            },
            "sections": sections,
        }

    def test_incident_snapshot_plans_only_m01_through_m07_descending(self) -> None:
        plan = build_recovery_plan(self._manifest(), self._snapshot(), self._baseline())
        self.assertEqual(plan.blockers, [])
        self.assertEqual(
            [item["canonical_id"] for item in plan.operations],
            ["M07", "M06", "M05", "M04", "M03", "M02", "M01"],
        )
        self.assertEqual(
            [item["canonical_id"] for item in plan.sentinels],
            ["M00", "M08"],
        )

    def test_partial_recovery_is_idempotently_classified(self) -> None:
        snapshot = self._snapshot()
        section_m07 = next(item for item in snapshot["sections"] if item["id"] == 107)
        section_m07["position"] = 8
        plan = build_recovery_plan(self._manifest(), snapshot, self._baseline())
        self.assertEqual(plan.blockers, [])
        self.assertEqual([item["canonical_id"] for item in plan.already_recovered], ["M07"])
        self.assertNotIn("M07", [item["canonical_id"] for item in plan.operations])

    def test_unexpected_position_blocks(self) -> None:
        snapshot = self._snapshot()
        section_m04 = next(item for item in snapshot["sections"] if item["id"] == 104)
        section_m04["position"] = 3
        plan = build_recovery_plan(self._manifest(), snapshot, self._baseline())
        self.assertTrue(any("M04" in item and "incident-state=1" in item for item in plan.blockers))

    def test_unit_identity_drift_blocks(self) -> None:
        snapshot = self._snapshot()
        snapshot["sections"][3]["units"][0]["id"] = 999999
        plan = build_recovery_plan(self._manifest(), snapshot, self._baseline())
        self.assertTrue(any("M03" in item and "unit IDs drift" in item for item in plan.blockers))

    def test_content_fingerprint_ignores_only_section_position(self) -> None:
        original = self._snapshot()
        moved = copy.deepcopy(original)
        moved["sections"][4]["position"] = 5
        self.assertEqual(
            snapshot_content_fingerprint(original),
            snapshot_content_fingerprint(moved),
        )

        title_changed = copy.deepcopy(original)
        title_changed["sections"][4]["title"] = "Unexpected"
        self.assertNotEqual(
            snapshot_content_fingerprint(original),
            snapshot_content_fingerprint(title_changed),
        )

        content_changed = copy.deepcopy(original)
        content_changed["sections"][4]["units"][0]["lesson"]["steps"][0]["step_source"]["block"]["text"] = "<p>changed</p>"
        self.assertNotEqual(
            snapshot_content_fingerprint(original),
            snapshot_content_fingerprint(content_changed),
        )


if __name__ == "__main__":
    unittest.main()
