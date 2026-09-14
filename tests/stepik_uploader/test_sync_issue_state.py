from __future__ import annotations

import unittest

from scripts.stepik_uploader.sync_issue_state import BEGIN, END, extract_state, replace_state
from scripts.stepik_uploader.sync_state import empty_state


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


if __name__ == "__main__":
    unittest.main()
