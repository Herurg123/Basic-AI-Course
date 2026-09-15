from __future__ import annotations

import hashlib
import json
from typing import Any


class AssetResolutionError(RuntimeError):
    pass


def learner_link_topology(inventory: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic structural snapshot of learner-facing repo links.

    Content hashes are intentionally excluded from the topology fingerprint: normal source
    edits must not silently become new publication *shapes*. Fixed published URL bindings are
    hash-checked separately by the publication policy.
    """
    rows: list[dict[str, str]] = []
    unique_sources: set[str] = set()
    extensions: dict[str, int] = {}

    lessons = inventory.get("lessons")
    if not isinstance(lessons, dict):
        raise AssetResolutionError("asset inventory не содержит lessons")

    for lesson_id, lesson in lessons.items():
        links = lesson.get("learner_links", []) if isinstance(lesson, dict) else []
        if not isinstance(links, list):
            raise AssetResolutionError(f"{lesson_id}: learner_links имеет неожиданный формат")
        for link in links:
            if not isinstance(link, dict):
                raise AssetResolutionError(f"{lesson_id}: learner link имеет неожиданный формат")
            if link.get("exists") is not True:
                raise AssetResolutionError(f"{lesson_id}: learner link не существует: {link.get('source_path')}")
            source_path = str(link.get("source_path") or "")
            asset_id = str(link.get("asset_id") or "")
            markdown_target = str(link.get("markdown_target") or "")
            extension = str(link.get("extension") or "").lower()
            if not source_path or not asset_id or not markdown_target or not extension:
                raise AssetResolutionError(f"{lesson_id}: неполная learner-link запись")
            rows.append(
                {
                    "lesson": str(lesson_id),
                    "asset_id": asset_id,
                    "source_path": source_path,
                    "markdown_target": markdown_target,
                    "extension": extension,
                }
            )
            unique_sources.add(source_path)
            extensions[extension] = extensions.get(extension, 0) + 1

    rows.sort(
        key=lambda item: (
            item["lesson"],
            item["source_path"],
            item["markdown_target"],
            item["asset_id"],
            item["extension"],
        )
    )
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "learner_link_occurrences": len(rows),
        "unique_source_files": len(unique_sources),
        "extensions_by_occurrence": dict(sorted(extensions.items())),
        "fingerprint": fingerprint,
        "rows": rows,
    }
