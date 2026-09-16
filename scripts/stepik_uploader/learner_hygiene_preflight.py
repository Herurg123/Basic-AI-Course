from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import CompiledStep, ContentCompileError
    from stepik_uploader.deployment_history import DeploymentHistoryError
    from stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.history_runtime import find_incomplete_object_events
    from stepik_uploader.learner_hygiene_runtime import (
        ASSET_POLICY_PATH,
        COURSE_ID,
        GOLDEN_PROFILE_PATH,
        TRACKED_HYGIENE_LESSONS,
        _credentials,
        _live_lesson,
        _manifest_index,
        _render_lesson,
    )
    from stepik_uploader.learner_hygiene_writer import _planned_operations
    from stepik_uploader.read_only_history import read_only_history_store
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, baseline_for, load_state
    from stepik_uploader.title_hygiene import TitleHygieneError, legacy_title, plan_title_hygiene
    from stepik_uploader.verified_rendering import VerifiedRenderingError
    from stepik_uploader.writer import ContentWriteError
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import CompiledStep, ContentCompileError
    from .deployment_history import DeploymentHistoryError
    from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .history_runtime import find_incomplete_object_events
    from .learner_hygiene_runtime import (
        ASSET_POLICY_PATH,
        COURSE_ID,
        GOLDEN_PROFILE_PATH,
        TRACKED_HYGIENE_LESSONS,
        _credentials,
        _live_lesson,
        _manifest_index,
        _render_lesson,
    )
    from .learner_hygiene_writer import _planned_operations
    from .read_only_history import read_only_history_store
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, baseline_for, load_state
    from .title_hygiene import TitleHygieneError, legacy_title, plan_title_hygiene
    from .verified_rendering import VerifiedRenderingError
    from .writer import ContentWriteError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only preflight for owner-dispatched learner-facing Stepik hygiene")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-learner-hygiene"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    return parser.parse_args()


def _serialize_title_operation(operation: Any) -> dict[str, Any]:
    return {
        "canonical_id": operation.canonical_id,
        "object_id": operation.object_id,
        "kind": operation.kind,
        "stepik_id": operation.stepik_id,
        "position": operation.position,
        "live_title": operation.live_title,
        "expected_title": operation.expected_title,
        "action": "UPDATE_TITLE",
        "method": "PUT",
        "target": f"{operation.kind}s/{operation.stepik_id}",
    }


def plan_tracked_lesson(
    live_lesson: dict[str, Any],
    *,
    canonical_id: str,
    expected_title: str,
    expected_steps: list[CompiledStep],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    lesson_id = int(live_lesson.get("id", -1))
    if lesson_id <= 0 or int(baseline.get("stepik_lesson_id", -2)) != lesson_id:
        raise ContentWriteError(f"{canonical_id}: target lesson ID отличается от deployment baseline")
    if live_lesson.get("language") != "ru":
        raise ContentWriteError(f"{canonical_id}: target lesson language не ru")
    allowed_titles = {legacy_title(canonical_id, expected_title), expected_title}
    if str(live_lesson.get("title") or "") not in allowed_titles:
        raise ContentWriteError(f"{canonical_id}: live title не равен exact legacy/canonical title")

    baseline_fp = str(baseline.get("applied_fingerprint") or "")
    if not baseline_fp.startswith("sha256:"):
        raise ContentWriteError(f"{canonical_id}: deployment baseline fingerprint отсутствует или повреждён")
    live_fp = live_lesson_fingerprint(live_lesson)
    if live_fp != baseline_fp:
        raise ContentWriteError(f"{canonical_id}: live lesson отличается от confirmed baseline до write")

    desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps)
    operations, desired_lesson = _planned_operations(
        live_lesson,
        expected_title=expected_title,
        expected_steps=expected_steps,
    )
    if live_lesson_fingerprint(desired_lesson) != desired_fp:
        raise ContentWriteError(f"{canonical_id}: planned final state не совпадает с desired fingerprint")

    serialized: list[dict[str, Any]] = []
    for operation in operations:
        if operation.kind == "title":
            serialized.append(
                {
                    "operation_id": operation.operation_id,
                    "action": "UPDATE_TITLE",
                    "method": "PUT",
                    "target": f"lessons/{lesson_id}",
                    "expected_title": expected_title,
                    "fingerprint_before": operation.fingerprint_before,
                    "expected_fingerprint_after": operation.fingerprint_after,
                }
            )
            continue
        if operation.kind != "step" or operation.step_id is None or operation.expected_step is None:
            raise ContentWriteError(f"{canonical_id}: неизвестная planned hygiene operation")
        serialized.append(
            {
                "operation_id": operation.operation_id,
                "action": "UPDATE_STEP",
                "method": "PUT",
                "target": f"step-sources/{operation.step_id}",
                "step_id": operation.step_id,
                "position": operation.expected_step.position,
                "expected_block": operation.expected_step.block(),
                "fingerprint_before": operation.fingerprint_before,
                "expected_fingerprint_after": operation.fingerprint_after,
            }
        )

    return {
        "canonical_id": canonical_id,
        "stepik_lesson_id": lesson_id,
        "baseline_fingerprint": baseline_fp,
        "desired_fingerprint": desired_fp,
        "operations": serialized,
        "stepik_writes_planned": len(serialized),
    }


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "learner-facing-hygiene-preflight",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "confirm_write": False,
        "ready_for_bulk_write": False,
        "stepik_writes": 0,
    }

    try:
        if args.course_id != COURSE_ID:
            raise ContentWriteError(f"learner hygiene разрешён только для fixed course_id={COURSE_ID}")

        manifest = build_structural_manifest(repo_root, source_sha=sha)
        manifest_by_id = _manifest_index(manifest)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        if snapshot.get("course", {}).get("id") != COURSE_ID:
            raise ContentWriteError("Live course ID не совпадает с fixed project target")
        if snapshot.get("course", {}).get("language") != "ru" or snapshot.get("course", {}).get("is_public") is not False:
            raise ContentWriteError("Learner hygiene разрешён только для непубличного русскоязычного project course")

        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        profile_blockers = validate_golden_profile(profile, snapshot, manifest)
        if profile_blockers:
            raise GoldenProfileError("Golden live integrity не подтверждён: " + "; ".join(profile_blockers))
        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("Golden profile не содержит free_answer_source")

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        store = read_only_history_store(sha)

        inventory = build_asset_inventory(repo_root, manifest)
        policy = load_asset_publication_policy(repo_root / ASSET_POLICY_PATH)
        asset_report = assess_asset_publication(
            repo_root=repo_root,
            inventory=inventory,
            policy=policy,
            course_id=args.course_id,
        )
        write_json(report_dir / "asset-publication-report.json", asset_report)
        if asset_report.get("route_gate_passed") is not True or asset_report.get("blockers"):
            raise AssetResolutionError("Asset publication gate не пройден")

        title_plan = plan_title_hygiene(manifest, snapshot)
        write_json(report_dir / "title-hygiene-plan.json", title_plan.as_dict())
        if title_plan.blockers:
            raise TitleHygieneError("Title hygiene blocked: " + "; ".join(title_plan.blockers))

        tracked_title_ids = {
            operation.canonical_id
            for operation in title_plan.operations
            if operation.kind == "lesson" and baseline_for(state, operation.canonical_id) is not None
        }
        unsupported_tracked = tracked_title_ids - TRACKED_HYGIENE_LESSONS
        if unsupported_tracked:
            raise TitleHygieneError(
                "Title-only route не может менять lesson с content baseline: " + ", ".join(sorted(unsupported_tracked))
            )

        title_only_ops = [
            operation
            for operation in title_plan.operations
            if operation.kind == "section" or baseline_for(state, operation.canonical_id) is None
        ]
        serialized_title_ops = [_serialize_title_operation(operation) for operation in title_only_ops]

        tracked_plans: list[dict[str, Any]] = []
        for lesson_id in sorted(TRACKED_HYGIENE_LESSONS):
            baseline = baseline_for(state, lesson_id)
            if not isinstance(baseline, dict):
                continue
            pending = state.get("pending", {}).get("lessons", {}).get(lesson_id)
            incomplete = find_incomplete_object_events(store, object_id=lesson_id)
            if len(incomplete) > 1:
                raise DeploymentHistoryError(f"{lesson_id}: несколько incomplete tracked hygiene events")
            if incomplete:
                raise DeploymentHistoryError(
                    f"{lesson_id}: read-only preflight требует завершённую history; найден incomplete event {incomplete[0][0].event_id}"
                )
            title_needs_cleanup = lesson_id in tracked_title_ids
            if not title_needs_cleanup and pending is None:
                continue

            module, lesson_manifest = manifest_by_id[lesson_id]
            live_lesson = _live_lesson(
                snapshot,
                module_position=int(module["position"]),
                lesson_position=int(lesson_manifest["position"]),
            )
            rendered_steps = _render_lesson(
                client,
                repo_root=repo_root,
                manifest=manifest,
                asset_report=asset_report,
                state=state,
                lesson_id=lesson_id,
                live_lesson=live_lesson,
                free_answer_source=free_answer_source,
            )
            if len(rendered_steps) != len(lesson_manifest.get("steps", [])):
                raise VerifiedRenderingError(f"{lesson_id}: rendered step count != canonical plan")
            tracked_plans.append(
                plan_tracked_lesson(
                    live_lesson,
                    canonical_id=lesson_id,
                    expected_title=str(lesson_manifest["title"]),
                    expected_steps=list(rendered_steps),
                    baseline=baseline,
                )
            )

        planned_writes = len(serialized_title_ops) + sum(item["stepik_writes_planned"] for item in tracked_plans)
        plan = {
            "mode": "learner-facing-hygiene-preflight",
            "source_main_sha": sha,
            "course_id": args.course_id,
            "title_only_operations": serialized_title_ops,
            "tracked_lessons": tracked_plans,
            "golden_owner_required": title_plan.owner_required,
            "already_clean": title_plan.already_clean,
            "stepik_writes_planned": planned_writes,
            "stepik_writes": 0,
            "creates_planned": False,
            "deletes_planned": False,
            "structural_writes_planned": False,
        }
        write_json(report_dir / "hygiene-plan.json", plan)
        report.update(
            {
                "verdict": "READY",
                "blockers": [],
                "ready_for_bulk_write": True,
                "stepik_writes_planned": planned_writes,
                "title_only_operations": serialized_title_ops,
                "tracked_lessons": tracked_plans,
                "golden_owner_required": title_plan.owner_required,
                "human_visual_validation": "NOT_RUN",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        RuntimeError,
        StepikAPIError,
        CanonicalBuildError,
        ContentCompileError,
        GoldenProfileError,
        AssetResolutionError,
        VerifiedRenderingError,
        SyncStateError,
        DeploymentHistoryError,
        TitleHygieneError,
        ContentWriteError,
        OSError,
        ValueError,
    ) as exc:
        report.update({"verdict": "BLOCKED", "blockers": [str(exc)]})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
