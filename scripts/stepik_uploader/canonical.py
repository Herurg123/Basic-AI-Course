from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ASSET_RE = re.compile(r"\bM\d{2}-L\d{2}-A\d{2}\b")
EXERCISE_RE = re.compile(r"\bM\d{2}-L\d{2}-E\d{2}\b")
CHECK_RE = re.compile(r"\bM\d{2}-L\d{2}-C\d{2}\b")
MODULE_HEADER_RE = re.compile(r"^###\s+(M\d{2})\.\s+(.+?)\s*$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
LESSON_DIR_RE = re.compile(r"^M\d{2}-L\d{2}$")
MODULE_DIR_RE = re.compile(r"^M\d{2}$")
RENDER_CONTRACT_TOKEN_RE = re.compile(r"learner-render-contract", re.IGNORECASE)

AUTHORED_SEMANTIC_RENDER_CONTRACT = "authored-semantic-v1"
AUTHORED_SEMANTIC_MARKER = "<!-- learner-render-contract: authored-semantic-v1 -->"
SEMANTIC_TYPES = frozenset(
    {
        "EXPLANATION",
        "DEMONSTRATION",
        "GUIDED_ACTION",
        "INDEPENDENT_PRACTICE",
        "CHECK",
        "REFLECTION",
        "NAVIGATION",
        "TECHNICAL_SUPPORT",
        "RECOVERY",
        "COMPOSITE",
    }
)

SENSITIVE_LESSONS = {
    "M03-L02",
    "M04-L02",
    "M05-L02",
    "M06-L04",
    "M07-L01",
    "M07-L02",
}


class CanonicalBuildError(RuntimeError):
    pass


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CanonicalBuildError(f"Не найден канонический файл: {path}") from exc


def parse_module_titles(course_readme: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in course_readme.splitlines():
        match = MODULE_HEADER_RE.match(line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def parse_lesson_title(lesson_markdown: str, *, path: Path) -> str:
    for line in lesson_markdown.splitlines():
        match = H1_RE.match(line)
        if match:
            return match.group(1).strip()
    raise CanonicalBuildError(f"В {path} отсутствует H1 заголовок урока")


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def parse_learner_render_contract(plan_markdown: str, *, path: Path) -> str | None:
    """Возвращает opt-in render contract и fail-closed проверяет его синтаксис."""
    lines = plan_markdown.splitlines()
    candidates = [
        (index, line.strip())
        for index, line in enumerate(lines)
        if RENDER_CONTRACT_TOKEN_RE.search(line)
    ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise CanonicalBuildError(
            f"В {path} learner render contract должен быть указан ровно один раз"
        )

    marker_index, marker = candidates[0]
    if marker != AUTHORED_SEMANTIC_MARKER:
        raise CanonicalBuildError(
            f"В {path} допустим только точный marker {AUTHORED_SEMANTIC_MARKER}"
        )

    header_index: int | None = None
    for index, line in enumerate(lines):
        cells = _split_table_row(line)
        if cells and cells[0] in {"№", "#"} and len(cells) >= 5:
            header_index = index
            break
    if header_index is not None and marker_index >= header_index:
        raise CanonicalBuildError(
            f"В {path} learner render contract должен находиться до таблицы Stepik-плана"
        )
    return AUTHORED_SEMANTIC_RENDER_CONTRACT


def _is_author_only(*, logical_type: str, summary: str, material: str, check: str) -> bool:
    """Определяет только явно служебные строки, не путая их с learner-facing словом «авторский».

    Раньше поиск любого фрагмента «авторск» по всей строке ошибочно скрывал, например,
    learner-facing «авторские версии» в M05-L01. Fail-closed остаётся для явных
    author-only/author rubric/ключей проверяющего, но обычное упоминание автора больше
    не превращает ученический шаг в служебный.
    """
    logical_lower = logical_type.lower()
    combined_lower = " ".join((summary, material, check)).lower()
    return (
        "author-only" in logical_lower
        or "author only" in logical_lower
        or "ключ проверяющего" in combined_lower
        or "author rubric" in combined_lower
        or "авторская рубрик" in combined_lower
        or "авторский ключ" in combined_lower
    )


def parse_stepik_plan(plan_markdown: str, *, lesson_id: str, path: Path) -> list[dict[str, Any]]:
    lines = plan_markdown.splitlines()
    header_index: int | None = None
    for index, line in enumerate(lines):
        cells = _split_table_row(line)
        if cells and cells[0] in {"№", "#"} and len(cells) >= 5:
            header_index = index
            break
    if header_index is None:
        raise CanonicalBuildError(f"В {path} не найдена таблица Stepik-плана")

    render_contract = parse_learner_render_contract(plan_markdown, path=path)
    header_cells = _split_table_row(lines[header_index])
    semantic_indexes = [
        index for index, cell in enumerate(header_cells) if cell == "Semantic type"
    ]
    if render_contract == AUTHORED_SEMANTIC_RENDER_CONTRACT:
        if len(semantic_indexes) != 1:
            raise CanonicalBuildError(
                f"В {path} authored-semantic-v1 требует ровно одну колонку Semantic type"
            )
        semantic_index = semantic_indexes[0]
    else:
        if semantic_indexes:
            raise CanonicalBuildError(
                f"В {path} колонка Semantic type допустима только с {AUTHORED_SEMANTIC_MARKER}"
            )
        semantic_index = None

    rows: list[dict[str, Any]] = []
    for line in lines[header_index + 2 :]:
        cells = _split_table_row(line)
        if not cells:
            if rows:
                break
            continue
        if len(cells) < 5:
            raise CanonicalBuildError(f"В {path} строка таблицы содержит меньше 5 колонок: {line}")
        if semantic_index is not None:
            if semantic_index >= len(cells):
                raise CanonicalBuildError(
                    f"В {path} строка authored-semantic-v1 не содержит Semantic type: {line}"
                )
            semantic_type = cells[semantic_index]
            if semantic_type not in SEMANTIC_TYPES:
                allowed = ", ".join(sorted(SEMANTIC_TYPES))
                raise CanonicalBuildError(
                    f"В {path} неизвестный Semantic type {semantic_type!r}; допустимы: {allowed}"
                )
        try:
            position = int(cells[0])
        except ValueError as exc:
            raise CanonicalBuildError(f"В {path} некорректная позиция шага: {cells[0]}") from exc
        logical_type, summary, material, check = cells[1], cells[2], cells[3], cells[4]
        combined = " ".join((logical_type, summary, material, check))
        lower = combined.lower()
        author_only = _is_author_only(
            logical_type=logical_type,
            summary=summary,
            material=material,
            check=check,
        )
        independent = lesson_id in SENSITIVE_LESSONS or any(
            marker in lower
            for marker in (
                "independent",
                "самостоятель",
                "post-action",
                "learner contract",
                "advisory",
                "recovery",
                "temporal",
            )
        )
        rows.append(
            {
                "position": position,
                "logical_type": logical_type,
                "summary": summary,
                "material_or_action": material,
                "check": check,
                "asset_ids": sorted(set(ASSET_RE.findall(combined))),
                "exercise_ids": sorted(set(EXERCISE_RE.findall(combined))),
                "check_ids": sorted(set(CHECK_RE.findall(combined))),
                "author_only": author_only,
                "independence_sensitive": independent,
                "f1_sensitive": lesson_id == "M07-L02",
                # Structural manifest намеренно не угадывает platform rendering.
                "stepik_block_type": None,
                "learner_body": None,
                "rendering_status": "structural-only",
            }
        )

    if not rows:
        raise CanonicalBuildError(f"В {path} таблица Stepik-плана пуста")
    expected = list(range(1, len(rows) + 1))
    actual = [row["position"] for row in rows]
    if actual != expected:
        raise CanonicalBuildError(f"В {path} позиции шагов должны быть последовательными 1..N, получено {actual}")
    if len(rows) > 16:
        raise CanonicalBuildError(
            f"{lesson_id}: {len(rows)} логических шагов превышают лимит Stepik 16 шагов на урок"
        )
    return rows


def _lesson_asset_ids(lesson_markdown: str, step_rows: list[dict[str, Any]]) -> list[str]:
    ids = set(ASSET_RE.findall(lesson_markdown))
    for row in step_rows:
        ids.update(row["asset_ids"])
    return sorted(ids)


def build_structural_manifest(repo_root: Path, *, source_sha: str = "unknown", strict_shape: bool = True) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    course_dir = repo_root / "04_course"
    course_readme = _read(course_dir / "README.md")
    module_titles = parse_module_titles(course_readme)

    modules: list[dict[str, Any]] = []
    lesson_count = 0
    for module_dir in sorted(
        (path for path in course_dir.iterdir() if path.is_dir() and MODULE_DIR_RE.match(path.name)),
        key=lambda path: path.name,
    ):
        module_id = module_dir.name
        if module_id not in module_titles:
            raise CanonicalBuildError(f"В 04_course/README.md не найден канонический заголовок {module_id}")
        lessons: list[dict[str, Any]] = []
        for lesson_dir in sorted(
            (path for path in module_dir.iterdir() if path.is_dir() and LESSON_DIR_RE.match(path.name)),
            key=lambda path: path.name,
        ):
            lesson_id = lesson_dir.name
            lesson_path = lesson_dir / "lesson.md"
            plan_path = lesson_dir / "stepik-plan.md"
            lesson_text = _read(lesson_path)
            plan_text = _read(plan_path)
            title = parse_lesson_title(lesson_text, path=lesson_path)
            rows = parse_stepik_plan(plan_text, lesson_id=lesson_id, path=plan_path)
            lessons.append(
                {
                    "canonical_id": lesson_id,
                    "title": title,
                    "position": len(lessons) + 1,
                    "source_git_path": str(lesson_path.relative_to(repo_root)).replace("\\", "/"),
                    "stepik_plan_git_path": str(plan_path.relative_to(repo_root)).replace("\\", "/"),
                    "asset_ids": _lesson_asset_ids(lesson_text, rows),
                    "exercise_ids": sorted(set(EXERCISE_RE.findall(lesson_text + "\n" + plan_text))),
                    "check_ids": sorted(set(CHECK_RE.findall(lesson_text + "\n" + plan_text))),
                    "independence_sensitive": lesson_id in SENSITIVE_LESSONS,
                    "f1_sensitive": lesson_id == "M07-L02",
                    "write_ready": False,
                    "write_blocker": "requires-live-write-gates",
                    "steps": rows,
                }
            )
            lesson_count += 1
        modules.append(
            {
                "canonical_id": module_id,
                "title": module_titles[module_id],
                "position": len(modules) + 1,
                "lessons": lessons,
            }
        )

    if strict_shape:
        if len(modules) != 9:
            raise CanonicalBuildError(f"Ожидалось 9 модулей M00–M08, найдено {len(modules)}")
        if lesson_count != 21:
            raise CanonicalBuildError(f"Ожидался 21 канонический урок, найдено {lesson_count}")
        expected_modules = [f"M{index:02d}" for index in range(9)]
        actual_modules = [module["canonical_id"] for module in modules]
        if actual_modules != expected_modules:
            raise CanonicalBuildError(
                f"Канонические модули должны быть M00–M08 без разрывов, найдено {actual_modules}"
            )

    return {
        "schema_version": "1.1-structural",
        "source_sha": source_sha,
        "phase": "structural",
        "write_enabled": False,
        "global_blockers": ["requires-live-write-gates"],
        "modules": modules,
        "summary": {
            "modules": len(modules),
            "lessons": lesson_count,
            "logical_steps": sum(len(lesson["steps"]) for module in modules for lesson in module["lessons"]),
        },
    }
