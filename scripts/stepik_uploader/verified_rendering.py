from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .step_model import RenderedStep
from .general_content import CompiledSourceStep
from .rendering import markdown_to_html

LOCAL_LINK_RE = re.compile(r"\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)")
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
REPO_RELATIVE_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")
INTERNAL_TITLE_PREFIX_RE = re.compile(
    r"^M\d{2}-L\d{2}(?:-[AEC]\d{2}(?:-[A-Za-z0-9_-]+)?)?\s*(?:[—–:]\s*)?"
)
STEPIC_HORIZONTAL_RULE_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
STEPIC_BREAK_RE = re.compile(r"<br\s*/>", re.IGNORECASE)
STEPIC_TEXT_ALIGN_RE = re.compile(r'style="text-align:(left|right|center)"', re.IGNORECASE)
STEPIC_PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
STEPIC_BLOCK_TAG_RE = re.compile(
    r"<(?:p|div|table|thead|tbody|tr|td|th|ul|ol|li|blockquote|pre|hr|h[1-6])\b",
    re.IGNORECASE,
)
STEPIC_HTML_NORMALIZATION_V1 = "stepik-plain-horizontal-rule-strip-v1"
STEPIC_HTML_NORMALIZATION_V2 = "stepik-observed-html-canonicalization-v2"
STEPIC_HTML_NORMALIZATION_V2_LESSONS = frozenset({"M06-L02"})
INLINE_MATERIAL_TOKEN_PREFIX = "STEPIK_INLINE_MATERIAL_"


class VerifiedRenderingError(RuntimeError):
    pass


class MaterializationRequired(VerifiedRenderingError):
    def __init__(self, requirements: list[dict[str, Any]]) -> None:
        self.requirements = requirements
        rendered = ", ".join(sorted({str(item.get("source_path")) for item in requirements}))
        super().__init__(f"Для verified rendering требуется physical materialization: {rendered}")


@dataclass(frozen=True)
class AssetBinding:
    source_path: str
    source_sha256: str
    url: str
    storage: str
    verified: bool = True


@dataclass(frozen=True)
class RenderingPlan:
    lesson_id: str
    rendered_steps: tuple[RenderedStep, ...]
    materialization_requirements: tuple[dict[str, Any], ...]
    dependency_source_paths: tuple[str, ...]

    @property
    def render_ready(self) -> bool:
        return not self.materialization_requirements


def normalize_stepik_html_v1(html: str) -> str:
    """Historical normalization contract used by already-started deployment events.

    Incident #80 proved only one transformation at that time: Stepik removes plain
    horizontal-rule tags. This function is intentionally frozen so an immutable event
    created under v1 can be reconstructed after the production renderer moves forward.
    """
    return STEPIC_HORIZONTAL_RULE_RE.sub("", html or "")


def _split_stepik_multiline_paragraph(match: re.Match[str]) -> str:
    body = match.group(1)
    if "\n" not in body or STEPIC_BREAK_RE.search(body) or STEPIC_BLOCK_TAG_RE.search(body):
        return match.group(0)
    lines = body.splitlines()
    if len(lines) < 2 or any(not line.strip() for line in lines):
        return match.group(0)
    return "\n".join(f"<p>{line.strip()}</p>" for line in lines)


def normalize_stepik_html(html: str) -> str:
    """Apply only HTML canonicalizations observed in Stepik write/read-back evidence.

    The v2 contract extends the frozen v1 rule with three transformations reproduced
    byte-for-byte from the M06-L02 incident in private course 299189:
    - newline-separated inline-only paragraph bodies become separate paragraphs;
    - XHTML-style ``<br />`` becomes ``<br>``;
    - exact table alignment styles receive Stepik's trailing semicolon.

    Broad sanitization remains forbidden. Paragraphs containing block tags or explicit
    ``<br>`` markup are not split, attributed ``<hr>`` tags are preserved, and unrelated
    style attributes are untouched. Production rendering applies this v2 contract only
    to lessons named in ``STEPIC_HTML_NORMALIZATION_V2_LESSONS`` until equivalent live
    evidence exists for another lesson.
    """
    normalized = html or ""
    normalized = STEPIC_PARAGRAPH_RE.sub(_split_stepik_multiline_paragraph, normalized)
    normalized = STEPIC_HORIZONTAL_RULE_RE.sub("", normalized)
    normalized = STEPIC_BREAK_RE.sub("<br>", normalized)
    normalized = STEPIC_TEXT_ALIGN_RE.sub(lambda match: f'style="text-align:{match.group(1).lower()};"', normalized)
    return normalized


def _normalize_repo_path(value: str) -> str:
    path = PurePosixPath(value)
    normalized = str(path)
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise VerifiedRenderingError(f"Недопустимый repo-relative path: {value}")
    return normalized


def _resolve_target(repo_root: Path, link_source_path: str, target: str) -> str:
    source = repo_root / _normalize_repo_path(link_source_path)
    candidate = (source.parent / target).resolve()
    root = repo_root.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise VerifiedRenderingError(f"Local learner link выходит за пределы репозитория: {target}") from exc
    return relative.as_posix()


def _drop_h1(markdown_text: str, *, source_path: str) -> tuple[str, str]:
    match = H1_RE.search(markdown_text)
    if match is None:
        raise VerifiedRenderingError(f"{source_path}: inline Markdown source не содержит H1")
    title = match.group(1).strip()
    body = (markdown_text[: match.start()] + markdown_text[match.end() :]).strip()
    if not body:
        raise VerifiedRenderingError(f"{source_path}: inline Markdown source пуст после H1")
    return title, body


def _practice_material_block(title: str, body: str) -> str:
    """Формирует единый визуальный контейнер для learner-facing материала практики.

    Материал должен визуально отличаться от инструкции ученику даже после удаления
    Stepik обычных <hr>. Для этого используется нативный blockquote, который Stepik
    поддерживает как разрешённый HTML-блок и может адаптировать под тему интерфейса.
    Внутренний Markdown остаётся каноническим и преобразуется общим renderer.
    """
    content = body.strip()
    if not content:
        raise VerifiedRenderingError("Inline material body пуст")
    return (
        "<blockquote>\n\n"
        f"**Материал: {title}**\n\n"
        f"{content}\n\n"
        "</blockquote>"
    )


def _inject_inline_material_blocks(html: str, placements: dict[str, str]) -> str:
    """Insert rendered inline materials immediately after the paragraph/list item that names them."""
    rendered = html
    for token, block_markdown in reversed(list(placements.items())):
        block_html = markdown_to_html(block_markdown).strip()
        token_re = re.escape(token)
        container_match = None
        for tag in ("p", "li"):
            pattern = re.compile(
                rf"<{tag}>(?:(?!</{tag}>).)*{token_re}(?:(?!</{tag}>).)*</{tag}>",
                re.IGNORECASE | re.DOTALL,
            )
            container_match = pattern.search(rendered)
            if container_match is not None:
                break
        if container_match is None:
            if token not in rendered:
                raise VerifiedRenderingError(f"Inline material placement token потерян: {token}")
            rendered = rendered.replace(token, block_html, 1)
            continue
        container = container_match.group(0).replace(token, "")
        rendered = (
            rendered[: container_match.start()]
            + container
            + "\n"
            + block_html
            + rendered[container_match.end() :]
        )
    if INLINE_MATERIAL_TOKEN_PREFIX in rendered:
        raise VerifiedRenderingError("После material placement остался служебный token")
    return rendered


def _humanize_inline_title(title: str, *, source_path: str) -> str:
    """Убирает production ID только из learner-visible заголовка inline-материала.

    Canonical ID остаётся в имени/пути исходного файла и machine metadata. Мы меняем только
    представление H1 при встраивании материала в Stepik, чтобы ученик видел смысловое название,
    а не внутренний идентификатор репозитория.
    """
    human_title = INTERNAL_TITLE_PREFIX_RE.sub("", title, count=1).strip()
    if not human_title:
        raise VerifiedRenderingError(
            f"{source_path}: после удаления production ID у inline H1 не осталось смыслового названия"
        )
    return human_title


def _resolution_index(asset_report: dict[str, Any], *, lesson_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    rows = asset_report.get("resolutions")
    if not isinstance(rows, list):
        raise VerifiedRenderingError("asset publication report не содержит resolutions")
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("lesson") != lesson_id:
            continue
        link_source_path = str(row.get("link_source_path") or "")
        source_path = str(row.get("source_path") or "")
        if not link_source_path or not source_path:
            raise VerifiedRenderingError(f"{lesson_id}: неполная asset resolution row")
        key = (link_source_path, source_path)
        existing = index.get(key)
        if existing is not None and existing != row:
            raise VerifiedRenderingError(f"{lesson_id}: неоднозначная resolution для {key}")
        index[key] = row
    return index


def _binding_index(bindings: Iterable[AssetBinding] | None) -> dict[str, AssetBinding]:
    result: dict[str, AssetBinding] = {}
    for binding in bindings or ():
        if binding.source_path in result and result[binding.source_path] != binding:
            raise VerifiedRenderingError(f"Конфликтующие runtime bindings для {binding.source_path}")
        if not binding.verified:
            raise VerifiedRenderingError(f"Runtime binding не verified: {binding.source_path}")
        if not binding.url.startswith("https://"):
            raise VerifiedRenderingError(f"Runtime binding должен иметь абсолютный https URL: {binding.source_path}")
        result[binding.source_path] = binding
    return result


def _read_utf8(repo_root: Path, source_path: str) -> str:
    path = repo_root / source_path
    if not path.is_file():
        raise VerifiedRenderingError(f"Не найден linked learner source: {source_path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise VerifiedRenderingError(f"{source_path}: inline-source должен быть UTF-8 text") from exc


def _render_local_markdown(
    markdown_text: str,
    *,
    repo_root: Path,
    lesson_id: str,
    link_source_path: str,
    resolution_index: dict[tuple[str, str], dict[str, Any]],
    bindings: dict[str, AssetBinding],
    appended_sources: set[str],
    dependency_sources: set[str],
    requirements: dict[str, dict[str, Any]],
    recursion_stack: tuple[str, ...],
    inline_material_blocks: dict[str, str],
    inline_material_counter: list[int],
) -> str:

    def replace(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        target = match.group(2).strip()
        source_path = _resolve_target(repo_root, link_source_path, target)
        row = resolution_index.get((link_source_path, source_path))
        if row is None:
            raise VerifiedRenderingError(
                f"{lesson_id}: local learner link не имеет asset publication resolution: "
                f"{link_source_path} -> {source_path}"
            )
        if row.get("route_resolved") is not True:
            raise VerifiedRenderingError(f"{lesson_id}: route не resolved для {source_path}")
        expected_sha = str(row.get("source_sha256") or "")
        if not expected_sha.startswith("sha256:"):
            raise VerifiedRenderingError(f"{source_path}: resolution не содержит source SHA-256")
        dependency_sources.add(source_path)
        mode = str(row.get("mode") or "")

        if mode == "inline-source":
            if source_path in recursion_stack:
                cycle = " -> ".join((*recursion_stack, source_path))
                raise VerifiedRenderingError(f"Циклическая inline dependency: {cycle}")
            if source_path not in appended_sources:
                appended_sources.add(source_path)
                raw = _read_utf8(repo_root, source_path)
                title, body = _drop_h1(raw, source_path=source_path)
                title = _humanize_inline_title(title, source_path=source_path)
                nested = _render_local_markdown(
                    body,
                    repo_root=repo_root,
                    lesson_id=lesson_id,
                    link_source_path=source_path,
                    resolution_index=resolution_index,
                    bindings=bindings,
                    appended_sources=appended_sources,
                    dependency_sources=dependency_sources,
                    requirements=requirements,
                    recursion_stack=(*recursion_stack, source_path),
                    inline_material_blocks=inline_material_blocks,
                    inline_material_counter=inline_material_counter,
                )
                token = f"{INLINE_MATERIAL_TOKEN_PREFIX}{inline_material_counter[0]}"
                inline_material_counter[0] += 1
                inline_material_blocks[token] = _practice_material_block(title, nested)
                return f"**{label}** {token}"
            return f"**{label}**"

        if mode == "confirmed-url":
            url = str(row.get("url") or "")
            if not url.startswith("https://"):
                raise VerifiedRenderingError(f"{source_path}: confirmed-url отсутствует или не https")
            return f"[{label}]({url})"

        if mode in {
            "stepik-attachment-upload",
            "stepik-image-upload",
            "rasterize-png-stepik-image",
        }:
            binding = bindings.get(source_path)
            if binding is None:
                requirements[source_path] = {
                    "lesson": lesson_id,
                    "source_path": source_path,
                    "source_sha256": expected_sha,
                    "mode": mode,
                    "derived_format": row.get("derived_format"),
                }
                return f"**{label} (будет доступен после подготовки материала)**"
            if binding.source_sha256 != expected_sha:
                raise VerifiedRenderingError(
                    f"{source_path}: runtime binding относится к другому source SHA-256"
                )
            return f"[{label}]({binding.url})"

        raise VerifiedRenderingError(f"{source_path}: publication mode {mode!r} не поддерживается renderer")

    return LOCAL_LINK_RE.sub(replace, markdown_text)


def build_rendering_plan(
    *,
    repo_root: Path,
    lesson_id: str,
    source_steps: Iterable[CompiledSourceStep],
    asset_report: dict[str, Any],
    bindings: Iterable[AssetBinding] | None = None,
    apply_stepik_html_normalization: bool = True,
) -> RenderingPlan:
    repo_root = repo_root.resolve()
    resolution_index = _resolution_index(asset_report, lesson_id=lesson_id)
    binding_map = _binding_index(bindings)
    rendered_steps: list[RenderedStep] = []
    requirements: dict[str, dict[str, Any]] = {}
    all_dependencies: set[str] = set()

    for source_step in source_steps:
        appended_sources: set[str] = set()
        dependency_sources: set[str] = set()
        inline_material_blocks: dict[str, str] = {}
        inline_material_counter = [0]
        rewritten = _render_local_markdown(
            source_step.markdown,
            repo_root=repo_root,
            lesson_id=lesson_id,
            link_source_path=source_step.source_git_paths[0],
            resolution_index=resolution_index,
            bindings=binding_map,
            appended_sources=appended_sources,
            dependency_sources=dependency_sources,
            requirements=requirements,
            recursion_stack=(source_step.source_git_paths[0],),
            inline_material_blocks=inline_material_blocks,
            inline_material_counter=inline_material_counter,
        )
        if REPO_RELATIVE_RE.search(rewritten):
            raise VerifiedRenderingError(
                f"{lesson_id}: после local dependency adaptation осталась repo-relative ссылка"
            )
        html = markdown_to_html(rewritten).strip()
        if inline_material_blocks:
            html = _inject_inline_material_blocks(html, inline_material_blocks).strip()
        if apply_stepik_html_normalization:
            normalizer = (
                normalize_stepik_html
                if lesson_id in STEPIC_HTML_NORMALIZATION_V2_LESSONS
                else normalize_stepik_html_v1
            )
            html = normalizer(html).strip()
        if not html:
            raise VerifiedRenderingError(f"{lesson_id}: step {source_step.position} rendered в пустой HTML")
        source_paths = tuple(
            dict.fromkeys((*source_step.source_git_paths, *sorted(dependency_sources)))
        )
        all_dependencies.update(dependency_sources)
        rendered_steps.append(
            RenderedStep(
                position=source_step.position,
                block_name=source_step.block_name,
                text=html,
                source=dict(source_step.source),
                source_git_paths=source_paths,
            )
        )

    return RenderingPlan(
        lesson_id=lesson_id,
        rendered_steps=tuple(rendered_steps),
        materialization_requirements=tuple(requirements[key] for key in sorted(requirements)),
        dependency_source_paths=tuple(sorted(all_dependencies)),
    )


def require_render_ready(plan: RenderingPlan) -> tuple[RenderedStep, ...]:
    if plan.materialization_requirements:
        raise MaterializationRequired(list(plan.materialization_requirements))
    return plan.rendered_steps
