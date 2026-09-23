from __future__ import annotations

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import (
    assess_asset_publication,
    load_asset_publication_policy,
)
from scripts.stepik_uploader.canonical import (
    AUTHORED_SEMANTIC_RENDER_CONTRACT,
    SEMANTIC_TYPES,
    build_structural_manifest,
    parse_learner_render_contract,
    parse_stepik_plan,
)
from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_all_lesson_sources,
)
from scripts.stepik_uploader.verified_rendering import (
    AssetBinding,
    build_rendering_plan,
)


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "90_reviews" / "semantic-step-audit-2026-09-20"
STATE_PATH = BASELINE_DIR / "evidence" / "machine-state-2026-09-20.json"
POLICY_PATH = ROOT / "04_course" / "stepik" / "automation" / "asset-publication.v1.json"
COURSE_ID = 299189
POST_BASELINE_LEARNER_STEP_DELTA = {
    "M04-L03": 1,
    "M06-L04": 1,
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def visible_text(self) -> str:
        return " ".join(" ".join(self.parts).split())


class B7WholeCourseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_structural_manifest(ROOT, source_sha="b7-whole-course-integration")
        cls.lessons = {
            lesson["canonical_id"]: lesson
            for module in cls.manifest["modules"]
            for lesson in module["lessons"]
        }
        cls.compiled = compile_all_lesson_sources(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=cls.lessons,
        )

        inventory = build_asset_inventory(ROOT, cls.manifest)
        policy = load_asset_publication_policy(POLICY_PATH)
        cls.asset_report = assess_asset_publication(
            repo_root=ROOT,
            inventory=inventory,
            policy=policy,
            course_id=COURSE_ID,
        )

        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        expected_hashes = {
            str(row["source_path"]): str(row["source_sha256"])
            for row in cls.asset_report["resolutions"]
            if row.get("source_path") and row.get("source_sha256")
        }
        cls.bindings = [
            AssetBinding(
                **{
                    key: row[key]
                    for key in ("source_path", "source_sha256", "url", "storage")
                }
            )
            for row in state["assets"].values()
            if expected_hashes.get(str(row.get("source_path"))) == row.get("source_sha256")
        ]

    def test_all_21_plans_are_authored_and_all_semantic_types_are_valid(self) -> None:
        self.assertEqual(len(self.lessons), 21)
        structural_rows = 0
        author_only_rows = 0
        learner_rows = 0

        for lesson_id in sorted(self.lessons):
            module_id = lesson_id.split("-", 1)[0]
            plan_path = ROOT / "04_course" / module_id / lesson_id / "stepik-plan.md"
            text = plan_path.read_text(encoding="utf-8")
            self.assertEqual(
                parse_learner_render_contract(text, path=plan_path),
                AUTHORED_SEMANTIC_RENDER_CONTRACT,
                lesson_id,
            )
            rows = parse_stepik_plan(text, lesson_id=lesson_id, path=plan_path)
            structural_rows += len(rows)
            author_only_rows += sum(1 for row in rows if row["author_only"])
            learner_rows += sum(1 for row in rows if not row["author_only"])
            for row in rows:
                self.assertIn(row["semantic_type"], SEMANTIC_TYPES, lesson_id)

        self.assertEqual(structural_rows, 152)
        self.assertEqual(author_only_rows, 2)
        self.assertEqual(learner_rows, 150)

    def test_all_150_learner_steps_render_and_reconcile_baseline_structure(self) -> None:
        rendered_total = 0
        materialization_requirements: set[str] = set()
        block_deltas: list[str] = []
        source_deltas: list[str] = []

        for lesson_id in sorted(self.lessons):
            plan = build_rendering_plan(
                repo_root=ROOT,
                lesson_id=lesson_id,
                source_steps=self.compiled[lesson_id],
                asset_report=self.asset_report,
                bindings=self.bindings,
            )
            rendered = plan.rendered_steps
            materialization_requirements.update(
                str(item["source_path"]) for item in plan.materialization_requirements
            )

            baseline = json.loads(
                (BASELINE_DIR / "rendered" / f"{lesson_id}.json").read_text(encoding="utf-8")
            )
            expected_steps = baseline["steps"]

            expected_delta = POST_BASELINE_LEARNER_STEP_DELTA.get(lesson_id, 0)
            self.assertEqual(
                len(rendered),
                len(expected_steps) + expected_delta,
                f"{lesson_id}: unexpected post-baseline learner-step delta",
            )
            rendered_total += len(rendered)

            for actual, expected in zip(rendered[: len(expected_steps)], expected_steps, strict=True):
                self.assertEqual(actual.position, expected["position"], lesson_id)
                if actual.block_name != expected["platform_block_type"]:
                    block_deltas.append(
                        f"{lesson_id} S{actual.position:02d}: "
                        f"{expected['platform_block_type']} -> {actual.block_name}"
                    )
                if actual.source != expected["platform_source"]:
                    source_deltas.append(
                        f"{lesson_id} S{actual.position:02d}: "
                        f"{expected['platform_source']} -> {actual.source}"
                    )

        self.assertEqual(rendered_total, 150)
        self.assertEqual(
            block_deltas,
            ["M08-L01 S02: free-answer -> text"],
            "Допустим ровно один явно reconciled B6 delta: M08 reflection E01 не является Stepik check",
        )
        self.assertEqual(
            source_deltas,
            [
                "M08-L01 S02: "
                "{'is_attachments_enabled': False, 'is_html_enabled': True, 'manual_scoring': False} -> {}"
            ],
            "Source delta допустим только как вторая половина reconciled M08 S02 free-answer -> text",
        )
        self.assertEqual(
            materialization_requirements,
            {"05_assets/M03/M03-L02/M03-L02-A03-alice.png"},
            "До post-merge guarded release допускается только известный B3 source-hash refresh Alice PNG",
        )

    def test_no_legacy_synthetic_frame_survives_in_final_learner_markdown(self) -> None:
        forbidden = (
            "**Зачем:**",
            "**Где и с чем:**",
            "**Что сделать**",
            "**Готово, если:**",
            "**Что сохранить:**",
            "**Что дальше:**",
        )
        for lesson_id, steps in self.compiled.items():
            for step in steps:
                for marker in forbidden:
                    self.assertNotIn(
                        marker,
                        step.markdown,
                        f"{lesson_id} step {step.position}: legacy frame marker {marker}",
                    )

    def test_final_visible_html_has_no_internal_production_jargon(self) -> None:
        forbidden_patterns = (
            re.compile(r"\\bM\\d{2}-L\\d{2}(?:-[AEC]\\d{2})?\\b"),
            re.compile(r"\\bM0[0-8]\\b"),
            re.compile(r"(?<![-\\w])C\\d{2}(?!\\w)"),
            re.compile(r"(?<![-\\w])E\\d{2}(?!\\w)"),
            re.compile(r"(?<![-\\w])B(?:10|11|12|[1-9])(?!\\w)"),
            re.compile(r"\\bF1\\b"),
            re.compile(r"\\bPASS\\b", re.IGNORECASE),
            re.compile(r"NOT\\s+PROVEN", re.IGNORECASE),
            re.compile(r"post[- ]action", re.IGNORECASE),
            re.compile(r"\\brecovery\\b", re.IGNORECASE),
            re.compile(r"\\bmaterialization\\b", re.IGNORECASE),
            re.compile(r"\\bproduction\\b", re.IGNORECASE),
            re.compile(r"\\bauthored\\b", re.IGNORECASE),
            re.compile(r"\\bsemantic\\b", re.IGNORECASE),
            re.compile(r"\\brubric\\b", re.IGNORECASE),
            re.compile(r"\\bindependent\\b", re.IGNORECASE),
            re.compile(r"\\bevidence\\b", re.IGNORECASE),
            re.compile(r"\\bcheck\\b", re.IGNORECASE),
            re.compile(r"\\bverified\\b", re.IGNORECASE),
            re.compile(r"Alice PNG|Опубликованную ветку|локальн.*восстанов", re.IGNORECASE),
        )

        for lesson_id, steps in self.compiled.items():
            plan = build_rendering_plan(
                repo_root=ROOT,
                lesson_id=lesson_id,
                source_steps=steps,
                asset_report=self.asset_report,
                bindings=self.bindings,
            )
            for rendered in plan.rendered_steps:
                parser = _VisibleTextParser()
                parser.feed(rendered.text)
                visible = parser.visible_text()
                for pattern in forbidden_patterns:
                    self.assertIsNone(
                        pattern.search(visible),
                        f"{lesson_id} step {rendered.position}: visible internal marker {pattern.pattern!r}",
                    )

    def test_semantic_type_and_explicit_check_ownership_define_block_type(self) -> None:
        for lesson_id, steps in self.compiled.items():
            for step in steps:
                expected = (
                    "free-answer"
                    if step.semantic_type == "CHECK"
                    or (step.semantic_type == "COMPOSITE" and step.check_ids)
                    else "text"
                )
                self.assertEqual(
                    step.block_name,
                    expected,
                    f"{lesson_id} step {step.position}: {step.semantic_type}",
                )


if __name__ == "__main__":
    unittest.main()
