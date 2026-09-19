from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COURSE = ROOT / "04_course"


class GigaChatAuthWordingTests(unittest.TestCase):
    def test_course_does_not_make_gigachat_login_universally_mandatory(self) -> None:
        prohibited = (
            re.compile(r"GigaChat[^\n]*после обычного входа", re.IGNORECASE),
            re.compile(r"авторизованн\w*\s+GigaChat", re.IGNORECASE),
            re.compile(r"GigaChat[^\n]*через\s+Сбер\s*ID\s*/\s*телефон", re.IGNORECASE),
        )
        offenders: list[str] = []
        active_files = [
            path
            for path in COURSE.rglob("*.md")
            if path.name in {"lesson.md", "stepik-plan.md", "lesson-card.md"}
        ]
        for path in sorted(active_files):
            text = path.read_text(encoding="utf-8")
            for pattern in prohibited:
                if pattern.search(text):
                    offenders.append(str(path.relative_to(ROOT)))
                    break
        self.assertEqual(offenders, [])

    def test_service_matrix_points_to_conditional_auth_route(self) -> None:
        readme = (ROOT / "01_architecture/service-matrix/README.md").read_text(encoding="utf-8")
        current = (ROOT / "01_architecture/service-matrix/service-matrix-v1.2.md").read_text(encoding="utf-8")
        self.assertIn("service-matrix-v1.2.md", readme)
        self.assertIn("Если сервис попросит войти для этого действия", current)
        self.assertIn("Попробовать GigaChat без входа", current)


if __name__ == "__main__":
    unittest.main()
