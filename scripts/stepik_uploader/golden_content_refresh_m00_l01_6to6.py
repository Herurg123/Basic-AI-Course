from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.golden_content_migration_7to8 as legacy
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.deployment_history import DeploymentRecorder, event_identity_from_environment, summarize_event
    from stepik_uploader.general_content import compile_lesson_source
    from stepik_uploader.golden import validate_golden_profile
    from stepik_uploader.transport_equivalence import lesson_transport_equivalent
    from stepik_uploader.verified_rendering import build_rendering_plan, require_render_ready
else:
    from . import golden_content_migration_7to8 as legacy
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import assess_asset_publication, load_asset_publication_policy
    from .deployment_history import DeploymentRecorder, event_identity_from_environment, summarize_event
    from .general_content import compile_lesson_source
    from .golden import validate_golden_profile
    from .transport_equivalence import lesson_transport_equivalent
    from .verified_rendering import build_rendering_plan, require_render_ready


COURSE_ID = 299189
TARGET_ID = "M00-L01"
GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")


class GoldenM00L01RefreshError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Owner-approved M00-L01 6-to-6 golden content-only refresh")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument("--confirm-write", action="store_true")
    return parser.parse_args()


def _target_profile(profile: dict[str, Any]) -> dict[str, Any]:
    narrowed = deepcopy(profile)
    row = profile.get("golden_lessons", {}).get(TARGET_ID)
    if not isinstance(row, dict):
        raise GoldenM00L01RefreshError(f"{TARGET_ID}: отсутствует в accepted golden profile")
    narrowed["golden_lessons"] = {TARGET_ID: deepcopy(row)}
    return narrowed


def _ordered_steps(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        list(lesson.get("steps", [])),
        key=lambda item: int(item.get("step_source", {}).get("position", 10**9)),
    )


def _step_ids(lesson: dict[str, Any]) -> list[int]:
    result: list[int] = []
    for item in _ordered_steps(lesson):
        source = item.get("step_source")
        if not isinstance(source, dict) or not isinstance(source.get("id"), int):
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: live step не содержит exact step_source id")
        result.append(int(source["id"]))
    return result


def _manifest_target(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == TARGET_ID:
                if lesson.get("golden_read_only") is not True:
                    raise GoldenM00L01RefreshError(f"{TARGET_ID}: canonical больше не golden_read_only")
                return module, lesson
    raise GoldenM00L01RefreshError(f"{TARGET_ID}: отсутствует в manifest")


def _compile_desired(repo_root: Path, manifest: dict[str, Any], profile: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
    if not isinstance(free_answer_source, dict):
        raise GoldenM00L01RefreshError("Golden profile не содержит free_answer_source")
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
        raise GoldenM00L01RefreshError("Asset publication gate не пройден для M00-L01")
    materialized = [
        row
        for row in asset_report.get("resolutions", [])
        if row.get("lesson") == TARGET_ID and row.get("materialization_required_at_write") is True
    ]
    if materialized:
        raise GoldenM00L01RefreshError(
            f"{TARGET_ID}: special 6→6 route не разрешает attachment writes; найдено {len(materialized)} materialization rows"
        )
    rendering = build_rendering_plan(
        repo_root=repo_root,
        lesson_id=TARGET_ID,
        source_steps=source_steps,
        asset_report=asset_report,
        bindings=(),
    )
    return list(require_render_ready(rendering)), asset_report


def _assert_content_only_shape(lesson: dict[str, Any], desired_steps: list[Any]) -> list[int]:
    live_steps = _ordered_steps(lesson)
    if len(live_steps) != 6 or len(desired_steps) != 6:
        raise GoldenM00L01RefreshError(f"{TARGET_ID}: owner-approved route разрешает только 6→6")
    live_positions = [int(item["step_source"]["position"]) for item in live_steps]
    desired_positions = [int(step.position) for step in desired_steps]
    if live_positions != desired_positions:
        raise GoldenM00L01RefreshError(
            f"{TARGET_ID}: positions drift, desired={desired_positions}, live={live_positions}"
        )
    for current, expected in zip(live_steps, desired_steps, strict=True):
        block = current["step_source"].get("block", {})
        expected_block = expected.block()
        if block.get("name") != expected_block.get("name"):
            raise GoldenM00L01RefreshError(
                f"{TARGET_ID}: block name change запрещён в position={expected.position}"
            )
        if block.get("source", {}) != expected_block.get("source", {}):
            raise GoldenM00L01RefreshError(
                f"{TARGET_ID}: block source change запрещён в position={expected.position}"
            )
    return _step_ids(lesson)


def _changed_positions(lesson: dict[str, Any], desired_steps: list[Any]) -> list[int]:
    return [
        int(expected.position)
        for current, expected in zip(_ordered_steps(lesson), desired_steps, strict=True)
        if not legacy.step_equivalent(current, expected)
    ]


def _fixture_fingerprint(profile: dict[str, Any]) -> str:
    row = profile.get("golden_lessons", {}).get(TARGET_ID)
    if not isinstance(row, dict):
        raise GoldenM00L01RefreshError(f"{TARGET_ID}: fixture отсутствует")
    return legacy.canonical_hash(row)


def _initial_step_ids(records: list[dict[str, Any]], fallback: list[int]) -> list[int]:
    started = next((row for row in records if row.get("phase") == "EVENT_STARTED"), None)
    if not isinstance(started, dict):
        return fallback
    state_before = started.get("state_before")
    if isinstance(state_before, dict) and isinstance(state_before.get("step_ids"), list):
        values = state_before["step_ids"]
        if all(isinstance(value, int) for value in values):
            return [int(value) for value in values]
    return fallback


def _history_state(records: list[dict[str, Any]], live_fp: str, desired_fp: str) -> tuple[str, dict[str, Any] | None]:
    if not records:
        return "NEW", None
    summary = summarize_event(records)
    if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
        raise legacy.DeploymentHistoryError(f"{TARGET_ID}: unsafe prior history требует manual reconcile")
    if summary.get("final_readback_confirmed"):
        final_live = summary.get("final_live_fingerprint") or summary.get("final_fingerprint")
        if final_live != live_fp or summary.get("final_fingerprint") != desired_fp:
            raise legacy.DeploymentHistoryError(f"{TARGET_ID}: final history больше не совпадает с live/desired")
        final = next(row for row in records if row.get("phase") == "FINAL_READBACK_CONFIRMED")
        baseline = final.get("actual_confirmed_state")
        if not isinstance(baseline, dict):
            raise legacy.DeploymentHistoryError(f"{TARGET_ID}: final history не содержит baseline_after")
        return "FINAL_PROVEN", baseline
    if summary.get("writes_started"):
        last = summary.get("last_confirmed_operation_fingerprint")
        if not isinstance(last, str) or live_fp != last:
            raise legacy.DeploymentHistoryError(
                f"{TARGET_ID}: partial history есть, но live не совпадает с last confirmed prefix"
            )
        return "PARTIAL_CONFIRMED", None
    return "STARTED_BEFORE_WRITE", None


def _replace_step_with_readback(lesson: dict[str, Any], *, step_id: int, readback: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(lesson)
    for item in updated.get("steps", []):
        source = item.get("step_source")
        if isinstance(source, dict) and int(source.get("id", -1)) == step_id:
            item["step_source"] = deepcopy(readback)
            return updated
    raise GoldenM00L01RefreshError(f"{TARGET_ID}: readback step_id={step_id} не найден в working lesson")


def _update_profile_row(row: dict[str, Any], live: dict[str, Any], *, run_id: int | str | None) -> None:
    steps = _ordered_steps(live)
    row["plan_rows"] = len(steps)
    row["step_count"] = len(steps)
    row["block_sequence"] = [str(item["step_source"]["block"].get("name") or "") for item in steps]
    row["step_text_sha256"] = [
        hashlib.sha256(str(item["step_source"]["block"].get("text") or "").encode("utf-8")).hexdigest()
        for item in steps
    ]
    row["free_answer_positions"] = [
        int(item["step_source"]["position"])
        for item in steps
        if item["step_source"]["block"].get("name") == "free-answer"
    ]
    row["content_observed_run_id"] = run_id


def _next_profile_all(profile: dict[str, Any], snapshot: dict[str, Any], *, sha: str) -> dict[str, Any]:
    proposed = deepcopy(profile)
    run_raw = os.getenv("GITHUB_RUN_ID")
    run_id: int | str | None = int(run_raw) if isinstance(run_raw, str) and run_raw.isdigit() else run_raw
    for canonical_id, row in proposed.get("golden_lessons", {}).items():
        live = legacy._live_target(snapshot, lesson_id=int(row["stepik_lesson_id"]))
        _update_profile_row(row, live, run_id=run_id)
    proposed["observed_run_id"] = run_id
    proposed["observed_source_sha"] = sha
    blockers = validate_golden_profile(proposed, snapshot)
    if blockers:
        raise legacy.GoldenProfileError(
            "Предложенный final golden profile не подтверждает final live: " + "; ".join(blockers)
        )
    return proposed


def _finalize_state(state: dict[str, Any], baseline: dict[str, Any], *, status: str) -> dict[str, Any]:
    next_state = legacy.with_record(state, canonical_id=TARGET_ID, record=baseline)
    return legacy.close_lesson_pending(
        next_state,
        canonical_id=TARGET_ID,
        confirmed_at=str(baseline.get("applied_at")),
        confirmation_status=status,
    )


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = legacy.source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "golden-content-refresh-m00-l01-6to6",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": sha,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }
    try:
        if args.course_id != COURSE_ID:
            raise GoldenM00L01RefreshError(f"route разрешён только для course_id={COURSE_ID}")
        manifest = legacy.build_structural_manifest(repo_root, source_sha=sha)
        _module, target_manifest = _manifest_target(manifest)
        profile = legacy.load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        if not isinstance(observed, dict) or int(observed.get("step_count", -1)) != 6:
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: accepted fixture должен содержать ровно 6 steps")
        if profile.get("observed_conventions", {}).get("golden_write_policy") != "READ_ONLY":
            raise GoldenM00L01RefreshError("Golden profile write policy неожиданно отличается от READ_ONLY")

        desired_steps, asset_report = _compile_desired(repo_root, manifest, profile)
        if len(desired_steps) != 6 or len(target_manifest.get("steps", [])) != 6:
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: canonical target должен оставаться ровно 6 steps")
        expected_title = str(target_manifest["title"])
        if expected_title != str(observed.get("lesson_title")):
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: title change запрещён content-only route")
        desired_fp = legacy.compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=desired_steps)
        legacy.write_json(report_dir / "asset-report.json", asset_report)

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = legacy.load_state(state_path, course_id=args.course_id)
        if legacy.baseline_for(state, TARGET_ID) is not None:
            raise GoldenM00L01RefreshError(
                f"{TARGET_ID}: machine baseline уже существует; one-time fixture-bootstrap route больше неприменим"
            )
        pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: текущий PENDING обязателен")
        pending_first_sha = str(pending.get("first_pending_sha") or "") or None

        client_id, client_secret = legacy._credentials()
        client = legacy.StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        legacy.write_json(report_dir / "course-snapshot.before.json", snapshot)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False or course.get("language") not in {None, "ru"}:
            raise GoldenM00L01RefreshError("M00-L01 refresh разрешён только в private ru course")
        lesson = legacy._live_target(snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        if lesson.get("is_public") is not False or lesson.get("language") != "ru" or lesson.get("title") != expected_title:
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: live metadata drift запрещает content-only route")
        live_ids = _assert_content_only_shape(lesson, desired_steps)
        live_fp = legacy.live_lesson_fingerprint(lesson)

        store = legacy._history_store(sha)
        identity = event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=TARGET_ID,
            kind="lesson",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=_fixture_fingerprint(profile),
            pending_first_sha=pending_first_sha,
        )
        records = store.load(identity.event_id)
        history_state, recovered_baseline = _history_state(records, live_fp, desired_fp)

        if history_state in {"NEW", "STARTED_BEFORE_WRITE"}:
            fixture_blockers = validate_golden_profile(_target_profile(profile), snapshot)
            if fixture_blockers:
                raise legacy.GoldenProfileError(
                    "До первого M00-L01 write live обязан точно совпадать с accepted target fixture: "
                    + "; ".join(fixture_blockers)
                )
        elif history_state == "PARTIAL_CONFIRMED":
            initial_ids = _initial_step_ids(records, live_ids)
            if live_ids != initial_ids:
                raise GoldenM00L01RefreshError(f"{TARGET_ID}: step IDs изменились во время partial refresh")
            _assert_content_only_shape(lesson, desired_steps)

        if history_state == "FINAL_PROVEN":
            if not isinstance(recovered_baseline, dict):
                raise legacy.DeploymentHistoryError(f"{TARGET_ID}: final history не содержит baseline")
            status = str(recovered_baseline.get("confirmation_status") or "APPLIED")
            recovered_baseline["confirmation_status"] = status
            next_state = _finalize_state(state, recovered_baseline, status=status)
            proposed = _next_profile_all(profile, snapshot, sha=sha)
            legacy.write_json(report_dir / "golden-profile.next.json", proposed)
            legacy.write_json(report_dir / "sync-state.next.json", next_state)
            legacy.write_json(
                report_dir / "golden-deployment-event.json",
                legacy._event_artifact(identity, recovered_baseline, status),
            )
            report.update(
                {
                    "verdict": "PASS",
                    "status": "RECOVER_FINAL",
                    "readback_verified": True,
                    "step_ids": live_ids,
                    "blockers": [],
                }
            )
            legacy.write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        changed = _changed_positions(lesson, desired_steps)
        plan = {
            "accepted_fixture_steps": 6,
            "desired_steps": 6,
            "changed_existing_positions": changed,
            "creates_allowed": False,
            "deletes_allowed": False,
            "reorder_allowed": False,
            "block_name_changes_allowed": False,
            "block_source_changes_allowed": False,
            "preserved_step_ids": _initial_step_ids(records, live_ids),
            "desired_fingerprint": desired_fp,
            "live_fingerprint": live_fp,
            "history_state": history_state,
        }
        legacy.write_json(report_dir / "refresh-plan.json", plan)
        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "status": "UPDATE_REQUIRED" if changed else "NOOP_PENDING",
                    "plan": plan,
                    "stepik_writes_planned": len(changed),
                    "blockers": [],
                }
            )
            legacy.write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        recorder = DeploymentRecorder(store, identity)
        initial_ids = _initial_step_ids(records, live_ids)
        recorder.ensure_started(
            operation_type="golden-content-m00-l01-6-to-6-refresh",
            state_before={
                "accepted_fixture_fingerprint": _fixture_fingerprint(profile),
                "step_ids": initial_ids,
            },
            expected_state={
                "desired_fingerprint": desired_fp,
                "step_count": 6,
                "step_ids": initial_ids,
                "content_only": True,
            },
            stepik_object_ids={"lesson_id": int(lesson["id"]), "step_ids": initial_ids},
            fingerprint_before=(
                str(next((row.get("fingerprint_before") for row in records if row.get("phase") == "EVENT_STARTED"), live_fp))
            ),
        )

        working = deepcopy(lesson)
        operations: list[dict[str, Any]] = []
        for current, expected in zip(_ordered_steps(working), desired_steps, strict=True):
            if legacy.step_equivalent(current, expected):
                continue
            step_id = int(current["step_source"]["id"])
            if step_id not in initial_ids:
                raise GoldenM00L01RefreshError(f"{TARGET_ID}: unknown step_id={step_id}")
            before_fp = legacy.live_lesson_fingerprint(working)
            expected_model = legacy._replace_step(working, step_id=step_id, expected=expected)
            expected_after_fp = legacy.live_lesson_fingerprint(expected_model)
            operation_id = f"refresh-{expected.position:04d}-{step_id}"
            recorder.write_intent(
                operation_id=operation_id,
                method="PUT",
                target=f"step-sources/{step_id}",
                fingerprint_before=before_fp,
                expected_fingerprint_after=expected_after_fp,
            )
            recorder.write_dispatch_started(operation_id=operation_id)
            try:
                client.update_step_source(
                    step_id=step_id,
                    lesson_id=int(lesson["id"]),
                    position=expected.position,
                    block=expected.block(),
                )
            except legacy.StepikWriteAmbiguousError:
                recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="m00-l01-refresh-put-ambiguous")
                raise
            except legacy.StepikAPIError:
                recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="m00-l01-refresh-put-failed-known")
                raise
            except Exception:
                recorder.write_result(
                    operation_id=operation_id,
                    status="AMBIGUOUS",
                    reason_code="m00-l01-refresh-put-unclassified-after-dispatch",
                )
                raise
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
            try:
                readback = client.fetch_one("step-sources", step_id)
                legacy._assert_step_readback(readback, expected)
            except Exception:
                recorder.readback_failed(operation_id=operation_id, reason_code="m00-l01-refresh-put-readback-mismatch")
                raise
            observed_model = _replace_step_with_readback(working, step_id=step_id, readback=readback)
            observed_fp = legacy.live_lesson_fingerprint(observed_model)
            recorder.operation_readback(
                operation_id=operation_id,
                expected_fingerprint_after=expected_after_fp,
                observed_live_fingerprint=observed_fp,
            )
            working = observed_model
            operations.append({"action": "UPDATE_STEP", "step_id": step_id, "position": expected.position})
            report["stepik_writes"] = int(report["stepik_writes"]) + 1

        final_snapshot = client.inspect_course(COURSE_ID)
        legacy.write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        final_lesson = legacy._live_target(final_snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        final_ids = _assert_content_only_shape(final_lesson, desired_steps)
        if final_ids != initial_ids:
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: final step IDs/order изменились")
        final_fp = legacy.live_lesson_fingerprint(final_lesson)
        if not lesson_transport_equivalent(
            final_lesson,
            expected_title=expected_title,
            expected_steps=desired_steps,
            language="ru",
            is_public=False,
        ):
            recorder.readback_failed(operation_id=None, reason_code="m00-l01-refresh-final-readback-mismatch")
            raise GoldenM00L01RefreshError(f"{TARGET_ID}: final live не transport-equivalent canonical desired")

        source_paths = [path for step in desired_steps for path in step.source_git_paths]
        status = "APPLIED" if operations or history_state == "PARTIAL_CONFIRMED" else "NOOP_CONFIRMED"
        final_baseline = legacy.build_record(
            canonical_id=TARGET_ID,
            stepik_lesson_id=int(final_lesson["id"]),
            expected_title=expected_title,
            expected_steps=desired_steps,
            source_sha=sha,
            step_ids=final_ids,
            source_git_paths=source_paths,
            confirmed_live_fingerprint=final_fp,
        )
        final_baseline["confirmation_status"] = status
        recorder.final_readback(
            fingerprint_after=desired_fp,
            observed_live_fingerprint=final_fp,
            stepik_object_ids={"lesson_id": int(final_lesson["id"]), "step_ids": final_ids},
            status=status,
            baseline_after=final_baseline,
        )
        next_state = _finalize_state(state, final_baseline, status=status)
        proposed = _next_profile_all(profile, final_snapshot, sha=sha)
        legacy.write_json(report_dir / "golden-profile.next.json", proposed)
        legacy.write_json(report_dir / "sync-state.next.json", next_state)
        legacy.write_json(
            report_dir / "golden-deployment-event.json",
            legacy._event_artifact(identity, final_baseline, status),
        )
        (report_dir / "sync-journal.md").write_text(
            "\n".join(
                [
                    f"### GOLDEN_CONTENT_REFRESH: `{TARGET_ID}`",
                    "",
                    f"- source main SHA: `{sha}`",
                    f"- Stepik lesson ID: `{final_lesson['id']}`",
                    "- accepted golden shape: `6 steps → 6 steps`",
                    "- structural writes: `0`",
                    "- block name/source changes: `0`",
                    f"- event: `{identity.event_id}`",
                    f"- preserved step IDs: `{final_ids}`",
                    f"- write operations: `{operations}`",
                    "",
                    "This is an explicit owner-approved exception route. The project-wide golden_write_policy remains READ_ONLY; the emitted golden-profile.next.json must be reviewed and committed separately from live writes.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report.update(
            {
                "verdict": "PASS",
                "status": status,
                "event_id": identity.event_id,
                "write_operations": operations,
                "rendered_steps": 6,
                "step_ids": final_ids,
                "readback_verified": True,
                "desired_fingerprint": desired_fp,
                "confirmed_live_fingerprint": final_fp,
                "golden_profile_update_required_after_run": True,
                "blockers": [],
            }
        )
        legacy.write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        GoldenM00L01RefreshError,
        legacy.GoldenProfileError,
        legacy.CanonicalBuildError,
        legacy.GeneralContentCompileError,
        legacy.AssetResolutionError,
        legacy.VerifiedRenderingError,
        legacy.DeploymentHistoryError,
        legacy.StepikAPIError,
        legacy.SyncStateError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "write_retry_policy": "no blind retry; inspect durable history and exact live state",
            }
        )
        legacy.write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
