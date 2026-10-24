"""Recover one proven NOOP machine-state commit gap, without any Stepik writes.

Incident: Stepik M06-L04 event evt-627ab4... had FINAL_READBACK_CONFIRMED
and no Stepik write, but the old runtime closed PENDING while retaining the
pre-reconciliation canonical baseline. This tool only copies the exact
immutable final record into Issue #54 after fresh read-back.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

from .api import StepikClient, StepikAPIError
from .deployment_history import DeploymentHistoryError, GitHubHistoryStore, utc_now
from .fingerprints import live_lesson_fingerprint
from .history_runtime import (
    final_confirmed_record, identity_from_records, mark_machine_state_committed,
)
from .sync_state import load_state, validate_state
from .stepik_uploader import source_sha

COURSE_ID = 299189
OBJECT_ID = "M06-L04"
LESSON_ID = 2591729
PREVIOUS_SHA = "9e73258db9377e1e709cc9a711bf6e1c66380a07"
EVENT_ID = "evt-627ab4a7a572fe63f1cccba6a16978ff"
RECONCILED_EVENT_ID = "evt-1433d5dd0f02668e42a42590ef93abf0"
INTERMEDIATE_FP = "sha256:6ceaff791df2dc635da50cb4d5f372a83901b41707594c63cee6fb5ae25c124f"
DESIRED_FP = "sha256:dd64e0d54c237b5f3665297e405595f66af6da47e1161286a1f4f3e07bb57ec4"
FIRST_PENDING_SHA = "ba1dc5e8b76f158fbda5130514651bd68649e166"
STEP_IDS = [11291316, 11346941, 11346949, 11346957, 11346967,
            11346977, 11346980, 11346993, 11347013, 11347029, 11598445]
EXPECTED_SOURCE_PATHS = [
    "04_course/M06/M06-L04/lesson.md",
    "04_course/M06/M06-L04/stepik-plan.md",
    "04_course/stepik/how-to-save-practice.md",
    "05_assets/M06/M06-L04/M06-L04-A01.md",
    "05_assets/M06/M06-L04/M06-L04-A02.md",
    "05_assets/M06/M06-L04/M06-L04-A03.md",
]


def proven_final(records: list[dict]) -> dict:
    identity = identity_from_records(records, expected_event_id=EVENT_ID)
    if (
        identity.event_id != EVENT_ID
        or identity.course_id != COURSE_ID
        or identity.kind != "lesson"
        or identity.object_id != OBJECT_ID
        or identity.source_sha != PREVIOUS_SHA
        or identity.desired_fingerprint != DESIRED_FP
        or identity.baseline_fingerprint_before != INTERMEDIATE_FP
        or identity.pending_first_sha != FIRST_PENDING_SHA
    ):
        raise DeploymentHistoryError("Не соответствует immutable identity proven NOOP M06-L04")
    phases = [record.get("phase") for record in records]
    if set(phases) - {"EVENT_STARTED", "FINAL_READBACK_CONFIRMED", "MACHINE_STATE_COMMITTED"}:
        raise DeploymentHistoryError("В Noop WAL есть неучтённые операции записи")
    if phases.count("EVENT_STARTED") != 1 or phases.count("FINAL_READBACK_CONFIRMED") != 1 or phases.count("MACHINE_STATE_COMMITTED") > 1:
        raise DeploymentHistoryError("В NOOP WAL неединственные start/final/commit records")
    initial = next(r for r in records if r["phase"] == "EVENT_STARTED")
    if (
        initial.get("fingerprint_before") != INTERMEDIATE_FP
        or initial.get("operation_type") != "lesson-content-refresh"
        or initial.get("stepik_object_ids", {}).get("lesson_id") != LESSON_ID
        or initial.get("stepik_object_ids", {}).get("step_ids") != STEP_IDS
    ):
        raise DeploymentHistoryError("Исходное состояние NOOP event изменилось")
    final = final_confirmed_record(records)
    if (
        final is None
        or final.get("status") != "NOOP_CONFIRMED"
        or final.get("fingerprint_after") != DESIRED_FP
        or final.get("observed_live_fingerprint") != INTERMEDIATE_FP
        or final.get("read_back_result") != "CONFIRMED"
    ):
        raise DeploymentHistoryError("NOOP final read-back не подтверждён ожидаемым WAL")
    record = final.get("actual_confirmed_state")
    if (
        not isinstance(record, dict)
        or record.get("canonical_id") != OBJECT_ID
        or record.get("stepik_lesson_id") != LESSON_ID
        or record.get("step_ids") != STEP_IDS
        or record.get("source_git_paths") != EXPECTED_SOURCE_PATHS
        or record.get("applied_fingerprint") != DESIRED_FP
        or record.get("confirmed_live_fingerprint") != INTERMEDIATE_FP
        or record.get("applied_source_sha") != PREVIOUS_SHA
        or not isinstance(record.get("applied_at"), str)
    ):
        raise DeploymentHistoryError("Неожиданный actual_confirmed_state в immutable финальном WAL")
    if phases.count("MACHINE_STATE_COMMITTED") == 1:
        committed = next(r for r in records if r["phase"] == "MACHINE_STATE_COMMITTED")
        if committed.get("status") != "NOOP_CONFIRMED" or committed.get("baseline_after") != record:
            raise DeploymentHistoryError("Существующий terminal commit не совпадает с FINAL_READBACK")
    return record


def verified_live(snapshot: dict, baseline: dict) -> str:
    course = snapshot.get("course", {})
    if course.get("id") != COURSE_ID or course.get("is_public") is not False:
        raise DeploymentHistoryError("Приватность курса или course ID изменились")
    sections = [x for x in snapshot.get("sections", []) if x.get("position") == 7]
    if len(sections) != 1:
        raise DeploymentHistoryError("Неверное положение модуля M06")
    units = [x for x in sections[0].get("units", []) if x.get("position") == 4]
    if len(units) != 1:
        raise DeploymentHistoryError("Неверное положение урока M06-L04")
    lesson = units[0].get("lesson")
    if not isinstance(lesson, dict) or lesson.get("id") != LESSON_ID:
        raise DeploymentHistoryError("Неверный Stepik ID урока")
    if lesson.get("title") != "Проверьте новые ситуации без готового маршрута" or lesson.get("is_public") is not False or lesson.get("language") != "ru":
        raise DeploymentHistoryError("Урок больше не private/ru или его название изменилось")
    steps = sorted(lesson.get("steps", []), key=lambda x: x["step_source"]["position"])
    if [x["step_source"]["position"] for x in steps] != list(range(1, 12)) or [x["step_source"]["id"] for x in steps] != STEP_IDS:
        raise DeploymentHistoryError("Stepik шаги не совпадают с immutable event")
    if baseline.get("step_ids") != STEP_IDS or baseline.get("stepik_lesson_id") != LESSON_ID:
        raise DeploymentHistoryError("Machine baseline содержит иной набор шагов")
    actual = live_lesson_fingerprint(lesson)
    if actual != INTERMEDIATE_FP:
        raise DeploymentHistoryError("Фактический live контент M06-L04 изменился: " + actual)
    return actual


def planned_state(state: dict, final_record: dict) -> dict:
    state = validate_state(state, course_id=COURSE_ID)
    if OBJECT_ID in state.get("pending", {}).get("lessons", {}):
        raise DeploymentHistoryError("M06-L04 снова PENDING; восстановление невозможно без расследования")
    existing = state["lessons"].get(OBJECT_ID)
    if not isinstance(existing, dict):
        raise DeploymentHistoryError("Missing machine baseline")
    if existing == final_record:
        return state
    if (
        existing.get("stepik_lesson_id") != LESSON_ID
        or existing.get("step_ids") != STEP_IDS
        or existing.get("partial_reconciliation") != RECONCILED_EVENT_ID
        or existing.get("applied_fingerprint") != INTERMEDIATE_FP
        or existing.get("confirmed_live_fingerprint") != INTERMEDIATE_FP
        or existing.get("applied_source_sha") != "bcf20b6ce0c5ca921247cba209a7a375f1bb72a2"
        or existing.get("source_git_paths") != EXPECTED_SOURCE_PATHS
    ):
        raise DeploymentHistoryError("Machine state M06-L04 уже изменено другим способом")
    next_state = deepcopy(state)
    next_state["lessons"][OBJECT_ID] = deepcopy(final_record)
    next_state["updated_at"] = utc_now()
    return validate_state(next_state, course_id=COURSE_ID)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "finalize"])
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved", action="store_true", required=True)
    args = parser.parse_args()
    try:
        sha = source_sha(Path(".").resolve())
        if sha == PREVIOUS_SHA:
            raise DeploymentHistoryError("Нужен обновлённый main с исправлением NOOP")
        if not args.approved:
            raise DeploymentHistoryError("Явное разрешение владельца отсутствует")
        state = load_state(args.sync_state, course_id=COURSE_ID)
        store = GitHubHistoryStore(
            repository=os.getenv("GITHUB_REPOSITORY", ""),
            token=os.getenv("GITHUB_TOKEN", ""),
            source_sha=sha,
        )
        records = store.load(EVENT_ID)
        expected = proven_final(records)
        client_id = os.getenv("STEPIC_CLIENT_ID") or ""
        client_secret = os.getenv("STEPIC_CLIENT_SECRET") or ""
        if not client_id or not client_secret:
            raise DeploymentHistoryError("Нужны Stepik credentials для read-only inspect")
        client = StepikClient(client_id, client_secret)
        verified_live(client.inspect_course(COURSE_ID), state["lessons"][OBJECT_ID])
        result = planned_state(state, expected)
        if args.phase == "prepare":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": "PREPARED", "object_id": OBJECT_ID,
                              "expected_fingerprint": DESIRED_FP, "observed_live": INTERMEDIATE_FP,
                              "stepik_writes": 0}, ensure_ascii=False))
            return 0
        if state["lessons"][OBJECT_ID] != expected:
            raise DeploymentHistoryError("Нельзя завершить историю до подтверждённого PATCH Issue #54")
        mark_machine_state_committed(
            store, event_id=EVENT_ID, status="NOOP_CONFIRMED",
            baseline_after=expected,
        )
        print(json.dumps({"verdict": "RECOVERED", "event_id": EVENT_ID,
                          "stepik_writes": 0}, ensure_ascii=False))
        return 0
    except (DeploymentHistoryError, StepikAPIError, RuntimeError, OSError, ValueError, TypeError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
