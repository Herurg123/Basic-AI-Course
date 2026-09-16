from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.course_page_sync import (
        COURSE_ID,
        SOURCE_PATH,
        _assert_course_safety,
        _baseline,
        _close_pending,
        _event_artifact,
        _same_page,
        parse_course_page,
        preserved_course_state,
    )
    from stepik_uploader.deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore
    from stepik_uploader.fingerprints import canonical_hash
    from stepik_uploader.history_runtime import find_incomplete_object_events, identity_from_records
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, load_state
else:
    from .api import StepikAPIError, StepikClient
    from .course_page_sync import (
        COURSE_ID,
        SOURCE_PATH,
        _assert_course_safety,
        _baseline,
        _close_pending,
        _event_artifact,
        _same_page,
        parse_course_page,
        preserved_course_state,
    )
    from .deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore
    from .fingerprints import canonical_hash
    from .history_runtime import find_incomplete_object_events, identity_from_records
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, load_state


class CoursePageRecoveryError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise CoursePageRecoveryError("Для course-page recovery нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write-free probe / confirmed finalization for Stepik course-page commit gap")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    parser.add_argument(
        "--confirm-recovery",
        action="store_true",
        help="Разрешить только durable FINAL_READBACK_CONFIRMED recovery; Stepik writes всё равно запрещены.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "course-page-commit-gap-recovery",
        "course_id": args.course_id,
        "source_main_sha": sha,
        "confirm_recovery": bool(args.confirm_recovery),
        "applicable": False,
        "stepik_writes": 0,
        "history_writes": 0,
    }
    try:
        if args.course_id != COURSE_ID:
            raise CoursePageRecoveryError(f"Recovery разрешён только для course_id={COURSE_ID}")
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=COURSE_ID)
        pending = state.get("pending", {}).get("course_page")
        if pending is None:
            report.update({"verdict": "NOOP", "reason": "course-page-not-pending"})
            write_json(report_dir / "course-page-commit-gap-recovery.json", report)
            return 0
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise CoursePageRecoveryError("course-page pending state повреждён")

        store = _store(sha)
        incomplete = [
            item for item in find_incomplete_object_events(store, object_id="course-page")
            if item[0].source_sha == sha and item[0].course_id == COURSE_ID
        ]
        if not incomplete:
            report.update({"verdict": "NOOP", "reason": "no-current-source-incomplete-event"})
            write_json(report_dir / "course-page-commit-gap-recovery.json", report)
            return 0
        if len(incomplete) != 1:
            raise DeploymentHistoryError("course-page: найдено несколько current-source incomplete events")

        identity, records, summary = incomplete[0]
        if identity.kind != "course-page":
            raise DeploymentHistoryError(f"course-page: unexpected incomplete kind={identity.kind}")
        loaded = identity_from_records(records, expected_event_id=identity.event_id)
        if loaded.source_sha != sha or loaded.course_id != COURSE_ID:
            raise DeploymentHistoryError("course-page: history provenance не соответствует current release")
        if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
            raise DeploymentHistoryError("course-page: unsafe prior write history запрещает automatic recovery")

        desired = parse_course_page(repo_root / SOURCE_PATH)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        course = client.fetch_one("courses", COURSE_ID)
        _assert_course_safety(course)
        current_preserved_fp = canonical_hash(preserved_course_state(course))
        started = records[0] if records else {}
        state_before = started.get("state_before") if isinstance(started, dict) else None
        expected_preserved_fp = state_before.get("preserved_fingerprint") if isinstance(state_before, dict) else None
        if not isinstance(expected_preserved_fp, str):
            raise DeploymentHistoryError("course-page: EVENT_STARTED не содержит preserved_fingerprint")
        if current_preserved_fp != expected_preserved_fp:
            raise DeploymentHistoryError("course-page: preserved metadata drifted относительно pre-write state")

        if not _same_page(course, desired):
            if not summary.get("writes_started"):
                report.update({"verdict": "NOOP", "reason": "prewrite-event-live-still-old"})
                write_json(report_dir / "course-page-commit-gap-recovery.json", report)
                return 0
            raise DeploymentHistoryError("course-page: write начинался, но live не равен exact canonical desired")

        final = next((record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED"), None)
        if final is not None:
            baseline = final.get("actual_confirmed_state")
            status = str(final.get("status"))
            if not isinstance(baseline, dict) or status not in {"APPLIED", "NOOP_CONFIRMED"}:
                raise DeploymentHistoryError("course-page: final history повреждён")
            if baseline.get("preserved_fingerprint") != current_preserved_fp:
                raise DeploymentHistoryError("course-page: final baseline preserved fingerprint не совпадает с live")
        else:
            if int(summary.get("writes_started") or 0) != 1 or int(summary.get("confirmed_operation_count") or 0) != 1:
                raise DeploymentHistoryError(
                    "course-page: live уже desired, но нет единственного confirmed PUT read-back для write-free finalization"
                )
            baseline = _baseline(course, desired, sha=sha, status="APPLIED")
            status = "APPLIED"
            if args.confirm_recovery:
                recorder = DeploymentRecorder(store, identity)
                recorder.final_readback(
                    fingerprint_after=identity.desired_fingerprint,
                    stepik_object_ids={"course_id": COURSE_ID},
                    status=status,
                    baseline_after=baseline,
                )
                report["history_writes"] = 1
            else:
                report.update(
                    {
                        "verdict": "READY",
                        "applicable": True,
                        "status": "RECOVERABLE_FINAL",
                        "event_id": identity.event_id,
                        "readback_verified": True,
                        "requires_confirm_recovery": True,
                    }
                )
                write_json(report_dir / "course-page-commit-gap-recovery.json", report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0

        next_state = _close_pending(state, confirmed_at=str(baseline.get("applied_at")))
        write_json(report_dir / "sync-state.next.json", next_state)
        write_json(report_dir / "course-page-deployment-event.json", _event_artifact(identity, baseline, status))
        (report_dir / "sync-journal.md").write_text(
            "\n".join([
                "### COURSE_PAGE_COMMIT_GAP_RECOVERY",
                "",
                f"- source main SHA: `{sha}`",
                f"- event: `{identity.event_id}`",
                f"- status: `{status}`",
                "- Stepik writes during recovery: `0`",
                f"- durable history writes during this invocation: `{report['history_writes']}`",
                "- live course page re-read: exact canonical desired",
                "- preserved metadata fingerprint: exact pre-write match",
                "",
                "Recovery только закрывает доказанный Issue/history commit gap; повторный course PUT не выполняется.",
            ]) + "\n",
            encoding="utf-8",
        )
        report.update({"verdict": "PASS", "applicable": True, "event_id": identity.event_id, "status": status, "readback_verified": True})
        write_json(report_dir / "course-page-commit-gap-recovery.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        CoursePageRecoveryError,
        DeploymentHistoryError,
        StepikAPIError,
        SyncStateError,
        OSError,
        ValueError,
    ) as exc:
        report.update({"verdict": "BLOCKED", "blockers": [str(exc)]})
        write_json(report_dir / "course-page-commit-gap-recovery.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
