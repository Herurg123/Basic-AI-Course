from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import learner_link_topology
from scripts.stepik_uploader.canonical import build_structural_manifest


class AssetResolutionDiagnosticTests(unittest.TestCase):
    def test_emit_exact_learner_asset_link_inventory(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="asset-resolution-diagnostic")
        inventory = build_asset_inventory(repo_root, manifest)
        self.assertEqual(inventory["missing_files"], [])

        rows = []
        for lesson_id, lesson in sorted(inventory["lessons"].items()):
            for link in lesson["learner_links"]:
                rows.append(
                    {
                        "lesson": lesson_id,
                        "asset_id": link["asset_id"],
                        "source_path": link["source_path"],
                        "filename": link.get("filename"),
                        "extension": link.get("extension"),
                        "size_bytes": link.get("size_bytes"),
                        "sha256": link.get("sha256"),
                        "markdown_target": link["markdown_target"],
                    }
                )

        topology = learner_link_topology(inventory)
        print("ASSET_RESOLUTION_TOPOLOGY=" + json.dumps(topology, ensure_ascii=False, separators=(",", ":")))
        self.assertEqual(len(rows), inventory["summary"]["learner_repo_links"])
        self.assertEqual(topology["learner_link_occurrences"], len(rows))
        self.assertGreater(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
