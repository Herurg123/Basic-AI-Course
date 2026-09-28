from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M06/M06-L04/M06-L04-A03.md"


class M06L04A03LanguageTests(unittest.TestCase):
    def test_asset_asks_for_observable_result_without_trace_jargon(self) -> None:
        text = ASSET.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Проверьте, что действие действительно выполнено"))
        self.assertIn("Что у вас сохранилось после выполненного действия?", text)
        self.assertIn("не подтверждает, что результат действительно был применён", text)
        self.assertNotIn("След фактического применения", text)
        self.assertNotIn("безопасный след выполненного действия", text)
        self.assertNotIn("следом применения", text)


if __name__ == "__main__":
    unittest.main()
