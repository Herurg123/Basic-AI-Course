"""One-time, fail-closed reconciliation of M06-L04's ambiguous Stepik PUT (2026-10-24).

This command NEVER writes to Stepik. It certifies a single immutable WAL event and a
single observed intermediate state; it only prepares the issue #54 machine-state
patch, then records a terminal reconciliation after that patch has succeeded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from .api import StepikClient, StepikAPIError
from .deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore, utc_now
from .fingerprints import live_lesson_fingerprint
from .history_runtime import identity_from_records
from .sync_state import load_state, validate_state
from .stepik_uploader import source_sha

COURSE_ID = 299189
OBJECT_ID = "M06-L04"
LESSON_ID = 2591729
STEP2_ID = 11346941
STEP9_ID = 11347013
STEP_IDS = [11291316, 11346941, 11346949, 11346957, 11346967, 11346977,
            11346980, 11346993, 11347013, 11347029, 11598445]
ORIGIN_SHA = "bcf20b6ce0c5ca921247cba209a7a375f1bb72a2"
EVENT_ID = "evt-1433d5dd0f02668e42a42590ef93abf0"
PENDING_FIRST_SHA = "ba1dc5e8b76f158fbda5130514651bd68649e166"
BASELINE_FP = "sha256:9438c3406bab7d403aa1f4dd61dbb5fcdc4f9f423b40bf5c2733b2f73af06595"
BASELINE_LIVE_FP = "sha256:64483d19de2d0e72f72650931d86006dcc1f3811b461f7f75d44428dd7f08cfc"
EXPECTED_STEP2 = "sha256:27b559315f0d760ee864f4015cc27853094aee2fbbf12da6cf843e5503801238"
EXPECTED_STEP9 = "sha256:6ceaff791df2dc635da50cb4d5f372a83901b41707594c63cee6fb5ae25c124f"
OBSERVED_INTERMEDIATE = EXPECTED_STEP9
FINAL_DESIRED = "sha256:dd64e0d54c237b5f3665297e405595f66af6da47e1161286a1f4f3e07bb57ec4"
OWNER_APPROVAL = "OWNER_APPROVED_M06L04_AMBIGUOUS_WRITE_RECONCILIATION"

def verify_wal(records: list[dict]) -> object:
    identity = identity_from_records(records, expected_event_id=EVENT_ID)
    if (
        identity.object_id != OBJECT_ID or identity.course_id != COURSE_ID
        or identity.source_sha != ORIGIN_SHA or identity.baseline_fingerprint_before != BASELINE_FP
        or identity.desired_fingerprint != FINAL_DESIRED
        or identity.pending_first_sha != PENDING_FIRST_SHA or identity.kind != "lesson"
    ):
        raise DeploymentHistoryError("Неизвестная identity операции M06-L04")
    expected = {
        "EVENT_STARTED": 1, "WRITE_INTENT": 2, "WRITE_DISPATCH_STARTED": 2,
        "WRITE_COMPLETED": 1, "OP_READBACK_CONFIRMED": 1,
        "WRITE_AMBIGUOUS": 1, "FAILED_AFTER_WRITE_STARTED": 1,
    }
    phases = [x.get("phase") for x in records]
    if set(phases) - set(expected) - {"RECONCILE_COMMITTED"}:
        raise DeploymentHistoryError("В WAL появились другие операции; авто-reconcile запрещён")
    if any(phases.count(phase) != count for phase, count in expected.items()):
        raise DeploymentHistoryError("Неверное количество WAL write / readback records")
    if phases.count("RECONCILE_COMMITTED") > 1:
        raise DeploymentHistoryError("Дубликат terminal reconciliation")
    if not (identity.desired_fingerprint != EXPECTED_STEP9):
        raise DeploymentHistoryError("Исходный event не был частичным")
    intent = {r.get("operation_id"): r for r in records if r.get("phase") == "WRITE_INTENT"}
    operations = {
        f"step-0002-{STEP2_ID}": (BASELINE_LIVE_FP, EXPECTED_STEP2),
        f"step-0009-{STEP9_ID}": (EXPECTED_STEP2, EXPECTED_STEP9),
    }
    if set(intent) != set(operations):
        raise DeploymentHistoryError("WAL содержит неожиданные write intents")
    for op, (before, after) in operations.items():
        row = intent[op]
        expected_id = STEP2_ID if op.startswith("step-0002") else STEP9_ID
        if (
            row.get("method") != "PUT" or row.get("target") != f"step-sources/{expected_id}"
            or row.get("fingerprint_before") != before
            or row.get("expected_fingerprint_after") != after
        ):
            raise DeploymentHistoryError("WRITE_INTENT не соответствует доказанным промежуточным состояниям")
    for phase, op in (
        ("WRITE_DISPATCH_STARTED", f"step-0002-{STEP2_ID}"),
        ("WRITE_COMPLETED", f"step-0002-{STEP2_ID}"),
        ("OP_READBACK_CONFIRMED", f"step-0002-{STEP2_ID}"),
        ("WRITE_DISPATCH_STARTED", f"step-0009-{STEP9_ID}"),
        ("WRITE_AMBIGUOUS", f"step-0009-{STEP9_ID}"),
    ):
        if len([r for r in records if r.get("phase") == phase and r.get("operation_id") == op]) != 1:
            raise DeploymentHistoryError(f"WAL отсутствует точное подтверждение {phase} {op}")
    op2_readback = next(r for r in records if r["phase"] == "OP_READBACK_CONFIRMED")
    if op2_readback.get("fingerprint_after") != EXPECTED_STEP2 or op2_readback.get("observed_live_fingerprint") != EXPECTED_STEP2:
        raise DeploymentHistoryError("Шаг 2 не подтверждён заявленным отпечатком")
    start = next(r for r in records if r["phase"] == "EVENT_STARTED")
    if (
        start.get("operation_type") != "lesson-content-refresh"
        or start.get("fingerprint_before") != BASELINE_LIVE_FP
        or start.get("stepik_object_ids", {}).get("lesson_id") != LESSON_ID
        or start.get("stepik_object_ids", {}).get("step_ids") != STEP_IDS
    ):
        raise DeploymentHistoryError("WAL EVENT_STARTED относится к другой структуре урока")
    if not all(
        r.get("reason_code") == code for code in ("stepik-write-ambiguous",)
        for r in records if r["phase"] == "WRITE_AMBIGUOUS"
    ):
        raise DeploymentHistoryError("Операция step9 не является доказанной network ambiguity")
    failed = next(r for r in records if r["phase"] == "FAILED_AFTER_WRITE_STARTED")
    if failed.get("reason_code") != "refresh-runtime-stepikwriteambiguouserror":
        raise DeploymentHistoryError("WAL failure не соответствует сетевой неоднозначности")
    return identity

def _live_target(snapshot: dict) -> dict:
    if snapshot.get("course", {}).get("id") != COURSE_ID or snapshot["course"].get("is_public") is not False:
        raise DeploymentHistoryError("Ожидается непубличный курс 299189")
    sections = [x for x in snapshot.get("sections", []) if x.get("position") == 7]
    if len(sections) != 1:
        raise DeploymentHistoryError("Не найден один модуль с position=7")
    units = [x for x in sections[0].get("units", []) if x.get("position") == 4]
    if len(units) != 1:
        raise DeploymentHistoryError("Не найден один unit с position=4")
    live = units[0].get("lesson")
    if not isinstance(live, dict) or live.get("id") != LESSON_ID:
        raise DeploymentHistoryError("Stepik lesson id изменился")
    if (
        live.get("title") != "Проверьте новые ситуации без готового маршрута"
        or live.get("is_public") is not False or live.get("language") != "ru"
    ):
        raise DeploymentHistoryError("Изменились title / language / visibility M06-L04")
    return live


def verify_observed_partial(snapshot: dict, baseline: dict) -> str:
    live = _live_target(snapshot)
    if baseline.get("stepik_lesson_id") != LESSON_ID or baseline.get("step_ids") != STEP_IDS:
        raise DeploymentHistoryError("Machine baseline содержит иные lesson/step IDs")
    steps = sorted(live.get("steps", []), key=lambda x: x["step_source"]["position"])
    if [x["step_source"]["position"] for x in steps] != list(range(1, 12)):
        raise DeploymentHistoryError("Изменилась топология позиций Stepik")
    if [x["step_source"]["id"] for x in steps] != STEP_IDS:
        raise DeploymentHistoryError("Идентификаторы шагов изменены")
    for pos, sid, block in ((2, STEP2_ID, "text"), (9, STEP9_ID, "free-answer")):
        row = steps[pos - 1]["step_source"]
        if row["id"] != sid or row.get("block", {}).get("name") != block:
            raise DeploymentHistoryError("У спорной операции другой тип или идентификатор шага")
    fp = live_lesson_fingerprint(live)
    if fp != EXPECTED_STEP9:
        raise DeploymentHistoryError(
            "Stepik live отличается от точного ожидаемого WAL после step9: " + fp
        )
    return fp

def proposed_state(state: dict, *, live_fp: str) -> dict:
    state = validate_state(state, course_id=COURSE_ID)
    if OBJECT_ID not in state["pending"]["lessons"]:
        raise DeploymentHistoryError("M06-L04 уже не находится в PENDING")
    old = state["lessons"][OBJECT_ID]
    if old.get("stepik_lesson_id") != LESSON_ID:
        raise DeploymentHistoryError("Сменился baseline lesson ID")
    if old["applied_fingerprint"] not in {BASELINE_FP, OBSERVED_INTERMEDIATE}:
        raise DeploymentHistoryError("Machine baseline уже изменён другим процессом")
    existing = old.get("partial_reconciliation")
    if existing is not None and existing != EVENT_ID:
        raise DeploymentHistoryError("Отмечено другое reconciliation")
    pending = state["pending"]["lessons"][OBJECT_ID]
    ref = pending.get("confirmed_baseline_ref")
    if not isinstance(ref, dict) or ref.get("stepik_lesson_id") != LESSON_ID:
        raise DeploymentHistoryError("PENDING baseline reference отсутствует или изменён")
    if old["applied_fingerprint"] == OBSERVED_INTERMEDIATE:
        if (
            old.get("confirmed_live_fingerprint") != OBSERVED_INTERMEDIATE
            or existing != EVENT_ID
            or ref.get("applied_fingerprint") != OBSERVED_INTERMEDIATE
        ):
            raise DeploymentHistoryError("Уже обновлённый baseline не подтверждён")
        return state
    if ref.get("applied_fingerprint") != BASELINE_FP:
        raise DeploymentHistoryError("PENDING baseline reference больше не соответствует исходному состоянию")
    if (old.get("confirmed_live_fingerprint") != BASELINE_LIVE_FP or ref.get("confirmed_live_fingerprint") != BASELINE_LIVE_FP):
        raise DeploymentHistoryError("Live подтверждённый baseline изменился")
    next_state = deepcopy(state)
    record = next_state["lessons"][OBJECT_ID]
    record["applied_fingerprint"] = live_fp
    record["confirmed_live_fingerprint"] = live_fp
    record["applied_source_sha"] = ORIGIN_SHA
    record["applied_at"] = utc_now()
    record["partial_reconciliation"] = EVENT_ID
    ref = next_state["pending"]["lessons"][OBJECT_ID]["confirmed_baseline_ref"]
    ref.update({
        "applied_fingerprint": live_fp,
        "confirmed_live_fingerprint": live_fp,
        "applied_source_sha": ORIGIN_SHA,
        "applied_at": record["applied_at"],
    })
    next_state["updated_at"] = record["applied_at"]
    # Pending remains OPEN: this is NOT a complete canonical deployment.
    return validate_state(next_state, course_id=COURSE_ID)


def _credentials() -> tuple[str, str]:
    cid = os.getenv("STEPIC_CLIENT_ID") or ""
    sec = os.getenv("STEPIC_CLIENT_SECRET") or ""
    if not cid or not sec:
        raise DeploymentHistoryError("Не заданы STEPIC_CLIENT_ID/STEPIC_CLIENT_SECRET")
    return cid, sec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "finalize"])
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-approve", action="store_true", required=True)
    args = parser.parse_args()
    try:
        root = args.repo_root.resolve()
        sha = source_sha(root)
        if not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == ORIGIN_SHA:
            raise DeploymentHistoryError("Нужна новая main с recovery-кодом")
        state = load_state(args.sync_state, course_id=COURSE_ID)
        store = GitHubHistoryStore(
            repository=os.getenv("GITHUB_REPOSITORY", ""),
            token=os.getenv("GITHUB_TOKEN", ""),
            source_sha=sha,
        )
        records = store.load(EVENT_ID)
        identity = verify_wal(records)
        already = [x for x in records if x.get("phase") == "RECONCILE_COMMITTED"]
        client = StepikClient(*_credentials())
        snapshot = client.inspect_course(COURSE_ID)
        live_fp = verify_observed_partial(snapshot, state["lessons"][OBJECT_ID])
        next_state = proposed_state(state, live_fp=live_fp)
        current = state["lessons"][OBJECT_ID]["applied_fingerprint"]
        if args.phase == "prepare":
            if already:
                raise DeploymentHistoryError("История уже reconciled; незапланированный повтор prepare запрещён")
            if current not in {BASELINE_FP, OBSERVED_INTERMEDIATE}:
                raise DeploymentHistoryError("Machine baseline не относится к исходному или частично восстановленному состоянию")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(next_state, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
            print(json.dumps({"verdict":"PREPARED", "live_fingerprint":live_fp, "original_event":EVENT_ID,"stepik_writes":0},ensure_ascii=False))
            return 0
        if current != OBSERVED_INTERMEDIATE or next_state["lessons"][OBJECT_ID].get("partial_reconciliation") != EVENT_ID:
            raise DeploymentHistoryError("Нельзя завершить WAL до patch Issue #54")
        if already:
            print(json.dumps({"verdict":"ALREADY_RECONCILED","stepik_writes":0},ensure_ascii=False))
            return 0
        recorder = DeploymentRecorder(store, identity)
        recorder._append(
            "RECONCILE_COMMITTED",
            {
                "reconciliation_mode":OWNER_APPROVAL,
                "old_expected_intermediate":EXPECTED_STEP9,
                "observed_live_fingerprint":OBSERVED_INTERMEDIATE,
                "baseline_before":BASELINE_FP,
                "owner_approved":True,
                "reconciled_at":utc_now(),
            },
            operation_id="step-0009-owner-reconciliation",
        )
        print(json.dumps({"verdict":"RECONCILED", "event":EVENT_ID,"live_fingerprint":live_fp,"stepik_writes":0},ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, TypeError, OSError, StepikAPIError, DeploymentHistoryError) as exc:
        print(f"OWNER RECONCILIATION BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
