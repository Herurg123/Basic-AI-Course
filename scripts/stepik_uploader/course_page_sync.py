from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from stepik_uploader.fingerprints import canonical_hash, html_fingerprint
    from stepik_uploader.history_runtime import find_incomplete_object_events
    from stepik_uploader.rendering import markdown_to_html
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, load_state, validate_state
else:
    from .api import StepikAPIError, StepikClient, StepikWriteAmbiguousError
    from .deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
        event_identity_from_environment,
        summarize_event,
    )
    from .fingerprints import canonical_hash, html_fingerprint
    from .history_runtime import find_incomplete_object_events
    from .rendering import markdown_to_html
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, load_state, validate_state


COURSE_ID = 299189
SOURCE_PATH = Path("04_course/stepik/course-page.md")
RICH_FIELDS = {"description", "target_audience", "requirements", "course_format"}
REQUIRED_FIELDS = (
    "title",
    "summary",
    "acquired_skills",
    "description",
    "target_audience",
    "requirements",
    "course_format",
    "workload",
)


class CoursePageSyncError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _section(text: str, number: int) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{number}\.\s+.*?\n(.*?)(?=^##\s+\d+\.|\Z)"
    )
    match = pattern.search(text)
    if not match:
        raise CoursePageSyncError(f"course-page.md: не найден раздел {number}")
    return match.group(1).strip()


def _plain_lines(block: str) -> list[str]:
    result: list[str] = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("**") and line.endswith("**") and ":" in line:
            continue
        if line.startswith("#") or line.startswith(">"):
            continue
        line = re.sub(r"^[-*]\s+", "", line).strip()
        if line:
            result.append(line)
    return result


def parse_course_page(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoursePageSyncError(f"Не удалось прочитать {path}: {exc}") from exc

    title_section = _section(text, 1)
    title_match = re.search(r"(?m)^\*\*(.+?)\*\*\s*$", title_section)
    if not title_match:
        raise CoursePageSyncError("course-page.md: не найдено утверждённое название")
    title = title_match.group(1).strip()

    meta = _section(text, 3)
    workload_match = re.search(r"(?m)^-\s*\*\*Рекомендуемая нагрузка:\*\*\s*(.+?)\s*$", meta)
    if not workload_match:
        raise CoursePageSyncError("course-page.md: не найдена рекомендуемая нагрузка")
    workload = workload_match.group(1).strip()

    summary_lines = _plain_lines(_section(text, 4))
    if not summary_lines:
        raise CoursePageSyncError("course-page.md: краткое описание пусто")
    summary = "\n".join(summary_lines).strip()

    skills_block = _section(text, 5)
    skills = [
        line.strip()
        for line in skills_block.splitlines()
        if line.strip()
        and not line.strip().startswith("Каждый пункт")
        and not line.strip().startswith("#")
    ]
    skills = [re.sub(r"\s{2,}$", "", line) for line in skills]
    if not skills:
        raise CoursePageSyncError("course-page.md: список «Чему вы научитесь» пуст")

    rich_sections = {
        "description": _section(text, 6),
        "target_audience": _section(text, 7),
        "requirements": _section(text, 8),
        "course_format": _section(text, 9),
    }
    rendered = {key: markdown_to_html(value).strip() for key, value in rich_sections.items()}
    if any(not value for value in rendered.values()):
        raise CoursePageSyncError("course-page.md: один из обязательных rich-text разделов пуст")

    result = {
        "title": title,
        "summary": summary,
        "acquired_skills": "\n".join(skills),
        "workload": workload,
        **rendered,
    }
    if set(result) != set(REQUIRED_FIELDS):
        raise CoursePageSyncError("course-page.md: внутренний parser contract нарушен")
    return result


def _normalized_value(field: str, value: Any) -> Any:
    if field in RICH_FIELDS:
        return html_fingerprint(str(value or ""))
    if field == "acquired_skills":
        if isinstance(value, list):
            return tuple(str(item).strip() for item in value if str(item).strip())
        return tuple(line.strip() for line in str(value or "").splitlines() if line.strip())
    return re.sub(r"\s+", " ", str(value or "")).strip()


def course_page_payload(course: dict[str, Any], *, fields: tuple[str, ...] = REQUIRED_FIELDS) -> dict[str, Any]:
    missing = [field for field in fields if field not in course]
    if missing:
        raise CoursePageSyncError(
            "Stepik course object не экспонирует обязательные поля карточки: " + ", ".join(missing)
        )
    return {field: _normalized_value(field, course.get(field)) for field in fields}


def course_page_fingerprint(course: dict[str, Any]) -> str:
    return canonical_hash(course_page_payload(course))


def desired_fingerprint(desired: dict[str, str]) -> str:
    return canonical_hash({field: _normalized_value(field, desired[field]) for field in REQUIRED_FIELDS})


def _same_page(course: dict[str, Any], desired: dict[str, str]) -> bool:
    live = course_page_payload(course)
    expected = {field: _normalized_value(field, desired[field]) for field in REQUIRED_FIELDS}
    return live == expected


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise CoursePageSyncError("Для course-page sync нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _baseline(course: dict[str, Any], desired: dict[str, str], *, sha: str, status: str) -> dict[str, Any]:
    return {
        "object_id": "course-page",
        "kind": "course_page",
        "stepik_course_id": COURSE_ID,
        "applied_source_sha": sha,
        "applied_at": _utc_now(),
        "applied_fingerprint": desired_fingerprint(desired),
        "source_git_paths": [str(SOURCE_PATH)],
        "fields": list(REQUIRED_FIELDS),
        "status": status,
        "readback": {field: course.get(field) for field in REQUIRED_FIELDS},
    }


def _close_pending(state: dict[str, Any], *, confirmed_at: str) -> dict[str, Any]:
    next_state = deepcopy(validate_state(state, course_id=COURSE_ID))
    pending = next_state.get("pending", {}).get("course_page")
    if not isinstance(pending, dict) or pending.get("status") != "PENDING":
        raise CoursePageSyncError("course-page не имеет текущего PENDING")
    next_state["pending"]["course_page"] = None
    next_state["updated_at"] = confirmed_at
    return validate_state(next_state, course_id=COURSE_ID)


def _event_artifact(identity: Any, baseline: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "event_id": identity.event_id,
        "source_sha": identity.source_sha,
        "status": status,
        "kind": "course_page",
        "object_id": "course-page",
        "baseline_after": baseline,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded private Stepik course-page sync")
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
        "mode": "course-page-sync",
        "course_id": args.course_id,
        "source_main_sha": sha,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
    }
    try:
        if args.course_id != COURSE_ID:
            raise CoursePageSyncError(f"course-page sync разрешён только для course_id={COURSE_ID}")
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=COURSE_ID)
        pending = state.get("pending", {}).get("course_page")
        if not isinstance(pending, dict) or pending.get("status") != "PENDING":
            raise CoursePageSyncError("course-page не имеет PENDING; blind metadata write запрещён")

        desired = parse_course_page(repo_root / SOURCE_PATH)
        desired_fp = desired_fingerprint(desired)
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        course_before = client.fetch_one("courses", COURSE_ID)
        write_json(report_dir / "course.before.json", course_before)
        if course_before.get("id") != COURSE_ID or course_before.get("language") != "ru":
            raise CoursePageSyncError("course-page sync требует exact ru course 299189")
        if course_before.get("is_public") is not False:
            raise CoursePageSyncError("course-page sync разрешён только пока course.is_public=false")
        before_fp = course_page_fingerprint(course_before)
        store = _history_store(sha)
        incomplete = find_incomplete_object_events(store, object_id="course-page")
        if len(incomplete) > 1:
            raise DeploymentHistoryError("course-page: найдено несколько incomplete events")

        identity = event_identity_from_environment(
            course_id=COURSE_ID,
            object_id="course-page",
            kind="course-page",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=before_fp,
            pending_first_sha=str(pending.get("first_pending_sha") or "") or None,
        )
        records = store.load(identity.event_id)
        summary = summarize_event(records) if records else None
        foreign = [item[0].event_id for item in incomplete if item[0].event_id != identity.event_id]
        if foreign:
            raise DeploymentHistoryError(f"course-page: incomplete event другой semantics/source: {foreign}")
        if summary and (summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes")):
            raise DeploymentHistoryError("course-page: unsafe prior write history требует reconcile")

        if summary and summary.get("final_readback_confirmed"):
            if not _same_page(course_before, desired):
                raise DeploymentHistoryError("course-page: immutable final history есть, но live больше не совпадает с desired")
            final = next(record for record in records if record.get("phase") == "FINAL_READBACK_CONFIRMED")
            baseline = final.get("actual_confirmed_state")
            if not isinstance(baseline, dict):
                raise DeploymentHistoryError("course-page: final history не содержит baseline")
            status = str(final.get("status"))
            next_state = _close_pending(state, confirmed_at=str(baseline.get("applied_at") or _utc_now()))
            write_json(report_dir / "sync-state.next.json", next_state)
            write_json(report_dir / "course-page-deployment-event.json", _event_artifact(identity, baseline, status))
            report.update({"verdict": "PASS", "status": "RECOVER_FINAL", "readback_verified": True, "blockers": []})
            write_json(report_dir / "run-report.json", report)
            return 0

        diff_fields = [
            field for field in REQUIRED_FIELDS
            if _normalized_value(field, course_before.get(field)) != _normalized_value(field, desired[field])
        ]
        write_json(report_dir / "course-page-plan.json", {
            "desired_fingerprint": desired_fp,
            "live_fingerprint": before_fp,
            "changed_fields": diff_fields,
            "desired": desired,
        })

        if not args.confirm_write:
            report.update({
                "verdict": "READY",
                "changed_fields": diff_fields,
                "stepik_writes_planned": 0 if not diff_fields else 1,
                "readback_required": True,
                "blockers": [],
            })
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type="course-page-sync",
            state_before={"fingerprint": before_fp},
            expected_state={"fingerprint": desired_fp},
            stepik_object_ids={"course_id": COURSE_ID},
            fingerprint_before=before_fp,
        )
        if diff_fields:
            operation_id = "course-page-put"
            recorder.write_intent(
                operation_id=operation_id,
                method="PUT",
                target=f"courses/{COURSE_ID}",
                fingerprint_before=before_fp,
                expected_fingerprint_after=desired_fp,
            )
            recorder.write_dispatch_started(operation_id=operation_id)
            try:
                client._request_write("PUT", f"/api/courses/{COURSE_ID}", {"course": desired})
            except StepikWriteAmbiguousError:
                recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="course-page-write-ambiguous")
                raise
            except StepikAPIError:
                recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="course-page-write-failed-known")
                raise
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
            report["stepik_writes"] = 1

        course_after = client.fetch_one("courses", COURSE_ID)
        write_json(report_dir / "course.after.json", course_after)
        if course_after.get("is_public") is not False or course_after.get("language") != "ru":
            recorder.readback_failed(operation_id=None, reason_code="course-safety-metadata-changed")
            raise CoursePageSyncError("После course-page write изменились private/language invariants")
        if not _same_page(course_after, desired):
            recorder.readback_failed(operation_id=None, reason_code="course-page-final-readback-mismatch")
            raise CoursePageSyncError("Финальный course-page read-back не совпал с canonical metadata")
        after_fp = course_page_fingerprint(course_after)
        if diff_fields:
            recorder.operation_readback(operation_id="course-page-put", expected_fingerprint_after=after_fp)
        baseline = _baseline(course_after, desired, sha=sha, status="APPLIED" if diff_fields else "NOOP_CONFIRMED")
        status = "APPLIED" if diff_fields else "NOOP_CONFIRMED"
        recorder.final_readback(
            fingerprint_after=after_fp,
            stepik_object_ids={"course_id": COURSE_ID},
            status=status,
            baseline_after=baseline,
        )
        next_state = _close_pending(state, confirmed_at=str(baseline["applied_at"]))
        write_json(report_dir / "sync-state.next.json", next_state)
        write_json(report_dir / "course-page-deployment-event.json", _event_artifact(identity, baseline, status))
        (report_dir / "sync-journal.md").write_text(
            "\n".join([
                "### COURSE_PAGE_SYNC",
                "",
                f"- source main SHA: `{sha}`",
                f"- Stepik course ID: `{COURSE_ID}`",
                f"- status: `{status}`",
                f"- event: `{identity.event_id}`",
                f"- fingerprint: `{after_fp}`",
                f"- changed fields: `{diff_fields}`",
                "",
                "Machine state должен быть patched только после final read-back; durable history затем получает MACHINE_STATE_COMMITTED.",
            ]) + "\n",
            encoding="utf-8",
        )
        report.update({
            "verdict": "PASS",
            "status": status,
            "event_id": identity.event_id,
            "changed_fields": diff_fields,
            "readback_verified": True,
            "blockers": [],
        })
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        CoursePageSyncError,
        DeploymentHistoryError,
        StepikAPIError,
        SyncStateError,
        OSError,
        ValueError,
    ) as exc:
        report.update({"verdict": "BLOCKED", "blockers": [str(exc)]})
        write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
