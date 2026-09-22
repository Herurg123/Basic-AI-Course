from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import (
    assess_asset_publication,
    load_asset_publication_policy,
)
from scripts.stepik_uploader.canonical import (
    build_structural_manifest,
    parse_learner_render_contract,
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


class AuthoredSemanticMigrationRegressionTests(unittest.TestCase):
    def test_every_unmigrated_lesson_matches_step1_exact_learner_html(self) -> None:
        manifest = build_structural_manifest(ROOT, source_sha="migration-regression")
        lessons = {
            lesson["canonical_id"]: lesson
            for module in manifest["modules"]
            for lesson in module["lessons"]
        }
        self.assertEqual(len(lessons), 21)

        compiled = compile_all_lesson_sources(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=lessons,
        )
        inventory = build_asset_inventory(ROOT, manifest)
        policy = load_asset_publication_policy(POLICY_PATH)
        asset_report = assess_asset_publication(
            repo_root=ROOT,
            inventory=inventory,
            policy=policy,
            course_id=COURSE_ID,
        )
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        bindings = [
            AssetBinding(
                **{
                    key: row[key]
                    for key in ("source_path", "source_sha256", "url", "storage")
                }
            )
            for row in state["assets"].values()
        ]

        legacy_lessons = 0
        legacy_steps = 0
        for lesson_id in sorted(lessons):
            module_id = lesson_id.split("-", 1)[0]
            plan_path = ROOT / "04_course" / module_id / lesson_id / "stepik-plan.md"
            render_contract = parse_learner_render_contract(
                plan_path.read_text(encoding="utf-8"),
                path=plan_path,
            )
            if render_contract is not None:
                continue

            legacy_lessons += 1
            rendered = require_render_ready(
                build_rendering_plan(
                    repo_root=ROOT,
                    lesson_id=lesson_id,
                    source_steps=compiled[lesson_id],
                    asset_report=asset_report,
                    bindings=bindings,
                )
            )
            baseline = json.loads(
                (BASELINE_DIR / "rendered" / f"{lesson_id}.json").read_text(encoding="utf-8")
            )
            expected_steps = baseline["steps"]
            self.assertEqual(len(rendered), len(expected_steps), lesson_id)

            for actual, expected in zip(rendered, expected_steps, strict=True):
                legacy_steps += 1
                actual_sha = hashlib.sha256(actual.text.encode()).hexdigest()
                self.assertEqual(actual_sha, expected["html_sha256"], f"{lesson_id} S{actual.position:02d}")
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

        # На B0 opt-in реальных уроков запрещён: baseline должен покрывать 21/21 и 148/148.
        # В B1-B6 эти числа закономерно уменьшаются только для явно мигрированных lessons.
        self.assertGreater(legacy_lessons, 0)
        self.assertGreater(legacy_steps, 0)
        if legacy_lessons == len(lessons):
            self.assertEqual(legacy_lessons, 21)
            self.assertEqual(legacy_steps, 148)


if __name__ == "__main__":
    unittest.main()
