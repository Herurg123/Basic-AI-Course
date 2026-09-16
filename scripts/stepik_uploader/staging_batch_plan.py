from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.canonical import build_structural_manifest
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import load_state
else:
    from .canonical import build_structural_manifest
    from .stepik_uploader import source_sha
    from .sync_state import load_state


GOLDEN_IDS = {"M00-L01", "M00-L02"}


def select_targets(manifest: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("pending", {})
    pending_lessons = pending.get("lessons", {})
    baselines = state.get("lessons", {})

    canonical_order: list[str] = []
    golden_ids: set[str] = set(GOLDEN_IDS)
    manifest_ids: set[str] = set()

    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            canonical_id = str(lesson.get("canonical_id") or "").strip()
            if not canonical_id:
                continue
            manifest_ids.add(canonical_id)
            canonical_order.append(canonical_id)
            if lesson.get("golden_read_only") is True:
                golden_ids.add(canonical_id)

    blockers: list[str] = []
    unknown_pending = sorted(
        canonical_id
        for canonical_id, record in pending_lessons.items()
        if isinstance(record, dict)
        and record.get("status") == "PENDING"
        and canonical_id not in manifest_ids
    )
    if unknown_pending:
        blockers.append(
            "PENDING lessons отсутствуют в canonical manifest: " + ", ".join(unknown_pending)
        )

    targets: list[str] = []
    excluded_golden_pending: list[str] = []
    incompatible_existing_baselines: list[str] = []

    for canonical_id in canonical_order:
        record = pending_lessons.get(canonical_id)
        if not isinstance(record, dict) or record.get("status") != "PENDING":
            continue
        if canonical_id in golden_ids:
            excluded_golden_pending.append(canonical_id)
            continue
        if canonical_id in baselines:
            incompatible_existing_baselines.append(canonical_id)
            continue
        targets.append(canonical_id)

    if incompatible_existing_baselines:
        blockers.append(
            "Batch initial-staging route не обновляет lessons с существующим baseline: "
            + ", ".join(incompatible_existing_baselines)
        )

    course_page_pending = pending.get("course_page")

    return {
        "target_ids": targets,
        "target_count": len(targets),
        "excluded_golden_pending": excluded_golden_pending,
        "course_page_pending": course_page_pending is not None,
        "blockers": blockers,
        "write_allowed": not blockers,
    }


def build_plan(*, repo_root: Path, sync_state: Path, course_id: int) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    sha = source_sha(repo_root)
    manifest = build_structural_manifest(repo_root, source_sha=sha)
    state_path = sync_state if sync_state.is_absolute() else repo_root / sync_state
    state = load_state(state_path, course_id=course_id)
    selection = select_targets(manifest, state)
    return {
        "mode": "staging-batch-plan",
        "course_id": course_id,
        "source_main_sha": sha,
        "manifest_summary": {
            "modules": len(manifest.get("modules", [])),
            "lessons": sum(len(module.get("lessons", [])) for module in manifest.get("modules", [])),
        },
        **selection,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan guarded sequential staging for all ordinary PENDING lessons")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.course_id != 299189:
        raise SystemExit("staging-batch-plan разрешён только для course_id=299189")

    plan = build_plan(
        repo_root=args.repo_root,
        sync_state=args.sync_state,
        course_id=args.course_id,
    )
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan["write_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
