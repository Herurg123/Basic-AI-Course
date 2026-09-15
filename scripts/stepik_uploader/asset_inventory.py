from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

ASSET_ID_RE = re.compile(r"M\d{2}-L\d{2}-A\d{2}")
ASSET_ID_FULL_RE = re.compile(r"(?P<module>M\d{2})-(?P<lesson>L\d{2})-A\d{2}")
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class AssetInventoryError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _repo_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError as exc:
        raise AssetInventoryError(f"Asset path выходит за пределы репозитория: {path}") from exc


def _asset_dir_for_id(repo_root: Path, asset_id: str) -> Path:
    match = ASSET_ID_FULL_RE.fullmatch(asset_id)
    if not match:
        raise AssetInventoryError(f"Некорректный Asset ID: {asset_id}")
    module_id = match.group("module")
    lesson_id = f"{module_id}-{match.group('lesson')}"
    return repo_root / "05_assets" / module_id / lesson_id


def _is_repo_relative_target(target: str) -> bool:
    target = target.strip()
    if not target or target.startswith("#") or target.startswith("/"):
        return False
    return URI_SCHEME_RE.match(target) is None


def _link_record(
    repo_root: Path,
    *,
    source_document: Path,
    target: str,
    dependency_depth: int,
) -> dict[str, Any]:
    clean_target = target.split("#", 1)[0].split("?", 1)[0]
    resolved = (source_document.parent / clean_target).resolve()
    exists = resolved.is_file()
    asset_match = ASSET_ID_RE.search(target) or ASSET_ID_RE.search(resolved.name)
    record: dict[str, Any] = {
        "asset_id": asset_match.group(0) if asset_match else None,
        "markdown_target": target,
        "link_source_path": _repo_path(repo_root, source_document),
        "source_path": _repo_path(repo_root, resolved),
        "exists": exists,
        "dependency_depth": dependency_depth,
        "requires_stepik_url_or_inline": True,
    }
    if exists:
        record.update(
            {
                "filename": resolved.name,
                "extension": resolved.suffix.lower(),
                "size_bytes": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )
    return record


def _document_links(
    repo_root: Path,
    source_document: Path,
    *,
    dependency_depth: int,
) -> list[dict[str, Any]]:
    text = source_document.read_text(encoding="utf-8")
    result: list[dict[str, Any]] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip()
        if not _is_repo_relative_target(target):
            continue
        result.append(
            _link_record(
                repo_root,
                source_document=source_document,
                target=target,
                dependency_depth=dependency_depth,
            )
        )
    return result


def _transitive_links(
    repo_root: Path,
    direct_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand repo-relative links found inside linked Markdown resources.

    A Markdown resource is scanned once per source path. Link occurrences in lesson.md remain
    untouched, while nested dependency edges are appended exactly once per parent document.
    """
    result = [dict(record) for record in direct_links]
    queue: list[Path] = []
    visited_documents: set[str] = set()

    for record in direct_links:
        if record.get("exists") and record.get("extension") == ".md":
            queue.append(repo_root / str(record["source_path"]))

    while queue:
        source_document = queue.pop(0).resolve()
        source_key = _repo_path(repo_root, source_document)
        if source_key in visited_documents:
            continue
        visited_documents.add(source_key)

        parent_depths = [
            int(item.get("dependency_depth", 0))
            for item in result
            if item.get("source_path") == source_key
        ]
        dependency_depth = (min(parent_depths) if parent_depths else 0) + 1
        for nested in _document_links(
            repo_root,
            source_document,
            dependency_depth=dependency_depth,
        ):
            result.append(nested)
            if nested.get("exists") and nested.get("extension") == ".md":
                queue.append(repo_root / str(nested["source_path"]))

    return result


def build_asset_inventory(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Build the complete learner-facing local dependency inventory without Stepik access.

    `learner_links` contains every direct repo-relative link from lesson.md, not only Asset IDs.
    `learner_dependency_links` additionally expands repo-relative links inside linked Markdown
    resources. This prevents an inline source from hiding a second unresolved local dependency.
    """
    repo_root = repo_root.resolve()
    lessons: dict[str, Any] = {}
    missing_files: list[str] = []
    linked_publication_requirements: list[dict[str, Any]] = []

    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            lesson_id = str(lesson["canonical_id"])
            lesson_path = repo_root / str(lesson["source_git_path"])
            if not lesson_path.is_file():
                raise AssetInventoryError(f"Не найден lesson.md для {lesson_id}: {lesson_path}")

            physical: list[dict[str, Any]] = []
            for asset_id in lesson.get("asset_ids", []):
                asset_dir = _asset_dir_for_id(repo_root, str(asset_id))
                matches = sorted(path for path in asset_dir.glob(f"{asset_id}*") if path.is_file())
                if not matches:
                    missing_files.append(asset_id)
                for path in matches:
                    physical.append(
                        {
                            "asset_id": asset_id,
                            "source_path": _repo_path(repo_root, path),
                            "filename": path.name,
                            "extension": path.suffix.lower(),
                            "size_bytes": path.stat().st_size,
                            "sha256": _sha256(path),
                        }
                    )

            direct = _document_links(repo_root, lesson_path, dependency_depth=0)
            dependencies = _transitive_links(repo_root, direct)
            for record in dependencies:
                if not record["exists"]:
                    missing_files.append(f"{lesson_id}:{record['source_path']}")
                linked_publication_requirements.append(
                    {
                        "lesson": lesson_id,
                        "asset_id": record.get("asset_id"),
                        "link_source_path": record["link_source_path"],
                        "source_path": record["source_path"],
                        "dependency_depth": record["dependency_depth"],
                    }
                )

            lessons[lesson_id] = {
                "asset_ids": list(lesson.get("asset_ids", [])),
                "physical_files": physical,
                "learner_links": direct,
                "learner_dependency_links": dependencies,
                "requires_publication_resolution": bool(dependencies),
            }

    return {
        "schema_version": 2,
        "lessons": lessons,
        "missing_files": sorted(set(missing_files)),
        "linked_publication_requirements": linked_publication_requirements,
        "summary": {
            "lessons_with_assets": sum(1 for value in lessons.values() if value["asset_ids"]),
            "physical_files": sum(len(value["physical_files"]) for value in lessons.values()),
            "learner_repo_links": sum(len(value["learner_links"]) for value in lessons.values()),
            "learner_dependency_links": sum(
                len(value["learner_dependency_links"]) for value in lessons.values()
            ),
            "unique_dependency_sources": len(
                {
                    item["source_path"]
                    for value in lessons.values()
                    for item in value["learner_dependency_links"]
                }
            ),
            "missing_files": len(set(missing_files)),
        },
    }
