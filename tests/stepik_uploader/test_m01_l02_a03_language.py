from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M01/M01-L02/M01-L02-A03.md"


class M01L02A03LanguageTests(unittest.TestCase):
    def test_asset_uses_plain_learner_facing_headings(self) -> None:
        text = ASSET.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Ещё одна ситуация для проверки"))
        self.assertIn("## Информация о встрече", text)
        self.assertNotIn("Вторая ситуация для переноса", text)
        self.assertNotIn("## Исходник", text)


if __name__ == "__main__":
    unittest.main()
