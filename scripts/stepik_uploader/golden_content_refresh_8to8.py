from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.golden_content_migration_7to8 as legacy
    from stepik_uploader.lesson_title_write import LessonTitleWriteError, execute_lesson_title_update
    from stepik_uploader.transport_equivalence import lesson_transport_equivalent
else:
    from . import golden_content_migration_7to8 as legacy
    from .lesson_title_write import LessonTitleWriteError, execute_lesson_title_update
    from .transport_equivalence import lesson_transport_equivalent


COURSE_ID = legacy.COURSE_ID
TARGET_ID = legacy.TARGET_ID
GoldenContentRefreshError = legacy.GoldenContentMigrationError


def _ordered_steps(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    steps = sorted(
        lesson.get("steps", []),
        key=lambda item: int(item.get("step_source", {}).get("position", 10**9)),
    )
    positions = [int(item.get("step_source", {}).get("position", -1)) for item in steps]
    if positions != list(range(1, len(steps) + 1)):
        raise GoldenContentRefreshError(
            f"{TARGET_ID}: live positions неоднозначны: {positions}"
        )
    return steps


def _ordered_ids(lesson: dict[str, Any]) -> list[int]:
    return [int(item["step_source"]["id"]) for item in _ordered_steps(lesson)]


def _assert_same_eight_ids(lesson: dict[str, Any], baseline: dict[str, Any]) -> list[int]:
    steps = _ordered_steps(lesson)
    if len(steps) != 8:
        raise GoldenContentRefreshError(
            f"{TARGET_ID}: 8→8 refresh запрещён при live step_count={len(steps)}"
        )
    live_ids = [int(item["step_source"]["id"]) for item in steps]
    baseline_ids = [int(value) for value in baseline.get("step_ids", [])]
    if len(baseline_ids) != 8 or live_ids != baseline_ids:
        raise GoldenContentRefreshError(
            f"{TARGET_ID}: live step IDs/порядок отличаются от confirmed 8-step baseline"
        )
    return live_ids


def _assert_content_only_shape(lesson: dict[str, Any], desired_steps: list[Any]) -> None:
    """Allow text/HTML changes only; block type and source config are immutable."""
    live = _ordered_steps(lesson)
    if len(live) != len(desired_steps):
        raise GoldenContentRefreshError(
            f"{TARGET_ID}: content refresh не меняет количество steps"
        )
    for item, expected in zip(live, desired_steps, strict=True):
        source = item.get("step_source")
        if not isinstance(source, dict):
            raise GoldenContentRefreshError(f"{TARGET_ID}: live step_source отсутствует")
        block = source.get("block")
        if not isinstance(block, dict):
            raise GoldenContentRefreshError(f"{TARGET_ID}: live block отсутствует")
        expected_block = expected.block()
        if block.get("name") != expected_block.get("name"):
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: position={expected.position} меняет тип блока; 8→8 refresh разрешает только text/HTML content"
            )
        if (block.get("source") or {}) != (expected_block.get("source") or {}):
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: position={expected.position} меняет block.source; 8→8 refresh разрешает только text/HTML content"
            )


def _changed_positions(lesson: dict[str, Any], desired_steps: list[Any]) -> list[int]:
    _assert_content_only_shape(lesson, desired_steps)
    live = _ordered_steps(lesson)
    return [
        int(expected.position)
        for item, expected in zip(live, desired_steps, strict=True)
        if not legacy.step_equivalent(item, expected)
    ]


def _baseline_live_fingerprint(baseline: dict[str, Any]) -> str:
    value = baseline.get("confirmed_live_fingerprint") or baseline.get("applied_fingerprint")
    if not isinstance(value, str):
        raise GoldenContentRefreshError(
            f"{TARGET_ID}: confirmed baseline не содержит live/applied fingerprint"
        )
    return value


def _replace_step_with_readback(
    lesson: dict[str, Any], *, step_id: int, readback: dict[str, Any]
) -> dict[str, Any]:
    updated = deepcopy(lesson)
    for item in updated.get("steps", []):
        source = item.get("step_source")
        if isinstance(source, dict) and int(source.get("id", -1)) == int(step_id):
            item["step_source"] = deepcopy(readback)
            return updated
    raise GoldenContentRefreshError(
        f"{TARGET_ID}: step_id={step_id} отсутствует при фиксации фактического read-back"
    )


def _refresh_history_state(
    records: list[dict[str, Any]], live_fp: str
) -> tuple[str, dict[str, Any] | None]:
    if not records:
        return "NEW", None
    summary = legacy.summarize_event(records)
    if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
        raise legacy.DeploymentHistoryError(
            f"{TARGET_ID}: unsafe prior refresh history требует manual reconcile"
        )
    if summary.get("final_readback_confirmed"):
        final_live = summary.get("final_live_fingerprint") or summary.get("final_fingerprint")
        if not isinstance(final_live, str) or live_fp != final_live:
            raise legacy.DeploymentHistoryError(
                f"{TARGET_ID}: final refresh history доказан, но live не равен final observed state"
            )
        final = next(
            record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED"
        )
        baseline = final.get("actual_confirmed_state")
        if not isinstance(baseline, dict):
            raise legacy.DeploymentHistoryError(
                f"{TARGET_ID}: final refresh history не содержит baseline_after"
            )
        return "FINAL_PROVEN", baseline
    if summary.get("writes_started"):
        last = summary.get("last_confirmed_operation_fingerprint")
        if not isinstance(last, str) or live_fp != last:
            raise legacy.DeploymentHistoryError(
                f"{TARGET_ID}: partial refresh history есть, но live не совпадает с last confirmed intermediate fingerprint"
            )
        return "PARTIAL_CONFIRMED", None
    return "STARTED_BEFORE_WRITE", None


def _finalize_state(
    *,
    state: dict[str, Any],
    baseline: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    next_state = legacy.with_record(state, canonical_id=TARGET_ID, record=baseline)
    if TARGET_ID in next_state.get("pending", {}).get("lessons", {}):
        next_state = legacy.close_lesson_pending(
            next_state,
            canonical_id=TARGET_ID,
            confirmed_at=str(baseline["applied_at"]),
            confirmation_status=status,
        )
    return next_state


def run(args: Any, profile: dict[str, Any]) -> int:
    """Refresh accepted 8-step M00-L02 content without structural writes."""
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = legacy.source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "golden-content-refresh-8to8",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": sha,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
        "structural_writes_allowed": False,
    }

    try:
        if args.course_id != COURSE_ID:
            raise GoldenContentRefreshError(
                f"golden content refresh разрешён только для course_id={COURSE_ID}"
            )

        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        if not isinstance(observed, dict) or int(observed.get("step_count", -1)) != 8:
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: 8→8 refresh требует accepted 8-step golden fixture"
            )

        manifest = legacy.build_structural_manifest(repo_root, source_sha=sha)
        _module, target_manifest = legacy._manifest_target(manifest)
        desired_steps, asset_report = legacy._compile_desired(repo_root, manifest, profile)
        learner_rows = [
            row for row in target_manifest.get("steps", []) if row.get("author_only") is not True
        ]
        if len(desired_steps) != 8 or len(learner_rows) != 8:
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: current canonical должен оставаться ровно 8 learner steps"
            )
        expected_title = str(target_manifest["title"])
        desired_fp = legacy.compiled_lesson_fingerprint(
            expected_title=expected_title,
            expected_steps=desired_steps,
        )
        legacy.write_json(report_dir / "asset-report.json", asset_report)

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = legacy.load_state(state_path, course_id=COURSE_ID)
        pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
        baseline = legacy.baseline_for(state, TARGET_ID)
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: 8→8 refresh разрешён только для текущего PENDING lesson"
            )
        if not isinstance(baseline, dict):
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: 8→8 refresh требует confirmed machine baseline"
            )
        if int(baseline.get("stepik_lesson_id", -1)) != int(
            observed.get("stepik_lesson_id", -2)
        ):
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: golden fixture и machine baseline относятся к разным lesson IDs"
            )

        client_id, client_secret = legacy._credentials()
        client = legacy.StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(COURSE_ID)
        legacy.write_json(report_dir / "course-snapshot.before.json", snapshot)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False or course.get("language") != "ru":
            raise GoldenContentRefreshError(
                "Golden 8→8 refresh разрешён только в private ru course"
            )
        lesson = legacy._live_target(snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        if lesson.get("is_public") is not False or lesson.get("language") != "ru":
            raise GoldenContentRefreshError(f"{TARGET_ID}: live private/language metadata drift")
        if not isinstance(lesson.get("title"), str) or not str(lesson.get("title")).strip():
            raise GoldenContentRefreshError(f"{TARGET_ID}: live title отсутствует")
        live_ids = _assert_same_eight_ids(lesson, baseline)
        _assert_content_only_shape(lesson, desired_steps)
        live_fp = legacy.live_lesson_fingerprint(lesson)

        identity = legacy.event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=TARGET_ID,
            kind="golden-content-refresh",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=legacy._fixture_fingerprint(profile),
            pending_first_sha=str(pending.get("first_pending_sha") or "") or None,
        )
        store = legacy._history_store(sha)
        records = store.load(identity.event_id)
        history_state, recovered_baseline = _refresh_history_state(records, live_fp)

        if history_state in {"NEW", "STARTED_BEFORE_WRITE"}:
            fixture_blockers = legacy.validate_golden_profile(profile, snapshot)
            if fixture_blockers:
                raise legacy.GoldenProfileError(
                    "До первого 8→8 content write live обязан точно совпадать с accepted golden fixture: "
                    + "; ".join(fixture_blockers)
                )
            if live_fp != _baseline_live_fingerprint(baseline):
                raise GoldenContentRefreshError(
                    f"{TARGET_ID}: live больше не совпадает с confirmed machine baseline"
                )
        elif history_state == "PARTIAL_CONFIRMED":
            _assert_same_eight_ids(lesson, baseline)
            _assert_content_only_shape(lesson, desired_steps)

        if history_state == "FINAL_PROVEN":
            if not isinstance(recovered_baseline, dict):
                raise legacy.DeploymentHistoryError(
                    f"{TARGET_ID}: final refresh history не содержит baseline"
                )
            final_status = str(recovered_baseline.get("confirmation_status") or "APPLIED")
            recovered_baseline["confirmation_status"] = final_status
            next_state = _finalize_state(
                state=state,
                baseline=recovered_baseline,
                status=final_status,
            )
            proposed = legacy._next_profile(profile, snapshot, sha=sha)
            legacy.write_json(report_dir / "golden-profile.next.json", proposed)
            legacy.write_json(report_dir / "sync-state.next.json", next_state)
            legacy.write_json(
                report_dir / "golden-deployment-event.json",
                legacy._event_artifact(identity, recovered_baseline, final_status),
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
        title_change = lesson.get("title") != expected_title
        plan = {
            "accepted_fixture_steps": 8,
            "desired_steps": 8,
            "changed_existing_positions": changed,
            "title_update_required": title_change,
            "accepted_live_title": str(observed.get("lesson_title") or ""),
            "desired_title": expected_title,
            "creates_allowed": False,
            "deletes_allowed": False,
            "reorder_allowed": False,
            "block_name_changes_allowed": False,
            "block_source_changes_allowed": False,
            "preserved_step_ids": live_ids,
            "desired_fingerprint": desired_fp,
            "live_fingerprint": live_fp,
            "history_state": history_state,
        }
        legacy.write_json(report_dir / "migration-plan.json", plan)

        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "status": "UPDATE_REQUIRED" if (changed or title_change) else "NOOP_PENDING",
                    "plan": plan,
                    "stepik_writes_planned": len(changed) + (1 if title_change else 0),
                    "blockers": [],
                }
            )
            legacy.write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        recorder = legacy.DeploymentRecorder(store, identity)
        initial_fp = live_fp
        if records:
            started = next(
                (row for row in records if row.get("phase") == "EVENT_STARTED"), None
            )
            if isinstance(started, dict) and isinstance(started.get("fingerprint_before"), str):
                initial_fp = str(started["fingerprint_before"])
        recorder.ensure_started(
            operation_type="golden-content-8-to-8-refresh",
            state_before={
                "fixture_fingerprint": legacy._fixture_fingerprint(profile),
                "step_ids": live_ids,
            },
            expected_state={
                "desired_fingerprint": desired_fp,
                "step_count": 8,
                "step_ids": live_ids,
                "content_only": True,
            },
            stepik_object_ids={"lesson_id": int(lesson["id"]), "step_ids": live_ids},
            fingerprint_before=initial_fp,
        )

        working = deepcopy(lesson)
        operations: list[dict[str, Any]] = []
        try:
            working, title_operation = execute_lesson_title_update(
                client,
                working,
                expected_title=expected_title,
                recorder=recorder,
                operation_id=f"golden-title-{int(lesson['id'])}",
            )
        except LessonTitleWriteError as exc:
            raise GoldenContentRefreshError(str(exc)) from exc
        if title_operation is not None:
            operations.append(title_operation)
            report["stepik_writes"] = int(report["stepik_writes"]) + 1

        for current, expected in zip(_ordered_steps(working), desired_steps, strict=True):
            if legacy.step_equivalent(current, expected):
                continue
            step_id = int(current["step_source"]["id"])
            if step_id not in live_ids:
                raise GoldenContentRefreshError(
                    f"{TARGET_ID}: попытка обновить неизвестный step_id={step_id}"
                )
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
                recorder.write_result(
                    operation_id=operation_id,
                    status="AMBIGUOUS",
                    reason_code="golden-refresh-put-ambiguous",
                )
                raise
            except legacy.StepikAPIError:
                recorder.write_result(
                    operation_id=operation_id,
                    status="FAILED_KNOWN",
                    reason_code="golden-refresh-put-failed-known",
                )
                raise
            except Exception:
                recorder.write_result(
                    operation_id=operation_id,
                    status="AMBIGUOUS",
                    reason_code="golden-refresh-put-unclassified-after-dispatch",
                )
                raise
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
            try:
                readback = client.fetch_one("step-sources", step_id)
                legacy._assert_step_readback(readback, expected)
            except Exception:
                recorder.readback_failed(
                    operation_id=operation_id,
                    reason_code="golden-refresh-put-readback-mismatch",
                )
                raise
            observed_model = _replace_step_with_readback(
                working, step_id=step_id, readback=readback
            )
            observed_after_fp = legacy.live_lesson_fingerprint(observed_model)
            recorder.operation_readback(
                operation_id=operation_id,
                expected_fingerprint_after=expected_after_fp,
                observed_live_fingerprint=observed_after_fp,
            )
            working = observed_model
            operations.append(
                {"action": "UPDATE_STEP", "step_id": step_id, "position": expected.position}
            )
            report["stepik_writes"] = int(report["stepik_writes"]) + 1

        final_snapshot = client.inspect_course(COURSE_ID)
        legacy.write_json(report_dir / "course-snapshot.after.json", final_snapshot)
        final_lesson = legacy._live_target(
            final_snapshot,
            lesson_id=int(observed["stepik_lesson_id"]),
        )
        final_ids = _assert_same_eight_ids(final_lesson, baseline)
        _assert_content_only_shape(final_lesson, desired_steps)
        final_fp = legacy.live_lesson_fingerprint(final_lesson)
        if not lesson_transport_equivalent(
            final_lesson,
            expected_title=expected_title,
            expected_steps=desired_steps,
            language="ru",
            is_public=False,
        ):
            recorder.readback_failed(
                operation_id=None,
                reason_code="golden-refresh-final-readback-mismatch",
            )
            raise GoldenContentRefreshError(
                f"{TARGET_ID}: final live не transport-equivalent current 8-step canonical desired"
            )

        source_paths = [path for step in desired_steps for path in step.source_git_paths]
        status = (
            "APPLIED"
            if operations or history_state == "PARTIAL_CONFIRMED"
            else "NOOP_CONFIRMED"
        )
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
        next_state = _finalize_state(state=state, baseline=final_baseline, status=status)
        proposed = legacy._next_profile(profile, final_snapshot, sha=sha)
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
                    "- accepted golden shape: `8 steps → 8 steps`",
                    "- structural writes: `0`",
                    "- block name/source changes: `0`",
                    f"- event: `{identity.event_id}`",
                    f"- desired fingerprint: `{desired_fp}`",
                    f"- confirmed live fingerprint: `{final_fp}`",
                    f"- preserved step IDs: `{final_ids}`",
                    f"- write operations: `{operations}`",
                    "",
                    "Only existing learner-facing step text/HTML was eligible for guarded PUT. Issue state may be patched only after final read-back; golden-profile.next.json requires a separate evidence PR.",
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
                "rendered_steps": 8,
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
        GoldenContentRefreshError,
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
