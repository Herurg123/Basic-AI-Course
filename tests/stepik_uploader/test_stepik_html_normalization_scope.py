from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.verified_rendering import (
    AssetBinding,
    build_rendering_plan,
    normalize_stepik_html_v1,
    require_render_ready,
)


class StepikHtmlNormalizationScopeTests(unittest.TestCase):
    def test_v2_fingerprint_delta_is_limited_to_m06_l02(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="normalization-scope-test")
        lessons = {
            str(lesson["canonical_id"]): lesson
            for module in manifest["modules"]
            for lesson in module["lessons"]
        }
        compiled = compile_all_lesson_sources(
            repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=list(lessons),
        )
        inventory = build_asset_inventory(repo_root, manifest)
        policy = load_asset_publication_policy(
            repo_root / "04_course/stepik/automation/asset-publication.v1.json"
        )
        asset_report = assess_asset_publication(
            repo_root=repo_root,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )
        bindings: dict[str, AssetBinding] = {}
        for row in asset_report["resolutions"]:
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

        changed: set[str] = set()
        for lesson_id, lesson in lessons.items():
            raw_plan = build_rendering_plan(
                repo_root=repo_root,
                lesson_id=lesson_id,
                source_steps=compiled[lesson_id],
                asset_report=asset_report,
                bindings=list(bindings.values()),
                apply_stepik_html_normalization=False,
            )
            raw_steps = require_render_ready(raw_plan)
            v1_steps = [replace(step, text=normalize_stepik_html_v1(step.text).strip()) for step in raw_steps]
            v2_steps = require_render_ready(
                build_rendering_plan(
                    repo_root=repo_root,
                    lesson_id=lesson_id,
                    source_steps=compiled[lesson_id],
                    asset_report=asset_report,
                    bindings=list(bindings.values()),
                )
            )
            title = str(lesson["title"])
            v1 = compiled_lesson_fingerprint(expected_title=title, expected_steps=v1_steps)
            v2 = compiled_lesson_fingerprint(expected_title=title, expected_steps=v2_steps)
            if v1 != v2:
                changed.add(lesson_id)

        self.assertEqual(changed, {"M06-L02"})


if __name__ == "__main__":
    unittest.main()
