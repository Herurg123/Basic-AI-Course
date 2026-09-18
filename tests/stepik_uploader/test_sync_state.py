from __future__ import annotations

import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint
from scripts.stepik_uploader.sync_state import assess_sync


FREE = {"is_attachments_enabled": False, "is_html_enabled": True, "manual_scoring": False}


def compiled(text: str, *, position: int = 1, block_name: str = "text") -> CompiledStep:
    return CompiledStep(
        position=position,
        block_name=block_name,
        text=text,
        source=FREE if block_name == "free-answer" else {},
        source_git_paths=("04_course/M02/M02-L01/lesson.md",),
    )


def live_lesson(steps: list[CompiledStep], *, title: str = "M02-L01 — Lesson", lesson_id: int = 100) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "language": "ru",
        "is_public": False,
        "steps": [
            {
                "step_source": {
                    "id": 1000 + step.position,
                    "position": step.position,
                    "block": step.block(),
                }
            }
            for step in steps
        ],
    }


def baseline(steps: list[CompiledStep], *, title: str = "M02-L01 — Lesson", lesson_id: int = 100) -> dict:
    return {
        "stepik_lesson_id": lesson_id,
        "applied_fingerprint": compiled_lesson_fingerprint(expected_title=title, expected_steps=steps),
    }


class SyncStateTests(unittest.TestCase):
    def test_in_sync_when_all_three_states_match(self) -> None:
        old = [compiled("<p>old</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(old),
            expected_title="M02-L01 — Lesson",
            expected_steps=old,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "IN_SYNC")
        self.assertFalse(result.changed_step_positions)

    def test_repo_change_is_update_required_only_when_live_still_matches_baseline(self) -> None:
        old = [compiled("<p>old</p>")]
        new = [compiled("<p>new</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(old),
            expected_title="M02-L01 — Lesson",
            expected_steps=new,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "UPDATE_REQUIRED")
        self.assertEqual(result.changed_step_positions, (1,))
        self.assertTrue(result.write_allowed)

    def test_manual_stepik_change_blocks_automatic_overwrite(self) -> None:
        old = [compiled("<p>old</p>")]
        manual = [compiled("<p>manual edit</p>")]
        new = [compiled("<p>new canonical</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(manual),
            expected_title="M02-L01 — Lesson",
            expected_steps=new,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "DRIFT_BLOCKED")
        self.assertFalse(result.write_allowed)

    def test_step_count_change_is_structural_and_blocked(self) -> None:
        old = [compiled("<p>old</p>")]
        new = [compiled("<p>old</p>"), compiled("<p>second</p>", position=2)]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(old),
            expected_title="M02-L01 — Lesson",
            expected_steps=new,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "STRUCTURAL_UPDATE_BLOCKED")

    def test_baseline_proven_title_change_is_update_required(self) -> None:
        old = [compiled("<p>old</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(old),
            expected_title="M02-L01 — Renamed",
            expected_steps=old,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "UPDATE_REQUIRED")
        self.assertTrue(result.write_allowed)

    def test_manual_title_drift_still_blocks(self) -> None:
        old = [compiled("<p>old</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(old, title="Manual title"),
            expected_title="M02-L01 — Renamed",
            expected_steps=old,
            baseline=baseline(old),
        )
        self.assertEqual(result.status, "DRIFT_BLOCKED")
        self.assertFalse(result.write_allowed)

    def test_matching_untracked_live_requires_baseline_bootstrap_not_write(self) -> None:
        current = [compiled("<p>same</p>")]
        result = assess_sync(
            canonical_id="M02-L01",
            live_lesson=live_lesson(current),
            expected_title="M02-L01 — Lesson",
            expected_steps=current,
            baseline=None,
        )
        self.assertEqual(result.status, "BASELINE_BOOTSTRAP_REQUIRED")
        self.assertFalse(result.write_allowed)


if __name__ == "__main__":
    unittest.main()
