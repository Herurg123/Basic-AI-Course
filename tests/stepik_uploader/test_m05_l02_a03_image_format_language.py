from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M05/M05-L02/M05-L02-A03.md"


class M05L02A03ImageFormatLanguageTests(unittest.TestCase):
    def test_asset_names_image_file_before_format_examples(self) -> None:
        text = ASSET.read_text(encoding="utf-8")

        self.assertIn("как файл изображения, например JPEG или PNG", text)
        self.assertNotIn("как обычный JPEG/PNG", text)


if __name__ == "__main__":
    unittest.main()
