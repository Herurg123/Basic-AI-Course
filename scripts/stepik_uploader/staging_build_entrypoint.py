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
    from stepik_uploader.content import ContentCompileError
    from stepik_uploader.deployment_history import DeploymentHistoryError
    from stepik_uploader.general_content import compile_lesson_source
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.reporting import write_json
    from stepik_uploader.staging_build_runtime import (
        ASSET_POLICY_PATH,
        GOLDEN_PROFILE_PATH,
        _assert_target_live,
        _credentials,
        _history_store,
        _live_lesson,
        _manifest_lesson,
        main as ordinary_main,
    )
    from stepik_uploader.staging_normalization_recovery import (
        RECOVERY_TARGET,
        build_staging_normalization_recovery_plan,
        execute_staging_normalization_recovery,
    )
    from stepik_uploader.stepik_uploader import mark_golden_profile_result, source_sha
    from stepik_uploader.sync_state import SyncStateError, baseline_for, load_state
    from stepik_uploader.verified_rendering import VerifiedRenderingError
    from stepik_uploader.visual_materialization import VisualMaterializationError
    from stepik_uploader.writer import ContentWriteError
    from stepik_uploader.planner import plan_dry_run
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError
    from .deployment_history import DeploymentHistoryError
    from .general_content import compile_lesson_source
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .reporting import write_json
    from .staging_build_runtime import (
        ASSET_POLICY_PATH,
        GOLDEN_PROFILE_PATH,
        _assert_target_live,
        _credentials,
        _history_store,
        _live_lesson,
        _manifest_lesson,
        main as ordinary_main,
    )
    from .staging_normalization_recovery import (
        RECOVERY_TARGET,
        build_staging_normalization_recovery_plan,
        execute_staging_normalization_recovery,
    )
    from .stepik_uploader import mark_golden_profile_result, source_sha
    from .sync_state import SyncStateError, baseline_for, load_state
    from .verified_rendering import VerifiedRenderingError
    from .visual_materialization import VisualMaterializationError
    from .writer import ContentWriteError
    from .planner import plan_dry_run


COURSE_ID = 299189


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route ordinary staging or exact M06 normalization recovery")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-staging-build"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _write_preflight_report(
    *,
    report_dir: Path,
    report: dict[str, Any],
    recovery_plan: Any,
    golden_status: str,
) -> None:
    recovery = recovery_plan.as_dict()
    write_json(report_dir / "normalization-recovery-plan.json", recovery)
    write_json(report_dir / "visual-materialization-plan.json", {"target": RECOVERY_TARGET, "items": []})
    report.update(
        {
            "verdict": "READY",
            "golden_profile_status": golden_status,
            "target_stepik_lesson_id": recovery_plan.lesson_id,
            "target_title": recovery_plan.expected_title,
            "target_state": recovery_plan.mode,
            "normalization_recovery": recovery,
            "preflight_rendered_steps": len(recovery_plan.normalized_steps),
            "materialization": [],
            "blockers": [],
            "stepik_writes": 0,
            "next_action": "same full private release may continue only through this exact recovery route",
        }
    )
    write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _write_success_artifacts(
    *,
    report_dir: Path,
    report: dict[str, Any],
    recovery_plan: Any,
    result: Any,
    golden_status: str,
) -> None:
    write_json(report_dir / "normalization-recovery-plan.json", recovery_plan.as_dict())
    write_json(report_dir / "visual-materialization-plan.json", {"target": RECOVERY_TARGET, "items": []})
    write_json(report_dir / "sync-state.next.json", result.next_state)
    event = result.event_artifact()
    write_json(report_dir / "lesson-deployment-event.json", event)
    journal = "\n".join(
        [
            f"### STAGING_NORMALIZATION_RECOVERY: `{RECOVERY_TARGET}`",
            "",
            f"- current source main SHA: `{recovery_plan.current_source_sha}`",
            f"- historical event source SHA: `{recovery_plan.identity.source_sha}`",
            f"- Stepik lesson ID: `{recovery_plan.lesson_id}`",
            f"- lesson event: `{recovery_plan.identity.event_id}`",
            f"- recovery mode: `{recovery_plan.mode}`",
            f"- normalization contract: `{recovery_plan.as_dict()['normalization_contract']}`",
            f"- historical desired fingerprint: `{recovery_plan.legacy_desired_fingerprint}`",
            f"- confirmed normalized fingerprint: `{recovery_plan.normalized_desired_fingerprint}`",
            f"- Stepik writes in this recovery: `{result.stepik_writes}`",
            "- duplicate POST for existing step 2: `false`",
            "",
            "Machine state должен быть patched только после final normalized read-back; затем historical event получает MACHINE_STATE_COMMITTED.",
        ]
    ) + "\n"
    (report_dir / "sync-journal.md").write_text(journal, encoding="utf-8")
    report.update(
        {
            "verdict": "PASS",
            "golden_profile_status": golden_status,
            "target_lesson": RECOVERY_TARGET,
            "stepik_lesson_id": recovery_plan.lesson_id,
            "lesson_status": "APPLIED",
            "lesson_event_id": recovery_plan.identity.event_id,
            "normalization_recovery": recovery_plan.as_dict(),
            "rendered_steps": len(recovery_plan.normalized_steps),
            "readback_verified": True,
            "blockers": [],
            "stepik_writes": result.stepik_writes,
        }
    )
    write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _m06_main(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "staging-build-entrypoint",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "target_lesson": RECOVERY_TARGET,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }

    try:
        if args.course_id != COURSE_ID:
            raise ContentWriteError("M06 normalization recovery разрешён только для course_id=299189")

        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        module, lesson_manifest = _manifest_lesson(manifest, RECOVERY_TARGET)
        expected_title = str(lesson_manifest["title"])

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        if baseline_for(state, RECOVERY_TARGET) is not None:
            return ordinary_main()
        pending = state.get("pending", {}).get("lessons", {}).get(RECOVERY_TARGET)
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            return ordinary_main()

        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        structural_plan = plan_dry_run(manifest, snapshot, golden_profile=profile)
        profile_blockers = validate_golden_profile(profile, snapshot, manifest)
        golden_status = mark_golden_profile_result(structural_plan, profile_blockers)
        if golden_status != "confirmed" or structural_plan.blockers:
            raise ContentWriteError(
                "prewrite live structural/golden guards не пройдены: "
                + "; ".join(sorted(set(profile_blockers + structural_plan.blockers)))
            )

        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_target_live(snapshot, live_lesson, expected_title)

        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("Golden profile не содержит free_answer_source")
        source_steps = compile_lesson_source(
            repo_root,
            free_answer_source=free_answer_source,
            lesson_id=RECOVERY_TARGET,
        )
        inventory = build_asset_inventory(repo_root, manifest)
        policy = load_asset_publication_policy(repo_root / ASSET_POLICY_PATH)
        asset_report = assess_asset_publication(
            repo_root=repo_root,
            inventory=inventory,
            policy=policy,
            course_id=args.course_id,
        )
        if asset_report.get("route_gate_passed") is not True or asset_report.get("blockers"):
            raise AssetResolutionError("Asset publication gate не пройден")
        incident_materialization = [
            row for row in asset_report.get("resolutions", [])
            if row.get("lesson") == RECOVERY_TARGET and row.get("materialization_required_at_write") is True
        ]
        if incident_materialization:
            raise AssetResolutionError("M06-L02 incident recovery не должен зависеть от runtime materialization")

        store = _history_store(sha)
        recovery_plan = build_staging_normalization_recovery_plan(
            target_id=RECOVERY_TARGET,
            client=client,
            repo_root=repo_root,
            state=state,
            store=store,
            current_source_sha=sha,
            source_steps=source_steps,
            asset_report=asset_report,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
            expected_title=expected_title,
        )
        if recovery_plan is None:
            return ordinary_main()

        if not args.confirm_write:
            _write_preflight_report(
                report_dir=report_dir,
                report=report,
                recovery_plan=recovery_plan,
                golden_status=golden_status,
            )
            return 0

        result = execute_staging_normalization_recovery(
            client=client,
            plan=recovery_plan,
            store=store,
            state=state,
        )
        _write_success_artifacts(
            report_dir=report_dir,
            report=report,
            recovery_plan=recovery_plan,
            result=result,
            golden_status=golden_status,
        )
        return 0
    except (
        RuntimeError,
        StepikAPIError,
        CanonicalBuildError,
        ContentCompileError,
        GoldenProfileError,
        ContentWriteError,
        AssetResolutionError,
        DeploymentHistoryError,
        SyncStateError,
        VerifiedRenderingError,
        VisualMaterializationError,
    ) as exc:
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "write_retry_policy": "no blind retry; exact incident proof required before any additional Stepik write",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


def main() -> int:
    args = parse_args()
    if str(args.target_id).strip() != RECOVERY_TARGET:
        return ordinary_main()
    return _m06_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
