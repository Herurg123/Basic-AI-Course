from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.stepik_uploader.golden_content_refresh_m00_l01_6to6 import (
    GoldenM00L01RefreshError,
    TARGET_ID,
    _assert_content_only_shape,
    _target_profile,
    _update_profile_row,
)


class ExpectedStep:
    def __init__(self, position: int, name: str, source: dict | None = None):
        self.position = position
        self._block = {"name": name, "text": f"desired-{position}", "source": source or {}}

    def block(self):
        return dict(self._block)


class GoldenM00L01RefreshTests(unittest.TestCase):
    def lesson(self, *, names: list[str] | None = None, positions: list[int] | None = None):
        names = names or ["text", "text", "free-answer", "text", "choice", "text"]
        positions = positions or [1, 2, 3, 4, 5, 6]
        return {
            "steps": [
                {
                    "step_source": {
                        "id": 100 + index,
                        "position": position,
                        "block": {
                            "name": names[index],
                            "text": f"old-{position}",
                            "source": {"is_always_correct": True} if names[index] == "free-answer" else {},
                        },
                    }
                }
                for index, position in enumerate(positions)
            ]
        }

    def desired(self, names: list[str] | None = None):
        names = names or ["text", "text", "free-answer", "text", "choice", "text"]
        return [
            ExpectedStep(
                index + 1,
                name,
                {"is_always_correct": True} if name == "free-answer" else {},
            )
            for index, name in enumerate(names)
        ]

    def test_shape_guard_preserves_exact_ids_positions_and_block_contract(self) -> None:
        ids = _assert_content_only_shape(self.lesson(), self.desired())
        self.assertEqual(ids, [100, 101, 102, 103, 104, 105])

    def test_position_change_is_blocked(self) -> None:
        with self.assertRaises(GoldenM00L01RefreshError):
            _assert_content_only_shape(
                self.lesson(positions=[1, 2, 4, 3, 5, 6]),
                self.desired(),
            )

    def test_block_type_change_is_blocked(self) -> None:
        names = ["text", "text", "free-answer", "text", "choice", "text"]
        desired_names = list(names)
        desired_names[4] = "text"
        with self.assertRaises(GoldenM00L01RefreshError):
            _assert_content_only_shape(self.lesson(names=names), self.desired(desired_names))

    def test_block_source_change_is_blocked(self) -> None:
        desired = self.desired()
        desired[2] = ExpectedStep(3, "free-answer", {"is_always_correct": False})
        with self.assertRaises(GoldenM00L01RefreshError):
            _assert_content_only_shape(self.lesson(), desired)

    def test_final_profile_row_captures_live_title(self) -> None:
        live = self.lesson()
        live["title"] = "Новый канонический заголовок"
        row = {"lesson_title": "Старый заголовок"}
        _update_profile_row(row, live, run_id=123)
        self.assertEqual(row["lesson_title"], "Новый канонический заголовок")
        self.assertEqual(row["lesson_title_observed_run_id"], 123)

    def test_target_profile_narrows_fixture_without_changing_global_policy(self) -> None:
        profile = {
            "observed_conventions": {"golden_write_policy": "READ_ONLY"},
            "golden_lessons": {
                TARGET_ID: {"stepik_lesson_id": 1},
                "M00-L02": {"stepik_lesson_id": 2},
            },
        }
        narrowed = _target_profile(profile)
        self.assertEqual(set(narrowed["golden_lessons"]), {TARGET_ID})
        self.assertEqual(narrowed["observed_conventions"]["golden_write_policy"], "READ_ONLY")
        self.assertEqual(set(profile["golden_lessons"]), {TARGET_ID, "M00-L02"})


if __name__ == "__main__":
    unittest.main()
