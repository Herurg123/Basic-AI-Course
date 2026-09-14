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
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from stepik_uploader.history_runtime import find_incomplete_object_events, find_object_events, final_confirmed_record
    from stepik_uploader.planner import plan_dry_run
    from stepik_uploader.reconcile import classify_reconcile
    from stepik_uploader.reporting import build_report, write_json
    from stepik_uploader.stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from stepik_uploader.sync_state import SyncStateError, assess_sync, baseline_for, close_lesson_pending, load_state, with_record
    from stepik_uploader.writer import ContentWriteError, execute_content_sync_one
else:
    from .api import StepikAPIError, StepikClient
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .content import ContentCompileError, TEST_LESSON_ID, compile_test_lesson
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .golden import GoldenProfileError, load_golden_profile, validate_golden_profile
    from .history_runtime import find_incomplete_object_events, find_object_events, final_confirmed_record
    from .planner import plan_dry_run
    from .reconcile import classify_reconcile
    from .reporting import build_report, write_json
    from .stepik_uploader import count_snapshot, mark_golden_profile_result, source_sha
    from .sync_state import SyncStateError, assess_sync, baseline_for, close_lesson_pending, load_state, with_record
    from .writer import ContentWriteError, execute_content_sync_one

GOLDEN_PROFILE_PATH = Path("04_course/stepik/automation/golden-profile.v1.json")
BLOCKED_SYNC_STATUSES = {
    "BASELINE_BOOTSTRAP_REQUIRED",
    "BASELINE_MISSING_BLOCKED",
    "DRIFT_BLOCKED",
    "METADATA_UPDATE_BLOCKED",
    "STRUCTURAL_UPDATE_BLOCKED",
}


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для live sync нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET в GitHub Actions Secrets")
    return client_id, client_secret


def _history_store(source_sha_value: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=source_sha_value,
    )


def _manifest_lesson(manifest: dict[str, Any], canonical_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == canonical_id:
                return module, lesson
    raise ContentCompileError(f"В derived manifest отсутствует {canonical_id}")


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [s for s in snapshot.get("sections", []) if s.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден единственный section position={module_position}")
    units = [u for u in sections[0].get("units", []) if u.get("position") == lesson_position]
    if len(units) != 1:
        raise ContentWriteError(f"Не найден единственный unit section={module_position} position={lesson_position}")
    lesson = units[0].get("lesson")
    if not isinstance(lesson, dict):
        raise ContentWriteError("В unit отсутствует lesson")
    return lesson


def _step_ids(lesson: dict[str, Any]) -> list[int]:
    result: list[int] = []
    for item in lesson.get("steps", []):
        source = item.get("step_source")
        if not isinstance(source, dict) or not isinstance(source.get("id"), int):
            raise ContentWriteError("Live lesson не содержит однозначные step_source IDs")
        result.append(int(source["id"]))
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _journal_markdown(
    *,
    source_sha_value: str,
    result: Any | None,
    record: dict[str, Any],
    confirmed_at: str,
    status: str,
    event_id: str,
    recovery: bool = False,
) -> str:
    run_url = ""
    if os.getenv("GITHUB_SERVER_URL") and os.getenv("GITHUB_REPOSITORY") and os.getenv("GITHUB_RUN_ID"):
        run_url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    operations = [] if result is None else list(result.operations)
    updated_positions = [op.get("position") for op in operations if op.get("action") == "UPDATE_STEP"]
    if recovery:
        heading = f"### RECOVERED_STATE: `{TEST_LESSON_ID}` восстановлен из доказанного deployment event"
        operation_line = "- повторные Stepik writes: `0`"
        final_note = "Machine state восстановлен только потому, что immutable history уже содержала подтверждённый final read-back, а свежий live fingerprint совпал с ним."
    elif status == "APPLIED":
        heading = f"### APPLIED: `{TEST_LESSON_ID}` синхронизирован со Stepik"
        operation_line = f"- обновлённые позиции steps: `{updated_positions}`"
        final_note = "Baseline и pending меняются только после durable FINAL_READBACK_CONFIRMED."
    else:
        heading = f"### NOOP_CONFIRMED: `{TEST_LESSON_ID}` уже синхронизирован"
        operation_line = "- Stepik writes: `0`"
        final_note = "Live Stepik, канон и baseline совпали; фиктивная запись не выполнялась."
    lines = [
        heading,
        "",
        f"- source main SHA: `{source_sha_value}`",
        f"- deployment event: `{event_id}`",
        f"- Stepik lesson ID: `{record['stepik_lesson_id']}`",
        operation_line,
        f"- подтверждённый read-back: `{confirmed_at}`",
        f"- fingerprint: `{record['applied_fingerprint']}`",
    ]
    if run_url:
        lines.append(f"- workflow run: {run_url}")
    lines.extend(["", final_note])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drift-guarded Stepik sync/reconcile runtime")
    parser.add_argument("mode", choices=["sync-status", "sync-changed", "sync-reconcile"])
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
    recorder: DeploymentRecorder | None = None

    try:
        manifest = build_structural_manifest(repo_root, source_sha=sha)
        write_json(report_dir / "build-manifest.structural.json", manifest)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        write_json(report_dir / "course-snapshot.json", snapshot)
        plan = plan_dry_run(manifest, snapshot)
        profile = load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        profile_blockers = validate_golden_profile(profile, snapshot, manifest, allow_course_publication_change=True)
        golden_status = mark_golden_profile_result(plan, profile_blockers)
        if golden_status != "confirmed" or plan.blockers:
            raise ContentWriteError("pre-sync live guards не пройдены: " + "; ".join(sorted(set(profile_blockers + plan.blockers))))

        module, lesson = _manifest_lesson(manifest, TEST_LESSON_ID)
        if lesson.get("golden_read_only") or lesson.get("independence_sensitive") or lesson.get("f1_sensitive"):
            raise ContentWriteError("Текущий pilot sync target попал в protected lesson")
        free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source")
        if not isinstance(free_answer_source, dict):
            raise ContentCompileError("В golden profile отсутствует free_answer_source")
        compiled = compile_test_lesson(repo_root, free_answer_source=free_answer_source, lesson_id=TEST_LESSON_ID)
        expected_title = f"{TEST_LESSON_ID} — {lesson['title']}"
        live_lesson = _live_lesson(snapshot, module_position=int(module["position"]), lesson_position=int(lesson["position"]))
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        baseline = baseline_for(state, TEST_LESSON_ID)
        assessment = assess_sync(
            canonical_id=TEST_LESSON_ID,
            live_lesson=live_lesson,
            expected_title=expected_title,
            expected_steps=compiled,
            baseline=baseline,
        )
        sync_payload = {
            "scope": "pilot-M02-L01-until-general-compiler-is-enabled",
            "canonical_id": TEST_LESSON_ID,
            "course_is_public": snapshot.get("course", {}).get("is_public"),
            "lesson_is_public": live_lesson.get("is_public"),
            "status": assessment.status,
            "desired_fingerprint": assessment.desired_fingerprint,
            "live_fingerprint": assessment.live_fingerprint,
            "baseline_fingerprint": assessment.baseline_fingerprint,
            "changed_step_positions": list(assessment.changed_step_positions),
            "reasons": list(assessment.reasons),
        }
        write_json(report_dir / "sync-status.json", sync_payload)
        report = build_report(
            mode=args.mode,
            source_sha=sha,
            course_id=args.course_id,
            manifest=manifest,
            plan=plan,
            read_objects=count_snapshot(snapshot),
        )
        report["sync"] = sync_payload
        report["golden_profile_status"] = golden_status

        if args.mode == "sync-status":
            report["verdict"] = "BLOCKED" if assessment.status in BLOCKED_SYNC_STATUSES else "PASS"
            report["blockers"] = list(assessment.reasons) if report["verdict"] == "BLOCKED" else []
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2 if report["verdict"] == "BLOCKED" else 0

        store = _history_store(sha)
        pending = state.get("pending", {}).get("lessons", {}).get(TEST_LESSON_ID)
        pending_first_sha = pending.get("first_pending_sha") if isinstance(pending, dict) else None
        current_identity = event_identity_from_environment(
            course_id=args.course_id,
            object_id=TEST_LESSON_ID,
            kind="lesson",
            source_sha=sha,
            desired_fingerprint=assessment.desired_fingerprint,
            baseline_fingerprint=assessment.baseline_fingerprint,
            pending_first_sha=pending_first_sha,
        )

        object_events = find_object_events(store, object_id=TEST_LESSON_ID)
        committed_candidates: list[tuple[str, str, str]] = []
        for identity, records, summary in object_events:
            committed_baseline = summary.get("committed_baseline_after")
            if not summary.get("machine_state_committed") or not isinstance(committed_baseline, dict):
                continue
            committed_records = [record for record in records if record.get("phase") == "MACHINE_STATE_COMMITTED"]
            if len(committed_records) != 1:
                continue
            committed_at = committed_records[0].get("confirmed_at")
            fingerprint = committed_baseline.get("applied_fingerprint")
            if isinstance(committed_at, str) and isinstance(fingerprint, str):
                committed_candidates.append((committed_at, identity.event_id, fingerprint))

        latest_committed_event_ids: list[str] = []
        latest_committed_fingerprints: set[str] = set()
        committed_history_ambiguous = False
        committed_history_live_match = False
        if committed_candidates:
            latest_time = max(value[0] for value in committed_candidates)
            latest = [value for value in committed_candidates if value[0] == latest_time]
            latest_committed_event_ids = sorted(value[1] for value in latest)
            latest_committed_fingerprints = {value[2] for value in latest}
            committed_history_ambiguous = len(latest_committed_fingerprints) != 1
            if not committed_history_ambiguous:
                latest_fp = next(iter(latest_committed_fingerprints))
                committed_history_live_match = latest_fp == assessment.live_fingerprint

        incomplete = find_incomplete_object_events(store, object_id=TEST_LESSON_ID)
        conflicting_event = len(incomplete) > 1 or committed_history_ambiguous
        if incomplete:
            event_identity, event_records, event_summary = incomplete[0]
        else:
            event_identity = current_identity
            event_records = store.load(event_identity.event_id)
            event_summary = summarize_event(event_records)

        if args.mode == "sync-changed" and not args.confirm_write:
            raise ContentWriteError("sync-changed требует явный confirm_write")

        if args.mode in {"sync-changed", "sync-reconcile"}:
            recorder = DeploymentRecorder(store, event_identity)

        if args.mode == "sync-changed" and not any(record.get("phase") == "EVENT_STARTED" for record in event_records):
            recorder.ensure_started(
                operation_type="lesson-content-sync",
                state_before=baseline,
                expected_state={"desired_fingerprint": assessment.desired_fingerprint, "source_sha": sha},
                stepik_object_ids={"lesson_id": int(live_lesson["id"]), "step_ids": _step_ids(live_lesson)},
                fingerprint_before=assessment.live_fingerprint,
            )
            event_identity = recorder.identity
            event_records = recorder.records(refresh=True)
            event_summary = summarize_event(event_records)

        decision_source_sha = event_identity.source_sha if event_records else sha
        decision_desired_fp = event_identity.desired_fingerprint if event_records else assessment.desired_fingerprint
        decision = classify_reconcile(
            source_sha=decision_source_sha,
            current_main_sha=sha,
            live_fingerprint=assessment.live_fingerprint,
            desired_fingerprint=decision_desired_fp,
            baseline_fingerprint=assessment.baseline_fingerprint,
            event_summary=event_summary if event_records else None,
            event_source_sha=event_identity.source_sha if event_records else None,
            committed_history_live_match=committed_history_live_match,
            golden_read_only=False,
            metadata_divergence=assessment.status == "METADATA_UPDATE_BLOCKED",
            structural_divergence=assessment.status == "STRUCTURAL_UPDATE_BLOCKED",
            conflicting_event=conflicting_event,
        )
        reconcile_payload = {
            **decision.as_dict(),
            "event_id": event_identity.event_id,
            "event_source_sha": event_identity.source_sha,
            "event_summary": event_summary if event_records else None,
            "live_fingerprint": assessment.live_fingerprint,
            "desired_fingerprint": assessment.desired_fingerprint,
            "baseline_fingerprint": assessment.baseline_fingerprint,
            "current_main_sha": sha,
            "committed_history_live_match": committed_history_live_match,
            "latest_committed_history_event_ids": latest_committed_event_ids,
            "latest_committed_history_fingerprints": sorted(latest_committed_fingerprints),
            "latest_committed_history_ambiguous": committed_history_ambiguous,
        }
        write_json(report_dir / "reconcile-report.json", reconcile_payload)
        report["reconcile"] = reconcile_payload

        if recorder is not None:
            recorder.reconcile_classified(
                classification=decision.classification,
                action=decision.action,
                reason_codes=decision.reason_codes,
                live_fingerprint=assessment.live_fingerprint,
                baseline_fingerprint=assessment.baseline_fingerprint,
                current_main_sha=sha,
                owner_approval_required=decision.owner_approval_required,
            )

        if args.mode == "sync-reconcile":
            report["verdict"] = "PASS" if decision.auto_allowed and not decision.action.startswith("STOP") else "BLOCKED"
            report["blockers"] = [] if report["verdict"] == "PASS" else list(decision.reason_codes)
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["verdict"] == "PASS" else 2

        if recorder is None:
            raise DeploymentHistoryError("sync-changed не получил durable deployment recorder")

        if not decision.auto_allowed or decision.action.startswith("STOP"):
            recorder.recovery_classified(classification=decision.classification, reason_codes=decision.reason_codes)
            raise ContentWriteError(
                f"reconcile={decision.classification}: {'; '.join(decision.reason_codes)}"
            )

        result = None
        recovered_state_only = False
        if decision.action == "AUTO_RECOVER_MACHINE_STATE":
            final = final_confirmed_record(event_records)
            if final is None or not isinstance(final.get("actual_confirmed_state"), dict):
                raise DeploymentHistoryError("History обещает final read-back, но confirmed baseline snapshot отсутствует")
            state_record = final["actual_confirmed_state"]
            confirmed_at = str(final.get("confirmed_at"))
            confirmation_status = str(final.get("status"))
            target_pending = state.get("pending", {}).get("lessons", {}).get(TEST_LESSON_ID)
            state_already_confirmed = baseline == state_record and target_pending is None
            if state_already_confirmed:
                next_state = state
            else:
                next_state = state
                if confirmation_status == "APPLIED":
                    next_state = with_record(next_state, canonical_id=TEST_LESSON_ID, record=state_record)
                next_state = close_lesson_pending(
                    next_state,
                    canonical_id=TEST_LESSON_ID,
                    confirmed_at=confirmed_at,
                    confirmation_status=confirmation_status,
                )
            recovered_state_only = True
        elif decision.action == "NOOP":
            state_record = baseline
            if not isinstance(state_record, dict):
                raise ContentWriteError("NOOP_CONFIRMED невозможен без подтверждённого baseline")
            confirmed_at = _utc_now()
            confirmation_status = "NOOP_CONFIRMED"
            if not event_summary.get("final_readback_confirmed"):
                recorder.final_readback(
                    fingerprint_after=assessment.live_fingerprint,
                    stepik_object_ids={"lesson_id": int(live_lesson["id"]), "step_ids": _step_ids(live_lesson)},
                    status=confirmation_status,
                    baseline_after=state_record,
                )
            next_state = close_lesson_pending(
                state,
                canonical_id=TEST_LESSON_ID,
                confirmed_at=confirmed_at,
                confirmation_status=confirmation_status,
            )
        elif decision.action in {"NORMAL_SYNC_ROUTE", "AUTO_CONTINUE_FROM_CONFIRMED_PREFIX"}:
            result = execute_content_sync_one(
                client,
                snapshot,
                canonical_id=TEST_LESSON_ID,
                expected_steps=compiled,
                module_position=int(module["position"]),
                lesson_position=int(lesson["position"]),
                expected_title=expected_title,
                baseline=baseline,
                source_sha=sha,
                recorder=recorder,
                recovery_expected_live_fingerprint=(
                    event_summary.get("last_confirmed_operation_fingerprint")
                    if decision.action == "AUTO_CONTINUE_FROM_CONFIRMED_PREFIX"
                    else None
                ),
            )
            if result.after_snapshot is not None:
                write_json(report_dir / "course-snapshot.after.json", result.after_snapshot)
            if result.state_record is None or not result.verified:
                raise ContentWriteError("Writer не сформировал подтверждённый final state")
            state_record = result.state_record
            confirmed_at = _utc_now()
            confirmation_status = "APPLIED" if result.operations else "NOOP_CONFIRMED"
            next_state = state
            if confirmation_status == "APPLIED":
                next_state = with_record(next_state, canonical_id=TEST_LESSON_ID, record=state_record)
            next_state = close_lesson_pending(
                next_state,
                canonical_id=TEST_LESSON_ID,
                confirmed_at=confirmed_at,
                confirmation_status=confirmation_status,
            )
        else:
            raise ContentWriteError(f"Неизвестное reconcile action: {decision.action}")

        write_json(report_dir / "sync-state.next.json", next_state)
        event_payload = {
            "event_id": event_identity.event_id,
            "canonical_id": TEST_LESSON_ID,
            "source_sha": event_identity.source_sha,
            "status": confirmation_status,
            "recovered_state_only": recovered_state_only,
        }
        write_json(report_dir / "deployment-event.json", event_payload)
        (report_dir / "sync-journal.md").write_text(
            _journal_markdown(
                source_sha_value=event_identity.source_sha,
                result=result,
                record=state_record,
                confirmed_at=confirmed_at,
                status=confirmation_status,
                event_id=event_identity.event_id,
                recovery=recovered_state_only,
            ),
            encoding="utf-8",
        )

        operations = [] if result is None else result.operations
        report["deployment_event_id"] = event_identity.event_id
        report["stepik_lesson_id"] = int(state_record["stepik_lesson_id"])
        report["write_operations"] = operations
        report["updated"] = sum(1 for op in operations if op.get("action") == "UPDATE_STEP")
        report["created"] = 0
        report["final_step_ids"] = list(state_record.get("step_ids", []))
        report["readback_verified"] = True
        report["state_only_recovery"] = recovered_state_only
        report["blockers"] = []
        report["verdict"] = "PASS"
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        CanonicalBuildError,
        ContentCompileError,
        ContentWriteError,
        DeploymentHistoryError,
        GoldenProfileError,
        SyncStateError,
        StepikAPIError,
        RuntimeError,
    ) as exc:
        if recorder is not None:
            try:
                records = recorder.records(refresh=True)
                summary = summarize_event(records)
                started_deployment = any(record.get("phase") == "EVENT_STARTED" for record in records)
                if started_deployment and not summary.get("final_readback_confirmed") and not any(
                    str(phase).startswith("FAILED_") for phase in summary.get("phases", [])
                ):
                    recorder.failure(
                        reason_code=f"runtime-{exc.__class__.__name__.lower()}",
                        before_any_write=not summary.get("external_write_started"),
                    )
            except DeploymentHistoryError:
                pass
        report = {
            "course_id": args.course_id,
            "source_main_sha": sha,
            "mode": args.mode,
            "verdict": "BLOCKED",
            "blockers": [f"sync:{exc}"],
            "write_retry_policy": "no automatic blind write retry; use history-backed reconcile/recovery",
        }
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
