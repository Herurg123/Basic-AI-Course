from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources

LINK_RE = re.compile(r"\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)")


class RenderingContextDiagnostic(unittest.TestCase):
    def test_dump_local_link_contexts(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="rendering-context-diagnostic")
        lesson_ids = [
            str(lesson["canonical_id"])
            for module in manifest["modules"]
            for lesson in module["lessons"]
        ]
        compiled = compile_all_lesson_sources(
            repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=lesson_ids,
        )
        rows = []
        for lesson_id in lesson_ids:
            for step in compiled[lesson_id]:
                for match in LINK_RE.finditer(step.markdown):
                    start = max(0, step.markdown.rfind("\n\n", 0, match.start()) + 2)
                    end = step.markdown.find("\n\n", match.end())
                    if end < 0:
                        end = len(step.markdown)
                    context = step.markdown[start:end].replace("\n", " ")
                    rows.append((lesson_id, step.position, match.group(1), match.group(2), context))
        self.assertEqual(len(rows), 48)
        print("RENDERING_LOCAL_LINK_CONTEXTS_BEGIN")
        for row in rows:
            print(" | ".join(str(value) for value in row))
        print("RENDERING_LOCAL_LINK_CONTEXTS_END")


if __name__ == "__main__":
    unittest.main()
