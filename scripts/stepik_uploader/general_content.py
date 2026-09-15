from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .canonical import ASSET_RE, parse_stepik_plan

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
    """Разбивает lesson.md на атомарные learner-facing куски без потери текста.

    H2/H3 становятся жирными метками внутри Stepik шага. Exercise/Check comments
    используются только как alignment anchors и learner-facing текстом не являются.
    Заголовок непосредственно перед marker принадлежит marker-шагу.

    Exercise-секция может быть разделена на практику и последующее объяснение, если
    это требует stepik-plan. Check-секция от marker до следующего H2/H3 считается
    атомарной: рубрика/post-action evidence не может частично съехать в recovery.
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
    """Возвращает границы между chunks, на которых нельзя завершать Stepik step."""
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
    """Компилирует canonical learner source в Stepik-step source без live write.

    Результат сохраняет весь learner-facing lesson.md, исключает author-only plan rows
    и оставляет repo-relative assets/links явными для отдельного asset-publication gate.
    """
    if free_answer_source != EXPECTED_FREE_ANSWER_SOURCE:
        raise GeneralContentCompileError(
            "free-answer source не совпадает с подтверждённым golden profile"
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
    for position, (row, span) in enumerate(zip(rows, spans, strict=True), start=1):
        markdown = "\n\n".join(chunk.markdown for chunk in span).strip()
        if not markdown:
            raise GeneralContentCompileError(f"{lesson_id}: пустой compiled learner step {position}")
        block_name = _block_name(row)
        source = dict(free_answer_source) if block_name == "free-answer" else {}
        headings = tuple(chunk.heading for chunk in span if chunk.heading)
        compiled.append(
            CompiledSourceStep(
                position=position,
                block_name=block_name,
                markdown=markdown,
                source=source,
                source_git_paths=source_paths,
                asset_ids=tuple(sorted(set(ASSET_RE.findall(markdown)))),
                exercise_ids=tuple(row.get("exercise_ids", [])),
                check_ids=tuple(row.get("check_ids", [])),
                source_chunk_indexes=tuple(chunk.index for chunk in span),
                source_headings=headings,
                unresolved_repo_links=_repo_links(markdown),
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
