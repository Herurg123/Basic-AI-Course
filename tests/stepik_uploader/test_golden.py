from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.golden import validate_golden_profile


PROFILE = {
    "schema_version": "1.0",
    "status": "confirmed-read-only",
    "course_id": 299189,
    "course_state": {"language": "ru", "is_public": False},
    "golden_lessons": {
        "M00-L01": {
            "stepik_section_id": 11,
            "stepik_unit_id": 101,
            "stepik_lesson_id": 201,
            "section_position": 1,
            "unit_position": 1,
            "step_count": 2,
            "block_sequence": ["text", "free-answer"],
            "language": "ru",
            "is_public": False,
        }
    },
    "observed_conventions": {
        "free_answer_source": {
            "is_attachments_enabled": False,
            "is_html_enabled": True,
            "manual_scoring": False,
        }
    },
}


def snapshot() -> dict:
    return {
        "course": {"id": 299189, "language": "ru", "is_public": False},
        "sections": [
            {
                "id": 11,
                "position": 1,
                "units": [
                    {
                        "id": 101,
                        "position": 1,
                        "lesson": {
                            "id": 201,
                            "language": "ru",
                            "is_public": False,
                            "steps": [
                                {
                                    "step_source": {
                                        "position": 1,
                                        "block": {"name": "text", "source": {}},
                                    }
                                },
                                {
                                    "step_source": {
                                        "position": 2,
                                        "block": {
                                            "name": "free-answer",
                                            "source": {
                                                "is_attachments_enabled": False,
                                                "is_html_enabled": True,
                                                "manual_scoring": False,
                                            },
                                        },
                                    }
                                },
                            ],
                        },
                    }
                ],
            }
        ],
    }


class GoldenProfileTests(unittest.TestCase):
    def test_matching_profile_has_no_blockers(self) -> None:
        self.assertEqual(validate_golden_profile(PROFILE, snapshot()), [])

    def test_course_publication_is_strict_by_default(self) -> None:
        live = snapshot()
        live["course"]["is_public"] = True
        blockers = validate_golden_profile(PROFILE, live)
        self.assertTrue(any("course.is_public" in blocker for blocker in blockers))

    def test_exploitation_sync_can_allow_course_publication_only(self) -> None:
        live = snapshot()
        live["course"]["is_public"] = True
        self.assertEqual(
            validate_golden_profile(PROFILE, live, allow_course_publication_change=True),
            [],
        )

        lesson_drift = copy.deepcopy(live)
        lesson_drift["sections"][0]["units"][0]["lesson"]["is_public"] = True
        blockers = validate_golden_profile(
            PROFILE,
            lesson_drift,
            allow_course_publication_change=True,
        )
        self.assertTrue(any("lesson.is_public" in blocker for blocker in blockers))

    def test_block_sequence_change_is_blocker(self) -> None:
        live = snapshot()
        live["sections"][0]["units"][0]["lesson"]["steps"][1]["step_source"]["block"]["name"] = "text"
        blockers = validate_golden_profile(PROFILE, live)
        self.assertTrue(any("block sequence" in blocker for blocker in blockers))

    def test_free_answer_configuration_change_is_blocker(self) -> None:
        live = snapshot()
        live["sections"][0]["units"][0]["lesson"]["steps"][1]["step_source"]["block"]["source"]["manual_scoring"] = True
        blockers = validate_golden_profile(PROFILE, live)
        self.assertTrue(any("free-answer source" in blocker for blocker in blockers))

    def test_wrong_course_is_blocker(self) -> None:
        live = snapshot()
        live["course"]["id"] = 999
        blockers = validate_golden_profile(PROFILE, live)
        self.assertTrue(any("course_id" in blocker for blocker in blockers))


if __name__ == "__main__":
    unittest.main()
