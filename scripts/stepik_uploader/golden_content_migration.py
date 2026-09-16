from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.fingerprints import canonical_hash, compiled_lesson_fingerprint, live_lesson_fingerprint, step_equivalent
    from stepik_uploader.general_content import GeneralContentCompileError, compile_lesson_source
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, baseline_for, build_record, close_lesson_pending, load_state, with_record
    from stepik_uploader.verified_rendering import VerifiedRenderingError, build_rendering_plan, require_render_ready
else:
    from .api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .fingerprints import canonical_hash, compiled_lesson_fingerprint, live_lesson_fingerprint, step_equivalent
    from .general_content import GeneralContentCompileError, compile_lesson_source
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, baseline_for, build_record, close_lesson_pending, load_state, with_record
    from .verified_rendering import VerifiedRenderingError, build_rendering_plan, require_render_ready


COURSE_ID = 299189
TARGET_ID = "M00-L02"
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")


class GoldenContentMigrationError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise GoldenContentMigrationError("Для golden content migration нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_target(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == TARGET_ID:
                if lesson.get("golden_read_only") is not True:
                    raise GoldenContentMigrationError(f"{TARGET_ID}: canonical больше не помечен golden_read_only")
                return module, lesson
    raise GoldenContentMigrationError(f"{TARGET_ID}: отсутствует в canonical manifest")


def _live_target(snapshot: dict[str, Any], *, lesson_id: int) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for section in snapshot.get("sections", []):
        for unit in section.get("units", []):
            lesson = unit.get("lesson")
            if isinstance(lesson, dict) and int(lesson.get("id", -1)) == lesson_id:
                matches.append(lesson)
    if len(matches) != 1:
        raise GoldenContentMigrationError(f"{TARGET_ID}: найдено {len(matches)} live lessons для lesson_id={lesson_id}")
    return matches[0]


def _fixture_fingerprint(profile: dict[str, Any]) -> str:
    row = profile.get("golden_lessons", {}).get(TARGET_ID)
    if not isinstance(row, dict):
        raise GoldenContentMigrationError(f"{TARGET_ID}: отсутствует в golden profile")
    return canonical_hash(row)


def _created_id(payload: dict[str, Any]) -> int:
    for key in ("step-sources", "stepSources"):
        objects = payload.get(key)
        if isinstance(objects, list) and len(objects) == 1 and isinstance(objects[0], dict) and "id" in objects[0]:
            return int(objects[0]["id"])
    raise GoldenContentMigrationError("POST /api/step-sources не вернул однозначный step ID")


def _replace_step(lesson: dict[str, Any], *, step_id: int, expected: Any) -> dict[str, Any]:
    updated = deepcopy(lesson)
    for item in updated.get("steps", []):
        source = item.get("step_source")
        if isinstance(source, dict) and int(source.get("id", -1)) == step_id:
            source["position"] = expected.position
            source["block"] = expected.block()
            return updated
    raise GoldenContentMigrationError(f"Не найден step_id={step_id} для intermediate fingerprint")


def _append_step(lesson: dict[str, Any], *, step_id: int, expected: Any) -> dict[str, Any]:
    updated = deepcopy(lesson)
    updated.setdefault("steps", []).append({
        "id": step_id,
        "step_source": {
            "id": step_id,
            "lesson": int(lesson["id"]),
            "position": expected.position,
            "block": expected.block(),
        },
    })
    return updated


def _assert_step_readback(source: dict[str, Any], expected: Any) -> None:
    wrapped = {"step_source": source}
    if not step_equivalent(wrapped, expected):
        raise GoldenContentMigrationError(f"Read-back position={expected.position} не совпал с canonical compiled step")


def _compile_desired(repo_root: Path, manifest: dict[str, Any], profile: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
    if not isinstance(free_answer_source, dict):
        raise GoldenContentMigrationError("Golden profile не содержит free_answer_source")
    source_steps = compile_lesson_source(repo_root, free_answer_source=free_answer_source, lesson_id=TARGET_ID)
    inventory = build_asset_inventory(repo_root, manifest)
    policy = load_asset_publication_policy(repo_root / ASSET_POLICY_PATH)
    asset_report = assess_asset_publication(
        repo_root=repo_root,
        inventory=inventory,
        policy=policy,
        course_id=COURSE_ID,
    )
    if asset_report.get("route_gate_passed") is not True or asset_report.get("blockers"):
        raise AssetResolutionError("Asset publication gate не пройден для golden migration")
    rendering = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=TARGET_ID,
        source_steps=source_steps,
        asset_report=asset_report,
        bindings=(),
    )
    rendered = list(require_render_ready(rendering))
    return rendered, asset_report


def _next_profile(profile: dict[str, Any], snapshot: dict[str, Any], *, sha: str) -> dict[str, Any]:
    proposed = deepcopy(profile)
    row = proposed["golden_lessons"][TARGET_ID]
    live = _live_target(snapshot, lesson_id=int(row["stepik_lesson_id"]))
    steps = sorted(live.get("steps", []), key=lambda item: int(item.get("step_source", {}).get("position", 10**9)))
    row["plan_rows"] = len(steps)
    row["step_count"] = len(steps)
    row["block_sequence"] = [str(item["step_source"]["block"].get("name") or "") for item in steps]
    import hashlib
    row["step_text_sha256"] = [
        hashlib.sha256(str(item["step_source"]["block"].get("text") or "").encode("utf-8")).hexdigest()
        for item in steps
    ]
    row["free_answer_positions"] = [
        int(item["step_source"]["position"])
        for item in steps
        if item["step_source"]["block"].get("name") == "free-answer"
    ]
    run_id_raw = os.getenv("GITHUB_RUN_ID")
    run_id: int | str | None = int(run_id_raw) if isinstance(run_id_raw, str) and run_id_raw.isdigit() else run_id_raw
    row["content_observed_run_id"] = run_id
    proposed["observed_run_id"] = run_id
    proposed["observed_source_sha"] = sha
    blockers = validate_golden_profile(proposed, snapshot)
    if blockers:
        raise GoldenProfileError("Новый golden fixture не подтверждает final live: " + "; ".join(blockers))
    return proposed


def _event_artifact(identity: Any, baseline: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "event_id": identity.event_id,
        "source_sha": identity.source_sha,
        "status": status,
        "kind": "lesson",
        "canonical_id": TARGET_ID,
        "baseline_after": baseline,
    }


def _history_state(records: list[dict[str, Any]], live_fp: str, desired_fp: str) -> tuple[str, dict[str, Any] | None]:
    if not records:
        return "NEW", None
    summary = summarize_event(records)
    if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
        raise DeploymentHistoryError(f"{TARGET_ID}: unsafe prior history требует manual reconcile")
    if summary.get("final_readback_confirmed"):
        if live_fp != desired_fp:
            raise DeploymentHistoryError(f"{TARGET_ID}: final history доказан, но live не равен desired")
        final = next(record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED")
        baseline = final.get("actual_confirmed_state")
        if not isinstance(baseline, dict):
            raise DeploymentHistoryError(f"{TARGET_ID}: final history не содержит baseline_after")
        return "FINAL_PROVEN", baseline
    if summary.get("writes_started"):
        last = summary.get("last_confirmed_operation_fingerprint")
        if not isinstance(last, str) or live_fp != last:
            raise DeploymentHistoryError(
                f"{TARGET_ID}: partial history есть, но live не совпадает с last confirmed intermediate fingerprint"
            )
        return "PARTIAL_CONFIRMED", None
    return "STARTED_BEFORE_WRITE", None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Owner-approved M00-L02 7-to-8 golden content migration")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "golden-content-migration",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": sha,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }
    try:
        if args.course_id != COURSE_ID:
            raise GoldenContentMigrationError(f"golden content migration разрешён только для course_id={COURSE_ID}")
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        _module, target_manifest = _manifest_target(manifest)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        if not isinstance(observed, dict):
            raise GoldenContentMigrationError(f"{TARGET_ID}: golden fixture отсутствует")
        if int(observed.get("step_count", -1)) != 7:
            raise GoldenContentMigrationError(f"{TARGET_ID}: owner-approved route ожидает old fixture ровно 7 steps")

        desired_steps, asset_report = _compile_desired(repo_root, manifest, profile)
        if len(desired_steps) != 8 or len(target_manifest.get("steps", [])) != 8:
            raise GoldenContentMigrationError(f"{TARGET_ID}: owner-approved target должен содержать ровно 8 steps")
        expected_title = str(target_manifest["title"])
        desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=desired_steps)
        write_json(report_dir / "asset-report.json", asset_report)

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=COURSE_ID)
        pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
        existing_baseline = baseline_for(state, TARGET_ID)
        if pending is None and existing_baseline is None:
            raise GoldenContentMigrationError(f"{TARGET_ID}: нет ни PENDING, ни confirmed baseline")
        if pending is not None and (not isinstance(pending, dict) or pending.get("status") != "PENDING"):
            raise GoldenContentMigrationError(f"{TARGET_ID}: pending state повреждён")

        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(COURSE_ID)
        write_json(report_dir / "course-snapshot.before.json", snapshot)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False or course.get("language") != "ru":
            raise GoldenContentMigrationError("Golden migration разрешён только в private ru course")
        lesson = _live_target(snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        if lesson.get("title") != expected_title or lesson.get("is_public") is not False or lesson.get("language") != "ru":
            raise GoldenContentMigrationError(f"{TARGET_ID}: live metadata drift")
        live_fp = live_lesson_fingerprint(lesson)

        identity = event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=TARGET_ID,
            kind="golden-content-migration",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=_fixture_fingerprint(profile),
            pending_first_sha=None,
        )
        store = _history_store(sha)
        records = store.load(identity.event_id)
        history_state, recovered_baseline = _history_state(records, live_fp, desired_fp)

        if history_state in {"NEW", "STARTED_BEFORE_WRITE"}:
            blockers = validate_golden_profile(profile, snapshot)
            if blockers:
                raise GoldenProfileError(
                    "До первого content write live обязан точно совпадать со старым golden fixture: " + "; ".join(blockers)
                )
        elif history_state == "PARTIAL_CONFIRMED":
            if len(lesson.get("steps", [])) not in {7, 8}:
                raise GoldenContentMigrationError(f"{TARGET_ID}: partial recovery допускает только 7 или 8 live steps")

        if history_state == "FINAL_PROVEN":
            baseline = recovered_baseline
            if existing_baseline is not None and existing_baseline != baseline:
                raise DeploymentHistoryError(f"{TARGET_ID}: Issue baseline конфликтует с immutable final history")
            next_state = state if existing_baseline is not None else with_record(state, canonical_id=TARGET_ID, record=baseline)
            if TARGET_ID in next_state.get("pending", {}).get("lessons", {}):
                next_state = close_lesson_pending(
                    next_state,
                    canonical_id=TARGET_ID,
                    confirmed_at=str(baseline["applied_at"]),
                    confirmation_status=str(baseline.get("confirmation_status") or "APPLIED"),
                )
            proposed = _next_profile(profile, snapshot, sha=sha)
            write_json(report_dir / "golden-profile.next.json", proposed)
            write_json(report_dir / "sync-state.next.json", next_state)
            write_json(report_dir / "golden-deployment-event.json", _event_artifact(identity, baseline, "APPLIED"))
            report.update({"verdict": "PASS", "status": "RECOVER_FINAL", "readback_verified": True, "blockers": []})
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        changed_positions = [
            index + 1
            for index, item in enumerate(sorted(lesson.get("steps", []), key=lambda v: int(v["step_source"]["position"])))
            if index < 7 and not step_equivalent(item, desired_steps[index])
        ]
        plan = {
            "old_fixture_steps": 7,
            "desired_steps": 8,
            "changed_existing_positions": changed_positions,
            "append_position": 8,
            "desired_fingerprint": desired_fp,
            "live_fingerprint": live_fp,
            "history_state": history_state,
            "deletes_allowed": False,
            "reorder_allowed": False,
        }
        write_json(report_dir / "migration-plan.json", plan)
        if not args.confirm_write:
            report.update({"verdict": "READY", "plan": plan, "blockers": [], "stepik_writes_planned": len(changed_positions) + 1})
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type="golden-content-7-to-8",
            state_before={"fixture_fingerprint": _fixture_fingerprint(profile)},
            expected_state={"desired_fingerprint": desired_fp, "step_count": 8},
            stepik_object_ids={"lesson_id": int(lesson["id"])},
            fingerprint_before=live_fp if history_state == "NEW" else str(records[0].get("fingerprint_before") or live_fp),
        )

        working = deepcopy(lesson)
        ordered = sorted(working.get("steps", []), key=lambda item: int(item["step_source"]["position"]))
        if len(ordered) not in {7, 8}:
            raise GoldenContentMigrationError(f"{TARGET_ID}: write route допускает только 7 или 8 live steps")

        operations: list[dict[str, Any]] = []
        for index in range(min(7, len(ordered))):
            current = ordered[index]
            expected = desired_steps[index]
            if step_equivalent(current, expected):
                continue
            step_id = int(current["step_source"]["id"])
            before_fp = live_lesson_fingerprint(working)
            after_model = _replace_step(working, step_id=step_id, expected=expected)
            after_fp = live_lesson_fingerprint(after_model)
            operation_id = f"update-{expected.position:04d}-{step_id}"
            recorder.write_intent(operation_id=operation_id, method="PUT", target=f"step-sources/{step_id}", fingerprint_before=before_fp, expected_fingerprint_after=after_fp)
            recorder.write_dispatch_started(operation_id=operation_id)
            try:
                client.update_step_source(step_id=step_id, lesson_id=int(lesson["id"]), position=expected.position, block=expected.block())
            except StepikWriteAmbiguousError:
                recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="golden-step-put-ambiguous")
                raise
            except StepikAPIError:
                recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="golden-step-put-failed-known")
                raise
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
            readback = client.fetch_one("step-sources", step_id)
            try:
                _assert_step_readback(readback, expected)
            except Exception:
                recorder.readback_failed(operation_id=operation_id, reason_code="golden-step-put-readback-mismatch")
                raise
            recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=after_fp)
            working = after_model
            operations.append({"action": "UPDATE_STEP", "step_id": step_id, "position": expected.position})
            report["stepik_writes"] = int(report["stepik_writes"]) + 1

        ordered = sorted(working.get("steps", []), key=lambda item: int(item["step_source"]["position"]))
        if len(ordered) == 7:
            expected = desired_steps[7]
            before_fp = live_lesson_fingerprint(working)
            after_model = _append_step(working, step_id=-1, expected=expected)
            after_fp = live_lesson_fingerprint(after_model)
            operation_id = "append-0008"
            recorder.write_intent(operation_id=operation_id, method="POST", target="step-sources", fingerprint_before=before_fp, expected_fingerprint_after=after_fp)
            recorder.write_dispatch_started(operation_id=operation_id)
            try:
                payload = client.create_step_source(lesson_id=int(lesson["id"]), position=8, block=expected.block())
            except StepikWriteAmbiguousError:
                recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="golden-step-post-ambiguous")
                raise
            except StepikAPIError:
                recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="golden-step-post-failed-known")
                raise
            step_id = _created_id(payload)
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
            readback = client.fetch_one("step-sources", step_id)
            try:
                _assert_step_readback(readback, expected)
            except Exception:
                recorder.readback_failed(operation_id=operation_id, reason_code="golden-step-post-readback-mismatch")
                raise
            recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=after_fp)
            working = _append_step(working, step_id=step_id, expected=expected)
            operations.append({"action": "CREATE_STEP", "step_id": step_id, "position": 8})
            report["stepik_writes"] = int(report["stepik_writes"]) + 1

        final_snapshot = client.inspect_course(COURSE_ID)
        write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        final_lesson = _live_target(final_snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        final_fp = live_lesson_fingerprint(final_lesson)
        if final_fp != desired_fp:
            recorder.readback_failed(operation_id=None, reason_code="golden-final-readback-mismatch")
            raise GoldenContentMigrationError(f"{TARGET_ID}: final live не совпал с 8-step canonical desired")
        final_ids = [int(item["step_source"]["id"]) for item in sorted(final_lesson["steps"], key=lambda item: int(item["step_source"]["position"]))]
        source_paths = [path for step in desired_steps for path in step.source_git_paths]
        baseline = build_record(
            canonical_id=TARGET_ID,
            stepik_lesson_id=int(final_lesson["id"]),
            expected_title=expected_title,
            expected_steps=desired_steps,
            source_sha=sha,
            step_ids=final_ids,
            source_git_paths=source_paths,
        )
        baseline["confirmation_status"] = "APPLIED"
        recorder.final_readback(
            fingerprint_after=final_fp,
            stepik_object_ids={"lesson_id": int(final_lesson["id"]), "step_ids": final_ids},
            status="APPLIED",
            baseline_after=baseline,
        )
        next_state = with_record(state, canonical_id=TARGET_ID, record=baseline)
        if TARGET_ID in next_state.get("pending", {}).get("lessons", {}):
            next_state = close_lesson_pending(next_state, canonical_id=TARGET_ID, confirmed_at=str(baseline["applied_at"]), confirmation_status="APPLIED")
        proposed = _next_profile(profile, final_snapshot, sha=sha)
        write_json(report_dir / "golden-profile.next.json", proposed)
        write_json(report_dir / "sync-state.next.json", next_state)
        write_json(report_dir / "golden-deployment-event.json", _event_artifact(identity, baseline, "APPLIED"))
        (report_dir / "sync-journal.md").write_text(
            "\n".join([
                f"### GOLDEN_CONTENT_MIGRATION: `{TARGET_ID}`",
                "",
                f"- source main SHA: `{sha}`",
                f"- Stepik lesson ID: `{final_lesson['id']}`",
                "- owner decision: canonical GitHub 8-step version replaces confirmed 7-step live golden",
                f"- event: `{identity.event_id}`",
                f"- final fingerprint: `{final_fp}`",
                f"- step IDs: `{final_ids}`",
                f"- write operations: `{operations}`",
                "",
                "Issue state должен быть patched после final read-back. Затем history получает MACHINE_STATE_COMMITTED. Новый golden-profile.next.json является evidence для отдельного post-run PR, а не self-modifying main.",
            ]) + "\n",
            encoding="utf-8",
        )
        report.update({
            "verdict": "PASS",
            "status": "APPLIED",
            "event_id": identity.event_id,
            "write_operations": operations,
            "rendered_steps": len(desired_steps),
            "step_ids": final_ids,
            "readback_verified": True,
            "golden_profile_update_required_after_run": True,
            "blockers": [],
        })
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        GoldenContentMigrationError,
        GoldenProfileError,
        CanonicalBuildError,
        GeneralContentCompileError,
        AssetResolutionError,
        VerifiedRenderingError,
        DeploymentHistoryError,
        StepikAPIError,
        SyncStateError,
        OSError,
        ValueError,
    ) as exc:
        report.update({"verdict": "BLOCKED", "blockers": [str(exc)], "write_retry_policy": "no blind retry; inspect durable history and live state"})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
