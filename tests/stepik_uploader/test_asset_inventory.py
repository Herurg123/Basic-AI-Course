from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.canonical import build_structural_manifest


class AssetInventoryTests(unittest.TestCase):
    def test_real_course_asset_sources_are_hashable_and_present(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="test")
        inventory = build_asset_inventory(repo_root, manifest)
        self.assertEqual(inventory["missing_files"], [])
        self.assertEqual(len(inventory["lessons"]), 21)
        for lesson in inventory["lessons"].values():
            for file_record in lesson["physical_files"]:
                self.assertTrue(file_record["sha256"].startswith("sha256:"))
                self.assertGreater(file_record["size_bytes"], 0)
            for link_record in lesson["learner_links"]:
                self.assertTrue(link_record["exists"])
                self.assertTrue(link_record["requires_stepik_url_or_inline"])

    def test_changed_file_hash_changes_without_url_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_dir = root / "04_course/M00/M00-L03"
            asset_dir = root / "05_assets/M00/M00-L03"
            lesson_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            lesson = lesson_dir / "lesson.md"
            asset = asset_dir / "M00-L03-A01.md"
            lesson.write_text(
                "# Test\n\n[asset](../../../05_assets/M00/M00-L03/M00-L03-A01.md)\n",
                encoding="utf-8",
            )
            asset.write_text("one", encoding="utf-8")
            manifest = {
                "modules": [
                    {
                        "canonical_id": "M00",
                        "lessons": [
                            {
                                "canonical_id": "M00-L03",
                                "source_git_path": "04_course/M00/M00-L03/lesson.md",
                                "asset_ids": ["M00-L03-A01"],
                            }
                        ],
                    }
                ]
            }
            first = build_asset_inventory(root, manifest)
            first_hash = first["lessons"]["M00-L03"]["physical_files"][0]["sha256"]
            asset.write_text("two", encoding="utf-8")
            second = build_asset_inventory(root, manifest)
            second_hash = second["lessons"]["M00-L03"]["physical_files"][0]["sha256"]
            self.assertNotEqual(first_hash, second_hash)

    def test_cross_lesson_asset_id_resolves_to_owning_lesson_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson_dir = root / "04_course/M00/M00-L02"
            asset_dir = root / "05_assets/M00/M00-L03"
            lesson_dir.mkdir(parents=True)
            asset_dir.mkdir(parents=True)
            lesson = lesson_dir / "lesson.md"
            asset = asset_dir / "M00-L03-A02.md"
            lesson.write_text(
                "# Test\n\n[help](../../../05_assets/M00/M00-L03/M00-L03-A02.md)\n",
                encoding="utf-8",
            )
            asset.write_text("shared help", encoding="utf-8")
            manifest = {
                "modules": [
                    {
                        "canonical_id": "M00",
                        "lessons": [
                            {
                                "canonical_id": "M00-L02",
                                "source_git_path": "04_course/M00/M00-L02/lesson.md",
                                "asset_ids": ["M00-L03-A02"],
                            }
                        ],
                    }
                ]
            }
            inventory = build_asset_inventory(root, manifest)
            self.assertEqual(inventory["missing_files"], [])
            record = inventory["lessons"]["M00-L02"]["physical_files"][0]
            self.assertEqual(record["asset_id"], "M00-L03-A02")
            self.assertEqual(record["source_path"], "05_assets/M00/M00-L03/M00-L03-A02.md")


if __name__ == "__main__":
    unittest.main()
