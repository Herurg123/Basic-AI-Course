from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from scripts.stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest, parse_stepik_plan
from scripts.stepik_uploader.planner import learner_write_rows


DISTRIBUTION = {"M00": 3, "M01": 2, "M02": 2, "M03": 2, "M04": 3, "M05": 2, "M06": 4, "M07": 2, "M08": 1}


def make_repo(root: Path) -> None:
    course = root / "04_course"
    course.mkdir(parents=True)
    readme_lines = ["# Course"]
    for module_id in DISTRIBUTION:
        readme_lines.append(f"### {module_id}. Модуль {module_id}")
    (course / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

    for module_id, count in DISTRIBUTION.items():
        module_dir = course / module_id
        module_dir.mkdir()
        for index in range(1, count + 1):
            lesson_id = f"{module_id}-L{index:02d}"
            lesson_dir = module_dir / lesson_id
            lesson_dir.mkdir()
            asset = f"{lesson_id}-A01"
            exercise = f"{lesson_id}-E01"
            check = f"{lesson_id}-C01"
            lesson = f"# Урок {lesson_id}\n\n<!-- Exercise: {exercise} -->\n[Материал](../../../05_assets/{module_id}/{lesson_id}/{asset}.md)\n<!-- Check: {check} -->\n"
            logical_type = "author-only" if lesson_id == "M06-L02" else "текст"
            plan = (
                f"# Stepik plan — {lesson_id}\n\n"
                "| № | Тип шага | Содержание | Материал | Проверка |\n"
                "|---:|---|---|---|---|\n"
                f"| 1 | {logical_type} | Содержание | `{asset}.md` | `{check}` |\n"
            )
            (lesson_dir / "lesson.md").write_text(lesson, encoding="utf-8")
            (lesson_dir / "stepik-plan.md").write_text(plan, encoding="utf-8")


class CanonicalTests(unittest.TestCase):
    def test_builds_nine_modules_twenty_one_lessons_and_flags_f1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_repo(root)
            manifest = build_structural_manifest(root, source_sha="abc")
            self.assertEqual(manifest["summary"]["modules"], 9)
            self.assertEqual(manifest["summary"]["lessons"], 21)
            self.assertFalse(manifest["write_enabled"])
            self.assertEqual(manifest["phase"], "structural")
            self.assertIn("requires-live-write-gates", manifest["global_blockers"])
            m07_l02 = next(
                lesson
                for module in manifest["modules"]
                for lesson in module["lessons"]
                if lesson["canonical_id"] == "M07-L02"
            )
            self.assertTrue(m07_l02["f1_sensitive"])
            self.assertTrue(m07_l02["independence_sensitive"])
            self.assertEqual(m07_l02["write_blocker"], "requires-live-write-gates")
            self.assertEqual(m07_l02["steps"][0]["rendering_status"], "structural-only")

    def test_generated_manifest_matches_json_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_repo(root)
            manifest = build_structural_manifest(root)
            schema_path = Path(__file__).resolve().parents[2] / "04_course/stepik/automation/schema/build-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(manifest)

    def test_author_only_rows_are_never_in_learner_write_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_repo(root)
            manifest = build_structural_manifest(root)
            rows = learner_write_rows(manifest)
            self.assertFalse(any(row["lesson"] == "M06-L02" for row in rows))

    def test_author_rubric_row_is_fail_closed_author_only(self) -> None:
        plan = (
            "| № | Тип шага | Содержание | Материал | Проверка |\n"
            "|---:|---|---|---|---|\n"
            "| 1 | evaluation | Author rubric применяется после попытки | `M07-L02-A02.md` | `M07-L02-C01` |\n"
        )
        rows = parse_stepik_plan(plan, lesson_id="M07-L02", path=Path("plan.md"))
        self.assertTrue(rows[0]["author_only"])

    def test_more_than_sixteen_plan_rows_is_blocker(self) -> None:
        rows = "\n".join(f"| {i} | текст | x | — | — |" for i in range(1, 18))
        plan = "| № | Тип шага | Содержание | Материал | Проверка |\n|---:|---|---|---|---|\n" + rows
        with self.assertRaisesRegex(CanonicalBuildError, "16 шагов"):
            parse_stepik_plan(plan, lesson_id="M00-L01", path=Path("plan.md"))


if __name__ == "__main__":
    unittest.main()
