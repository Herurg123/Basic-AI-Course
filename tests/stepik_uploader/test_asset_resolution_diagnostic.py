from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import learner_link_topology
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import (
    EXPECTED_FREE_ANSWER_SOURCE,
    compile_all_lesson_sources,
)


class AssetResolutionDiagnosticTests(unittest.TestCase):
    def test_emit_exact_learner_asset_link_inventory(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="asset-resolution-diagnostic")
        inventory = build_asset_inventory(repo_root, manifest)
        self.assertEqual(inventory["missing_files"], [])

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
        compiler_links = [
            {
                "lesson": lesson_id,
                "step": step.position,
                "markdown_target": target,
            }
            for lesson_id in lesson_ids
            for step in compiled[lesson_id]
            for target in step.unresolved_repo_links
        ]

        topology = learner_link_topology(inventory)
        print("ASSET_RESOLUTION_TOPOLOGY=" + json.dumps(topology, ensure_ascii=False, separators=(",", ":")))
        print("ALL_COMPILER_REPO_LINKS=" + json.dumps(compiler_links, ensure_ascii=False, separators=(",", ":")))
        self.assertEqual(topology["learner_link_occurrences"], inventory["summary"]["learner_repo_links"])
        self.assertGreater(len(compiler_links), 0)


if __name__ == "__main__":
    unittest.main()
