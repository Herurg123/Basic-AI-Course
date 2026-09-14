from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.canonical import build_structural_manifest, parse_stepik_plan


class AuthorOnlyRegressionTests(unittest.TestCase):
    def test_plain_author_word_does_not_hide_learner_step(self) -> None:
        plan = (
            "| № | Тип шага | Содержание | Материал | Проверка |\n"
            "|---:|---|---|---|---|\n"
            "| 1 | визуальная практика | Сравнить две авторские версии и выбрать правку | `M05-L01-A02.svg` | `M05-L01-E02` |\n"
        )
        rows = parse_stepik_plan(plan, lesson_id="M05-L01", path=Path("plan.md"))
        self.assertFalse(rows[0]["author_only"])

    def test_explicit_author_rubric_stays_hidden(self) -> None:
        plan = (
            "| № | Тип шага | Содержание | Материал | Проверка |\n"
            "|---:|---|---|---|---|\n"
            "| 1 | evaluation | Author rubric применяется после попытки | `M07-L02-A02.md` | PASS / NOT PROVEN |\n"
        )
        rows = parse_stepik_plan(plan, lesson_id="M07-L02", path=Path("plan.md"))
        self.assertTrue(rows[0]["author_only"])

    def test_real_m05_l01_keeps_all_five_learner_rows(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root)
        lesson = next(
            lesson
            for module in manifest["modules"]
            for lesson in module["lessons"]
            if lesson["canonical_id"] == "M05-L01"
        )
        self.assertEqual(len(lesson["steps"]), 5)
        self.assertEqual([row["position"] for row in lesson["steps"] if not row["author_only"]], [1, 2, 3, 4, 5])

    def test_real_hidden_rows_remain_only_explicit_service_rows(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root)
        hidden = [
            (lesson["canonical_id"], row["position"])
            for module in manifest["modules"]
            for lesson in module["lessons"]
            for row in lesson["steps"]
            if row["author_only"]
        ]
        self.assertEqual(hidden, [("M06-L02", 6), ("M07-L02", 7)])


if __name__ == "__main__":
    unittest.main()
