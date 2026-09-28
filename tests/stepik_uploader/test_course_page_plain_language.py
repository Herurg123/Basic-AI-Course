from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "04_course/stepik/course-page.md"


class StepikCoursePageLanguageTests(unittest.TestCase):
    def test_course_title_is_preserved_and_body_terms_are_explained(self) -> None:
        text = PAGE.read_text(encoding="utf-8")

        self.assertIn("**ИИ с нуля: не коллекция промптов, а инструмент для реальных дел**", text)
        self.assertIn("«идеальных запросов» (промптов)", text)
        self.assertIn("обмена данными между сервисами через API", text)
        self.assertIn("доступные из России напрямую", text)
        self.assertIn("без обязательного использования VPN", text)
        self.assertIn("«идеальный запрос» (промпт)", text)

        self.assertNotIn("Здесь не нужно учить коллекцию «идеальных промптов»", text)
        self.assertNotIn("Программирование, API и техническая подготовка не нужны.", text)
        self.assertNotIn("английский язык, API, зарубежная банковская карта", text)
        self.assertNotIn("доступные из России без обязательного VPN", text)
        self.assertNotIn("искать «идеальный промпт»", text)


if __name__ == "__main__":
    unittest.main()
