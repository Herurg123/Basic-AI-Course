from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.attachment_materialization import file_sha256_bytes
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import ContentCompileError
    from stepik_uploader.deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore, event_identity_from_environment
    from stepik_uploader.fingerprints import compiled_lesson_fingerprint
    from stepik_uploader.general_content import compile_lesson_source
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.history_runtime import find_incomplete_object_events, final_confirmed_record
    from stepik_uploader.learner_hygiene_writer import execute_tracked_learner_hygiene
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, asset_binding_for, baseline_for, close_lesson_pending, load_state, with_record
    from stepik_uploader.title_hygiene import TitleHygieneError, TitleOperation, execute_title_only_operation, legacy_title, plan_title_hygiene, title_fingerprint
    from stepik_uploader.verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from stepik_uploader.writer import ContentWriteError
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .attachment_materialization import file_sha256_bytes
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError
    from .deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore, event_identity_from_environment
    from .fingerprints import compiled_lesson_fingerprint
    from .general_content import compile_lesson_source
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .history_runtime import find_incomplete_object_events, final_confirmed_record
    from .learner_hygiene_writer import execute_tracked_learner_hygiene
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, asset_binding_for, baseline_for, close_lesson_pending, load_state, with_record
    from .title_hygiene import TitleHygieneError, TitleOperation, execute_title_only_operation, legacy_title, plan_title_hygiene, title_fingerprint
    from .verified_rendering import AssetBinding, VerifiedRenderingError, build_rendering_plan, require_render_ready
    from .writer import ContentWriteError

COURSE_ID = 299189
TRACKED_HYGIENE_LESSONS = {"M02-L01", "M04-L01"}
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Owner-dispatched learner-facing Stepik hygiene")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, default=Path("artifacts/stepik-learner-hygiene"))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для learner hygiene нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_index(manifest: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    result: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            result[str(lesson["canonical_id"])] = (module, lesson)
    return result


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден section position={module_position}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1 or not isinstance(units[0].get("lesson"), dict):
        raise ContentWriteError(f"Не найден lesson {module_position}/{lesson_position}")
    return units[0]["lesson"]


def _verified_binding(
    client: StepikClient,
    *,
    state: dict[str, Any],
    row: dict[str, Any],
    stepik_lesson_id: int,
) -> AssetBinding:
    source_path = str(row.get("source_path") or "")
    expected_sha = str(row.get("source_sha256") or "")
    record = asset_binding_for(state, source_path)
    if not isinstance(record, dict):
        raise ContentWriteError(f"{source_path}: hygiene route не материализует новые assets; verified baseline отсутствует")
    if record.get("source_sha256") != expected_sha:
        raise ContentWriteError(f"{source_path}: asset baseline относится к другому source hash")
    if int(record.get("stepik_lesson_id", -1)) != int(stepik_lesson_id):
        raise ContentWriteError(f"{source_path}: asset baseline относится к другому Stepik lesson")
    attachments = client.list_attachments(lesson_id=stepik_lesson_id)
    attachment_id = int(record.get("stepik_attachment_id", -1))
    matches = [item for item in attachments if int(item.get("id", -2)) == attachment_id]
    if len(matches) != 1:
        raise ContentWriteError(f"{source_path}: verified attachment ID исчез или неоднозначен")
    live = matches[0]
    if live.get("name") != record.get("filename"):
        raise ContentWriteError(f"{source_path}: live attachment filename drift")
    try:
        if int(live.get("size", -1)) != int(record.get("size", -2)):
            raise ContentWriteError(f"{source_path}: live attachment size drift")
    except (TypeError, ValueError) as exc:
        raise ContentWriteError(f"{source_path}: attachment size повреждён") from exc
    url = str(record.get("url") or "")
    if not url.startswith("https://") or urlsplit(url).path != str(live.get("file") or ""):
        raise ContentWriteError(f"{source_path}: live attachment URL drift")
    if file_sha256_bytes(client.download_attachment(url)) != expected_sha:
        raise ContentWriteError(f"{source_path}: live attachment bytes больше не canonical")
    return AssetBinding(
        source_path=source_path,
        source_sha256=expected_sha,
        url=url,
        storage=str(record.get("storage") or "stepik-attachment"),
        verified=True,
    )


def _render_lesson(
    client: StepikClient,
    *,
    repo_root: Path,
    manifest: dict[str, Any],
    asset_report: dict[str, Any],
    state: dict[str, Any],
    lesson_id: str,
    live_lesson: dict[str, Any],
    free_answer_source: dict[str, Any],
) -> list[Any]:
    source_steps = compile_lesson_source(
        repo_root,
        free_answer_source=free_answer_source,
        lesson_id=lesson_id,
    )
    bindings: list[AssetBinding] = []
    for row in asset_report.get("resolutions", []):
        if row.get("lesson") != lesson_id or row.get("materialization_required_at_write") is not True:
            continue
        bindings.append(
            _verified_binding(
                client,
                state=state,
                row=row,
                stepik_lesson_id=int(live_lesson["id"]),
            )
        )
    rendering = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=lesson_id,
        source_steps=source_steps,
        asset_report=asset_report,
        bindings=bindings,
    )
    return list(require_render_ready(rendering))


def _event_artifact(identity: Any, *, status: str) -> dict[str, Any]:
    return {
        "event_id": identity.event_id,
        "source_sha": identity.source_sha,
        "status": status,
        "kind": "lesson",
        "canonical_id": identity.object_id,
    }


def _write_journal(
    path: Path,
    *,
    sha: str,
    title_results: list[dict[str, Any]],
    tracked_results: list[dict[str, Any]],
    golden_owner_required: list[dict[str, Any]],
    blockers: list[str],
) -> None:
    lines = [
        "### LEARNER_HYGIENE: production ID cleanup",
        "",
        f"- source main SHA: `{sha}`",
        f"- title-only results: `{title_results}`",
        f"- tracked lesson results: `{tracked_results}`",
        f"- golden owner-required titles: `{[item.get('canonical_id') for item in golden_owner_required]}`",
        f"- blockers: `{blockers}`",
        "",
        "Внутренние IDs остаются production metadata; learner-facing title/body очищаются только через guarded exact-match route.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "learner-facing-hygiene",
        "source_main_sha": sha,
        "course_id": args.course_id,
        "ready_for_bulk_write": False,
    }
    if args.course_id != COURSE_ID:
        report.update({"verdict": "BLOCKED", "blockers": [f"fixed-course-id-required:{COURSE_ID}"], "stepik_writes": 0})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if not args.confirm_write:
        report.update({"verdict": "BLOCKED", "blockers": ["explicit-confirm-write-required"], "stepik_writes": 0})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    try:
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
        next_state = deepcopy(state)
        store = _history_store(sha)

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

        title_plan = plan_title_hygiene(manifest, snapshot)
        write_json(report_dir / "title-hygiene-plan.json", title_plan.as_dict())
        if title_plan.blockers:
            raise TitleHygieneError("Title hygiene blocked: " + "; ".join(title_plan.blockers))

        tracked_title_ids = {
            op.canonical_id
            for op in title_plan.operations
            if op.kind == "lesson" and baseline_for(state, op.canonical_id) is not None
        }
        unsupported_tracked = tracked_title_ids - TRACKED_HYGIENE_LESSONS
        if unsupported_tracked:
            raise TitleHygieneError(
                "Title-only route не может менять lesson с content baseline: " + ", ".join(sorted(unsupported_tracked))
            )

        title_results: list[dict[str, Any]] = []
        tracked_results: list[dict[str, Any]] = []
        stepik_writes = 0

        # Сначала section titles и lessons без content baseline. Exact legacy match уже доказан plan'ом.
        title_only_ops = [
            op for op in title_plan.operations
            if op.kind == "section" or baseline_for(state, op.canonical_id) is None
        ]
        for operation in title_only_ops:
            desired_fp = title_fingerprint(
                kind=operation.kind,
                stepik_id=operation.stepik_id,
                title=operation.expected_title,
            )
            baseline_fp = title_fingerprint(
                kind=operation.kind,
                stepik_id=operation.stepik_id,
                title=operation.live_title,
            )
            expected_identity = event_identity_from_environment(
                course_id=args.course_id,
                object_id=operation.object_id,
                kind="title-metadata",
                source_sha=sha,
                desired_fingerprint=desired_fp,
                baseline_fingerprint=baseline_fp,
                pending_first_sha=None,
            )
            incomplete = find_incomplete_object_events(store, object_id=operation.object_id)
            if len(incomplete) > 1:
                raise DeploymentHistoryError(f"{operation.object_id}: несколько incomplete title events")
            if incomplete and incomplete[0][0].event_id != expected_identity.event_id:
                raise DeploymentHistoryError(
                    f"{operation.object_id}: существует incomplete title event от другого source/semantics"
                )
            identity = incomplete[0][0] if incomplete else expected_identity
            recorder = DeploymentRecorder(store, identity)
            result = execute_title_only_operation(client, operation, recorder)
            if result.get("action") == "UPDATE_TITLE":
                stepik_writes += 1
            title_results.append({"event_id": identity.event_id, **result})

        # Если предыдущий run успел выполнить title PUT + final read-back, но упал до history commit,
        # live title уже clean и plan не создаст operation. Завершаем только доказанный event.
        for item in title_plan.already_clean:
            kind = str(item.get("kind"))
            canonical_id = str(item.get("canonical_id"))
            if kind == "lesson" and baseline_for(state, canonical_id) is not None:
                continue
            object_id = f"title:{kind}:{canonical_id}"
            incomplete = find_incomplete_object_events(store, object_id=object_id)
            if not incomplete:
                continue
            if len(incomplete) != 1:
                raise DeploymentHistoryError(f"{object_id}: несколько incomplete title events")
            identity, records, summary = incomplete[0]
            if identity.source_sha != sha or not summary.get("final_readback_confirmed"):
                raise DeploymentHistoryError(f"{object_id}: clean live title имеет незавершённую/чужую history")
            operation = TitleOperation(
                kind=kind,
                canonical_id=canonical_id,
                stepik_id=int(item["stepik_id"]),
                position=0,
                live_title=legacy_title(canonical_id, str(item["title"])),
                expected_title=str(item["title"]),
            )
            result = execute_title_only_operation(client, operation, DeploymentRecorder(store, identity))
            title_results.append({"event_id": identity.event_id, **result})

        current_snapshot = client.inspect_course(args.course_id)

        # Tracked lessons синхронизируем content-aware. Target возникает из title cleanup,
        # pending learner change или incomplete event, который нужно безопасно завершить.
        for lesson_id in sorted(TRACKED_HYGIENE_LESSONS):
            baseline = baseline_for(state, lesson_id)
            if not isinstance(baseline, dict):
                continue
            module, lesson_manifest = manifest_by_id[lesson_id]
            pending = state.get("pending", {}).get("lessons", {}).get(lesson_id)
            incomplete = find_incomplete_object_events(store, object_id=lesson_id)
            if len(incomplete) > 1:
                raise DeploymentHistoryError(f"{lesson_id}: несколько incomplete tracked hygiene events")

            if incomplete:
                old_identity, old_records, old_summary = incomplete[0]
                final = final_confirmed_record(old_records)
                if old_summary.get("final_readback_confirmed") and isinstance(final, dict):
                    recovered = final.get("actual_confirmed_state")
                    if isinstance(recovered, dict) and recovered == baseline:
                        # Issue state уже PATCHed; нужно только закрыть durable history после crash.
                        event_dir = report_dir / "tracked-events"
                        event_dir.mkdir(parents=True, exist_ok=True)
                        write_json(event_dir / f"{lesson_id}.json", _event_artifact(old_identity, status=str(final["status"])))
                        tracked_results.append({
                            "canonical_id": lesson_id,
                            "action": "RECOVER_HISTORY_COMMIT_ONLY",
                            "event_id": old_identity.event_id,
                        })
                        if old_identity.source_sha != sha:
                            raise DeploymentHistoryError(
                                f"{lesson_id}: предыдущий event нужно committed перед sync нового main; повторите run после commit"
                            )
                        continue

            title_needs_cleanup = lesson_id in tracked_title_ids
            if not title_needs_cleanup and pending is None and not incomplete:
                continue

            live_lesson = _live_lesson(
                current_snapshot,
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
            expected_title = str(lesson_manifest["title"])
            desired_fp = compiled_lesson_fingerprint(
                expected_title=expected_title,
                expected_steps=rendered_steps,
            )
            pending_first_sha = pending.get("first_pending_sha") if isinstance(pending, dict) else None
            expected_identity = event_identity_from_environment(
                course_id=args.course_id,
                object_id=lesson_id,
                kind="lesson",
                source_sha=sha,
                desired_fingerprint=desired_fp,
                baseline_fingerprint=str(baseline["applied_fingerprint"]),
                pending_first_sha=pending_first_sha,
            )
            if incomplete and incomplete[0][0].event_id != expected_identity.event_id:
                raise DeploymentHistoryError(
                    f"{lesson_id}: incomplete tracked event относится к другому main/rendered desired"
                )
            identity = incomplete[0][0] if incomplete else expected_identity
            recorder = DeploymentRecorder(store, identity)
            result = execute_tracked_learner_hygiene(
                client,
                current_snapshot,
                canonical_id=lesson_id,
                expected_steps=rendered_steps,
                module_position=int(module["position"]),
                lesson_position=int(lesson_manifest["position"]),
                expected_title=expected_title,
                legacy_title=legacy_title(lesson_id, expected_title),
                baseline=baseline,
                source_sha=sha,
                recorder=recorder,
            )
            if not result.verified or not isinstance(result.state_record, dict) or result.history_status not in {"APPLIED", "NOOP_CONFIRMED"}:
                raise DeploymentHistoryError(f"{lesson_id}: tracked hygiene не дал verified final baseline")
            stepik_writes += sum(
                1 for item in result.operations if item.get("action") in {"UPDATE_TITLE", "UPDATE_STEP"}
            )
            next_state = with_record(next_state, canonical_id=lesson_id, record=result.state_record)
            next_state = close_lesson_pending(
                next_state,
                canonical_id=lesson_id,
                confirmed_at=str(result.state_record["applied_at"]),
                confirmation_status=str(result.history_status),
            )
            event_dir = report_dir / "tracked-events"
            event_dir.mkdir(parents=True, exist_ok=True)
            write_json(event_dir / f"{lesson_id}.json", _event_artifact(identity, status=str(result.history_status)))
            tracked_results.append({
                "canonical_id": lesson_id,
                "event_id": identity.event_id,
                "operations": result.operations,
                "final_fingerprint": result.state_record["applied_fingerprint"],
            })
            current_snapshot = result.after_snapshot or client.inspect_course(args.course_id)

        state_changed = next_state != state
        write_json(report_dir / "sync-state.next.json", next_state)
        if state_changed:
            (report_dir / "state-update-required.flag").write_text("true\n", encoding="utf-8")

        final_snapshot = client.inspect_course(args.course_id)
        final_title_plan = plan_title_hygiene(manifest, final_snapshot)
        write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        write_json(report_dir / "title-hygiene-plan.after.json", final_title_plan.as_dict())
        non_golden_remaining = [
            item for item in final_title_plan.operations
            if not (item.kind == "lesson" and item.canonical_id in {row.get("canonical_id") for row in final_title_plan.owner_required})
        ]
        if final_title_plan.blockers or non_golden_remaining:
            raise TitleHygieneError("После hygiene остались non-golden title blockers/operations")

        blockers: list[str] = []
        _write_journal(
            report_dir / "sync-journal.md",
            sha=sha,
            title_results=title_results,
            tracked_results=tracked_results,
            golden_owner_required=final_title_plan.owner_required,
            blockers=blockers,
        )
        report.update({
            "verdict": "PASS",
            "blockers": blockers,
            "stepik_writes": stepik_writes,
            "title_only_results": title_results,
            "tracked_results": tracked_results,
            "golden_owner_required": final_title_plan.owner_required,
            "state_update_required": state_changed,
            "human_visual_validation": "RETEST_REQUIRED",
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
