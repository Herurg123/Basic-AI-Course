from __future__ import annotations

import json
import unittest
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
    require_render_ready,
)


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "90_reviews" / "semantic-step-audit-2026-09-20"
STATE_PATH = BASELINE_DIR / "evidence" / "machine-state-2026-09-20.json"
POLICY_PATH = ROOT / "04_course" / "stepik" / "automation" / "asset-publication.v1.json"
COURSE_ID = 299189


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
        cls.bindings = [
            AssetBinding(
                **{
                    key: row[key]
                    for key in ("source_path", "source_sha256", "url", "storage")
                }
            )
            for row in state["assets"].values()
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

        self.assertEqual(structural_rows, 150)
        self.assertEqual(author_only_rows, 2)
        self.assertEqual(learner_rows, 148)

    def test_all_148_learner_steps_render_and_keep_baseline_structure(self) -> None:
        rendered_total = 0
        for lesson_id in sorted(self.lessons):
            rendered = require_render_ready(
                build_rendering_plan(
                    repo_root=ROOT,
                    lesson_id=lesson_id,
                    source_steps=self.compiled[lesson_id],
                    asset_report=self.asset_report,
                    bindings=self.bindings,
                )
            )
            baseline = json.loads(
                (BASELINE_DIR / "rendered" / f"{lesson_id}.json").read_text(encoding="utf-8")
            )
            expected_steps = baseline["steps"]

            self.assertEqual(len(rendered), len(expected_steps), lesson_id)
            rendered_total += len(rendered)

            for actual, expected in zip(rendered, expected_steps, strict=True):
                self.assertEqual(actual.position, expected["position"], lesson_id)
                self.assertEqual(
                    actual.block_name,
                    expected["platform_block_type"],
                    f"{lesson_id} S{actual.position:02d}",
                )
                self.assertEqual(
                    actual.source,
                    expected["platform_source"],
                    f"{lesson_id} S{actual.position:02d}",
                )

        self.assertEqual(rendered_total, 148)

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

    def test_semantic_type_is_the_only_block_type_contract(self) -> None:
        for lesson_id, steps in self.compiled.items():
            for step in steps:
                expected = "free-answer" if step.semantic_type == "CHECK" else "text"
                self.assertEqual(
                    step.block_name,
                    expected,
                    f"{lesson_id} step {step.position}: {step.semantic_type}",
                )


if __name__ == "__main__":
    unittest.main()
