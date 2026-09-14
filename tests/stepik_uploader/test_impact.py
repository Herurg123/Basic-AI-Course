from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.impact import Change, assess_changes, assess_paths, parse_changes


class ImpactTests(unittest.TestCase):
    def test_maps_lesson_and_asset_changes_to_canonical_lesson(self) -> None:
        result = assess_paths([
            "04_course/M03/M03-L02/lesson.md",
            "05_assets/M03/M03-L02/M03-L02-A03.png",
            "04_course/M03/M03-L02/author-notes.md",
        ])
        self.assertEqual(result["affected_lessons"], ["M03-L02"])
        self.assertFalse(result["course_page_changed"])
        self.assertTrue(result["stepik_content_impact"])
        self.assertNotIn("04_course/M03/M03-L02/author-notes.md", result["paths_by_lesson"]["M03-L02"])

    def test_course_page_is_tracked_separately(self) -> None:
        result = assess_paths(["04_course/stepik/course-page.md"])
        self.assertEqual(result["affected_lessons"], [])
        self.assertTrue(result["course_page_changed"])
        self.assertTrue(result["stepik_content_impact"])

    def test_tooling_only_change_does_not_mark_course_content_pending(self) -> None:
        result = assess_paths(["scripts/stepik_uploader/writer.py"])
        self.assertFalse(result["stepik_content_impact"])

    def test_name_status_parser_supports_added_modified_renamed_deleted(self) -> None:
        changes = parse_changes([
            "A\tnew.md",
            "M\tmodified.md",
            "R100\told.md\trenamed.md",
            "D\tdeleted.md",
        ])
        self.assertEqual([change.status for change in changes], ["A", "M", "R", "D"])
        self.assertEqual(changes[2].paths, ("old.md", "renamed.md"))

    def test_shared_learner_file_marks_all_canonical_dependents(self) -> None:
        with self._roots() as (base, head):
            self._lesson(base, "M06-L04", "[guide](../../stepik/how-to-save-practice.md)")
            self._lesson(base, "M07-L02", "[guide](../../stepik/how-to-save-practice.md)")
            self._lesson(head, "M06-L04", "[guide](../../stepik/how-to-save-practice.md)")
            self._lesson(head, "M07-L02", "[guide](../../stepik/how-to-save-practice.md)")
            self._shared(base, "how-to-save-practice.md")
            self._shared(head, "how-to-save-practice.md", "changed")
            result = assess_changes(
                [Change("M", "04_course/stepik/how-to-save-practice.md", "04_course/stepik/how-to-save-practice.md")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertEqual(result["affected_lessons"], ["M06-L04", "M07-L02"])
        self.assertFalse(result["blockers"])

    def test_rename_shared_file_uses_before_and_after_graphs(self) -> None:
        with self._roots() as (base, head):
            self._lesson(base, "M07-L01", "[guide](../../stepik/old-guide.md)")
            self._lesson(head, "M07-L01", "[guide](../../stepik/new-guide.md)")
            self._shared(base, "old-guide.md")
            self._shared(head, "new-guide.md")
            result = assess_changes(
                [Change("R", "04_course/stepik/old-guide.md", "04_course/stepik/new-guide.md")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertEqual(result["affected_lessons"], ["M07-L01"])
        self.assertFalse(result["blockers"])
        self.assertEqual(set(result["paths_by_lesson"]["M07-L01"]), {"04_course/stepik/old-guide.md", "04_course/stepik/new-guide.md"})

    def test_delete_shared_file_uses_base_graph(self) -> None:
        with self._roots() as (base, head):
            self._lesson(base, "M06-L04", "[guide](../../stepik/old-guide.md)")
            self._lesson(head, "M06-L04", "No shared guide now")
            self._shared(base, "old-guide.md")
            result = assess_changes(
                [Change("D", "04_course/stepik/old-guide.md", None)],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertEqual(result["affected_lessons"], ["M06-L04"])
        self.assertFalse(result["blockers"])

    def test_author_notes_do_not_create_learner_impact(self) -> None:
        with self._roots() as (base, head):
            result = assess_changes(
                [Change("M", "04_course/M03/M03-L02/author-notes.md", "04_course/M03/M03-L02/author-notes.md")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertFalse(result["stepik_content_impact"])
        self.assertFalse(result["blockers"])

    def test_tooling_only_change_does_not_create_pending(self) -> None:
        with self._roots() as (base, head):
            result = assess_changes(
                [Change("M", "scripts/stepik_uploader/writer.py", "scripts/stepik_uploader/writer.py")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertFalse(result["stepik_content_impact"])

    def test_course_page_remains_separate_in_dependency_aware_mode(self) -> None:
        with self._roots() as (base, head):
            result = assess_changes(
                [Change("M", "04_course/stepik/course-page.md", "04_course/stepik/course-page.md")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertEqual(result["affected_lessons"], [])
        self.assertTrue(result["course_page_changed"])

    def test_unknown_shared_learner_dependency_fails_closed(self) -> None:
        with self._roots() as (base, head):
            self._shared(head, "new-unmapped-guide.md")
            result = assess_changes(
                [Change("A", None, "04_course/stepik/new-unmapped-guide.md")],
                repo_root=head,
                base_repo_root=base,
            )
        self.assertTrue(result["blockers"])
        self.assertIn("unknown-learner-facing-dependency", result["blockers"][0])

    class _roots:
        def __enter__(self):
            self.base_tmp = tempfile.TemporaryDirectory()
            self.head_tmp = tempfile.TemporaryDirectory()
            return Path(self.base_tmp.name), Path(self.head_tmp.name)

        def __exit__(self, exc_type, exc, tb):
            self.base_tmp.cleanup()
            self.head_tmp.cleanup()

    def _lesson(self, root: Path, lesson_id: str, body: str) -> None:
        module = lesson_id.split("-")[0]
        path = root / "04_course" / module / lesson_id / "lesson.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Lesson\n\n" + body + "\n", encoding="utf-8")

    def _shared(self, root: Path, name: str, body: str = "guide") -> None:
        path = root / "04_course" / "stepik" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
