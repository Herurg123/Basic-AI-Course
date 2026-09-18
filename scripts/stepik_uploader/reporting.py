from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_report(
    *,
    mode: str,
    source_sha: str,
    course_id: int | None,
    manifest: dict[str, Any],
    plan: Any | None = None,
    read_objects: int = 0,
    unresolved_assets: list[str] | None = None,
    readback_failures: list[str] | None = None,
) -> dict[str, Any]:
    blockers = list(getattr(plan, "blockers", []) or [])
    notices = list(getattr(plan, "notices", []) or [])
    unresolved_assets = unresolved_assets or []
    readback_failures = readback_failures or []
    blockers.extend(f"unresolved-asset:{asset_id}" for asset_id in unresolved_assets)
    blockers.extend(f"readback:{message}" for message in readback_failures)
    operations = list(getattr(plan, "operations", []) or [])
    counts: dict[str, int] = {}
    for operation in operations:
        action = str(operation.get("action"))
        counts[action] = counts.get(action, 0) + 1
    return {
        "course_id": course_id,
        "source_main_sha": source_sha,
        "mode": mode,
        "read_objects": read_objects,
        "planned_operations": len(operations),
        "operation_counts": counts,
        "created": 0,
        "skipped": counts.get("SKIP", 0) + counts.get("SKIP_STALE_TITLE", 0),
        "blockers": sorted(set(blockers)),
        "notices": notices,
        "unresolved_assets": unresolved_assets,
        "readback_failures": readback_failures,
        "manifest_summary": manifest.get("summary", {}),
        "verdict": "BLOCKED" if blockers else "PASS",
    }
