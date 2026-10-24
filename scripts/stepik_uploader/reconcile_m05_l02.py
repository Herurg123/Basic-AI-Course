"""One-time, fail-closed reconciliation of Stepik M05-L02's 2026-10-24 transport rewrite.

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
OBJECT_ID = "M05-L02"
LESSON_ID = 2591725
STEP_ID = 11339649
ORIGIN_SHA = "aadcdabfc81535001dbbe3fa6a6bc9eb659dfb29"
EVENT_ID = "evt-676a1303134137527c4198fa433cbcee"
BASELINE_FP = "sha256:7fc269552cd90cabbfec6ce3f735e74c0a0a43fde5dd69399ff0df6bf54a614b"
EXPECTED_INTERMEDIATE = "sha256:81b14454ea4488e149d69ee463f4848050cfa1402185ee2504545c14cc4526be"
OBSERVED_INTERMEDIATE = "sha256:d8b141cb27e579fee1051cf432fa7260ab458085ffc40e9d752b3d48d70b8e9d"
OWNER_APPROVAL = "OWNER_APPROVED_M05L02_TRANSPORT_RECONCILIATION"
ATTR_REMOVED_ANCHOR = "<p>Теперь попробуйте изменить эту же картинку.</p>\n<ol>"
ATTR_RESTORED_ANCHOR = "<p>Теперь попробуйте изменить эту же картинку.</p>\n<ol start=\"4\">"


def verify_wal(records: list[dict]) -> object:
    identity = identity_from_records(records, expected_event_id=EVENT_ID)
    if (
        identity.object_id != OBJECT_ID or identity.course_id != COURSE_ID
        or identity.source_sha != ORIGIN_SHA or identity.baseline_fingerprint_before != BASELINE_FP
        or identity.kind != "lesson"
    ):
        raise DeploymentHistoryError("Неподходящая immutable history identity")
    if not records or len([x for x in records if x.get("phase") == "EVENT_STARTED"]) != 1:
        raise DeploymentHistoryError("Неоднозначная WAL history")
    expected = {
        "EVENT_STARTED", "WRITE_INTENT", "WRITE_DISPATCH_STARTED",
        "WRITE_COMPLETED", "READBACK_FAILED", "FAILED_AFTER_WRITE_STARTED",
    }
    phases = [x.get("phase") for x in records]
    if set(phases) - expected - {"RECONCILE_COMMITTED"}:
        raise DeploymentHistoryError("Неизвестные phases: незапланированные операции записи")
    if any(phases.count(x) != 1 for x in expected):
        raise DeploymentHistoryError("WAL запись неполная или содержит несколько операций")
    intent = next(x for x in records if x["phase"] == "WRITE_INTENT")
    if (
        intent.get("operation_id") != f"step-0002-{STEP_ID}"
        or intent.get("method") != "PUT"
        or intent.get("target") != f"step-sources/{STEP_ID}"
        or intent.get("fingerprint_before") != BASELINE_FP
        or intent.get("expected_fingerprint_after") != EXPECTED_INTERMEDIATE
    ):
        raise DeploymentHistoryError("WAL write intent отличается от доказанного случая")
    if identity.desired_fingerprint == BASELINE_FP:
        raise DeploymentHistoryError("Неверный desired WAL")
    if phases.count("RECONCILE_COMMITTED") > 1:
        raise DeploymentHistoryError("Более одного terminal reconcile")
    return identity


def _live_target(snapshot: dict) -> dict:
    if snapshot.get("course", {}).get("id") != COURSE_ID or snapshot["course"].get("is_public") is not False:
        raise DeploymentHistoryError("Нужен исходный непубличный курс")
    sections = [x for x in snapshot.get("sections", []) if x.get("position") == 6]
    if len(sections) != 1:
        raise DeploymentHistoryError("Не найден единственный шестой модуль")
    units = [x for x in sections[0].get("units", []) if x.get("position") == 2]
    if len(units) != 1:
        raise DeploymentHistoryError("Не найдена единственная вторая секция M05-L02")
    live = units[0].get("lesson")
    if not isinstance(live, dict) or live.get("id") != LESSON_ID:
        raise DeploymentHistoryError("Stepik lesson ID отличается от журнала")
    if live.get("is_public") is not False or live.get("language") != "ru" or live.get("title") != "Создайте изображение и затем измените именно его":
        raise DeploymentHistoryError("Изменились публичность, язык или название M05-L02")
    return live


def verify_observed_partial(snapshot: dict, baseline: dict) -> str:
    live = _live_target(snapshot)
    if baseline.get("stepik_lesson_id") != LESSON_ID:
        raise DeploymentHistoryError("Machine baseline имеет другой lesson ID")
    ordered = sorted(live.get("steps", []), key=lambda x: x["step_source"]["position"])
    ids = [x["step_source"]["id"] for x in ordered]
    if ids != baseline.get("step_ids") or len(ids) != 12:
        raise DeploymentHistoryError("Структура или идентификаторы шагов изменились")
    fp = live_lesson_fingerprint(live)
    if fp != OBSERVED_INTERMEDIATE:
        raise DeploymentHistoryError("Live M05-L02 не совпадает с точным forensic fingerprint; остановка")
    source = ordered[1]["step_source"]
    if source.get("id") != STEP_ID or source.get("position") != 2 or source.get("block", {}).get("name") != "text":
        raise DeploymentHistoryError("Неверный Stepik source для шага 2")
    old_html = source.get("block", {}).get("text")
    if not isinstance(old_html, str) or old_html.count(ATTR_REMOVED_ANCHOR) != 1:
        raise DeploymentHistoryError("HTML не содержит единственный подтверждённый transport rewrite")
    expected = deepcopy(live)
    source_copy = sorted(expected["steps"], key=lambda x: x["step_source"]["position"])[1]["step_source"]
    source_copy["block"]["text"] = old_html.replace(ATTR_REMOVED_ANCHOR, ATTR_RESTORED_ANCHOR)
    if live_lesson_fingerprint(expected) != EXPECTED_INTERMEDIATE:
        raise DeploymentHistoryError("Другие отличия Stepik от зафиксированного WAL intermediate")
    return fp


def proposed_state(state: dict, *, live_fp: str) -> dict:
    state = validate_state(state, course_id=COURSE_ID)
    if OBJECT_ID not in state["pending"]["lessons"]:
        raise DeploymentHistoryError("M05-L02 уже не находится в PENDING")
    old = state["lessons"][OBJECT_ID]
    if old.get("stepik_lesson_id") != LESSON_ID:
        raise DeploymentHistoryError("Сменился baseline lesson ID")
    if old["applied_fingerprint"] not in {BASELINE_FP, OBSERVED_INTERMEDIATE}:
        raise DeploymentHistoryError("Machine baseline уже изменён другим процессом")
    existing = old.get("partial_reconciliation")
    if existing is not None and existing != EVENT_ID:
        raise DeploymentHistoryError("Отмечено другое reconciliation")
    if old["applied_fingerprint"] == OBSERVED_INTERMEDIATE:
        if old.get("confirmed_live_fingerprint") != OBSERVED_INTERMEDIATE or existing != EVENT_ID:
            raise DeploymentHistoryError("Уже обновлённый baseline не подтверждён")
        return state
    if old.get("confirmed_live_fingerprint", BASELINE_FP) != BASELINE_FP:
        raise DeploymentHistoryError("Live подтверждённый baseline изменился")
    next_state = deepcopy(state)
    record = next_state["lessons"][OBJECT_ID]
    record["applied_fingerprint"] = live_fp
    record["confirmed_live_fingerprint"] = live_fp
    record["applied_source_sha"] = ORIGIN_SHA
    record["applied_at"] = utc_now()
    record["partial_reconciliation"] = EVENT_ID
    # Pending remains OPEN: this is not a complete canonical deployment.
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
            raise DeploymentHistoryError("Нужна новая main с исправленной карточкой A03")
        asset = (root / "05_assets/M05/M05-L02/M05-L02-A03.md").read_text(encoding="utf-8")
        if not all(x in asset for x in ("Теперь попробуйте изменить эту же картинку.", "1. В чате с Алисой AI", "4. Когда получите изменённую картинку")):
            raise DeploymentHistoryError("Исправление карточки A03 отсутствует")
        from .rendering import markdown_to_html
        rendered = markdown_to_html(asset)
        if rendered.count("<ol>") != 3 or "<ol start=" in rendered:
            raise DeploymentHistoryError("HTML карточки ещё зависит от атрибута start")
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
            if current != BASELINE_FP:
                raise DeploymentHistoryError("Machine baseline уже обновлён; используйте finalize")
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
                "old_expected_intermediate":EXPECTED_INTERMEDIATE,
                "observed_live_fingerprint":OBSERVED_INTERMEDIATE,
                "baseline_before":BASELINE_FP,
                "owner_approved":True,
                "reconciled_at":utc_now(),
            },
            operation_id="step-0002-owner-reconciliation",
        )
        print(json.dumps({"verdict":"RECONCILED", "event":EVENT_ID,"live_fingerprint":live_fp,"stepik_writes":0},ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, TypeError, OSError, StepikAPIError, DeploymentHistoryError) as exc:
        print(f"OWNER RECONCILIATION BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
