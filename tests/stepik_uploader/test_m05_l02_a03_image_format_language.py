from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "05_assets/M05/M05-L02/M05-L02-A03.md"


class M05L02A03ImageFormatLanguageTests(unittest.TestCase):
    def test_asset_names_image_file_before_format_examples(self) -> None:
        text = ASSET.read_text(encoding="utf-8")

        # Специальные названия форматов необязательны, если ученик
        # видит понятный объект действия: свою ранее сохранённую картинку.
        self.assertIn("Выберите **именно ту картинку, которую только что сохранили**", text)
        self.assertIn("значок добавления файла", text)
        self.assertIn("**«Проба — исходная»**", text)
        self.assertIn("**«Проба — изменённая»**", text)
        self.assertIn("Откройте оба файла и сравните", text)
        self.assertIn("а не попросить ИИ нарисовать с нуля похожую", text)
        self.assertNotIn("Сохраните результат так, чтобы потом снова найти его на устройстве", text)
        self.assertNotIn("как обычный JPEG/PNG", text)


if __name__ == "__main__":
    unittest.main()
