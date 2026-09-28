from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M08/M08-L01/M08-L01-A01.md"


class M08L01A01LanguageTests(unittest.TestCase):
    def test_card_hides_internal_id_and_uses_plain_future_task_language(self) -> None:
        text = ASSET.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Карточка следующей задачи"))
        self.assertIn("Что из уже знакомого пригодится", text)
        self.assertIn("обмена данными между сервисами через API", text)
        self.assertNotIn("M08-L01-A01", text)
        self.assertNotIn("рамку размышления", text)
        self.assertNotIn("Что из базы переносится", text)


if __name__ == "__main__":
    unittest.main()
