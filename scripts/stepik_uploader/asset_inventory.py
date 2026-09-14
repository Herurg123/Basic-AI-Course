from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

ASSET_ID_RE = re.compile(r"M\d{2}-L\d{2}-A\d{2}")
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")


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


def _lesson_links(repo_root: Path, lesson_path: Path) -> list[dict[str, Any]]:
    text = lesson_path.read_text(encoding="utf-8")
    result: list[dict[str, Any]] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        asset_match = ASSET_ID_RE.search(target)
        if not asset_match:
            continue
        clean_target = target.split("#", 1)[0].split("?", 1)[0]
        resolved = (lesson_path.parent / clean_target).resolve()
        exists = resolved.is_file()
        record: dict[str, Any] = {
            "asset_id": asset_match.group(0),
            "markdown_target": target,
            "source_path": _repo_path(repo_root, resolved),
            "exists": exists,
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
        result.append(record)
    return result


def build_asset_inventory(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Build a source-hash inventory without contacting Stepik.

    It records both all physical files matching canonical Asset IDs and the subset that is
    actually linked from learner-facing lesson.md. A changed physical file therefore cannot
    silently look "in sync" merely because a rendered URL stayed unchanged.
    """
    repo_root = repo_root.resolve()
    lessons: dict[str, Any] = {}
    missing_files: list[str] = []
    linked_publication_requirements: list[dict[str, str]] = []

    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            lesson_id = str(lesson["canonical_id"])
            lesson_path = repo_root / str(lesson["source_git_path"])
            if not lesson_path.is_file():
                raise AssetInventoryError(f"Не найден lesson.md для {lesson_id}: {lesson_path}")

            asset_dir = repo_root / "05_assets" / str(module["canonical_id"]) / lesson_id
            physical: list[dict[str, Any]] = []
            for asset_id in lesson.get("asset_ids", []):
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

            linked = _lesson_links(repo_root, lesson_path)
            for record in linked:
                if not record["exists"]:
                    missing_files.append(f"{lesson_id}:{record['source_path']}")
                linked_publication_requirements.append(
                    {
                        "lesson": lesson_id,
                        "asset_id": record["asset_id"],
                        "source_path": record["source_path"],
                    }
                )

            lessons[lesson_id] = {
                "asset_ids": list(lesson.get("asset_ids", [])),
                "physical_files": physical,
                "learner_links": linked,
                "requires_publication_resolution": bool(linked),
            }

    return {
        "schema_version": 1,
        "lessons": lessons,
        "missing_files": sorted(set(missing_files)),
        "linked_publication_requirements": linked_publication_requirements,
        "summary": {
            "lessons_with_assets": sum(1 for value in lessons.values() if value["asset_ids"]),
            "physical_files": sum(len(value["physical_files"]) for value in lessons.values()),
            "learner_repo_links": sum(len(value["learner_links"]) for value in lessons.values()),
            "missing_files": len(set(missing_files)),
        },
    }
