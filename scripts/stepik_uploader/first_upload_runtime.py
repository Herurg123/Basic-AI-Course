from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.attachment_materialization import AttachmentMaterializationError, file_sha256_bytes, materialize_attachment
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
    from stepik_uploader.writer import ContentWriteError, PLACEHOLDER_TEXT, _placeholder
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .attachment_materialization import AttachmentMaterializationError, file_sha256_bytes, materialize_attachment
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
    from .writer import ContentWriteError, PLACEHOLDER_TEXT, _placeholder

TARGET_ID = "M04-L01"
ASSET_PATH = "05_assets/M04/M04-L01/M04-L01-A01.txt"
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для first upload нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_lesson(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == TARGET_ID:
                return module, lesson
    raise ContentCompileError(f"В manifest отсутствует {TARGET_ID}")


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден section position={module_position}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1 or not isinstance(units[0].get("lesson"), dict):
        raise ContentWriteError(f"Не найден target unit {module_position}/{lesson_position}")
    return units[0]["lesson"]


def _assert_target_before_asset(snapshot: dict[str, Any], lesson: dict[str, Any], expected_title: str) -> None:
    if snapshot.get("course", {}).get("is_public") is not False:
        raise ContentWriteError("Initial upload разрешён только в непубличном черновом курсе")
    if lesson.get("is_public") is not False:
        raise ContentWriteError("Initial upload разрешён только в непубличном target lesson")
    if lesson.get("language") != "ru":
        raise ContentWriteError("Target lesson language не ru")
    if lesson.get("title") != expected_title:
        raise ContentWriteError(
            f"Target lesson title отличается: ожидается «{expected_title}», найдено «{lesson.get('title')}»"
        )


def _asset_row(asset_report: dict[str, Any]) -> dict[str, Any]:
    rows = [
        item for item in asset_report.get("resolutions", [])
        if item.get("lesson") == TARGET_ID and item.get("source_path") == ASSET_PATH
    ]
    if len(rows) != 1:
        raise AssetResolutionError(f"{TARGET_ID}: ожидается одна resolution для {ASSET_PATH}, найдено {len(rows)}")
    row = rows[0]
    if row.get("mode") != "stepik-attachment-upload" or row.get("route_resolved") is not True:
        raise AssetResolutionError(f"{ASSET_PATH}: attachment route не resolved")
    return row


def _verified_binding_from_record(client: StepikClient, record: dict[str, Any], expected_sha: str, lesson_id: int) -> AssetBinding:
    if record.get("source_path") != ASSET_PATH or record.get("source_sha256") != expected_sha:
        raise ContentWriteError("Asset baseline не соответствует текущему canonical source")
    if int(record.get("stepik_lesson_id", -1)) != int(lesson_id):
        raise ContentWriteError("Asset baseline относится к другому Stepik lesson")
    attachments = client.list_attachments(lesson_id=lesson_id)
    attachment_id = int(record.get("stepik_attachment_id", -1))
    matches = [item for item in attachments if int(item.get("id", -2)) == attachment_id]
    if len(matches) != 1:
        raise ContentWriteError("Asset baseline attachment ID больше не существует или неоднозначен")
    live_attachment = matches[0]
    if live_attachment.get("name") != record.get("filename"):
        raise ContentWriteError("Asset baseline filename отличается от live attachment")
    try:
        if int(live_attachment.get("size", -1)) != int(record.get("size", -2)):
            raise ContentWriteError("Asset baseline size отличается от live attachment")
    except (TypeError, ValueError) as exc:
        raise ContentWriteError("Asset baseline/live size повреждён") from exc
    live_file = str(live_attachment.get("file") or "")
    record_url = str(record.get("url") or "")
    if not live_file or urlsplit(record_url).path != live_file:
        raise ContentWriteError("Asset baseline URL больше не совпадает с live attachment file path")
    actual_sha = file_sha256_bytes(client.download_attachment(record_url))
    if actual_sha != expected_sha:
        raise ContentWriteError("Asset baseline URL больше не отдаёт canonical bytes")
    return AssetBinding(
        source_path=ASSET_PATH,
        source_sha256=expected_sha,
        url=record_url,
        storage=str(record["storage"]),
        verified=True,
    )


def _event_artifact(*, identity: Any, status: str, kind: str, source_sha_value: str, source_path: str | None = None) -> dict[str, Any]:
    payload = {
        "event_id": identity.event_id,
        "source_sha": source_sha_value,
        "status": status,
        "kind": kind,
    }
    if kind == "asset":
        payload["source_path"] = source_path
    else:
        payload["canonical_id"] = TARGET_ID
    return payload


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled first upload for M04-L01")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-uploader-live"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {"mode": "first-upload-m04-l01", "source_main_sha": sha, "course_id": args.course_id}
    if not args.confirm_write:
        report.update({"verdict": "BLOCKED", "blockers": ["explicit-confirm-write-required"], "stepik_writes": 0})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.json", snapshot)
        plan = plan_dry_run(manifest, snapshot)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        profile_blockers = validate_golden_profile(profile, snapshot, manifest)
        golden_status = mark_golden_profile_result(plan, profile_blockers)
        if golden_status != "confirmed" or plan.blockers:
            raise ContentWriteError("prewrite live guards не пройдены: " + "; ".join(sorted(set(profile_blockers + plan.blockers))))

        module, lesson_manifest = _manifest_lesson(manifest)
        if lesson_manifest.get("golden_read_only") or lesson_manifest.get("independence_sensitive") or lesson_manifest.get("f1_sensitive"):
            raise ContentWriteError("M04-L01 неожиданно попал в protected lesson class")
        expected_title = f"{TARGET_ID} — {lesson_manifest['title']}"
        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        _assert_target_before_asset(snapshot, live_lesson, expected_title)

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        existing_lesson_baseline = baseline_for(state, TARGET_ID)
        pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
        pending_first_sha = pending.get("first_pending_sha") if isinstance(pending, dict) else None

        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("Golden profile не содержит free_answer_source")
        source_steps = compile_lesson_source(
            repo_root,
            free_answer_source=free_answer_source,
            lesson_id=TARGET_ID,
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
        row = _asset_row(asset_report)
        expected_asset_sha = str(row["source_sha256"])
        store = _history_store(sha)

        asset_object_id = f"asset:{ASSET_PATH}"
        incomplete_assets = find_incomplete_object_events(store, object_id=asset_object_id)
        if len(incomplete_assets) > 1:
            raise DeploymentHistoryError("Найдено несколько incomplete asset events")
        asset_record = asset_binding_for(state, ASSET_PATH)
        asset_event_artifact: dict[str, Any] | None = None
        if asset_record is not None:
            binding = _verified_binding_from_record(client, asset_record, expected_asset_sha, int(live_lesson["id"]))
            asset_status = "BASELINE_REUSED"
            if incomplete_assets:
                asset_identity, asset_records, asset_summary = incomplete_assets[0]
                if asset_identity.source_sha != sha or asset_identity.desired_fingerprint != expected_asset_sha:
                    raise DeploymentHistoryError("Incomplete asset event относится к другому main/source hash")
                if not asset_summary.get("final_readback_confirmed"):
                    raise DeploymentHistoryError("Machine asset baseline существует без final asset read-back")
                recovered, asset_status = _recover_final_state(asset_records, label="Asset")
                if recovered != asset_record:
                    raise DeploymentHistoryError("Machine asset baseline не совпадает с immutable final history")
                asset_event_artifact = _event_artifact(
                    identity=asset_identity,
                    status=asset_status,
                    kind="asset",
                    source_sha_value=sha,
                    source_path=ASSET_PATH,
                )
        else:
            if incomplete_assets:
                asset_identity, asset_records, asset_summary = incomplete_assets[0]
                if asset_identity.source_sha != sha or asset_identity.desired_fingerprint != expected_asset_sha:
                    raise DeploymentHistoryError("Incomplete asset event относится к другому main/source hash")
                if asset_summary.get("final_readback_confirmed"):
                    recovered, asset_status = _recover_final_state(asset_records, label="Asset")
                    binding = _verified_binding_from_record(client, recovered, expected_asset_sha, int(live_lesson["id"]))
                    asset_record = recovered
                    asset_event_artifact = _event_artifact(
                        identity=asset_identity,
                        status=asset_status,
                        kind="asset",
                        source_sha_value=sha,
                        source_path=ASSET_PATH,
                    )
                else:
                    raise DeploymentHistoryError(
                        "Incomplete asset event не имеет final read-back; blind retry запрещён, требуется отдельный reconcile"
                    )
            else:
                if not (len(live_lesson.get("steps", [])) == 1 and _placeholder(live_lesson["steps"][0])):
                    raise ContentWriteError(
                        f"До нового attachment POST target lesson должен быть исходным skeleton placeholder «{PLACEHOLDER_TEXT}»"
                    )
                asset_identity = event_identity_from_environment(
                    course_id=args.course_id,
                    object_id=asset_object_id,
                    kind="asset",
                    source_sha=sha,
                    desired_fingerprint=expected_asset_sha,
                    baseline_fingerprint=None,
                    pending_first_sha=pending_first_sha,
                )
                asset_recorder = DeploymentRecorder(store, asset_identity)
                asset_record, asset_status = materialize_attachment(
                    client,
                    recorder=asset_recorder,
                    source_file=repo_root / ASSET_PATH,
                    source_path=ASSET_PATH,
                    expected_source_sha256=expected_asset_sha,
                    stepik_lesson_id=int(live_lesson["id"]),
                )
                binding = _verified_binding_from_record(client, asset_record, expected_asset_sha, int(live_lesson["id"]))
                asset_event_artifact = _event_artifact(
                    identity=asset_identity,
                    status=asset_status,
                    kind="asset",
                    source_sha_value=sha,
                    source_path=ASSET_PATH,
                )

        if not isinstance(asset_record, dict):
            raise DeploymentHistoryError("Verified asset baseline отсутствует")
        rendering = build_rendering_plan(
            repo_root=repo_root,
            lesson_id=TARGET_ID,
            source_steps=source_steps,
            asset_report=asset_report,
            bindings=[binding],
        )
        rendered_steps = list(require_render_ready(rendering))
        if len(rendered_steps) != len(lesson_manifest.get("steps", [])):
            raise VerifiedRenderingError("Rendered step count не совпадает с canonical Stepik plan")
        desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=rendered_steps)

        current_snapshot = client.inspect_course(args.course_id)
        current_lesson = _live_lesson(
            current_snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        current_live_fp = live_lesson_fingerprint(current_lesson)
        incomplete_lessons = find_incomplete_object_events(store, object_id=TARGET_ID)
        if len(incomplete_lessons) > 1:
            raise DeploymentHistoryError("Найдено несколько incomplete lesson first-upload events")

        result = None
        lesson_record: dict[str, Any]
        lesson_status: str
        if existing_lesson_baseline is not None:
            if int(existing_lesson_baseline.get("stepik_lesson_id", -1)) != int(current_lesson["id"]):
                raise DeploymentHistoryError("Machine lesson baseline относится к другому Stepik lesson")
            if existing_lesson_baseline.get("applied_fingerprint") != desired_fp or current_live_fp != desired_fp:
                raise DeploymentHistoryError("Machine lesson baseline/live больше не совпадают с текущим rendered desired")
            if not incomplete_lessons:
                raise ContentWriteError("M04-L01 initial upload уже полностью committed; дальнейшие изменения идут через sync route")
            lesson_identity, lesson_records, lesson_summary = incomplete_lessons[0]
            if lesson_identity.source_sha != sha or lesson_identity.desired_fingerprint != desired_fp:
                raise DeploymentHistoryError("Incomplete lesson event относится к другому main/rendered desired")
            if not lesson_summary.get("final_readback_confirmed"):
                raise DeploymentHistoryError("Machine lesson baseline существует без final lesson read-back")
            recovered, lesson_status = _recover_final_state(lesson_records, label="Lesson")
            if recovered != existing_lesson_baseline:
                raise DeploymentHistoryError("Machine lesson baseline не совпадает с immutable final history")
            lesson_record = recovered
        elif incomplete_lessons:
            lesson_identity, lesson_records, lesson_summary = incomplete_lessons[0]
            if lesson_identity.source_sha != sha or lesson_identity.desired_fingerprint != desired_fp:
                raise DeploymentHistoryError("Incomplete lesson event относится к другому main/rendered desired")
            if lesson_summary.get("final_readback_confirmed"):
                lesson_record, lesson_status = _recover_final_state(lesson_records, label="Lesson")
                if current_live_fp != desired_fp:
                    raise DeploymentHistoryError("Live lesson больше не совпадает с final history")
            else:
                if lesson_summary.get("ambiguous") or lesson_summary.get("readback_failed"):
                    raise DeploymentHistoryError("Lesson event содержит ambiguous/read-back failure; автоматическое продолжение запрещено")
                last_confirmed = lesson_summary.get("last_confirmed_operation_fingerprint")
                allow_partial = bool(last_confirmed and last_confirmed == current_live_fp)
                if lesson_summary.get("writes_started") and not allow_partial:
                    raise DeploymentHistoryError("Live lesson не совпадает с последним подтверждённым intermediate state")
                lesson_recorder = DeploymentRecorder(store, lesson_identity)
                result = execute_initial_upload_one(
                    client,
                    current_snapshot,
                    canonical_id=TARGET_ID,
                    expected_steps=rendered_steps,
                    module_position=int(module["position"]),
                    lesson_position=int(lesson_manifest["position"]),
                    expected_title=expected_title,
                    source_sha=sha,
                    recorder=lesson_recorder,
                    allow_partial_resume=allow_partial,
                )
                lesson_record = result.state_record or {}
                lesson_records = lesson_recorder.records(refresh=True)
                lesson_status = _final_status(lesson_records)
        else:
            lesson_identity = event_identity_from_environment(
                course_id=args.course_id,
                object_id=TARGET_ID,
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
                canonical_id=TARGET_ID,
                expected_steps=rendered_steps,
                module_position=int(module["position"]),
                lesson_position=int(lesson_manifest["position"]),
                expected_title=expected_title,
                source_sha=sha,
                recorder=lesson_recorder,
                allow_partial_resume=False,
            )
            lesson_record = result.state_record or {}
            lesson_records = lesson_recorder.records(refresh=True)
            lesson_status = _final_status(lesson_records)

        if not lesson_record:
            raise DeploymentHistoryError("Lesson baseline-after отсутствует")
        next_state = with_asset_record(state, source_path=ASSET_PATH, record=asset_record)
        next_state = with_record(next_state, canonical_id=TARGET_ID, record=lesson_record)
        confirmed_at = str(lesson_record.get("applied_at") or _utc_now())
        next_state = close_lesson_pending(
            next_state,
            canonical_id=TARGET_ID,
            confirmed_at=confirmed_at,
            confirmation_status=lesson_status,
        )
        write_json(report_dir / "sync-state.next.json", next_state)
        if asset_event_artifact is not None:
            write_json(report_dir / "asset-deployment-event.json", asset_event_artifact)
        lesson_event_artifact = _event_artifact(
            identity=lesson_identity,
            status=lesson_status,
            kind="lesson",
            source_sha_value=sha,
        )
        write_json(report_dir / "lesson-deployment-event.json", lesson_event_artifact)

        operations = [] if result is None else result.operations
        journal = "\n".join([
            f"### FIRST_UPLOAD: `{TARGET_ID}` verified rendering + attachment",
            "",
            f"- source main SHA: `{sha}`",
            f"- Stepik lesson ID: `{live_lesson['id']}`",
            f"- asset: `{ASSET_PATH}`",
            f"- asset status: `{asset_status}`",
            f"- asset URL: `{asset_record['url']}`",
            f"- lesson status: `{lesson_status}`",
            f"- lesson event: `{lesson_identity.event_id}`",
            f"- write operations: `{operations}`",
            f"- rendered fingerprint: `{desired_fp}`",
            "",
            "Machine state обновляется только после подтверждённых asset bytes и финального lesson read-back.",
        ]) + "\n"
        (report_dir / "sync-journal.md").write_text(journal, encoding="utf-8")

        report = build_report(
            mode="first-upload-m04-l01",
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=count_snapshot(snapshot),
        )
        report.update({
            "golden_profile_status": golden_status,
            "target_lesson": TARGET_ID,
            "stepik_lesson_id": int(live_lesson["id"]),
            "asset_status": asset_status,
            "asset_source_path": ASSET_PATH,
            "asset_url": asset_record["url"],
            "lesson_status": lesson_status,
            "lesson_event_id": lesson_identity.event_id,
            "write_operations": operations,
            "rendered_steps": len(rendered_steps),
            "readback_verified": True,
            "blockers": [],
            "verdict": "PASS",
        })
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
        AttachmentMaterializationError,
        DeploymentHistoryError,
        SyncStateError,
        VerifiedRenderingError,
    ) as exc:
        report.update({
            "verdict": "BLOCKED",
            "blockers": [str(exc)],
            "write_retry_policy": "no blind retry; inspect durable history and live state before rerun",
        })
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
