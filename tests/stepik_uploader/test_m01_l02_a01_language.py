from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M01/M01-L02/M01-L02-A01.md"


class M01L02A01LanguageTests(unittest.TestCase):
    def test_asset_hides_internal_id_and_uses_plain_language(self) -> None:
        text = ASSET.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Памятка участнику учебной встречи «Практика»"))
        self.assertNotIn("M01-L02-A01", text)
        self.assertNotIn("контролируемый исходник", text)
        self.assertIn("вымышленный учебный материал", text)
        self.assertIn("информацией в исходном тексте", text)


if __name__ == "__main__":
    unittest.main()
