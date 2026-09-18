from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .rendering import render_markdown

TEST_LESSON_ID = "M02-L01"
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
H2_RE = re.compile(r"^##\s+(.+?)\s*$")


class ContentCompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompiledStep:
    position: int
    block_name: str
    text: str
    source: dict[str, Any]
    source_git_paths: tuple[str, ...]

    def block(self) -> dict[str, Any]:
        return {"name": self.block_name, "text": self.text, "source": dict(self.source)}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContentCompileError(f"Не найден production-файл: {path}") from exc


def _drop_h1(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[index + 1 :]).strip()
    raise ContentCompileError("В learner-facing Markdown отсутствует H1")


def _split_h2(markdown_text: str) -> tuple[str, dict[str, str]]:
    text = _drop_h1(markdown_text)
    intro_lines: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = H2_RE.match(line)
        if match:
            current = match.group(1).strip()
            if current in sections:
                raise ContentCompileError(f"Повторяющийся H2: {current}")
            sections[current] = []
            continue
        if current is None:
            intro_lines.append(line)
        else:
            sections[current].append(line)
    return "\n".join(intro_lines).strip(), {key: "\n".join(value).strip() for key, value in sections.items()}


def _without_comments(markdown_text: str) -> str:
    return COMMENT_RE.sub("", markdown_text).strip()


def _render(markdown_text: str) -> str:
    cleaned = _without_comments(markdown_text)
    if "../../../05_assets/" in cleaned:
        raise ContentCompileError("В compiled step осталась unresolved repo-relative asset link")
    return render_markdown(cleaned, asset_url_map={}).strip()


def _section(sections: dict[str, str], heading: str) -> str:
    try:
        return sections[heading]
    except KeyError as exc:
        raise ContentCompileError(f"В lesson.md отсутствует ожидаемый H2 «{heading}»") from exc


def _asset_section(sections: dict[str, str], heading: str) -> str:
    body = _section(sections, heading)
    return re.sub(r"(?m)^---\s*$", "", body).strip()


def _tail_from(text: str, marker: str) -> str:
    index = text.find(marker)
    if index < 0:
        raise ContentCompileError(f"Не найден обязательный marker для production adaptation: {marker}")
    return text[index:].strip()


def compile_test_lesson(
    repo_root: Path,
    *,
    free_answer_source: dict[str, Any],
    lesson_id: str = TEST_LESSON_ID,
) -> list[CompiledStep]:
    """Компилирует только первый write-test lesson. Остальные уроки этой фазой не поддерживаются."""
    if lesson_id != TEST_LESSON_ID:
        raise ContentCompileError(
            f"content-test-one поддерживает только {TEST_LESSON_ID}; получено {lesson_id}"
        )
    if free_answer_source != {
        "is_attachments_enabled": False,
        "is_html_enabled": True,
        "manual_scoring": False,
    }:
        raise ContentCompileError("free-answer source не совпадает с подтверждённым Stepik platform profile")

    repo_root = repo_root.resolve()
    lesson_path = repo_root / "04_course/M02/M02-L01/lesson.md"
    asset_path = repo_root / "05_assets/M02/M02-L01/M02-L01-A01.md"
    lesson_text = _read(lesson_path)
    asset_text = _read(asset_path)
    intro, lesson_sections = _split_h2(lesson_text)
    _asset_intro, asset_sections = _split_h2(asset_text)

    expected_headings = {
        "Первое действие",
        "Что сейчас изменилось",
        "Вторая ситуация",
        "Проверка урока",
        "Если основной маршрут не работает",
        "Итог",
    }
    if set(lesson_sections) != expected_headings:
        missing = sorted(expected_headings - set(lesson_sections))
        extra = sorted(set(lesson_sections) - expected_headings)
        raise ContentCompileError(
            f"M02-L01 H2 shape drifted; missing={missing}, extra={extra}"
        )

    first_asset_heading = "Ситуация 1 — с большей поддержкой"
    second_asset_heading = "Ситуация 2 — с меньшей поддержкой"
    if first_asset_heading not in asset_sections or second_asset_heading not in asset_sections:
        raise ContentCompileError("M02-L01-A01 больше не содержит две ожидаемые ситуации")

    first_tail = _tail_from(_section(lesson_sections, "Первое действие"), "Откройте [Алису AI]")
    second_tail = _tail_from(_section(lesson_sections, "Вторая ситуация"), "После этого отправьте")

    step_markdown = [
        intro,
        "\n\n".join(
            [
                "**Первое действие**",
                "Используйте первую учебную ситуацию ниже.",
                f"**{first_asset_heading}**",
                _asset_section(asset_sections, first_asset_heading),
                first_tail,
            ]
        ),
        "\n\n".join(["**Что сейчас изменилось**", _section(lesson_sections, "Что сейчас изменилось")]),
        "\n\n".join(
            [
                "**Вторая ситуация**",
                "Теперь используйте вторую учебную ситуацию ниже. Поддержки здесь меньше.",
                f"**{second_asset_heading}**",
                _asset_section(asset_sections, second_asset_heading),
                second_tail,
            ]
        ),
        "\n\n".join(["**Проверка урока**", _section(lesson_sections, "Проверка урока")]),
        "\n\n".join(
            [
                "**Если основной маршрут не работает**",
                _section(lesson_sections, "Если основной маршрут не работает"),
                "**Итог**",
                _section(lesson_sections, "Итог"),
            ]
        ),
    ]
    block_names = ["text", "text", "text", "text", "free-answer", "text"]
    paths = (
        "04_course/M02/M02-L01/lesson.md",
        "05_assets/M02/M02-L01/M02-L01-A01.md",
    )
    result: list[CompiledStep] = []
    for index, (block_name, markdown_text) in enumerate(zip(block_names, step_markdown, strict=True), start=1):
        source = dict(free_answer_source) if block_name == "free-answer" else {}
        result.append(
            CompiledStep(
                position=index,
                block_name=block_name,
                text=_render(markdown_text),
                source=source,
                source_git_paths=paths,
            )
        )
    return result
