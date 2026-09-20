from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .canonical import ASSET_RE, parse_stepik_plan

# Этот compiler формирует learner-facing body каждого Stepik-шага во всех 21 уроках.
# Любое содержательное изменение файла является глобальным Stepik-impact и должно
# ставить все канонические уроки в PENDING через impact.py.

MARKER_RE = re.compile(
    r"<!--\s*(Exercise|Check)\s*:\s*(M\d{2}-L\d{2}-[EC]\d{2})\s*-->",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
REPO_LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")
FREE_ANSWER_HINTS = (
    "check",
    "рубри",
    "rubric",
    "evidence",
    "reflection",
    "explanation",
    "свободн",
)
EXPECTED_FREE_ANSWER_SOURCE = {
    "is_attachments_enabled": False,
    "is_html_enabled": True,
    "manual_scoring": False,
}
STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "для", "по", "из", "к", "до", "после",
    "если", "или", "не", "это", "как", "что", "у", "а", "но", "же", "при",
    "the", "a", "an", "to", "of", "in", "on", "and", "or", "is", "are",
}
SCORE_EPS = 1e-12


class GeneralContentCompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceChunk:
    index: int
    markdown: str
    heading: str | None
    marker_ids: tuple[str, ...]
    atomic_check_group: str | None = None


@dataclass(frozen=True)
class CompiledSourceStep:
    position: int
    block_name: str
    markdown: str
    source: dict[str, Any]
    source_git_paths: tuple[str, ...]
    asset_ids: tuple[str, ...]
    exercise_ids: tuple[str, ...]
    check_ids: tuple[str, ...]
    source_chunk_indexes: tuple[int, ...]
    source_headings: tuple[str, ...]
    unresolved_repo_links: tuple[str, ...]
    source_markdown: str = ""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GeneralContentCompileError(f"Не найден production-файл: {path}") from exc


def _lesson_paths(repo_root: Path, lesson_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"M\d{2}-L\d{2}", lesson_id):
        raise GeneralContentCompileError(f"Некорректный canonical lesson id: {lesson_id}")
    module_id = lesson_id.split("-", 1)[0]
    lesson_dir = repo_root / "04_course" / module_id / lesson_id
    return lesson_dir / "lesson.md", lesson_dir / "stepik-plan.md"


def _drop_h1(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[index + 1 :]).strip()
    raise GeneralContentCompileError("В learner-facing Markdown отсутствует H1")


def _flush_chunk(
    chunks: list[SourceChunk],
    paragraph_lines: list[str],
    pending_headings: list[str],
    marker_ids: list[str],
    atomic_check_group: str | None,
) -> None:
    if not paragraph_lines and not pending_headings:
        return
    pieces: list[str] = []
    if pending_headings:
        pieces.extend(f"**{heading}**" for heading in pending_headings)
    paragraph = "\n".join(paragraph_lines).strip()
    if paragraph:
        pieces.append(paragraph)
    markdown = "\n\n".join(pieces).strip()
    if not markdown:
        return
    chunks.append(
        SourceChunk(
            index=len(chunks),
            markdown=markdown,
            heading=pending_headings[-1] if pending_headings else None,
            marker_ids=tuple(dict.fromkeys(marker_ids)),
            atomic_check_group=atomic_check_group,
        )
    )


def split_source_chunks(markdown_text: str) -> list[SourceChunk]:
    """Разбивает lesson.md на learner-facing chunks без потери текста.

    H2/H3 становятся жирными метками. Exercise/Check comments используются только
    как production anchors. Заголовок непосредственно перед marker принадлежит
    marker-шагу. Check-секция от marker до следующего H2/H3 атомарна.
    """
    body = _drop_h1(markdown_text)
    chunks: list[SourceChunk] = []
    paragraph_lines: list[str] = []
    pending_headings: list[str] = []
    pending_markers: list[str] = []
    active_check_group: str | None = None
    check_group_counter = 0
    in_fence = False

    def flush() -> None:
        nonlocal paragraph_lines, pending_headings, pending_markers
        _flush_chunk(
            chunks,
            paragraph_lines,
            pending_headings,
            pending_markers,
            active_check_group,
        )
        paragraph_lines = []
        pending_headings = []
        pending_markers = []

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            paragraph_lines.append(line)
            continue

        if not in_fence:
            heading_match = HEADING_RE.match(line)
            if heading_match:
                if paragraph_lines or pending_markers:
                    flush()
                active_check_group = None
                pending_headings.append(heading_match.group(2).strip())
                continue

            marker_matches = list(MARKER_RE.finditer(line))
            if marker_matches:
                if paragraph_lines:
                    flush()
                pending_markers.extend(match.group(2) for match in marker_matches)
                if any(match.group(1).lower() == "check" for match in marker_matches):
                    check_group_counter += 1
                    marker_key = "+".join(match.group(2) for match in marker_matches)
                    active_check_group = f"check-{check_group_counter}:{marker_key}"
                line = MARKER_RE.sub("", line).strip()
                if not line:
                    continue

            line = COMMENT_RE.sub("", line).rstrip()
            if not line.strip():
                if paragraph_lines:
                    flush()
                continue

        paragraph_lines.append(line)

    flush()
    if not chunks:
        raise GeneralContentCompileError("lesson.md не содержит learner-facing body после H1")
    return [
        SourceChunk(
            index=index,
            markdown=chunk.markdown,
            heading=chunk.heading,
            marker_ids=chunk.marker_ids,
            atomic_check_group=chunk.atomic_check_group,
        )
        for index, chunk in enumerate(chunks)
    ]


def _tokens(text: str) -> set[str]:
    result: set[str] = set()
    for token in WORD_RE.findall(text.lower()):
        if token in STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        result.add(token)
    return result


def _row_text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("logical_type", "summary", "material_or_action", "check")
    )


def _row_ids(row: dict[str, Any]) -> set[str]:
    return set(row.get("exercise_ids", [])) | set(row.get("check_ids", []))


def _check_span_is_closed(span: list[SourceChunk]) -> bool:
    """Check section may be preceded by context, but may not absorb a later section."""
    groups = {chunk.atomic_check_group for chunk in span if chunk.atomic_check_group is not None}
    if not groups:
        return True
    if len(groups) != 1:
        return False
    group = next(iter(groups))
    last_group_index = max(
        index for index, chunk in enumerate(span) if chunk.atomic_check_group == group
    )
    return last_group_index == len(span) - 1


def _span_score(
    row: dict[str, Any],
    span: list[SourceChunk],
    *,
    row_index: int,
    row_count: int,
    chunk_count: int,
    required_ids: set[str],
) -> float:
    span_markers = {marker for chunk in span for marker in chunk.marker_ids}
    allowed_ids = _row_ids(row)
    if span_markers - allowed_ids:
        return -math.inf
    if required_ids - span_markers:
        return -math.inf
    if not _check_span_is_closed(span):
        return -math.inf

    plan_tokens = _tokens(_row_text(row))
    source_tokens = _tokens("\n".join(chunk.markdown for chunk in span))
    if plan_tokens and source_tokens:
        overlap = len(plan_tokens & source_tokens)
        lexical = overlap / math.sqrt(len(plan_tokens) * len(source_tokens))
    else:
        lexical = 0.0

    heading_tokens = _tokens(" ".join(chunk.heading or "" for chunk in span))
    logical_tokens = _tokens(str(row.get("logical_type") or ""))
    heading_overlap = len(heading_tokens & logical_tokens)

    marker_bonus = 8.0 * len(span_markers & allowed_ids)
    lexical_bonus = 12.0 * lexical
    heading_bonus = 0.8 * heading_overlap
    source_center = (span[0].index + span[-1].index + 1) / 2.0 / max(chunk_count, 1)
    expected_center = (row_index + 0.5) / max(row_count, 1)
    position_penalty = 0.9 * abs(source_center - expected_center)
    span_penalty = 0.04 * max(0, len(span) - 3) ** 2
    return marker_bonus + lexical_bonus + heading_bonus - position_penalty - span_penalty


def _forbidden_check_cuts(chunks: list[SourceChunk]) -> set[int]:
    """Границы между chunks, на которых нельзя завершать Stepik step."""
    forbidden: set[int] = set()
    for boundary in range(1, len(chunks)):
        left = chunks[boundary - 1].atomic_check_group
        right = chunks[boundary].atomic_check_group
        if left is not None and left == right:
            forbidden.add(boundary)
    return forbidden


def _align_chunks(rows: list[dict[str, Any]], chunks: list[SourceChunk]) -> list[list[SourceChunk]]:
    if len(chunks) < len(rows):
        raise GeneralContentCompileError(
            f"Недостаточно source chunks для learner rows: chunks={len(chunks)}, rows={len(rows)}"
        )

    source_marker_ids = {marker for chunk in chunks for marker in chunk.marker_ids}
    row_id_counts: dict[str, int] = {}
    for row in rows:
        for marker in _row_ids(row):
            row_id_counts[marker] = row_id_counts.get(marker, 0) + 1

    required_by_row: list[set[str]] = []
    for row in rows:
        required_by_row.append(
            {
                marker
                for marker in _row_ids(row)
                if marker in source_marker_ids and row_id_counts.get(marker) == 1
            }
        )

    n = len(rows)
    m = len(chunks)
    forbidden_cuts = _forbidden_check_cuts(chunks)
    neg = -math.inf
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    prev: list[list[int | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best_ways = [[0] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    best_ways[0][0] = 1

    for i in range(n):
        min_end = i + 1
        max_end = m - (n - (i + 1))
        for start in range(i, m):
            if dp[i][start] == neg:
                continue
            for end in range(max(start + 1, min_end), max_end + 1):
                if end in forbidden_cuts:
                    continue
                score = _span_score(
                    rows[i],
                    chunks[start:end],
                    row_index=i,
                    row_count=n,
                    chunk_count=m,
                    required_ids=required_by_row[i],
                )
                if score == neg:
                    continue
                candidate = dp[i][start] + score
                current = dp[i + 1][end]
                if candidate > current + SCORE_EPS:
                    dp[i + 1][end] = candidate
                    prev[i + 1][end] = start
                    best_ways[i + 1][end] = min(2, best_ways[i][start])
                elif abs(candidate - current) <= SCORE_EPS:
                    best_ways[i + 1][end] = min(
                        2,
                        best_ways[i + 1][end] + best_ways[i][start],
                    )

    if dp[n][m] == neg:
        diagnostics = [
            {
                "position": row.get("position"),
                "logical_type": row.get("logical_type"),
                "ids": sorted(_row_ids(row)),
            }
            for row in rows
        ]
        raise GeneralContentCompileError(
            "Не удалось выстроить source-preserving alignment; "
            f"lesson rows={diagnostics}, source_markers={sorted(source_marker_ids)}"
        )
    if best_ways[n][m] != 1:
        raise GeneralContentCompileError(
            "Alignment неоднозначен: найдено несколько одинаково лучших разбиений source chunks; "
            "нужна явная production-граница, автоматический выбор запрещён"
        )

    spans: list[list[SourceChunk]] = []
    end = m
    for i in range(n, 0, -1):
        start = prev[i][end]
        if start is None:
            raise GeneralContentCompileError("Внутренняя ошибка восстановления alignment")
        spans.append(chunks[start:end])
        end = start
    spans.reverse()

    used = [chunk.index for span in spans for chunk in span]
    if used != list(range(m)):
        raise GeneralContentCompileError("Compiler потерял или продублировал source chunk")
    return spans



def _lesson_title(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise GeneralContentCompileError("В learner-facing Markdown отсутствует H1")


def _fallback_step_title(row: dict[str, Any]) -> str:
    logical = str(row.get("logical_type") or "").lower()
    if any(hint in logical for hint in FREE_ANSWER_HINTS):
        return "Проверьте выполненную работу"
    if "recovery" in logical or "повтор" in logical:
        return "Повторите попытку на новой ситуации"
    if "резерв" in logical or "backup" in logical:
        return "Используйте резервный маршрут"
    if row.get("exercise_ids"):
        return "Выполните практику"
    return "Разберитесь с текущим шагом"


def _purpose_for_step(row: dict[str, Any], *, block_name: str) -> str:
    logical = str(row.get("logical_type") or "").lower()
    if block_name == "free-answer":
        return "Проверьте уже выполненную работу и зафиксируйте результат, не меняя её задним числом."
    if "recovery" in logical or "повтор" in logical:
        return "Получите новую самостоятельную попытку, если предыдущая стала тренировочной."
    if "резерв" in logical or "backup" in logical:
        return "Сохраните возможность продолжить урок, если основной маршрут временно недоступен."
    if any(word in logical for word in ("применение", "внешнее действие", "application")):
        return "Доведите уже полученный результат до небольшого реального применения."
    if row.get("exercise_ids"):
        return "Выполните следующий учебный шаг и получите результат, с которым можно продолжить."
    return "Разберитесь, что важно учесть перед следующим действием."


def _place_for_step(source_markdown: str, row: dict[str, Any], *, block_name: str) -> tuple[str, bool]:
    material = str(row.get("material_or_action") or "")
    lower = (source_markdown + "\n" + material).lower()
    places: list[str] = []
    outside_stepik = False

    if "alice.yandex.ru" in lower or "алиса ai" in lower:
        if any(phrase in lower for phrase in ("тот же чат", "продолжите диалог", "вернитесь в чат")):
            places.append("в том же чате Алисы AI")
        else:
            places.append("в Алисе AI")
        outside_stepik = True

    if "giga.chat" in lower and "alice.yandex.ru" not in lower:
        places.append("в GigaChat")
        outside_stepik = True

    if ("чат" in material.lower() or "ai" in material.lower()) and not places:
        places.append("в ИИ-чате")
        outside_stepik = True

    if "калькулятор" in lower:
        places.append("в калькуляторе")
        outside_stepik = True

    if any(word in lower for word in ("браузер", "исходник", "источник")) and "stepik" not in lower:
        places.append("в браузере или открытом исходном материале")
        outside_stepik = True

    if any(word in lower for word in ("заметк", "текстовый файл")) and not places:
        places.append("в своей заметке или текстовом файле")
        outside_stepik = True

    if block_name == "free-answer" and not places:
        places.append("здесь, в Stepik, по уже выполненной работе")

    if not places:
        places.append("здесь, в Stepik")

    unique = list(dict.fromkeys(places))
    return "; ".join(unique), outside_stepik


def _done_for_step(source_markdown: str, row: dict[str, Any], *, block_name: str) -> str:
    lower = source_markdown.lower()
    if block_name == "free-answer":
        return "вы ответили на вопросы шага по уже выполненной работе и зафиксировали результат."
    if row.get("exercise_ids"):
        if "сохран" in lower:
            return "действие выполнено и нужный результат сохранён так, как указано ниже."
        return "вы выполнили действие ниже и получили результат, с которым можно продолжить."
    return "вам понятен смысл этого шага и вы готовы перейти к следующему действию."


def _strip_leading_source_heading(source_markdown: str, heading: str | None) -> str:
    if not heading:
        return source_markdown
    prefix = f"**{heading}**"
    if source_markdown.startswith(prefix):
        return source_markdown[len(prefix):].lstrip()
    return source_markdown


def _frame_step_card(
    *,
    lesson_title: str,
    position: int,
    total: int,
    row: dict[str, Any],
    block_name: str,
    source_markdown: str,
    headings: tuple[str, ...],
) -> str:
    base_title = lesson_title if position == 1 else (headings[0] if headings else _fallback_step_title(row))
    body = _strip_leading_source_heading(source_markdown, headings[0] if headings else None)
    place, outside_stepik = _place_for_step(source_markdown, row, block_name=block_name)

    parts = [
        f"## Шаг {position} из {total}. {base_title}",
        f"**Зачем:** {_purpose_for_step(row, block_name=block_name)}",
        f"**Где и с чем:** {place}. Используйте материалы и результаты, которые названы ниже.",
        "**Что сделать**",
        body,
        f"**Готово, если:** {_done_for_step(source_markdown, row, block_name=block_name)}",
    ]

    if "сохран" in source_markdown.lower():
        parts.append(
            "**Что сохранить:** сохраните только то, что прямо требуется в задании ниже; "
            "дополнительный отчёт не нужен."
        )

    if outside_stepik:
        if position < total:
            parts.append(
                "**Что дальше:** после выполнения вернитесь в Stepik и переходите к следующему шагу."
            )
        else:
            parts.append(
                "**Что дальше:** после выполнения вернитесь в Stepik и завершите этот урок."
            )

    return "\n\n".join(part for part in parts if part).strip()



def _block_name(row: dict[str, Any]) -> str:
    logical = str(row.get("logical_type") or "").lower()
    if any(hint in logical for hint in FREE_ANSWER_HINTS):
        return "free-answer"
    return "text"


def _repo_links(markdown_text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(1).strip() for match in REPO_LINK_RE.finditer(markdown_text)))


def compile_lesson_source(
    repo_root: Path,
    *,
    free_answer_source: dict[str, Any],
    lesson_id: str,
) -> list[CompiledSourceStep]:
    """Компилирует canonical learner source в Stepik-step source без live write."""
    if free_answer_source != EXPECTED_FREE_ANSWER_SOURCE:
        raise GeneralContentCompileError(
            "free-answer source не совпадает с подтверждённым Stepik platform profile"
        )

    repo_root = repo_root.resolve()
    lesson_path, plan_path = _lesson_paths(repo_root, lesson_id)
    lesson_text = _read(lesson_path)
    plan_text = _read(plan_path)
    rows = [
        row
        for row in parse_stepik_plan(plan_text, lesson_id=lesson_id, path=plan_path)
        if not row.get("author_only")
    ]
    if not rows:
        raise GeneralContentCompileError(f"{lesson_id}: после author-only фильтра нет learner rows")

    chunks = split_source_chunks(lesson_text)
    spans = _align_chunks(rows, chunks)
    source_paths = (
        str(lesson_path.relative_to(repo_root)).replace("\\", "/"),
        str(plan_path.relative_to(repo_root)).replace("\\", "/"),
    )

    compiled: list[CompiledSourceStep] = []
    title = _lesson_title(lesson_text)
    total = len(rows)
    for position, (row, span) in enumerate(zip(rows, spans, strict=True), start=1):
        source_markdown = "\n\n".join(chunk.markdown for chunk in span).strip()
        if not source_markdown:
            raise GeneralContentCompileError(f"{lesson_id}: пустой compiled learner step {position}")
        block_name = _block_name(row)
        source = dict(free_answer_source) if block_name == "free-answer" else {}
        headings = tuple(chunk.heading for chunk in span if chunk.heading)
        markdown = _frame_step_card(
            lesson_title=title,
            position=position,
            total=total,
            row=row,
            block_name=block_name,
            source_markdown=source_markdown,
            headings=headings,
        )
        compiled.append(
            CompiledSourceStep(
                position=position,
                block_name=block_name,
                markdown=markdown,
                source=source,
                source_git_paths=source_paths,
                asset_ids=tuple(sorted(set(ASSET_RE.findall(source_markdown)))),
                exercise_ids=tuple(row.get("exercise_ids", [])),
                check_ids=tuple(row.get("check_ids", [])),
                source_chunk_indexes=tuple(chunk.index for chunk in span),
                source_headings=headings,
                unresolved_repo_links=_repo_links(source_markdown),
                source_markdown=source_markdown,
            )
        )

    return compiled


def compile_all_lesson_sources(
    repo_root: Path,
    *,
    free_answer_source: dict[str, Any],
    lesson_ids: Iterable[str],
) -> dict[str, list[CompiledSourceStep]]:
    return {
        lesson_id: compile_lesson_source(
            repo_root,
            free_answer_source=free_answer_source,
            lesson_id=lesson_id,
        )
        for lesson_id in lesson_ids
    }
