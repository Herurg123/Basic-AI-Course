from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
WORKFLOWS = (
    WORKFLOW_DIR / "repository-janitor.yml",
    WORKFLOW_DIR / "stepik-private-release.yml",
    WORKFLOW_DIR / "stepik-uploader.yml",
)

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
DESCRIPTION_RE = re.compile(r"^\\s*description:\\s*['\\\"]?(.*?)['\\\"]?\\s*$")
TOP_NAME_RE = re.compile(r"^name:\\s*(.+?)\\s*$", re.MULTILINE)

BANNED_OWNER_FACING_PHRASES = (
    "Stepik private course release",
    "- confirm_write:",
    "- source SHA:",
    "initial targets:",
    "refresh targets:",
    "recovery targets:",
    "course-page pending:",
    "committed lessons:",
    "final machine state:",
    "Offline private-release tests",
    "Sync complete private Stepik course",
    "Read-only Stepik",
    "Repository Janitor",
    "**Default branch:**",
)

CONTROLLED_ERROR_PATTERNS = (
    re.compile(r"echo\\s+(['\\\"])(.+?)\\1\\s+>&2"),
    re.compile(r"raise SystemExit\\((?:f)?(['\\\"])(.+?)\\1\\)"),
    re.compile(r"core\\.setFailed\\((?:`|['\\\"])(.+?)(?:`|['\\\"])\\)"),
)


class RussianActionsOutputContractTests(unittest.TestCase):
    def test_all_workflows_have_russian_human_name_and_summary(self) -> None:
        self.assertEqual(len(WORKFLOWS), 3)
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            match = TOP_NAME_RE.search(text)
            self.assertIsNotNone(match, path)
            self.assertRegex(match.group(1), CYRILLIC_RE, path)
            self.assertIn("GITHUB_STEP_SUMMARY", text, path)

    def test_manual_input_descriptions_are_russian(self) -> None:
        for path in WORKFLOWS:
            for line in path.read_text(encoding="utf-8").splitlines():
                match = DESCRIPTION_RE.match(line)
                if not match:
                    continue
                description = match.group(1)
                self.assertRegex(description, CYRILLIC_RE, f"{path}: {description}")

    def test_old_english_owner_facing_labels_do_not_return(self) -> None:
        combined = "\\n".join(path.read_text(encoding="utf-8") for path in WORKFLOWS)
        for phrase in BANNED_OWNER_FACING_PHRASES:
            self.assertNotIn(phrase, combined, phrase)

    def test_controlled_workflow_errors_have_russian_explanation(self) -> None:
        offenders: list[str] = []
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            for pattern in CONTROLLED_ERROR_PATTERNS:
                for match in pattern.finditer(text):
                    message = match.group(match.lastindex or 1)
                    if not CYRILLIC_RE.search(message):
                        offenders.append(f"{path.relative_to(ROOT)}: {message}")
        self.assertEqual(offenders, [])

    def test_failure_summaries_explain_next_action_in_russian(self) -> None:
        private_release = (WORKFLOW_DIR / "stepik-private-release.yml").read_text(encoding="utf-8")
        uploader = (WORKFLOW_DIR / "stepik-uploader.yml").read_text(encoding="utf-8")
        janitor = (WORKFLOW_DIR / "repository-janitor.yml").read_text(encoding="utf-8")

        self.assertIn("### Что делать при ошибке", private_release)
        self.assertIn("### Причина остановки или ошибки", private_release)
        self.assertIn("### Что делать при ошибке", uploader)
        self.assertIn("Дополнительная отметка об ошибке", janitor)

    def test_v16_makes_actions_language_contract_normative(self) -> None:
        readme = (ROOT / "00_governance/project-instructions/README.md").read_text(encoding="utf-8")
        instructions = (
            ROOT / "00_governance/project-instructions/project-instructions-v1.6.md"
        ).read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("project-instructions-v1.6.md", readme)
        self.assertIn("Обязательный русский человекочитаемый слой GitHub Actions", instructions)
        self.assertIn("каждый workflow обязан формировать `GITHUB_STEP_SUMMARY`", instructions)
        self.assertIn("project-instructions v1.6", agents)


if __name__ == "__main__":
    unittest.main()
