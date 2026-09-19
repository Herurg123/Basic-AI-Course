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
    from stepik_uploader.attachment_materialization import AttachmentMaterializationError, verify_attachment_binding, verify_attachment_capability
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.general_content import GeneralContentCompileError, compile_lesson_source
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from stepik_uploader.platform_profile import (
        PLATFORM_PROFILE_PATH,
        PlatformProfileError,
        free_answer_source as platform_free_answer_source,
        load_platform_profile,
    )
    from stepik_uploader.history_runtime import find_incomplete_object_events, final_confirmed_record
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reporting import write_json
    from stepik_uploader.staging_build_runtime import (
        ASSET_POLICY_PATH,
        _assert_no_unknown_same_name,
        _assert_target_live,
        _credentials,
        _event_artifact,
        _history_store,
        _learner_step_count,
        _live_lesson,
        _manifest_lesson,
        _recover_final_state,
        _safe_prewrite_retry,
        _synthetic_preflight_binding,
        _utc_now,
    )
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import (
        SyncStateError,
        asset_binding_for,
        assess_sync,
        baseline_for,
        close_lesson_pending,
        load_state,
        with_asset_record,
        with_record,
    )
    from stepik_uploader.verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from stepik_uploader.visual_materialization import (
        VisualMaterializationError,
        materialize_visual,
        prepare_visual_file,
        verify_visual_binding,
    )
    from stepik_uploader.writer import ContentWriteError, execute_content_sync_one
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .attachment_materialization import AttachmentMaterializationError, verify_attachment_binding, verify_attachment_capability
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .general_content import GeneralContentCompileError, compile_lesson_source
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        event_identity_from_environment,
        summarize_event,
    )
    from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
    from .platform_profile import (
        PLATFORM_PROFILE_PATH,
        PlatformProfileError,
        free_answer_source as platform_free_answer_source,
        load_platform_profile,
    )
    from .history_runtime import find_incomplete_object_events, final_confirmed_record
    from .planner import plan_dry_run
    from .reporting import write_json
    from .staging_build_runtime import (
        ASSET_POLICY_PATH,
        _assert_no_unknown_same_name,
        _assert_target_live,
        _credentials,
        _event_artifact,
        _history_store,
        _learner_step_count,
        _live_lesson,
        _manifest_lesson,
        _recover_final_state,
        _safe_prewrite_retry,
        _synthetic_preflight_binding,
        _utc_now,
    )
    from .stepik_uploader import source_sha
    from .sync_state import (
        SyncStateError,
        asset_binding_for,
        assess_sync,
        baseline_for,
        close_lesson_pending,
        load_state,
        with_asset_record,
        with_record,
    )
    from .verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from .visual_materialization import (
        VisualMaterializationError,
        materialize_visual,
        prepare_visual_file,
        verify_visual_binding,
    )
    from .writer import ContentWriteError, execute_content_sync_one


COURSE_ID = 299189
SAFE_ASSESSMENT_STATUSES = {"IN_SYNC", "UPDATE_REQUIRED"}


def _assert_refresh_target_live(snapshot: dict[str, Any], lesson: dict[str, Any]) -> None:
    """Validate immutable safety metadata while allowing a baseline-proven title migration."""
    course = snapshot.get("course", {})
    if course.get("is_public") is not False:
        raise ContentWriteError("Refresh разрешён только в private course")
    if course.get("language") not in {None, "ru"}:
        raise ContentWriteError("Course language неожиданно отличается от ru")
    if lesson.get("is_public") is not False:
        raise ContentWriteError("Refresh разрешён только для private target lesson")
    if lesson.get("language") != "ru":
        raise ContentWriteError("Target lesson language не ru")
    if not isinstance(lesson.get("title"), str) or not str(lesson.get("title")).strip():
        raise ContentWriteError("Target lesson title отсутствует или некорректен")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded content refresh for an already-baselined private Stepik lesson")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _step_ids(lesson: dict[str, Any]) -> list[int]:
    result: list[int] = []
    for item in lesson.get("steps", []):
        source = item.get("step_source") if isinstance(item, dict) else None
        if not isinstance(source, dict) or not isinstance(source.get("id"), int):
            raise ContentWriteError("Live lesson не содержит однозначные existing step IDs")
        result.append(int(source["id"]))
    return result


def _version_suffix(source_sha256: str) -> str:
    value = source_sha256.removeprefix("sha256:")
    if len(value) < 12:
        raise VisualMaterializationError("Visual source SHA слишком короткий для versioned filename")
    return value[:12]



VISUAL_MATERIALIZATION_MODES = {"stepik-image-upload", "rasterize-png-stepik-image"}


def _all_materialization_rows(asset_report: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
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
    return [by_source[key] for key in sorted(by_source)]


def _refresh_asset_inputs(
    *,
    client: StepikClient,
    state: dict[str, Any],
    asset_report: dict[str, Any],
    target_id: str,
    live_lesson_id: int,
) -> tuple[list[dict[str, Any]], list[AssetBinding], list[dict[str, Any]]]:
    """Split visual writes from already-confirmed generic attachments.

    Existing non-visual attachments are verified and reused from machine state.
    A changed/missing generic attachment baseline remains fail-closed; lesson-level
    refresh never guesses or adopts an attachment by filename alone.
    """
    visual_rows: list[dict[str, Any]] = []
    bindings: list[AssetBinding] = []
    checks: list[dict[str, Any]] = []
    for row in _all_materialization_rows(asset_report, target_id):
        source_path = str(row["source_path"])
        source_sha = str(row["source_sha256"])
        mode = str(row["mode"])
        if mode in VISUAL_MATERIALIZATION_MODES:
            visual_rows.append(row)
            continue
        if mode != "stepik-attachment-upload":
            raise AssetResolutionError(f"{target_id}: unsupported materialization mode {mode!r} for {source_path}")
        record = asset_binding_for(state, source_path)
        if not isinstance(record, dict):
            raise AttachmentMaterializationError(
                f"{source_path}: existing lesson attachment требует confirmed machine baseline before refresh"
            )
        if record.get("source_sha256") != source_sha:
            raise AttachmentMaterializationError(
                f"{source_path}: canonical attachment bytes changed; generic versioned replacement route is not yet proven"
            )
        binding = verify_attachment_binding(
            client,
            record,
            source_path=source_path,
            expected_source_sha256=source_sha,
            stepik_lesson_id=live_lesson_id,
        )
        bindings.append(binding)
        checks.append({"source_path": source_path, "status": "VERIFIED_ATTACHMENT_BASELINE_REUSE"})
    return visual_rows, bindings, checks


def _refresh_materialization_plan(
    *,
    repo_root: Path,
    report_dir: Path,
    rows: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for row in rows:
        source_path = str(row["source_path"])
        source_sha = str(row["source_sha256"])
        mode = str(row["mode"])
        previous = asset_binding_for(state, source_path)
        replacement = bool(previous is not None and previous.get("source_sha256") != source_sha)
        if previous is not None and previous.get("materialization_mode") != mode:
            raise VisualMaterializationError(
                f"{source_path}: publication mode изменился; automatic attachment migration не разрешён"
            )
        suffix = _version_suffix(source_sha) if replacement else None
        material_file, materialized_sha, materialization_fp = prepare_visual_file(
            source_file=repo_root / source_path,
            source_path=source_path,
            expected_source_sha256=source_sha,
            mode=mode,
            work_dir=report_dir / "prepared-visuals" / Path(source_path).stem,
            filename_suffix=suffix,
        )
        plan.append(
            {
                "source_path": source_path,
                "source_sha256": source_sha,
                "mode": mode,
                "materialized_filename": material_file.name,
                "materialized_sha256": materialized_sha,
                "materialization_fingerprint": materialization_fp,
                "filename_suffix": suffix,
                "replacement": replacement,
                "previous_source_sha256": previous.get("source_sha256") if isinstance(previous, dict) else None,
                "previous_attachment_id": previous.get("stepik_attachment_id") if isinstance(previous, dict) else None,
            }
        )
    return plan


def _verify_previous_visual(
    client: StepikClient,
    record: dict[str, Any],
    *,
    source_path: str,
    live_lesson_id: int,
) -> None:
    previous_sha = str(record.get("source_sha256") or "")
    previous_mode = str(record.get("materialization_mode") or "")
    if not previous_sha or not previous_mode:
        raise VisualMaterializationError(f"{source_path}: previous visual baseline неполон")
    verify_visual_binding(
        client,
        record,
        source_path=source_path,
        expected_source_sha256=previous_sha,
        expected_mode=previous_mode,
        stepik_lesson_id=live_lesson_id,
    )


def _assert_asset_event_scope(identity: Any, *, sha: str, desired: str, source_path: str) -> None:
    if identity.source_sha != sha or identity.desired_fingerprint != desired:
        raise DeploymentHistoryError(
            f"{source_path}: incomplete asset event относится к другому source/materialization"
        )


def _preflight_assets(
    *,
    client: StepikClient,
    state: dict[str, Any],
    store: Any,
    material_rows: list[dict[str, Any]],
    material_plan: list[dict[str, Any]],
    live_lesson_id: int,
    target_id: str,
    sha: str,
) -> tuple[list[AssetBinding], list[dict[str, Any]]]:
    by_source = {str(item["source_path"]): item for item in material_plan}
    bindings: list[AssetBinding] = []
    checks: list[dict[str, Any]] = []

    for row in material_rows:
        source_path = str(row["source_path"])
        source_sha = str(row["source_sha256"])
        mode = str(row["mode"])
        prepared = by_source[source_path]
        desired = str(prepared["materialization_fingerprint"])
        record = asset_binding_for(state, source_path)
        incomplete = find_incomplete_object_events(store, object_id=f"asset:{source_path}")
        if len(incomplete) > 1:
            raise DeploymentHistoryError(f"{source_path}: найдено несколько incomplete asset events")

        if record is not None and record.get("source_sha256") == source_sha:
            binding = verify_visual_binding(
                client,
                record,
                source_path=source_path,
                expected_source_sha256=source_sha,
                expected_mode=mode,
                stepik_lesson_id=live_lesson_id,
            )
            if incomplete:
                identity, records, summary = incomplete[0]
                _assert_asset_event_scope(identity, sha=sha, desired=desired, source_path=source_path)
                if not summary.get("final_readback_confirmed"):
                    raise DeploymentHistoryError(
                        f"{source_path}: machine baseline существует, но incomplete asset history не закрыт"
                    )
                recovered, _ = _recover_final_state(records, label=source_path)
                if recovered != record:
                    raise DeploymentHistoryError(
                        f"{source_path}: machine baseline не совпадает с immutable final asset history"
                    )
            bindings.append(binding)
            checks.append({"source_path": source_path, "status": "VERIFIED_BASELINE_REUSE"})
            continue

        if record is not None:
            _verify_previous_visual(client, record, source_path=source_path, live_lesson_id=live_lesson_id)

        if incomplete:
            identity, records, summary = incomplete[0]
            _assert_asset_event_scope(identity, sha=sha, desired=desired, source_path=source_path)
            if summary.get("final_readback_confirmed"):
                recovered, _ = _recover_final_state(records, label=source_path)
                binding = verify_visual_binding(
                    client,
                    recovered,
                    source_path=source_path,
                    expected_source_sha256=source_sha,
                    expected_mode=mode,
                    stepik_lesson_id=live_lesson_id,
                )
                bindings.append(binding)
                checks.append({"source_path": source_path, "status": "RECOVERABLE_FINAL_HISTORY"})
                continue
            if not _safe_prewrite_retry(summary):
                raise DeploymentHistoryError(
                    f"{source_path}: prior asset write started without final proof; automatic retry запрещён"
                )
            status = "SAFE_VERSIONED_RETRY_BEFORE_WRITE" if prepared["replacement"] else "SAFE_RETRY_BEFORE_WRITE"
        else:
            status = "READY_VERSIONED_REPLACEMENT" if prepared["replacement"] else "READY_TO_MATERIALIZE"

        verify_attachment_capability(client)
        _assert_no_unknown_same_name(
            client,
            lesson_id=live_lesson_id,
            materialized_filename=str(prepared["materialized_filename"]),
            target_id=target_id,
        )
        bindings.append(_synthetic_preflight_binding(prepared))
        checks.append(
            {
                "source_path": source_path,
                "status": status,
                "materialized_filename": prepared["materialized_filename"],
                "previous_attachment_id": prepared.get("previous_attachment_id"),
            }
        )

    return bindings, checks


def _materialize_assets(
    *,
    client: StepikClient,
    state: dict[str, Any],
    store: Any,
    material_rows: list[dict[str, Any]],
    material_plan: list[dict[str, Any]],
    live_lesson_id: int,
    target_id: str,
    sha: str,
    pending_first_sha: str | None,
    repo_root: Path,
    report_dir: Path,
) -> tuple[list[AssetBinding], dict[str, Any], list[dict[str, Any]]]:
    by_source = {str(item["source_path"]): item for item in material_plan}
    bindings: list[AssetBinding] = []
    next_state = state
    artifacts: list[dict[str, Any]] = []

    for row in material_rows:
        source_path = str(row["source_path"])
        source_sha = str(row["source_sha256"])
        mode = str(row["mode"])
        prepared = by_source[source_path]
        desired = str(prepared["materialization_fingerprint"])
        record = asset_binding_for(state, source_path)
        incomplete = find_incomplete_object_events(store, object_id=f"asset:{source_path}")
        if len(incomplete) > 1:
            raise DeploymentHistoryError(f"{source_path}: найдено несколько incomplete asset events")

        if record is not None and record.get("source_sha256") == source_sha:
            binding = verify_visual_binding(
                client,
                record,
                source_path=source_path,
                expected_source_sha256=source_sha,
                expected_mode=mode,
                stepik_lesson_id=live_lesson_id,
            )
            bindings.append(binding)
            continue

        if record is not None:
            _verify_previous_visual(client, record, source_path=source_path, live_lesson_id=live_lesson_id)

        identity = None
        status = "APPLIED"
        new_record: dict[str, Any]
        if incomplete:
            identity, records, summary = incomplete[0]
            _assert_asset_event_scope(identity, sha=sha, desired=desired, source_path=source_path)
            if summary.get("final_readback_confirmed"):
                new_record, status = _recover_final_state(records, label=source_path)
            elif _safe_prewrite_retry(summary):
                recorder = DeploymentRecorder(store, identity)
                new_record, status = materialize_visual(
                    client,
                    recorder=recorder,
                    source_file=repo_root / source_path,
                    source_path=source_path,
                    expected_source_sha256=source_sha,
                    mode=mode,
                    stepik_lesson_id=live_lesson_id,
                    work_dir=report_dir / "materialized-visuals" / Path(source_path).stem,
                    filename_suffix=prepared.get("filename_suffix"),
                )
            else:
                raise DeploymentHistoryError(
                    f"{source_path}: prior asset write started without final proof; automatic retry запрещён"
                )
        else:
            baseline_fp = None
            if isinstance(record, dict):
                raw = record.get("materialization_fingerprint")
                baseline_fp = str(raw) if isinstance(raw, str) else None
            identity = event_identity_from_environment(
                course_id=COURSE_ID,
                object_id=f"asset:{source_path}",
                kind="asset",
                source_sha=sha,
                desired_fingerprint=desired,
                baseline_fingerprint=baseline_fp,
                pending_first_sha=pending_first_sha,
            )
            recorder = DeploymentRecorder(store, identity)
            new_record, status = materialize_visual(
                client,
                recorder=recorder,
                source_file=repo_root / source_path,
                source_path=source_path,
                expected_source_sha256=source_sha,
                mode=mode,
                stepik_lesson_id=live_lesson_id,
                work_dir=report_dir / "materialized-visuals" / Path(source_path).stem,
                filename_suffix=prepared.get("filename_suffix"),
            )

        binding = verify_visual_binding(
            client,
            new_record,
            source_path=source_path,
            expected_source_sha256=source_sha,
            expected_mode=mode,
            stepik_lesson_id=live_lesson_id,
        )
        next_state = with_asset_record(next_state, source_path=source_path, record=new_record)
        bindings.append(binding)
        if identity is not None:
            artifact = _event_artifact(
                identity,
                status=status,
                kind="asset",
                target_id=target_id,
                source_path=source_path,
            )
            artifacts.append(artifact)
            safe_name = Path(source_path).name.replace(".", "-")
            write_json(report_dir / f"asset-deployment-event-{safe_name}.json", artifact)

    return bindings, next_state, artifacts


def _assessment_or_history_gate(
    *,
    target_id: str,
    assessment: Any,
    incomplete: list[Any],
    desired_fp: str,
    sha: str,
) -> tuple[str, Any | None, list[dict[str, Any]], dict[str, Any] | None]:
    if len(incomplete) > 1:
        raise DeploymentHistoryError(f"{target_id}: найдено несколько incomplete lesson events")
    if not incomplete:
        if assessment.status not in SAFE_ASSESSMENT_STATUSES:
            raise ContentWriteError(
                f"{target_id}: refresh blocked: {assessment.status}: {'; '.join(assessment.reasons)}"
            )
        return "FRESH", None, [], None

    identity, records, summary = incomplete[0]
    if identity.source_sha != sha or identity.desired_fingerprint != desired_fp:
        raise DeploymentHistoryError(
            f"{target_id}: incomplete lesson event относится к другому source/rendered desired"
        )
    if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
        raise DeploymentHistoryError(f"{target_id}: unsafe prior lesson history требует owner reconcile")
    if summary.get("final_readback_confirmed"):
        final_live = summary.get("final_live_fingerprint") or summary.get("final_fingerprint")
        if assessment.live_fingerprint != final_live:
            raise DeploymentHistoryError(
                f"{target_id}: final history доказан, но live больше не совпадает с final read-back"
            )
        return "FINAL_PROVEN", identity, records, summary
    if summary.get("writes_started"):
        last = summary.get("last_confirmed_operation_fingerprint")
        if not isinstance(last, str) or assessment.live_fingerprint != last:
            raise DeploymentHistoryError(
                f"{target_id}: partial history не совпадает с last confirmed intermediate fingerprint"
            )
        return "PARTIAL_CONFIRMED", identity, records, summary
    if not _safe_prewrite_retry(summary):
        raise DeploymentHistoryError(f"{target_id}: prior lesson event не является safe prewrite retry")
    return "STARTED_BEFORE_WRITE", identity, records, summary


def _journal(
    *,
    target_id: str,
    sha: str,
    lesson_id: int,
    status: str,
    event_id: str,
    operations: list[dict[str, Any]],
    asset_events: list[dict[str, Any]],
    recovered_state_only: bool,
) -> str:
    return "\n".join(
        [
            f"### CONTENT_REFRESH: `{target_id}`",
            "",
            f"- source main SHA: `{sha}`",
            f"- Stepik lesson ID: `{lesson_id}`",
            f"- lesson event: `{event_id}`",
            f"- status: `{status}`",
            f"- updated existing steps: `{[op.get('position') for op in operations if op.get('action') == 'UPDATE_STEP']}`",
            "- created/deleted/reordered lesson steps: `0`",
            f"- asset deployment events: `{[item.get('event_id') for item in asset_events]}`",
            f"- state-only recovery: `{str(recovered_state_only).lower()}`",
            "",
            "Refresh разрешён только когда live lesson совпадает с подтверждённым baseline либо с доказанным WAL prefix. Versioned visual replacement никогда не удаляет прежний attachment.",
        ]
    ) + "\n"


def main() -> int:
    args = parse_args()
    target_id = str(args.target_id).strip()
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    lesson_recorder: DeploymentRecorder | None = None
    report: dict[str, Any] = {
        "mode": "staging-refresh-one",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "target_lesson": target_id,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }

    try:
        if args.course_id != COURSE_ID:
            raise ContentWriteError(f"staging-refresh-one разрешён только для course_id={COURSE_ID}")
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        module, lesson_manifest = _manifest_lesson(manifest, target_id)
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        baseline = baseline_for(state, target_id)
        if not isinstance(baseline, dict):
            raise ContentWriteError(f"{target_id}: refresh требует подтверждённый deployment baseline")
        pending = state.get("pending", {}).get("lessons", {}).get(target_id)
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise ContentWriteError(f"{target_id}: refresh разрешён только для текущего PENDING")
        pending_first_sha = str(pending.get("first_pending_sha") or "") or None

        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        plan = plan_dry_run(manifest, snapshot)
        if plan.blockers:
            raise ContentWriteError(
                "pre-refresh structural guards не пройдены: " + "; ".join(sorted(set(plan.blockers)))
            )
        platform_profile = load_platform_profile(repo_root / PLATFORM_PROFILE_PATH, course_id=args.course_id)

        expected_title = str(lesson_manifest["title"])
        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_refresh_target_live(snapshot, live_lesson)
        if int(baseline.get("stepik_lesson_id", -1)) != int(live_lesson.get("id", -2)):
            raise ContentWriteError(f"{target_id}: live lesson ID отличается от machine baseline")

        free_answer_source = platform_free_answer_source(platform_profile)
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
        material_rows, fixed_bindings, fixed_asset_checks = _refresh_asset_inputs(
            client=client,
            state=state,
            asset_report=asset_report,
            target_id=target_id,
            live_lesson_id=int(live_lesson["id"]),
        )
        material_plan = _refresh_materialization_plan(
            repo_root=repo_root,
            report_dir=report_dir,
            rows=material_rows,
            state=state,
        )
        write_json(report_dir / "visual-materialization-plan.json", {"target": target_id, "items": material_plan})
        store = _history_store(sha)

        visual_preflight_bindings, visual_asset_checks = _preflight_assets(
            client=client,
            state=state,
            store=store,
            material_rows=material_rows,
            material_plan=material_plan,
            live_lesson_id=int(live_lesson["id"]),
            target_id=target_id,
            sha=sha,
        )
        preflight_bindings = [*fixed_bindings, *visual_preflight_bindings]
        asset_checks = [*fixed_asset_checks, *visual_asset_checks]
        preflight_rendering = build_rendering_plan(
            repo_root=repo_root,
            lesson_id=target_id,
            source_steps=source_steps,
            asset_report=asset_report,
            bindings=preflight_bindings,
        )
        preflight_steps = list(require_render_ready(preflight_rendering))
        if len(preflight_steps) != _learner_step_count(lesson_manifest):
            raise VerifiedRenderingError(
                f"{target_id}: rendered learner step count не совпадает с canonical learner plan"
            )
        preflight_assessment = assess_sync(
            canonical_id=target_id,
            live_lesson=live_lesson,
            expected_title=expected_title,
            expected_steps=preflight_steps,
            baseline=baseline,
        )
        preflight_desired_fp = compiled_lesson_fingerprint(
            expected_title=expected_title,
            expected_steps=preflight_steps,
        )
        incomplete_preflight = find_incomplete_object_events(store, object_id=target_id)
        _assessment_or_history_gate(
            target_id=target_id,
            assessment=preflight_assessment,
            incomplete=incomplete_preflight,
            desired_fp=preflight_desired_fp,
            sha=sha,
        )

        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "platform_profile_status": "confirmed",
                    "target_stepik_lesson_id": int(live_lesson["id"]),
                    "baseline_fingerprint": preflight_assessment.baseline_fingerprint,
                    "live_fingerprint": preflight_assessment.live_fingerprint,
                    "preflight_status": preflight_assessment.status,
                    "changed_step_positions": list(preflight_assessment.changed_step_positions),
                    "materialization": asset_checks,
                    "preflight_rendered_steps": len(preflight_steps),
                    "stepik_writes": 0,
                    "blockers": [],
                }
            )
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        visual_bindings, state_after_assets, asset_event_artifacts = _materialize_assets(
            client=client,
            state=state,
            store=store,
            material_rows=material_rows,
            material_plan=material_plan,
            live_lesson_id=int(live_lesson["id"]),
            target_id=target_id,
            sha=sha,
            pending_first_sha=pending_first_sha,
            repo_root=repo_root,
            report_dir=report_dir,
        )
        bindings = [*fixed_bindings, *visual_bindings]
        rendering = build_rendering_plan(
            repo_root=repo_root,
            lesson_id=target_id,
            source_steps=source_steps,
            asset_report=asset_report,
            bindings=bindings,
        )
        rendered_steps = list(require_render_ready(rendering))
        if len(rendered_steps) != _learner_step_count(lesson_manifest):
            raise VerifiedRenderingError(
                f"{target_id}: rendered learner step count не совпадает с canonical learner plan"
            )
        desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=rendered_steps)

        current_snapshot = client.inspect_course(args.course_id)
        current_lesson = _live_lesson(
            current_snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_refresh_target_live(current_snapshot, current_lesson)
        assessment = assess_sync(
            canonical_id=target_id,
            live_lesson=current_lesson,
            expected_title=expected_title,
            expected_steps=rendered_steps,
            baseline=baseline,
        )
        incomplete = find_incomplete_object_events(store, object_id=target_id)
        history_state, lesson_identity, lesson_records, history_summary = _assessment_or_history_gate(
            target_id=target_id,
            assessment=assessment,
            incomplete=incomplete,
            desired_fp=desired_fp,
            sha=sha,
        )

        recovered_state_only = False
        operations: list[dict[str, Any]] = []
        if history_state == "FINAL_PROVEN":
            lesson_record, lesson_status = _recover_final_state(lesson_records, label=target_id)
            next_state = with_record(state_after_assets, canonical_id=target_id, record=lesson_record)
            confirmed_at = str(final_confirmed_record(lesson_records).get("confirmed_at") or _utc_now())
            next_state = close_lesson_pending(
                next_state,
                canonical_id=target_id,
                confirmed_at=confirmed_at,
                confirmation_status=lesson_status,
            )
            recovered_state_only = True
        else:
            if lesson_identity is None:
                lesson_identity = event_identity_from_environment(
                    course_id=args.course_id,
                    object_id=target_id,
                    kind="lesson",
                    source_sha=sha,
                    desired_fingerprint=desired_fp,
                    baseline_fingerprint=assessment.baseline_fingerprint,
                    pending_first_sha=pending_first_sha,
                )
                lesson_records = []
                history_summary = None
            lesson_recorder = DeploymentRecorder(store, lesson_identity)
            if not any(row.get("phase") == "EVENT_STARTED" for row in lesson_records):
                lesson_recorder.ensure_started(
                    operation_type="lesson-content-refresh",
                    state_before=baseline,
                    expected_state={"desired_fingerprint": desired_fp, "source_sha": sha},
                    stepik_object_ids={
                        "lesson_id": int(current_lesson["id"]),
                        "step_ids": _step_ids(current_lesson),
                    },
                    fingerprint_before=assessment.live_fingerprint,
                )
                lesson_records = lesson_recorder.records(refresh=True)
                history_summary = summarize_event(lesson_records)

            if history_state in {"FRESH", "STARTED_BEFORE_WRITE"} and assessment.status == "IN_SYNC":
                lesson_record = baseline
                lesson_status = "NOOP_CONFIRMED"
                if not (history_summary or {}).get("final_readback_confirmed"):
                    lesson_recorder.final_readback(
                        fingerprint_after=assessment.desired_fingerprint,
                        observed_live_fingerprint=assessment.live_fingerprint,
                        stepik_object_ids={
                            "lesson_id": int(current_lesson["id"]),
                            "step_ids": _step_ids(current_lesson),
                        },
                        status=lesson_status,
                        baseline_after=lesson_record,
                    )
            else:
                recovery_fp = None
                if history_state == "PARTIAL_CONFIRMED":
                    recovery_fp = (history_summary or {}).get("last_confirmed_operation_fingerprint")
                result = execute_content_sync_one(
                    client,
                    current_snapshot,
                    canonical_id=target_id,
                    expected_steps=rendered_steps,
                    module_position=int(module["position"]),
                    lesson_position=int(lesson_manifest["position"]),
                    expected_title=expected_title,
                    baseline=baseline,
                    source_sha=sha,
                    recorder=lesson_recorder,
                    recovery_expected_live_fingerprint=recovery_fp,
                )
                if result.state_record is None or not result.verified:
                    raise ContentWriteError(f"{target_id}: writer не сформировал verified final state")
                lesson_record = result.state_record
                operations = list(result.operations)
                lesson_status = "APPLIED" if operations else "NOOP_CONFIRMED"
                if result.after_snapshot is not None:
                    write_json(report_dir / "course-snapshot.after.json", result.after_snapshot)

            confirmed_at = _utc_now()
            next_state = state_after_assets
            if lesson_status == "APPLIED":
                next_state = with_record(next_state, canonical_id=target_id, record=lesson_record)
            next_state = close_lesson_pending(
                next_state,
                canonical_id=target_id,
                confirmed_at=confirmed_at,
                confirmation_status=lesson_status,
            )

        if lesson_identity is None:
            raise DeploymentHistoryError(f"{target_id}: отсутствует lesson deployment identity")
        write_json(report_dir / "sync-state.next.json", next_state)
        lesson_event = _event_artifact(
            lesson_identity,
            status=lesson_status,
            kind="lesson",
            target_id=target_id,
        )
        write_json(report_dir / "lesson-deployment-event.json", lesson_event)
        (report_dir / "sync-journal.md").write_text(
            _journal(
                target_id=target_id,
                sha=sha,
                lesson_id=int(lesson_record["stepik_lesson_id"]),
                status=lesson_status,
                event_id=lesson_identity.event_id,
                operations=operations,
                asset_events=asset_event_artifacts,
                recovered_state_only=recovered_state_only,
            ),
            encoding="utf-8",
        )
        report.update(
            {
                "verdict": "PASS",
                "platform_profile_status": "confirmed",
                "lesson_status": lesson_status,
                "lesson_event_id": lesson_identity.event_id,
                "stepik_lesson_id": int(lesson_record["stepik_lesson_id"]),
                "write_operations": operations,
                "updated": sum(1 for op in operations if op.get("action") == "UPDATE_STEP"),
                "created": 0,
                "deleted": 0,
                "readback_verified": True,
                "state_only_recovery": recovered_state_only,
                "asset_events": asset_event_artifacts,
                "versioned_visual_replacements": [
                    item for item in material_plan if item.get("replacement") is True
                ],
                "stepik_writes": len(operations) + len(
                    [item for item in asset_event_artifacts if item.get("status") == "APPLIED"]
                ),
                "blockers": [],
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        RuntimeError,
        StepikAPIError,
        CanonicalBuildError,
        GeneralContentCompileError,
        PlatformProfileError,
        ContentWriteError,
        AssetResolutionError,
        DeploymentHistoryError,
        SyncStateError,
        VerifiedRenderingError,
        VisualMaterializationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        if lesson_recorder is not None:
            try:
                records = lesson_recorder.records(refresh=True)
                summary = summarize_event(records)
                started = any(row.get("phase") == "EVENT_STARTED" for row in records)
                if started and not summary.get("final_readback_confirmed") and not any(
                    str(phase).startswith("FAILED_") for phase in summary.get("phases", [])
                ):
                    lesson_recorder.failure(
                        reason_code=f"refresh-runtime-{exc.__class__.__name__.lower()}",
                        before_any_write=not summary.get("external_write_started"),
                    )
            except DeploymentHistoryError:
                pass
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "write_retry_policy": "no blind retry; inspect immutable history and exact live state",
            }
        )
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
