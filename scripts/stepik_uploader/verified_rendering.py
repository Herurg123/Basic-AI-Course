from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .content import CompiledStep
from .general_content import CompiledSourceStep
from .rendering import markdown_to_html

LOCAL_LINK_RE = re.compile(r"\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)")
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
REPO_RELATIVE_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")


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
    rendered_steps: tuple[CompiledStep, ...]
    materialization_requirements: tuple[dict[str, Any], ...]
    dependency_source_paths: tuple[str, ...]

    @property
    def render_ready(self) -> bool:
        return not self.materialization_requirements


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
) -> str:
    append_blocks: list[str] = []

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
                )
                append_blocks.append(f"**Материал: {title}**\n\n{nested}")
            return f"**{label} (материал ниже)**"

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
                return f"**{label} (будет доступен после verified materialization)**"
            if binding.source_sha256 != expected_sha:
                raise VerifiedRenderingError(
                    f"{source_path}: runtime binding относится к другому source SHA-256"
                )
            return f"[{label}]({binding.url})"

        raise VerifiedRenderingError(f"{source_path}: publication mode {mode!r} не поддерживается renderer")

    rewritten = LOCAL_LINK_RE.sub(replace, markdown_text)
    if append_blocks:
        rewritten = rewritten.rstrip() + "\n\n---\n\n" + "\n\n---\n\n".join(append_blocks)
    return rewritten


def build_rendering_plan(
    *,
    repo_root: Path,
    lesson_id: str,
    source_steps: Iterable[CompiledSourceStep],
    asset_report: dict[str, Any],
    bindings: Iterable[AssetBinding] | None = None,
) -> RenderingPlan:
    repo_root = repo_root.resolve()
    resolution_index = _resolution_index(asset_report, lesson_id=lesson_id)
    binding_map = _binding_index(bindings)
    rendered_steps: list[CompiledStep] = []
    requirements: dict[str, dict[str, Any]] = {}
    all_dependencies: set[str] = set()

    for source_step in source_steps:
        appended_sources: set[str] = set()
        dependency_sources: set[str] = set()
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
        )
        if REPO_RELATIVE_RE.search(rewritten):
            raise VerifiedRenderingError(
                f"{lesson_id}: после local dependency adaptation осталась repo-relative ссылка"
            )
        html = markdown_to_html(rewritten).strip()
        if not html:
            raise VerifiedRenderingError(f"{lesson_id}: step {source_step.position} rendered в пустой HTML")
        source_paths = tuple(
            dict.fromkeys((*source_step.source_git_paths, *sorted(dependency_sources)))
        )
        all_dependencies.update(dependency_sources)
        rendered_steps.append(
            CompiledStep(
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


def require_render_ready(plan: RenderingPlan) -> tuple[CompiledStep, ...]:
    if plan.materialization_requirements:
        raise MaterializationRequired(list(plan.materialization_requirements))
    return plan.rendered_steps
