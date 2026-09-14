from __future__ import annotations

import unittest

from scripts.stepik_uploader.sync_issue_state import BEGIN, END, IssueStateError, assert_expected_state, extract_state, replace_state
from scripts.stepik_uploader.sync_state import empty_state, with_pending_impact


class SyncIssueStateTests(unittest.TestCase):
    def test_extract_returns_empty_state_when_marker_absent(self) -> None:
        state = extract_state("human text", course_id=299189)
        self.assertEqual(state, empty_state(299189))

    def test_replace_and_extract_roundtrip(self) -> None:
        state = empty_state(299189)
        state["lessons"]["M02-L01"] = {
            "stepik_lesson_id": 2591717,
            "applied_fingerprint": "sha256:" + "a" * 64,
        }
        body = replace_state("human text", state, course_id=299189)
        self.assertIn(BEGIN, body)
        self.assertIn(END, body)
        self.assertEqual(extract_state(body, course_id=299189), state)

    def test_damaged_markers_fail_closed(self) -> None:
        with self.assertRaises(Exception):
            extract_state(BEGIN + "\n{}", course_id=299189)

    def test_race_compare_stops_if_machine_state_changed(self) -> None:
        expected = empty_state(299189)
        current = with_pending_impact(
            expected,
            source_sha="1" * 40,
            occurred_at="2026-09-14T10:00:00Z",
            paths_by_lesson={"M03-L02": ["04_course/M03/M03-L02/lesson.md"]},
            reasons_by_lesson={"M03-L02": ["direct-lesson-source"]},
        )
        with self.assertRaises(IssueStateError):
            assert_expected_state(expected, current, course_id=299189)

    def test_race_compare_accepts_legacy_and_normalized_equivalent_state(self) -> None:
        legacy = {"schema_version": 1, "course_id": 299189, "updated_at": None, "lessons": {}}
        assert_expected_state(legacy, empty_state(299189), course_id=299189)


if __name__ == "__main__":
    unittest.main()
