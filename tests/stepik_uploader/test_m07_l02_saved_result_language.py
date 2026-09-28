from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_lesson_source


ROOT = Path(__file__).resolve().parents[2]


class M07L02SavedResultLanguageTests(unittest.TestCase):
    def test_step2_uses_ready_result_instead_of_artifact_jargon(self) -> None:
        steps = compile_lesson_source(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_id="M07-L02",
        )
        saved_work = steps[1].markdown

        self.assertIn("заметки и готовый результат", saved_work)
        self.assertNotIn("конечный артефакт", saved_work)


if __name__ == "__main__":
    unittest.main()
