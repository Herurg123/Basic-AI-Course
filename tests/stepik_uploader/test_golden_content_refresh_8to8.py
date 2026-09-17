from __future__ import annotations

import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import scripts.stepik_uploader.golden_content_migration as migration
import scripts.stepik_uploader.golden_content_refresh_8to8 as refresh
from scripts.stepik_uploader.content import CompiledStep


class GoldenContentRefresh8to8Tests(unittest.TestCase):
    def _args(self) -> Namespace:
        return Namespace(
            course_id=299189,
            repo_root=Path("."),
            report_dir=Path("artifacts/test"),
            sync_state=Path("state.json"),
            api_host="https://stepik.org",
            confirm_write=False,
        )

    def _profile(self) -> dict:
        return {
            "golden_lessons": {
                "M00-L02": {
                    "step_count": 8,
                    "stepik_lesson_id": 202,
                }
            }
        }

    def _lesson(self) -> dict:
        return {
            "id": 202,
            "steps": [
                {
                    "step_source": {
                        "id": 1000 + position,
                        "position": position,
                        "block": {"name": "text", "source": {}, "text": f"<p>Шаг {position}</p>"},
                    }
                }
                for position in range(1, 9)
            ],
        }

    def _baseline(self) -> dict:
        return {
            "stepik_lesson_id": 202,
            "step_ids": [1000 + position for position in range(1, 9)],
            "applied_fingerprint": "sha256:" + "a" * 64,
        }

    def _desired(self) -> list[CompiledStep]:
        return [
            CompiledStep(
                position=position,
                block_name="text",
                text=f"<p>Шаг {position}</p>",
                source={},
                source_git_paths=("lesson.md",),
            )
            for position in range(1, 9)
        ]

    def test_accepted_eight_step_fixture_with_pending_routes_to_refresh(self) -> None:
        args = self._args()
        state = {"pending": {"lessons": {"M00-L02": {"status": "PENDING"}}}}
        expected_profile = self._profile()
        with (
            patch.object(migration.legacy, "parse_args", return_value=args),
            patch.object(migration.legacy, "load_golden_profile", return_value=expected_profile),
            patch.object(migration.legacy, "load_state", return_value=state),
            patch.object(migration.refresh, "run", return_value=0) as refresh_run,
            patch.object(migration, "_current_fixture_noop", return_value=99) as noop,
            patch.object(migration.legacy, "main", return_value=98) as legacy_main,
        ):
            self.assertEqual(migration.main(), 0)
        refresh_run.assert_called_once_with(args, expected_profile)
        noop.assert_not_called()
        legacy_main.assert_not_called()

    def test_accepted_eight_step_fixture_without_pending_keeps_noop_route(self) -> None:
        args = self._args()
        state = {"pending": {"lessons": {}}}
        expected_profile = self._profile()
        with (
            patch.object(migration.legacy, "parse_args", return_value=args),
            patch.object(migration.legacy, "load_golden_profile", return_value=expected_profile),
            patch.object(migration.legacy, "load_state", return_value=state),
            patch.object(migration.refresh, "run", return_value=98) as refresh_run,
            patch.object(migration, "_current_fixture_noop", return_value=0) as noop,
            patch.object(migration.legacy, "main", return_value=97) as legacy_main,
        ):
            self.assertEqual(migration.main(), 0)
        noop.assert_called_once_with(args, expected_profile)
        refresh_run.assert_not_called()
        legacy_main.assert_not_called()

    def test_same_eight_ids_is_required(self) -> None:
        lesson = self._lesson()
        baseline = self._baseline()
        self.assertEqual(refresh._assert_same_eight_ids(lesson, baseline), baseline["step_ids"])
        lesson["steps"][3]["step_source"]["id"] = 999999
        with self.assertRaises(refresh.GoldenContentRefreshError):
            refresh._assert_same_eight_ids(lesson, baseline)

    def test_reorder_or_missing_position_is_blocked(self) -> None:
        lesson = self._lesson()
        lesson["steps"][3]["step_source"]["position"] = 5
        with self.assertRaises(refresh.GoldenContentRefreshError):
            refresh._assert_same_eight_ids(lesson, self._baseline())

    def test_changed_positions_are_content_only(self) -> None:
        lesson = self._lesson()
        desired = self._desired()
        desired[1] = CompiledStep(
            position=2,
            block_name="text",
            text="<p>Изменённый текст</p>",
            source={},
            source_git_paths=("lesson.md",),
        )
        desired[5] = CompiledStep(
            position=6,
            block_name="text",
            text="<p>Ещё изменённый текст</p>",
            source={},
            source_git_paths=("lesson.md",),
        )
        self.assertEqual(refresh._changed_positions(lesson, desired), [2, 6])

    def test_block_type_change_is_blocked(self) -> None:
        desired = self._desired()
        desired[2] = CompiledStep(
            position=3,
            block_name="free-answer",
            text=desired[2].text,
            source={"is_html_enabled": True},
            source_git_paths=("lesson.md",),
        )
        with self.assertRaises(refresh.GoldenContentRefreshError):
            refresh._assert_content_only_shape(self._lesson(), desired)

    def test_block_source_change_is_blocked(self) -> None:
        desired = self._desired()
        desired[4] = CompiledStep(
            position=5,
            block_name="text",
            text=desired[4].text,
            source={"unexpected": True},
            source_git_paths=("lesson.md",),
        )
        with self.assertRaises(refresh.GoldenContentRefreshError):
            refresh._assert_content_only_shape(self._lesson(), desired)

    def test_refresh_requires_exactly_eight_live_steps(self) -> None:
        lesson = self._lesson()
        lesson["steps"].pop()
        with self.assertRaises(refresh.GoldenContentRefreshError):
            refresh._assert_same_eight_ids(lesson, self._baseline())


if __name__ == "__main__":
    unittest.main()
