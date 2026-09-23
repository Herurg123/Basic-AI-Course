from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.verified_rendering import AssetBinding, build_rendering_plan, require_render_ready

# Canonical/production IDs are stable internal metadata. They must not become learner-visible text.
# The pattern intentionally catches a bare lesson ID as well as Asset/Exercise/Check IDs and
# suffixes such as M03-L02-A03-alice. Paths/URLs and hidden HTML comments are excluded below.
INTERNAL_ID_RE = re.compile(r"\bM\d{2}-L\d{2}(?:-[AEC]\d{2}(?:-[A-Za-z0-9_-]+)?)?\b")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def visible_text(self) -> str:
        return "\n".join(self.parts)


def _visible_markdown(markdown: str) -> str:
    """Возвращает только то, что ученик потенциально читает в Markdown.

    Production anchors в HTML comments и link destinations могут содержать canonical IDs;
    label ссылки остаётся видимым и поэтому проверяется.
    """
    without_comments = HTML_COMMENT_RE.sub("", markdown)
    return MARKDOWN_LINK_RE.sub(lambda match: match.group(1), without_comments)


def _visible_html(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    return parser.visible_text()


class LearnerIdHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.manifest = build_structural_manifest(cls.repo_root, source_sha="learner-id-hygiene-test")
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
        inventory = build_asset_inventory(cls.repo_root, cls.manifest)
        policy = load_asset_publication_policy(
            cls.repo_root / "04_course/stepik/automation/asset-publication.v1.json"
        )
        cls.asset_report = assess_asset_publication(
            repo_root=cls.repo_root,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )

    def _synthetic_bindings(self) -> list[AssetBinding]:
        bindings: dict[str, AssetBinding] = {}
        for row in self.asset_report["resolutions"]:
            if row.get("materialization_required_at_write") is not True:
                continue
            source_path = str(row["source_path"])
            if source_path in bindings:
                continue
            filename = Path(source_path).name
            if row["mode"] == "rasterize-png-stepik-image":
                filename = Path(filename).stem + ".png"
            bindings[source_path] = AssetBinding(
                source_path=source_path,
                source_sha256=str(row["source_sha256"]),
                url=f"https://stepik.org/media/attachments/lesson/999999/{filename}",
                storage="test-only-synthetic-stepik-binding",
                verified=True,
            )
        return list(bindings.values())

    def test_canonical_lesson_visible_markdown_has_no_internal_ids(self) -> None:
        offenders: list[str] = []
        for lesson_id in self.lesson_ids:
            module_id = lesson_id.split("-", 1)[0]
            path = self.repo_root / "04_course" / module_id / lesson_id / "lesson.md"
            visible = _visible_markdown(path.read_text(encoding="utf-8"))
            for line_number, line in enumerate(visible.splitlines(), start=1):
                ids = sorted(set(INTERNAL_ID_RE.findall(line)))
                if ids:
                    offenders.append(f"{lesson_id}: visible line {line_number}: {', '.join(ids)} :: {line.strip()}")
        self.assertEqual([], offenders, "Internal IDs leaked into canonical learner text:\n" + "\n".join(offenders))

    def test_verified_rendering_visible_text_has_no_internal_ids(self) -> None:
        bindings = self._synthetic_bindings()
        offenders: list[str] = []
        total_steps = 0
        for lesson_id in self.lesson_ids:
            plan = build_rendering_plan(
                repo_root=self.repo_root,
                lesson_id=lesson_id,
                source_steps=self.compiled[lesson_id],
                asset_report=self.asset_report,
                bindings=bindings,
            )
            steps = require_render_ready(plan)
            total_steps += len(steps)
            for step in steps:
                visible = _visible_html(step.text)
                ids = sorted(set(INTERNAL_ID_RE.findall(visible)))
                if ids:
                    offenders.append(
                        f"{lesson_id} step {step.position}: {', '.join(ids)} :: "
                        + " ".join(visible.split())[:280]
                    )
        # P3 deliberately adds exactly two learner-facing steps after the immutable B7 baseline:
        # M04-L03 +1 and M06-L04 +1. The whole-course integration test reconciles those deltas explicitly.
        self.assertEqual(total_steps, 150)
        self.assertEqual([], offenders, "Internal IDs leaked into verified rendering:\n" + "\n".join(offenders))

    def test_canonical_lesson_titles_are_human_facing(self) -> None:
        offenders: list[str] = []
        for module in self.manifest["modules"]:
            for lesson in module["lessons"]:
                title = str(lesson["title"])
                if INTERNAL_ID_RE.search(title):
                    offenders.append(f"{lesson['canonical_id']}: {title}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
