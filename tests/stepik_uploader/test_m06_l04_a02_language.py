from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M06/M06-L04/M06-L04-A02.md"


class M06L04A02LanguageTests(unittest.TestCase):
    def test_asset_hides_internal_id_and_uses_plain_material_language(self) -> None:
        text = ASSET.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Дополнительный материал для учебной задачи"))
        self.assertNotIn("M06-L04-A02", text)
        self.assertNotIn("контролируемый исходный материал", text)
        self.assertIn("Других сведений в нём нет.", text)


if __name__ == "__main__":
    unittest.main()
