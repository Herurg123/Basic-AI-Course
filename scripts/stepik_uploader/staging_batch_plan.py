from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.canonical import build_structural_manifest
    from stepik_uploader.deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from stepik_uploader.history_runtime import find_incomplete_object_events
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import load_state
else:
    from .canonical import build_structural_manifest
    from .deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from .history_runtime import find_incomplete_object_events
    from .stepik_uploader import source_sha
    from .sync_state import load_state


GOLDEN_IDS = {"M00-L01", "M00-L02"}


def _manifest_index(manifest: dict[str, Any]) -> tuple[list[str], set[str]]:
    canonical_order: list[str] = []
    golden_ids: set[str] = set(GOLDEN_IDS)
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            canonical_id = str(lesson.get("canonical_id") or "").strip()
            if not canonical_id:
                continue
            canonical_order.append(canonical_id)
            if lesson.get("golden_read_only") is True:
                golden_ids.add(canonical_id)
    return canonical_order, golden_ids


def select_targets(manifest: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("pending", {})
    pending_lessons = pending.get("lessons", {})
    baselines = state.get("lessons", {})
    canonical_order, golden_ids = _manifest_index(manifest)
    manifest_ids = set(canonical_order)

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

    initial_targets: list[str] = []
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
        initial_targets.append(canonical_id)

    if incompatible_existing_baselines:
        blockers.append(
            "Batch initial-staging route не обновляет lessons с существующим baseline: "
            + ", ".join(incompatible_existing_baselines)
        )

    course_page_pending = pending.get("course_page")

    return {
        "initial_target_ids": initial_targets,
        "recovery_target_ids": [],
        "target_ids": list(initial_targets),
        "target_count": len(initial_targets),
        "excluded_golden_pending": excluded_golden_pending,
        "course_page_pending": course_page_pending is not None,
        "blockers": blockers,
        "write_allowed": not blockers,
    }


def add_history_recovery_targets(
    *,
    selection: dict[str, Any],
    manifest: dict[str, Any],
    state: dict[str, Any],
    source_main_sha: str,
    store: Any,
    course_id: int,
) -> dict[str, Any]:
    canonical_order, golden_ids = _manifest_index(manifest)
    initial_targets = set(selection.get("initial_target_ids", []))
    pending_lessons = state.get("pending", {}).get("lessons", {})
    baselines = state.get("lessons", {})
    blockers = list(selection.get("blockers", []))
    recovery_targets: list[str] = []

    for canonical_id in canonical_order:
        if canonical_id in golden_ids:
            continue
        incomplete = find_incomplete_object_events(store, object_id=canonical_id)
        if len(incomplete) > 1:
            blockers.append(f"{canonical_id}: найдено несколько incomplete lesson history events")
            continue
        if not incomplete:
            continue

        identity, _records, _summary = incomplete[0]
        if identity.course_id != course_id or identity.kind != "lesson":
            blockers.append(f"{canonical_id}: incomplete history имеет неожиданный course/kind")
            continue
        if identity.source_sha != source_main_sha:
            blockers.append(
                f"{canonical_id}: incomplete history относится к source_sha={identity.source_sha}, "
                f"а batch закреплён на {source_main_sha}"
            )
            continue
        if canonical_id in initial_targets:
            continue

        pending_record = pending_lessons.get(canonical_id)
        has_pending = isinstance(pending_record, dict) and pending_record.get("status") == "PENDING"
        has_baseline = canonical_id in baselines
        if not has_pending and not has_baseline:
            blockers.append(
                f"{canonical_id}: incomplete history существует без PENDING и без machine baseline; automatic recovery scope недоказуем"
            )
            continue
        recovery_targets.append(canonical_id)

    recovery_set = set(recovery_targets)
    total_targets = [
        canonical_id
        for canonical_id in canonical_order
        if canonical_id in initial_targets or canonical_id in recovery_set
    ]
    result = dict(selection)
    result["recovery_target_ids"] = recovery_targets
    result["target_ids"] = total_targets
    result["target_count"] = len(total_targets)
    result["blockers"] = blockers
    result["write_allowed"] = not blockers
    return result


def build_plan(
    *,
    repo_root: Path,
    sync_state: Path,
    course_id: int,
    include_history_recovery: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    sha = source_sha(repo_root)
    manifest = build_structural_manifest(repo_root, source_sha=sha)
    state_path = sync_state if sync_state.is_absolute() else repo_root / sync_state
    state = load_state(state_path, course_id=course_id)
    selection = select_targets(manifest, state)

    if include_history_recovery:
        repository = os.getenv("GITHUB_REPOSITORY", "").strip()
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if not repository or not token:
            raise DeploymentHistoryError(
                "Для batch history recovery нужны GITHUB_REPOSITORY и GITHUB_TOKEN"
            )
        store = GitHubHistoryStore(
            repository=repository,
            token=token,
            source_sha=sha,
        )
        selection = add_history_recovery_targets(
            selection=selection,
            manifest=manifest,
            state=state,
            source_main_sha=sha,
            store=store,
            course_id=course_id,
        )

    return {
        "mode": "staging-batch-plan",
        "course_id": course_id,
        "source_main_sha": sha,
        "history_recovery_checked": bool(include_history_recovery),
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
    parser.add_argument(
        "--include-history-recovery",
        action="store_true",
        default=os.getenv("GITHUB_ACTIONS", "").lower() == "true",
        help="Include current-source lessons with incomplete durable history so batch reruns heal commit gaps. Enabled by default in GitHub Actions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.course_id != 299189:
        raise SystemExit("staging-batch-plan разрешён только для course_id=299189")

    plan = build_plan(
        repo_root=args.repo_root,
        sync_state=args.sync_state,
        course_id=args.course_id,
        include_history_recovery=bool(args.include_history_recovery),
    )
    output = args.output if args.output.is_absolute() else args.repo_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan["write_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
