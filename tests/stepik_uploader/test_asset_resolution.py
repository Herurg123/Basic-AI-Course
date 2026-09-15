from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import (
    AssetResolutionError,
    assess_asset_publication,
    load_asset_publication_policy,
)
from scripts.stepik_uploader.canonical import build_structural_manifest


class AssetResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(cls.repo_root, source_sha="asset-resolution-test")
        cls.inventory = build_asset_inventory(cls.repo_root, manifest)
        cls.policy = load_asset_publication_policy(
            cls.repo_root / "04_course/stepik/automation/asset-publication.v1.json"
        )

    def _assess(self, *, inventory=None, policy=None):
        return assess_asset_publication(
            repo_root=self.repo_root,
            inventory=self.inventory if inventory is None else inventory,
            policy=self.policy if policy is None else policy,
            course_id=299189,
        )

    def test_current_course_has_one_explicit_external_prerequisite(self) -> None:
        report = self._assess()
        self.assertFalse(report["route_gate_passed"])
        self.assertFalse(report["ready_for_bulk_write"])
        self.assertEqual(report["next_gate"], "asset-publication-resolution")
        self.assertEqual(report["stepik_writes"], 0)
        self.assertEqual(
            report["topology"]["fingerprint"],
            "sha256:77833131b344938cc396f4e32e2274bdb4f141111b73252e7f9794bbbb76dabc",
        )
        self.assertEqual(
            report["summary"],
            {
                "learner_link_occurrences": 45,
                "resolved_occurrences": 44,
                "unresolved_occurrences": 1,
                "unique_source_files": 41,
                "resolved_unique_source_files": 40,
                "unresolved_unique_source_files": 1,
                "materialization_required_unique_files": 4,
                "modes_by_occurrence": {
                    "confirmed-url": 2,
                    "download-url-required": 1,
                    "inline-source": 38,
                    "rasterize-png-stepik-image": 2,
                    "stepik-image-upload": 2,
                },
            },
        )
        self.assertEqual(
            report["unresolved_sources"],
            ["05_assets/M04/M04-L01/M04-L01-A01.txt"],
        )
        self.assertEqual(len(report["blockers"]), 1)
        self.assertIn("mandatory-real-file-upload-practice", report["blockers"][0])

    def test_golden_existing_urls_are_bound_to_exact_source_hashes(self) -> None:
        report = self._assess()
        confirmed = [item for item in report["resolutions"] if item["mode"] == "confirmed-url"]
        self.assertEqual(len(confirmed), 2)
        self.assertEqual(
            {item["source_path"] for item in confirmed},
            {
                "05_assets/M00/M00-L02/M00-L02-A01.docx",
                "05_assets/M00/M00-L02/M00-L02-A02.png",
            },
        )
        for item in confirmed:
            self.assertTrue(item["url"].startswith("https://stepik.org/media/attachments/lesson/2591710/"))
            self.assertEqual(item["binding_scope"], "golden-read-only-live-observation")

    def test_non_golden_visuals_use_future_transactional_materialization_routes(self) -> None:
        report = self._assess()
        materialized = {
            item["source_path"]: item["mode"]
            for item in report["resolutions"]
            if item["materialization_required_at_write"]
        }
        self.assertEqual(
            materialized,
            {
                "05_assets/M03/M03-L02/M03-L02-A03-alice.png": "stepik-image-upload",
                "05_assets/M03/M03-L02/M03-L02-A03.png": "stepik-image-upload",
                "05_assets/M04/M04-L02/M04-L02-A02.svg": "rasterize-png-stepik-image",
                "05_assets/M05/M05-L01/M05-L01-A02.svg": "rasterize-png-stepik-image",
            },
        )

    def test_topology_drift_fails_closed(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["lessons"]["M08-L01"]["learner_links"].clear()
        with self.assertRaisesRegex(AssetResolutionError, "asset topology drift"):
            self._assess(inventory=inventory)

    def test_stale_override_fails_closed(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["source_overrides"]["05_assets/DOES-NOT-EXIST.txt"] = {
            "mode": "download-url-required"
        }
        with self.assertRaisesRegex(AssetResolutionError, "stale source_overrides"):
            self._assess(policy=policy)

    def test_confirmed_url_hash_drift_fails_closed(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        links = inventory["lessons"]["M00-L02"]["learner_links"]
        target = next(
            item for item in links
            if item["source_path"] == "05_assets/M00/M00-L02/M00-L02-A01.docx"
        )
        target["sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(AssetResolutionError, "confirmed URL source hash устарел"):
            self._assess(inventory=inventory)

    def test_unapproved_extension_route_fails_closed(self) -> None:
        policy = copy.deepcopy(self.policy)
        del policy["source_overrides"]["05_assets/M04/M04-L01/M04-L01-A01.txt"]
        with self.assertRaisesRegex(AssetResolutionError, "Нет утверждённого asset route"):
            self._assess(policy=policy)

    def test_wrong_course_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssetResolutionError, "предназначен для course_id"):
            assess_asset_publication(
                repo_root=self.repo_root,
                inventory=self.inventory,
                policy=self.policy,
                course_id=123,
            )


if __name__ == "__main__":
    unittest.main()
