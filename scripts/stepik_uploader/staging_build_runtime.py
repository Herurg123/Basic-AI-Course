from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.attachment_materialization import verify_attachment_capability
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import ContentCompileError
    from stepik_uploader.deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore, event_identity_from_environment
    from stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from stepik_uploader.general_content import compile_lesson_source
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.history_runtime import find_incomplete_object_events, final_confirmed_record
    from stepik_uploader.initial_upload_writer import execute_initial_upload_one
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reporting import build_report, write_json
    from stepik_uploader.stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from stepik_uploader.sync_state import SyncStateError, asset_binding_for, baseline_for, close_lesson_pending, load_state, with_asset_record, with_record
    from stepik_uploader.verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from stepik_uploader.visual_materialization import VisualMaterializationError, materialize_visual, prepare_visual_file, verify_visual_binding
    from stepik_uploader.writer import ContentWriteError, PLACEHOLDER_TEXT, _placeholder
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .attachment_materialization import verify_attachment_capability
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError
    from .deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore, event_identity_from_environment
    from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from .general_content import compile_lesson_source
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .history_runtime import find_incomplete_object_events, final_confirmed_record
    from .initial_upload_writer import execute_initial_upload_one
    from .planner import plan_dry_run
    from .reporting import build_report, write_json
    from .stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from .sync_state import SyncStateError, asset_binding_for, baseline_for, close_lesson_pending, load_state, with_asset_record, with_record
    from .verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from .visual_materialization import VisualMaterializationError, materialize_visual, prepare_visual_file, verify_visual_binding
    from .writer import ContentWriteError, PLACEHOLDER_TEXT, _placeholder


GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")
GOLDEN_IDS = {"M00-L01", "M00-L02"}
VISUAL_MODES = {"stepik-image-upload", "rasterize-png-stepik-image"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для staging build нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_lesson(manifest: dict[str, Any], target_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == target_id:
                return module, lesson
    raise ContentCompileError(f"В manifest отсутствует {target_id}")


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден exact section position={module_position}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1 or not isinstance(units[0].get("lesson"), dict):
        raise ContentWriteError(f"Не найден exact target unit {module_position}/{lesson_position}")
    return units[0]["lesson"]


def _assert_target_live(snapshot: dict[str, Any], lesson: dict[str, Any], expected_title: str) -> None:
    course = snapshot.get("course", {})
    if course.get("is_public") is not False:
        raise ContentWriteError("Staging build разрешён только в private course")
    if course.get("language") not in {None, "ru"}:
        raise ContentWriteError("Course language неожиданно отличается от ru")
    if lesson.get("is_public") is not False:
        raise ContentWriteError("Staging build разрешён только в private target lesson")
    if lesson.get("language") != "ru":
        raise ContentWriteError("Target lesson language не ru")
    if lesson.get("title") != expected_title:
        raise ContentWriteError(
            f"Target lesson title drift: ожидалось {expected_title!r}, найдено {lesson.get('title')!r}"
        )


def _require_pristine_skeleton(live_lesson: dict[str, Any]) -> None:
    steps = list(live_lesson.get("steps", []))
    if len(steps) != 1 or not _placeholder(steps[0]):
        raise ContentWriteError(
            f"Новый initial upload без recovery history разрешён только из exact skeleton placeholder «{PLACEHOLDER_TEXT}»"
        )


def _materialization_rows(asset_report: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for row in asset_report.get("resolutions", []):
        if row.get("lesson") != target_id or row.get("materialization_required_at_write") is not True:
            continue
        source_path = str(row.get("source_path") or "")
        if not source_path:
            raise AssetResolutionError(f"{target_id}: materialization row без source_path")
        existing = by_source.get(source_path)
        if existing is not None:
            comparable = {key: row.get(key) for key in ("source_sha256", "mode", "derived_format")}
            prior = {key: existing.get(key) for key in ("source_sha256", "mode", "derived_format")}
            if comparable != prior:
                raise AssetResolutionError(f"{target_id}: конфликтующие materialization rows для {source_path}")
            continue
        by_source[source_path] = row
    rows = [by_source[key] for key in sorted(by_source)]
    unsupported = [str(row.get("source_path")) for row in rows if row.get("mode") not in VISUAL_MODES]
    if unsupported:
        raise AssetResolutionError(
            f"{target_id}: staging-build-one пока не принимает non-visual materialization: {', '.join(unsupported)}"
        )
    return rows


def _final_status(records: list[dict[str, Any]]) -> str:
    final = final_confirmed_record(records)
    if final is None or final.get("status") not in {"APPLIED", "NOOP_CONFIRMED"}:
        raise DeploymentHistoryError("History event не содержит подтверждённый final status")
    return str(final["status"])


def _recover_final_state(records: list[dict[str, Any]], *, label: str) -> tuple[dict[str, Any], str]:
    final = final_confirmed_record(records)
    recovered = final.get("actual_confirmed_state") if isinstance(final, dict) else None
    if not isinstance(recovered, dict):
        raise DeploymentHistoryError(f"{label} final history не содержит actual_confirmed_state")
    return recovered, _final_status(records)


def _event_artifact(identity: Any, *, status: str, kind: str, target_id: str, source_path: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": identity.event_id,
        "source_sha": identity.source_sha,
        "status": status,
        "kind": kind,
    }
    if kind == "asset":
        payload["source_path"] = source_path
    else:
        payload["canonical_id"] = target_id
    return payload


def _asset_materialization_plan(
    *,
    repo_root: Path,
    report_dir: Path,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for row in rows:
        source_path = str(row["source_path"])
        material_file, materialized_sha, materialization_fp = prepare_visual_file(
            source_file=repo_root / source_path,
            source_path=source_path,
            expected_source_sha256=str(row["source_sha256"]),
            mode=str(row["mode"]),
            work_dir=report_dir / "prepared-visuals" / Path(source_path).stem,
        )
        plan.append(
            {
                "source_path": source_path,
                "source_sha256": str(row["source_sha256"]),
                "mode": str(row["mode"]),
                "materialized_filename": material_file.name,
                "materialized_sha256": materialized_sha,
                "materialization_fingerprint": materialization_fp,
            }
        )
    return plan


def _synthetic_preflight_binding(item: dict[str, Any]) -> AssetBinding:
    return AssetBinding(
        source_path=str(item["source_path"]),
        source_sha256=str(item["source_sha256"]),
        url=f"https://preflight.invalid/{item['materialized_filename']}",
        storage="preflight-synthetic-only",
        verified=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded one-lesson private Stepik staging builder")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-staging-build"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_id = str(args.target_id).strip()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "staging-build-one",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "target_lesson": target_id,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }

    try:
        if target_id in GOLDEN_IDS:
            raise ContentWriteError(
                f"{target_id} является READ_ONLY_GOLDEN; staging-build-one не имеет права менять golden content"
            )
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        module, lesson_manifest = _manifest_lesson(manifest, target_id)
        if lesson_manifest.get("golden_read_only"):
            raise ContentWriteError(f"{target_id} помечен golden_read_only")

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        if baseline_for(state, target_id) is not None:
            raise ContentWriteError(
                f"{target_id} уже имеет deployment baseline; initial staging route запрещён, использовать baseline-aware sync"
            )
        pending = state.get("pending", {}).get("lessons", {}).get(target_id)
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise ContentWriteError(f"{target_id} не имеет текущего PENDING; blind initial upload запрещён")
        pending_first_sha = str(pending.get("first_pending_sha") or "") or None

        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        plan = plan_dry_run(manifest, snapshot)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        profile_blockers = validate_golden_profile(profile, snapshot, manifest)
        golden_status = mark_golden_profile_result(plan, profile_blockers)
        if golden_status != "confirmed" or plan.blockers:
            raise ContentWriteError(
                "prewrite live structural/golden guards не пройдены: " + "; ".join(sorted(set(profile_blockers + plan.blockers)))
            )

        expected_title = str(lesson_manifest["title"])
        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_target_live(snapshot, live_lesson, expected_title)

        store = _history_store(sha)
        incomplete_lessons = find_incomplete_object_events(store, object_id=target_id)
        if len(incomplete_lessons) > 1:
            raise DeploymentHistoryError(f"{target_id}: найдено несколько incomplete lesson events")
        if not incomplete_lessons:
            _require_pristine_skeleton(live_lesson)

        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("Golden profile не содержит free_answer_source")
        source_steps = compile_lesson_source(repo_root, free_answer_source=free_answer_source, lesson_id=target_id)
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
        material_rows = _materialization_rows(asset_report, target_id)
        material_plan = _asset_materialization_plan(
            repo_root=repo_root,
            report_dir=report_dir,
            rows=material_rows,
        )
        material_by_source = {item["source_path"]: item for item in material_plan}
        write_json(report_dir / "visual-materialization-plan.json", {"target": target_id, "items": material_plan})

        if not args.confirm_write:
            preflight_bindings: list[AssetBinding] = []
            asset_checks: list[dict[str, Any]] = []
            for row in material_rows:
                source_path = str(row["source_path"])
                expected_source_sha = str(row["source_sha256"])
                mode = str(row["mode"])
                prepared = material_by_source[source_path]
                record = asset_binding_for(state, source_path)
                incomplete_assets = find_incomplete_object_events(store, object_id=f"asset:{source_path}")
                if len(incomplete_assets) > 1:
                    raise DeploymentHistoryError(f"{source_path}: найдено несколько incomplete asset events")

                if record is not None:
                    binding = verify_visual_binding(
                        client,
                        record,
                        source_path=source_path,
                        expected_source_sha256=expected_source_sha,
                        expected_mode=mode,
                        stepik_lesson_id=int(live_lesson["id"]),
                    )
                    if incomplete_assets:
                        identity, records, summary = incomplete_assets[0]
                        if identity.source_sha != sha or identity.desired_fingerprint != prepared["materialization_fingerprint"]:
                            raise DeploymentHistoryError(f"{source_path}: incomplete asset event относится к другому source/materialization")
                        if not summary.get("final_readback_confirmed"):
                            raise DeploymentHistoryError(f"{source_path}: machine baseline существует без final history read-back")
                        recovered, _ = _recover_final_state(records, label=source_path)
                        if recovered != record:
                            raise DeploymentHistoryError(f"{source_path}: machine baseline расходится с final immutable history")
                    asset_checks.append({"source_path": source_path, "status": "VERIFIED_BASELINE_REUSE"})
                    preflight_bindings.append(binding)
                    continue

                if incomplete_assets:
                    identity, records, summary = incomplete_assets[0]
                    if identity.source_sha != sha or identity.desired_fingerprint != prepared["materialization_fingerprint"]:
                        raise DeploymentHistoryError(f"{source_path}: incomplete asset event относится к другому source/materialization")
                    if not summary.get("final_readback_confirmed"):
                        raise DeploymentHistoryError(
                            f"{source_path}: incomplete asset event без final read-back; blind retry запрещён"
                        )
                    recovered, _ = _recover_final_state(records, label=source_path)
                    binding = verify_visual_binding(
                        client,
                        recovered,
                        source_path=source_path,
                        expected_source_sha256=expected_source_sha,
                        expected_mode=mode,
                        stepik_lesson_id=int(live_lesson["id"]),
                    )
                    asset_checks.append({"source_path": source_path, "status": "RECOVERABLE_FINAL_HISTORY"})
                    preflight_bindings.append(binding)
                    continue

                verify_attachment_capability(client)
                same_name = [
                    item for item in client.list_attachments(lesson_id=int(live_lesson["id"]))
                    if item.get("name") == prepared["materialized_filename"]
                ]
                if same_name:
                    raise VisualMaterializationError(
                        f"{target_id}: {prepared['materialized_filename']} уже существует без machine asset baseline/history; automatic adoption запрещён"
                    )
                asset_checks.append({"source_path": source_path, "status": "READY_TO_MATERIALIZE"})
                preflight_bindings.append(_synthetic_preflight_binding(prepared))

            preflight_rendering = build_rendering_plan(
                repo_root=repo_root,
                lesson_id=target_id,
                source_steps=source_steps,
                asset_report=asset_report,
                bindings=preflight_bindings,
            )
            preflight_steps = list(require_render_ready(preflight_rendering))
            if len(preflight_steps) != len(lesson_manifest.get("steps", [])):
                raise VerifiedRenderingError(f"{target_id}: preflight rendered step count не совпадает с canonical plan")

            report.update(
                {
                    "verdict": "READY",
                    "golden_profile_status": golden_status,
                    "target_stepik_lesson_id": int(live_lesson["id"]),
                    "target_title": expected_title,
                    "target_state": "PRISTINE_SKELETON" if not incomplete_lessons else "RECOVERY_HISTORY_PRESENT",
                    "independence_sensitive": bool(lesson_manifest.get("independence_sensitive")),
                    "f1_sensitive": bool(lesson_manifest.get("f1_sensitive")),
                    "materialization": asset_checks,
                    "preflight_rendered_steps": len(preflight_steps),
                    "preflight_render_uses_synthetic_urls": any(item["status"] == "READY_TO_MATERIALIZE" for item in asset_checks),
                    "blockers": [],
                    "next_action": "owner dispatch same target with confirm_write=true after artifact review",
                    "stepik_writes": 0,
                }
            )
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        bindings: list[AssetBinding] = []
        next_state = state
        asset_event_artifacts: list[dict[str, Any]] = []
        for row in material_rows:
            source_path = str(row["source_path"])
            expected_source_sha = str(row["source_sha256"])
            mode = str(row["mode"])
            prepared = material_by_source[source_path]
            incomplete_assets = find_incomplete_object_events(store, object_id=f"asset:{source_path}")
            if len(incomplete_assets) > 1:
                raise DeploymentHistoryError(f"{source_path}: найдено несколько incomplete asset events")
            record = asset_binding_for(state, source_path)
            identity = None
            status = "BASELINE_REUSED"
            if record is not None:
                binding = verify_visual_binding(
                    client,
                    record,
                    source_path=source_path,
                    expected_source_sha256=expected_source_sha,
                    expected_mode=mode,
                    stepik_lesson_id=int(live_lesson["id"]),
                )
                if incomplete_assets:
                    identity, records, summary = incomplete_assets[0]
                    if identity.source_sha != sha or identity.desired_fingerprint != prepared["materialization_fingerprint"]:
                        raise DeploymentHistoryError(f"{source_path}: incomplete asset event относится к другому source/materialization")
                    if not summary.get("final_readback_confirmed"):
                        raise DeploymentHistoryError(f"{source_path}: machine asset baseline существует без final history read-back")
                    recovered, status = _recover_final_state(records, label=source_path)
                    if recovered != record:
                        raise DeploymentHistoryError(f"{source_path}: machine asset baseline не совпадает с immutable final history")
            elif incomplete_assets:
                identity, records, summary = incomplete_assets[0]
                if identity.source_sha != sha or identity.desired_fingerprint != prepared["materialization_fingerprint"]:
                    raise DeploymentHistoryError(f"{source_path}: incomplete asset event относится к другому source/materialization")
                if not summary.get("final_readback_confirmed"):
                    raise DeploymentHistoryError(
                        f"{source_path}: incomplete asset event не имеет final read-back; blind retry запрещён"
                    )
                record, status = _recover_final_state(records, label=source_path)
                binding = verify_visual_binding(
                    client,
                    record,
                    source_path=source_path,
                    expected_source_sha256=expected_source_sha,
                    expected_mode=mode,
                    stepik_lesson_id=int(live_lesson["id"]),
                )
                next_state = with_asset_record(next_state, source_path=source_path, record=record)
            else:
                identity = event_identity_from_environment(
                    course_id=args.course_id,
                    object_id=f"asset:{source_path}",
                    kind="asset",
                    source_sha=sha,
                    desired_fingerprint=str(prepared["materialization_fingerprint"]),
                    baseline_fingerprint=None,
                    pending_first_sha=pending_first_sha,
                )
                recorder = DeploymentRecorder(store, identity)
                record, status = materialize_visual(
                    client,
                    recorder=recorder,
                    source_file=repo_root / source_path,
                    source_path=source_path,
                    expected_source_sha256=expected_source_sha,
                    mode=mode,
                    stepik_lesson_id=int(live_lesson["id"]),
                    work_dir=report_dir / "materialized-visuals" / Path(source_path).stem,
                )
                binding = verify_visual_binding(
                    client,
                    record,
                    source_path=source_path,
                    expected_source_sha256=expected_source_sha,
                    expected_mode=mode,
                    stepik_lesson_id=int(live_lesson["id"]),
                )
                next_state = with_asset_record(next_state, source_path=source_path, record=record)

            bindings.append(binding)
            if identity is not None:
                artifact = _event_artifact(identity, status=status, kind="asset", target_id=target_id, source_path=source_path)
                asset_event_artifacts.append(artifact)
                safe_name = Path(source_path).name.replace(".", "-")
                write_json(report_dir / f"asset-deployment-event-{safe_name}.json", artifact)

        rendering = build_rendering_plan(
            repo_root=repo_root,
            lesson_id=target_id,
            source_steps=source_steps,
            asset_report=asset_report,
            bindings=bindings,
        )
        rendered_steps = list(require_render_ready(rendering))
        if len(rendered_steps) != len(lesson_manifest.get("steps", [])):
            raise VerifiedRenderingError(f"{target_id}: rendered step count не совпадает с canonical Stepik plan")
        desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=rendered_steps)

        current_snapshot = client.inspect_course(args.course_id)
        current_lesson = _live_lesson(
            current_snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_target_live(current_snapshot, current_lesson, expected_title)
        current_live_fp = live_lesson_fingerprint(current_lesson)
        incomplete_lessons = find_incomplete_object_events(store, object_id=target_id)
        if len(incomplete_lessons) > 1:
            raise DeploymentHistoryError(f"{target_id}: найдено несколько incomplete lesson events")

        result = None
        if incomplete_lessons:
            lesson_identity, lesson_records, summary = incomplete_lessons[0]
            if lesson_identity.source_sha != sha or lesson_identity.desired_fingerprint != desired_fp:
                raise DeploymentHistoryError(f"{target_id}: incomplete lesson event относится к другому current main/rendered desired")
            if summary.get("final_readback_confirmed"):
                lesson_record, lesson_status = _recover_final_state(lesson_records, label=target_id)
                if current_live_fp != desired_fp:
                    raise DeploymentHistoryError(f"{target_id}: live lesson больше не совпадает с final immutable history")
            else:
                if summary.get("ambiguous") or summary.get("readback_failed"):
                    raise DeploymentHistoryError(f"{target_id}: ambiguous/read-back failure запрещает automatic continuation")
                last_confirmed = summary.get("last_confirmed_operation_fingerprint")
                allow_partial = bool(last_confirmed and last_confirmed == current_live_fp)
                if summary.get("writes_started") and not allow_partial:
                    raise DeploymentHistoryError(f"{target_id}: live state не совпадает с last confirmed intermediate fingerprint")
                lesson_recorder = DeploymentRecorder(store, lesson_identity)
                result = execute_initial_upload_one(
                    client,
                    current_snapshot,
                    canonical_id=target_id,
                    expected_steps=rendered_steps,
                    module_position=int(module["position"]),
                    lesson_position=int(lesson_manifest["position"]),
                    expected_title=expected_title,
                    source_sha=sha,
                    recorder=lesson_recorder,
                    allow_partial_resume=allow_partial,
                )
                lesson_record = result.state_record or {}
                lesson_status = _final_status(lesson_recorder.records(refresh=True))
        else:
            _require_pristine_skeleton(current_lesson)
            lesson_identity = event_identity_from_environment(
                course_id=args.course_id,
                object_id=target_id,
                kind="lesson",
                source_sha=sha,
                desired_fingerprint=desired_fp,
                baseline_fingerprint=None,
                pending_first_sha=pending_first_sha,
            )
            lesson_recorder = DeploymentRecorder(store, lesson_identity)
            lesson_recorder.ensure_started(
                operation_type="lesson-initial-upload",
                state_before=None,
                expected_state={"desired_fingerprint": desired_fp, "source_sha": sha},
                stepik_object_ids={"lesson_id": int(current_lesson["id"])},
                fingerprint_before=current_live_fp,
            )
            result = execute_initial_upload_one(
                client,
                current_snapshot,
                canonical_id=target_id,
                expected_steps=rendered_steps,
                module_position=int(module["position"]),
                lesson_position=int(lesson_manifest["position"]),
                expected_title=expected_title,
                source_sha=sha,
                recorder=lesson_recorder,
                allow_partial_resume=False,
            )
            lesson_record = result.state_record or {}
            lesson_status = _final_status(lesson_recorder.records(refresh=True))

        if not lesson_record:
            raise DeploymentHistoryError(f"{target_id}: lesson baseline-after отсутствует")
        next_state = with_record(next_state, canonical_id=target_id, record=lesson_record)
        confirmed_at = str(lesson_record.get("applied_at") or _utc_now())
        next_state = close_lesson_pending(
            next_state,
            canonical_id=target_id,
            confirmed_at=confirmed_at,
            confirmation_status=lesson_status,
        )
        write_json(report_dir / "sync-state.next.json", next_state)
        write_json(report_dir / "asset-deployment-events.json", {"events": asset_event_artifacts})
        lesson_event_artifact = _event_artifact(
            lesson_identity,
            status=lesson_status,
            kind="lesson",
            target_id=target_id,
        )
        write_json(report_dir / "lesson-deployment-event.json", lesson_event_artifact)

        operations = [] if result is None else result.operations
        journal_lines = [
            f"### STAGING_BUILD_ONE: `{target_id}`",
            "",
            f"- source main SHA: `{sha}`",
            f"- Stepik lesson ID: `{current_lesson['id']}`",
            f"- lesson status: `{lesson_status}`",
            f"- lesson event: `{lesson_identity.event_id}`",
            f"- rendered fingerprint: `{desired_fp}`",
            f"- write operations: `{operations}`",
            f"- visual asset events: `{[item['event_id'] for item in asset_event_artifacts]}`",
            "",
            "Machine state должен быть patched только после final read-back; asset/lesson history затем получает MACHINE_STATE_COMMITTED.",
        ]
        (report_dir / "sync-journal.md").write_text("\n".join(journal_lines) + "\n", encoding="utf-8")

        report = build_report(
            mode="staging-build-one",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=count_snapshot(snapshot),
        )
        report.update(
            {
                "golden_profile_status": golden_status,
                "target_lesson": target_id,
                "stepik_lesson_id": int(current_lesson["id"]),
                "lesson_status": lesson_status,
                "lesson_event_id": lesson_identity.event_id,
                "write_operations": operations,
                "visual_asset_events": asset_event_artifacts,
                "rendered_steps": len(rendered_steps),
                "readback_verified": True,
                "blockers": [],
                "verdict": "PASS",
                "stepik_writes": len(operations) + len([item for item in asset_event_artifacts if item.get("status") == "APPLIED"]),
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
                "write_retry_policy": "no blind retry; inspect durable history and live state before rerun",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
