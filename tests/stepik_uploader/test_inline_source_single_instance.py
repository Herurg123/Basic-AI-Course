from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LESSON_ROOT = ROOT / "04_course"
LOCAL_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+?\.md(?:#[^)]*)?)\)")


def _local_md_targets(source_path: Path) -> list[Path]:
    text = source_path.read_text(encoding="utf-8")
    targets: list[Path] = []
    for match in LOCAL_MD_LINK_RE.finditer(text):
        raw = match.group(1).strip()
        if raw.startswith(("http://", "https://", "#")):
            continue
        raw_path = raw.split("#", 1)[0]
        target = (source_path.parent / raw_path).resolve()
        try:
            target.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise AssertionError(f"{source_path}: learner link escapes repository: {raw}") from exc
        if not target.is_file():
            raise AssertionError(f"{source_path}: learner Markdown target missing: {raw}")
        targets.append(target)
    return targets


def _walk_graph(source_path: Path, *, stack: tuple[Path, ...] = ()) -> list[Path]:
    if source_path in stack:
        cycle = " -> ".join(str(path.relative_to(ROOT)) for path in (*stack, source_path))
        raise AssertionError(f"cyclic learner Markdown dependency: {cycle}")
    result: list[Path] = []
    for target in _local_md_targets(source_path):
        result.append(target)
        result.extend(_walk_graph(target, stack=(*stack, source_path)))
    return result


class InlineSourceSingleInstanceTests(unittest.TestCase):
    def test_local_markdown_is_inlined_only_once_across_learner_graph(self) -> None:
        lesson_paths = sorted(LESSON_ROOT.glob("M*/M*-L*/lesson.md"))
        self.assertEqual(len(lesson_paths), 21)

        occurrences: Counter[str] = Counter()
        for lesson_path in lesson_paths:
            for target in _walk_graph(lesson_path):
                occurrences[str(target.relative_to(ROOT))] += 1

        duplicates = {
            source: count
            for source, count in sorted(occurrences.items())
            if count > 1
        }
        self.assertEqual(
            duplicates,
            {},
            "One local Markdown source would be physically inlined more than once in Stepik. "
            "Keep one canonical inline occurrence and use an HTTPS Stepik link for later references.",
        )

    def test_known_support_materials_have_one_canonical_inline_location(self) -> None:
        support_sources = {
            "05_assets/M00/M00-L03/M00-L03-A02.md": 1,
            "05_assets/M05/M05-L02/M05-L02-A03.md": 1,
            "04_course/stepik/how-to-save-practice.md": 1,
        }
        lesson_paths = sorted(LESSON_ROOT.glob("M*/M*-L*/lesson.md"))
        occurrences: Counter[str] = Counter()
        for lesson_path in lesson_paths:
            for target in _walk_graph(lesson_path):
                occurrences[str(target.relative_to(ROOT))] += 1
        for source, expected in support_sources.items():
            self.assertEqual(occurrences[source], expected, source)


if __name__ == "__main__":
    unittest.main()
