from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_all_lesson_sources,
    compile_lesson_source,
    split_source_chunks,
)


class GeneralContentCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.manifest = build_structural_manifest(cls.repo_root, source_sha="test")
        cls.lesson_ids = [
            str(lesson["canonical_id"])
            for module in cls.manifest["modules"]
            for lesson in module["lessons"]
        ]
        cls.compiled = compile_all_lesson_sources(
            cls.repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=cls.lesson_ids,
        )

    def _manifest_lesson(self, lesson_id: str) -> dict:
        for module in self.manifest["modules"]:
            for lesson in module["lessons"]:
                if lesson["canonical_id"] == lesson_id:
                    return lesson
        self.fail(f"lesson not found: {lesson_id}")

    def test_all_21_lessons_compile_and_author_only_rows_are_excluded(self) -> None:
        self.assertEqual(len(self.lesson_ids), 21)
        self.assertEqual(set(self.compiled), set(self.lesson_ids))

        structural_rows = sum(
            len(lesson["steps"])
            for module in self.manifest["modules"]
            for lesson in module["lessons"]
        )
        author_only_rows = sum(
            1
            for module in self.manifest["modules"]
            for lesson in module["lessons"]
            for step in lesson["steps"]
            if step["author_only"]
        )
        compiled_rows = sum(len(steps) for steps in self.compiled.values())

        self.assertEqual(structural_rows, 150)
        self.assertEqual(author_only_rows, 2)
        self.assertEqual(compiled_rows, 148)

        for lesson_id, steps in self.compiled.items():
            learner_rows = [
                step for step in self._manifest_lesson(lesson_id)["steps"] if not step["author_only"]
            ]
            self.assertEqual(len(steps), len(learner_rows), lesson_id)
            self.assertEqual(
                [step.position for step in steps],
                list(range(1, len(steps) + 1)),
                lesson_id,
            )

    def test_compiler_preserves_all_learner_source_text_in_order(self) -> None:
        for lesson_id, steps in self.compiled.items():
            module_id = lesson_id.split("-", 1)[0]
            lesson_path = self.repo_root / "04_course" / module_id / lesson_id / "lesson.md"
            source_chunks = split_source_chunks(lesson_path.read_text(encoding="utf-8"))
            source = "\n\n".join(chunk.markdown for chunk in source_chunks)
            compiled = "\n\n".join(step.markdown for step in steps)
            self.assertEqual(compiled, source, lesson_id)
            self.assertNotIn("<!-- Exercise:", compiled, lesson_id)
            self.assertNotIn("<!-- Check:", compiled, lesson_id)

    def test_free_answer_rows_use_only_confirmed_golden_source(self) -> None:
        free_answer_count = 0
        for lesson_id, steps in self.compiled.items():
            for step in steps:
                if step.block_name == "free-answer":
                    free_answer_count += 1
                    self.assertEqual(step.source, EXPECTED_FREE_ANSWER_SOURCE, lesson_id)
                else:
                    self.assertEqual(step.block_name, "text", lesson_id)
                    self.assertEqual(step.source, {}, lesson_id)
        self.assertGreater(free_answer_count, 0)

    def test_sensitive_and_branching_lessons_keep_expected_step_shapes(self) -> None:
        self.assertEqual(
            [step.block_name for step in self.compiled["M03-L02"]],
            ["text", "text", "text", "text", "free-answer", "text", "text", "free-answer", "text"],
        )
        self.assertEqual(
            [step.block_name for step in self.compiled["M06-L04"]],
            ["text", "text", "text", "free-answer", "text", "text", "free-answer", "text", "free-answer", "text"],
        )
        self.assertEqual(len(self.compiled["M00-L02"]), 8)
        self.assertEqual(len(self.compiled["M06-L02"]), 6)

    def test_check_steps_do_not_absorb_following_semantic_sections(self) -> None:
        m05 = self.compiled["M05-L02"]
        self.assertEqual(m05[8].source_headings, ("Проверьте реальное редактирование",))
        self.assertEqual(m05[8].check_ids, ("M05-L02-C02",))
        self.assertIn("Повторная ситуация для редактирования", m05[9].source_headings)

        m07 = self.compiled["M07-L02"]
        self.assertEqual(m07[5].source_headings, ("Финальная проверка",))
        self.assertEqual(m07[5].check_ids, ("M07-L02-C01",))
        self.assertIn("Если попытка стала тренировочной", m07[6].source_headings)

        m08 = self.compiled["M08-L01"]
        self.assertEqual(m08[4].source_headings, ("Короткая проверка переноса",))
        self.assertEqual(m08[4].check_ids, ("M08-L01-C01",))
        self.assertIn("Важная граница", m08[5].source_headings)
        self.assertIn("Итог", m08[5].source_headings)

    def test_m01_l02_transfer_precedes_final_check_as_in_canonical_lesson(self) -> None:
        steps = self.compiled["M01-L02"]
        self.assertEqual(steps[3].block_name, "text")
        self.assertIn("Проверьте себя на второй ситуации", steps[3].source_headings)
        self.assertEqual(steps[4].block_name, "free-answer")
        self.assertEqual(steps[4].source_headings, ("Проверка урока",))
        self.assertEqual(steps[4].check_ids, ("M01-L02-C01",))
        self.assertIn("Если основной маршрут не работает", steps[5].source_headings)
        self.assertIn("Итог", steps[5].source_headings)

    def test_unique_exercise_and_check_markers_align_to_their_plan_rows(self) -> None:
        for lesson_id, steps in self.compiled.items():
            marker_to_positions: dict[str, list[int]] = {}
            for step in steps:
                for marker in (*step.exercise_ids, *step.check_ids):
                    marker_to_positions.setdefault(marker, []).append(step.position)

            module_id = lesson_id.split("-", 1)[0]
            lesson_path = self.repo_root / "04_course" / module_id / lesson_id / "lesson.md"
            source_chunks = split_source_chunks(lesson_path.read_text(encoding="utf-8"))
            source_markers = {marker for chunk in source_chunks for marker in chunk.marker_ids}

            for marker in source_markers:
                positions = marker_to_positions.get(marker, [])
                self.assertTrue(positions, f"{lesson_id}: source marker {marker} отсутствует в plan rows")
                owning_steps = [
                    step
                    for step in steps
                    if marker in (*step.exercise_ids, *step.check_ids)
                    and any(
                        marker in chunk.marker_ids
                        for chunk in source_chunks
                        if chunk.index in step.source_chunk_indexes
                    )
                ]
                self.assertEqual(
                    len(owning_steps),
                    1,
                    f"{lesson_id}: source marker {marker} должен принадлежать ровно одному compiled step",
                )

    def test_repo_relative_links_remain_explicit_for_next_asset_gate(self) -> None:
        links = [
            (lesson_id, link)
            for lesson_id, steps in self.compiled.items()
            for step in steps
            for link in step.unresolved_repo_links
        ]
        self.assertTrue(links)
        self.assertTrue(any("05_assets" in link for _, link in links))
        self.assertTrue(any("stepik/" in link for _, link in links))

    def test_free_answer_source_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(Exception, "free-answer source"):
            compile_lesson_source(
                self.repo_root,
                free_answer_source={"manual_scoring": True},
                lesson_id="M03-L02",
            )


if __name__ == "__main__":
    unittest.main()
