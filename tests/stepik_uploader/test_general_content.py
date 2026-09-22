from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.canonical import (
    build_structural_manifest,
    parse_learner_render_contract,
)
from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    GeneralContentCompileError,
    compile_all_lesson_sources,
    compile_lesson_source,
    split_source_chunks,
)


class GeneralContentCompilerTests(unittest.TestCase):
    def _write_authored_fixture(
        self,
        root: Path,
        *,
        lesson_markdown: str,
        learner_rows: list[tuple[str, str, str]],
        author_only_rows: list[tuple[str, str, str]] | None = None,
    ) -> str:
        lesson_id = "M99-L01"
        lesson_dir = root / "04_course" / "M99" / lesson_id
        lesson_dir.mkdir(parents=True)
        (lesson_dir / "lesson.md").write_text(lesson_markdown, encoding="utf-8")

        rows = [*learner_rows, *(author_only_rows or [])]
        table_rows = [
            f"| {index} | {logical_type} | {summary} | — | — | {semantic_type} |"
            for index, (logical_type, summary, semantic_type) in enumerate(rows, start=1)
        ]
        plan = (
            "# Stepik plan — fixture\n\n"
            "<!-- learner-render-contract: authored-semantic-v1 -->\n\n"
            "| № | Тип шага | Содержание | Материал | Проверка | Semantic type |\n"
            "|---:|---|---|---|---|---|\n"
            + "\n".join(table_rows)
            + "\n"
        )
        (lesson_dir / "stepik-plan.md").write_text(plan, encoding="utf-8")
        return lesson_id

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

    def _is_legacy_lesson(self, lesson_id: str) -> bool:
        module_id = lesson_id.split("-", 1)[0]
        plan_path = self.repo_root / "04_course" / module_id / lesson_id / "stepik-plan.md"
        return (
            parse_learner_render_contract(
                plan_path.read_text(encoding="utf-8"),
                path=plan_path,
            )
            is None
        )

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
            compiled_source = "\n\n".join(step.source_markdown for step in steps)
            self.assertEqual(compiled_source, source, lesson_id)
            compiled = "\n\n".join(step.markdown for step in steps)
            self.assertNotIn("<!-- Exercise:", compiled, lesson_id)
            self.assertNotIn("<!-- Check:", compiled, lesson_id)

    def test_legacy_learner_steps_keep_orientation_card_until_migrated(self) -> None:
        for lesson_id, steps in self.compiled.items():
            if not self._is_legacy_lesson(lesson_id):
                continue
            total = len(steps)
            for step in steps:
                self.assertTrue(
                    step.markdown.startswith(f"## Шаг {step.position} из {total}. "),
                    f"{lesson_id} step {step.position}",
                )
                self.assertIn("**Зачем:**", step.markdown, lesson_id)
                self.assertIn("**Где и с чем:**", step.markdown, lesson_id)
                self.assertIn("**Что сделать**", step.markdown, lesson_id)
                self.assertIn("**Готово, если:**", step.markdown, lesson_id)

    def test_orientation_header_does_not_leak_internal_production_markers(self) -> None:
        forbidden = (
            "PRIMARY",
            "BACKUP",
            "PRACTICE",
            "INDEPENDENT",
            "natural trace",
            "post-action",
            "live-output",
            "Asset ID",
        )
        for lesson_id, steps in self.compiled.items():
            if not self._is_legacy_lesson(lesson_id):
                continue
            for step in steps:
                header = step.markdown.split("**Что сделать**", 1)[0]
                for marker in forbidden:
                    self.assertNotIn(marker, header, f"{lesson_id} step {step.position}: {marker}")

    def test_legacy_first_step_uses_lesson_title_until_lesson_is_migrated(self) -> None:
        if not self._is_legacy_lesson("M01-L01"):
            self.skipTest("M01-L01 уже использует authored-semantic-v1")
        self.assertTrue(
            self.compiled["M01-L01"][0].markdown.startswith(
                "## Шаг 1 из 7. Превратите первый ответ в полезный результат"
            )
        )

    def test_legacy_outside_stepik_step_keeps_generated_return_until_migrated(self) -> None:
        if not self._is_legacy_lesson("M01-L01"):
            self.skipTest("M01-L01 уже использует authored-semantic-v1")
        step = self.compiled["M01-L01"][1]
        self.assertIn("**Что дальше:** после выполнения вернитесь в Stepik", step.markdown)

    def test_free_answer_rows_use_only_confirmed_platform_source(self) -> None:
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

    def test_unmigrated_sensitive_and_branching_lessons_keep_legacy_step_shapes(self) -> None:
        expectations = {
            "M03-L02": ["text", "text", "text", "text", "free-answer", "text", "text", "free-answer", "text"],
            "M06-L04": ["text", "text", "text", "free-answer", "text", "text", "free-answer", "text", "free-answer", "text"],
            "M00-L02": ["text"] * 6 + ["free-answer", "text"],
            "M06-L02": ["text", "text", "text", "text", "free-answer", "text"],
        }
        for lesson_id, expected in expectations.items():
            if not self._is_legacy_lesson(lesson_id):
                continue
            self.assertEqual(
                [step.block_name for step in self.compiled[lesson_id]],
                expected,
                lesson_id,
            )

    def test_unmigrated_check_steps_keep_proven_legacy_boundaries(self) -> None:
        if self._is_legacy_lesson("M05-L02"):
            m05 = self.compiled["M05-L02"]
            self.assertEqual(m05[8].source_headings, ("Проверьте реальное редактирование",))
            self.assertEqual(m05[8].check_ids, ("M05-L02-C02",))
            self.assertIn("Повторная ситуация для редактирования", m05[9].source_headings)

        if self._is_legacy_lesson("M07-L02"):
            m07 = self.compiled["M07-L02"]
            self.assertEqual(m07[5].source_headings, ("Финальная проверка",))
            self.assertEqual(m07[5].check_ids, ("M07-L02-C01",))
            self.assertIn("Если попытка стала тренировочной", m07[6].source_headings)

        if self._is_legacy_lesson("M08-L01"):
            m08 = self.compiled["M08-L01"]
            self.assertEqual(m08[4].source_headings, ("Короткая проверка переноса",))
            self.assertEqual(m08[4].check_ids, ("M08-L01-C01",))
            self.assertIn("Важная граница", m08[5].source_headings)
            self.assertIn("Итог", m08[5].source_headings)

    def test_m01_l02_keeps_proven_legacy_order_until_migrated(self) -> None:
        if not self._is_legacy_lesson("M01-L02"):
            self.skipTest("M01-L02 уже использует authored-semantic-v1")
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

    def test_authored_semantic_mode_keeps_only_authored_title_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_id = self._write_authored_fixture(
                root,
                lesson_markdown=(
                    "# Fixture\n\n"
                    "## Работайте со своим результатом\n\n"
                    "Сохраните файл после работы в чате и затем вернитесь в Stepik. "
                    "Ссылка: https://alice.yandex.ru/.\n"
                ),
                learner_rows=[("текст", "Проверка нового renderer", "EXPLANATION")],
            )
            step = compile_lesson_source(
                root,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id=lesson_id,
            )[0]

            self.assertEqual(
                step.markdown,
                (
                    "## Шаг 1 из 1. Работайте со своим результатом\n\n"
                    "Сохраните файл после работы в чате и затем вернитесь в Stepik. "
                    "Ссылка: https://alice.yandex.ru/."
                ),
            )
            for synthetic in (
                "**Зачем:**",
                "**Где и с чем:**",
                "**Что сделать**",
                "**Готово, если:**",
                "**Что сохранить:**",
                "**Что дальше:**",
            ):
                self.assertNotIn(synthetic, step.markdown)
            self.assertNotIn("EXPLANATION", step.markdown)
            self.assertEqual(step.semantic_type, "EXPLANATION")

    def test_authored_semantic_title_uses_first_consecutive_h2_h3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_id = self._write_authored_fixture(
                root,
                lesson_markdown=(
                    "# Fixture\n\n"
                    "## Первый смысловой заголовок\n"
                    "### Вложенный подзаголовок\n\n"
                    "Learner body.\n"
                ),
                learner_rows=[("текст", "Consecutive headings", "EXPLANATION")],
            )
            step = compile_lesson_source(
                root,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id=lesson_id,
            )[0]
            self.assertTrue(
                step.markdown.startswith("## Шаг 1 из 1. Первый смысловой заголовок")
            )
            self.assertIn("**Вложенный подзаголовок**", step.markdown)

    def test_authored_semantic_mode_has_no_lesson_title_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_id = self._write_authored_fixture(
                root,
                lesson_markdown="# Lesson title must not become step title\n\nТолько authored body без H2/H3.\n",
                learner_rows=[("текст", "Без heading", "EXPLANATION")],
            )
            with self.assertRaisesRegex(GeneralContentCompileError, "не имеет authored H2/H3 heading"):
                compile_lesson_source(
                    root,
                    free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                    lesson_id=lesson_id,
                )

    def test_authored_semantic_mode_rejects_production_id_only_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_id = self._write_authored_fixture(
                root,
                lesson_markdown="# Fixture\n\n## M99-L01-E01\n\nLearner body.\n",
                learner_rows=[("текст", "Production id heading", "EXPLANATION")],
            )
            with self.assertRaisesRegex(GeneralContentCompileError, "недопустимый authored title"):
                compile_lesson_source(
                    root,
                    free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                    lesson_id=lesson_id,
                )

    def test_authored_semantic_author_only_plan_row_does_not_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_id = self._write_authored_fixture(
                root,
                lesson_markdown="# Fixture\n\n## Видимый шаг\n\nТолько learner body.\n",
                learner_rows=[("текст", "Learner row", "EXPLANATION")],
                author_only_rows=[("author-only evaluation", "Author rubric secret", "CHECK")],
            )
            steps = compile_lesson_source(
                root,
                free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
                lesson_id=lesson_id,
            )
            self.assertEqual(len(steps), 1)
            self.assertNotIn("Author rubric", steps[0].markdown)
            self.assertNotIn("CHECK", steps[0].markdown)

    def test_free_answer_source_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(Exception, "free-answer source"):
            compile_lesson_source(
                self.repo_root,
                free_answer_source={"manual_scoring": True},
                lesson_id="M03-L02",
            )


if __name__ == "__main__":
    unittest.main()
