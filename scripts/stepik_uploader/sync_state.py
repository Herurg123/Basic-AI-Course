from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .fingerprints import (
    compiled_lesson_fingerprint,
    compiled_lesson_payload,
    live_lesson_fingerprint,
    live_lesson_payload,
)
from .transport_equivalence import lesson_transport_equivalent, step_transport_equivalent

SCHEMA_VERSION = 3
PREVIOUS_SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CONFIRMATION_STATUSES = {"APPLIED", "NOOP_CONFIRMED"}


class SyncStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncAssessment:
    canonical_id: str
    status: str
    desired_fingerprint: str
    live_fingerprint: str
    baseline_fingerprint: str | None
    changed_step_positions: tuple[int, ...]
    reasons: tuple[str, ...]

    @property
    def write_allowed(self) -> bool:
        return self.status == "UPDATE_REQUIRED"


def empty_pending() -> dict[str, Any]:
    return {"lessons": {}, "course_page": None}


def empty_state(course_id: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "course_id": int(course_id),
        "updated_at": None,
        "lessons": {},
        "assets": {},
        "pending": empty_pending(),
    }


def load_state(path: Path | None, *, course_id: int) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_state(course_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncStateError(f"Не удалось прочитать Stepik sync state: {exc}") from exc
    return validate_state(payload, course_id=course_id)


def _timestamp(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SyncStateError(f"{field}: ожидается UTC timestamp вида ...Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SyncStateError(f"{field}: некорректный timestamp {value!r}") from exc
    return value


def _sha(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise SyncStateError(f"{field}: ожидается полный Git SHA")
    return value


def _fingerprint(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not FINGERPRINT_RE.fullmatch(value):
        raise SyncStateError(f"{field}: ожидается sha256 fingerprint")
    return value


def _asset_path(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SyncStateError(f"{field}: ожидается непустой repo-relative source path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SyncStateError(f"{field}: source path должен оставаться внутри репозитория")
    return str(path)


def _baseline_ref(record: dict[str, Any] | None, *, canonical_id: str) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "state_path": f"lessons.{canonical_id}",
        "stepik_lesson_id": int(record["stepik_lesson_id"]),
        "applied_source_sha": record.get("applied_source_sha"),
        "applied_at": record.get("applied_at"),
        "applied_fingerprint": record.get("applied_fingerprint"),
        "confirmed_live_fingerprint": record.get("confirmed_live_fingerprint"),
    }


def _validate_baseline_ref(value: Any, *, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise SyncStateError(f"{field}: confirmed_baseline_ref должен быть object или null")
    if not isinstance(value.get("state_path"), str) or not value["state_path"].startswith("lessons."):
        raise SyncStateError(f"{field}: некорректный state_path baseline")
    if not isinstance(value.get("stepik_lesson_id"), int):
        raise SyncStateError(f"{field}: отсутствует stepik_lesson_id baseline")
    fingerprint = value.get("applied_fingerprint")
    if fingerprint is not None:
        _fingerprint(fingerprint, field=f"{field}.applied_fingerprint")
    live_fingerprint = value.get("confirmed_live_fingerprint")
    if live_fingerprint is not None:
        _fingerprint(live_fingerprint, field=f"{field}.confirmed_live_fingerprint")
    applied_sha = value.get("applied_source_sha")
    if applied_sha is not None:
        _sha(applied_sha, field=f"{field}.applied_source_sha")
    applied_at = value.get("applied_at")
    if applied_at is not None:
        _timestamp(applied_at, field=f"{field}.applied_at")


def _validate_pending_record(record: Any, *, object_id: str, kind: str) -> None:
    if not isinstance(record, dict):
        raise SyncStateError(f"{object_id}: pending record должен быть object")
    if record.get("object_id") != object_id:
        raise SyncStateError(f"{object_id}: object_id pending record не совпадает с ключом")
    if record.get("kind") != kind:
        raise SyncStateError(f"{object_id}: некорректный kind pending record")
    if record.get("status") != "PENDING":
        raise SyncStateError(f"{object_id}: machine backlog хранит только status=PENDING")
    reasons = record.get("reason_codes")
    if not isinstance(reasons, list) or not reasons or any(not isinstance(v, str) or not v for v in reasons):
        raise SyncStateError(f"{object_id}: reason_codes должны быть непустым списком строк")
    if reasons != sorted(set(reasons)):
        raise SyncStateError(f"{object_id}: reason_codes должны быть уникальны и отсортированы")
    paths = record.get("source_paths")
    if not isinstance(paths, list) or not paths or any(not isinstance(v, str) or not v for v in paths):
        raise SyncStateError(f"{object_id}: source_paths должны быть непустым списком строк")
    if paths != sorted(set(paths)):
        raise SyncStateError(f"{object_id}: source_paths должны быть уникальны и отсортированы")
    _sha(record.get("first_pending_sha"), field=f"{object_id}.first_pending_sha")
    _sha(record.get("latest_pending_sha"), field=f"{object_id}.latest_pending_sha")
    _timestamp(record.get("first_pending_at"), field=f"{object_id}.first_pending_at")
    _timestamp(record.get("latest_pending_at"), field=f"{object_id}.latest_pending_at")
    _validate_baseline_ref(record.get("confirmed_baseline_ref"), field=object_id)


def _validate_asset_record(record: Any, *, source_path: str) -> None:
    if not isinstance(record, dict):
        raise SyncStateError(f"assets.{source_path}: asset baseline должен быть object")
    normalized_path = _asset_path(source_path, field=f"assets.{source_path}")
    if record.get("source_path") != normalized_path:
        raise SyncStateError(f"assets.{source_path}: source_path внутри record не совпадает с ключом")
    _fingerprint(record.get("source_sha256"), field=f"assets.{source_path}.source_sha256")
    url = record.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise SyncStateError(f"assets.{source_path}.url: ожидается абсолютный https URL")
    if not isinstance(record.get("storage"), str) or not record.get("storage"):
        raise SyncStateError(f"assets.{source_path}.storage: ожидается непустая строка")
    if not isinstance(record.get("stepik_attachment_id"), int):
        raise SyncStateError(f"assets.{source_path}: отсутствует stepik_attachment_id")
    if not isinstance(record.get("stepik_lesson_id"), int):
        raise SyncStateError(f"assets.{source_path}: отсутствует stepik_lesson_id")
    if not isinstance(record.get("filename"), str) or not record.get("filename"):
        raise SyncStateError(f"assets.{source_path}: отсутствует filename")
    size = record.get("size")
    if not isinstance(size, int) or size < 0:
        raise SyncStateError(f"assets.{source_path}.size: ожидается неотрицательный integer")
    _timestamp(record.get("materialized_at"), field=f"assets.{source_path}.materialized_at")


def validate_state(payload: Any, *, course_id: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SyncStateError("Stepik sync state должен быть JSON object")
    version = payload.get("schema_version")
    if version not in {LEGACY_SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise SyncStateError(f"Неподдерживаемая schema_version sync state: {version!r}")
    try:
        state_course_id = int(payload.get("course_id", -1))
    except (TypeError, ValueError) as exc:
        raise SyncStateError(f"Некорректный course_id в sync state: {payload.get('course_id')!r}") from exc
    if state_course_id != int(course_id):
        raise SyncStateError(f"Sync state относится к course_id={payload.get('course_id')}, ожидается {course_id}")

    state = deepcopy(payload)
    if version == LEGACY_SCHEMA_VERSION:
        state["pending"] = empty_pending()
    if version in {LEGACY_SCHEMA_VERSION, PREVIOUS_SCHEMA_VERSION}:
        state["assets"] = {}
        state["schema_version"] = SCHEMA_VERSION

    lessons = state.get("lessons")
    if not isinstance(lessons, dict):
        raise SyncStateError("В sync state отсутствует lessons object")
    for canonical_id, record in lessons.items():
        if not isinstance(canonical_id, str) or not isinstance(record, dict):
            raise SyncStateError("Некорректная запись lessons в sync state")
        if record.get("canonical_id") not in {None, canonical_id}:
            raise SyncStateError(f"{canonical_id}: canonical_id внутри record не совпадает с ключом")
        _fingerprint(record.get("applied_fingerprint"), field=f"{canonical_id}.applied_fingerprint")
        confirmed_live = record.get("confirmed_live_fingerprint")
        if confirmed_live is not None:
            _fingerprint(confirmed_live, field=f"{canonical_id}.confirmed_live_fingerprint")
        if not isinstance(record.get("stepik_lesson_id"), int):
            raise SyncStateError(f"{canonical_id}: отсутствует stepik_lesson_id")
        step_ids = record.get("step_ids")
        if step_ids is not None and (not isinstance(step_ids, list) or any(not isinstance(value, int) for value in step_ids)):
            raise SyncStateError(f"{canonical_id}: step_ids должны быть списком integer")

    assets = state.get("assets")
    if not isinstance(assets, dict):
        raise SyncStateError("В sync state отсутствует assets object")
    for source_path, record in assets.items():
        if not isinstance(source_path, str):
            raise SyncStateError("Некорректный ключ assets")
        _validate_asset_record(record, source_path=source_path)

    pending = state.get("pending")
    if not isinstance(pending, dict):
        raise SyncStateError("В sync state отсутствует pending object")
    pending_lessons = pending.get("lessons")
    if not isinstance(pending_lessons, dict):
        raise SyncStateError("В sync state отсутствует pending.lessons object")
    for canonical_id, record in pending_lessons.items():
        if not re.fullmatch(r"M\d{2}-L\d{2}", canonical_id):
            raise SyncStateError(f"Некорректный Lesson ID в pending: {canonical_id!r}")
        _validate_pending_record(record, object_id=canonical_id, kind="lesson")
    course_page = pending.get("course_page")
    if course_page is not None:
        _validate_pending_record(course_page, object_id="course-page", kind="course_page")
    return state


def baseline_for(state: dict[str, Any], canonical_id: str) -> dict[str, Any] | None:
    record = state.get("lessons", {}).get(canonical_id)
    return record if isinstance(record, dict) else None


def asset_binding_for(state: dict[str, Any], source_path: str) -> dict[str, Any] | None:
    record = state.get("assets", {}).get(source_path)
    return record if isinstance(record, dict) else None


def _new_pending_record(*, object_id: str, kind: str, source_paths: Iterable[str], reason_codes: Iterable[str], source_sha: str, occurred_at: str, confirmed_baseline_ref: dict[str, Any] | None) -> dict[str, Any]:
    paths = sorted(set(str(value) for value in source_paths))
    reasons = sorted(set(str(value) for value in reason_codes))
    if not paths or not reasons:
        raise SyncStateError(f"{object_id}: pending требует source_paths и reason_codes")
    _sha(source_sha, field=f"{object_id}.source_sha")
    _timestamp(occurred_at, field=f"{object_id}.occurred_at")
    return {
        "object_id": object_id,
        "kind": kind,
        "status": "PENDING",
        "reason_codes": reasons,
        "source_paths": paths,
        "first_pending_sha": source_sha,
        "latest_pending_sha": source_sha,
        "first_pending_at": occurred_at,
        "latest_pending_at": occurred_at,
        "confirmed_baseline_ref": confirmed_baseline_ref,
    }


def _merge_pending_record(existing: dict[str, Any], *, source_paths: Iterable[str], reason_codes: Iterable[str], source_sha: str, occurred_at: str) -> dict[str, Any]:
    record = deepcopy(existing)
    record["source_paths"] = sorted(set(record.get("source_paths", [])) | set(source_paths))
    record["reason_codes"] = sorted(set(record.get("reason_codes", [])) | set(reason_codes))
    record["latest_pending_sha"] = source_sha
    record["latest_pending_at"] = occurred_at
    return record


def with_pending_impact(state: dict[str, Any], *, source_sha: str, occurred_at: str, paths_by_lesson: dict[str, list[str]], reasons_by_lesson: dict[str, list[str]], course_page_paths: Iterable[str] = (), course_page_reason_codes: Iterable[str] = ()) -> dict[str, Any]:
    next_state = deepcopy(validate_state(state, course_id=int(state["course_id"])))
    pending_lessons = next_state["pending"]["lessons"]
    for canonical_id in sorted(paths_by_lesson):
        paths = paths_by_lesson[canonical_id]
        reasons = reasons_by_lesson.get(canonical_id, ["canonical-learner-change"])
        existing = pending_lessons.get(canonical_id)
        if existing is None:
            pending_lessons[canonical_id] = _new_pending_record(
                object_id=canonical_id,
                kind="lesson",
                source_paths=paths,
                reason_codes=reasons,
                source_sha=source_sha,
                occurred_at=occurred_at,
                confirmed_baseline_ref=_baseline_ref(baseline_for(next_state, canonical_id), canonical_id=canonical_id),
            )
        else:
            pending_lessons[canonical_id] = _merge_pending_record(existing, source_paths=paths, reason_codes=reasons, source_sha=source_sha, occurred_at=occurred_at)

    course_paths = sorted(set(str(value) for value in course_page_paths))
    if course_paths:
        reasons = sorted(set(str(value) for value in course_page_reason_codes)) or ["course-page-source"]
        existing_course = next_state["pending"].get("course_page")
        if existing_course is None:
            next_state["pending"]["course_page"] = _new_pending_record(
                object_id="course-page",
                kind="course_page",
                source_paths=course_paths,
                reason_codes=reasons,
                source_sha=source_sha,
                occurred_at=occurred_at,
                confirmed_baseline_ref=None,
            )
        else:
            next_state["pending"]["course_page"] = _merge_pending_record(existing_course, source_paths=course_paths, reason_codes=reasons, source_sha=source_sha, occurred_at=occurred_at)
    next_state["updated_at"] = occurred_at
    return validate_state(next_state, course_id=int(next_state["course_id"]))


def close_lesson_pending(state: dict[str, Any], *, canonical_id: str, confirmed_at: str, confirmation_status: str) -> dict[str, Any]:
    if confirmation_status not in CONFIRMATION_STATUSES:
        raise SyncStateError(f"{canonical_id}: pending можно закрыть только после APPLIED или NOOP_CONFIRMED")
    _timestamp(confirmed_at, field=f"{canonical_id}.confirmed_at")
    next_state = deepcopy(validate_state(state, course_id=int(state["course_id"])))
    next_state["pending"]["lessons"].pop(canonical_id, None)
    next_state["updated_at"] = confirmed_at
    return validate_state(next_state, course_id=int(next_state["course_id"]))


def _positions(payload: dict[str, Any]) -> list[int]:
    return [int(step["position"]) for step in payload.get("steps", [])]


def assess_sync(*, canonical_id: str, live_lesson: dict[str, Any], expected_title: str, expected_steps: Iterable[Any], baseline: dict[str, Any] | None) -> SyncAssessment:
    expected_steps_list = list(expected_steps)
    desired_payload = compiled_lesson_payload(expected_title=expected_title, expected_steps=expected_steps_list)
    live_payload = live_lesson_payload(live_lesson)
    desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps_list)
    live = live_lesson_fingerprint(live_lesson)
    baseline_fp = None if baseline is None else str(baseline.get("applied_fingerprint"))
    transport_match = lesson_transport_equivalent(
        live_lesson,
        expected_title=expected_title,
        expected_steps=expected_steps_list,
        language="ru",
        is_public=False,
    )

    live_items: dict[int, dict[str, Any]] = {}
    for item in live_lesson.get("steps", []):
        source = item.get("step_source") if isinstance(item, dict) else None
        if isinstance(source, dict) and isinstance(source.get("position"), int):
            live_items[int(source["position"])] = item
    changed_positions = [
        int(step.position)
        for step in expected_steps_list
        if int(step.position) not in live_items or not step_transport_equivalent(live_items[int(step.position)], step)
    ]

    if baseline is None:
        if transport_match:
            return SyncAssessment(canonical_id, "BASELINE_BOOTSTRAP_REQUIRED", desired, live, None, tuple(changed_positions), ("live content транспортно эквивалентен канону, но подтверждённый deployment baseline ещё не записан",))
        return SyncAssessment(canonical_id, "BASELINE_MISSING_BLOCKED", desired, live, None, tuple(changed_positions), ("нет подтверждённого baseline, поэтому существующий Stepik content нельзя перезаписывать автоматически",))

    if int(baseline.get("stepik_lesson_id", -1)) != int(live_lesson.get("id", -2)):
        return SyncAssessment(canonical_id, "DRIFT_BLOCKED", desired, live, baseline_fp, tuple(changed_positions), ("Stepik lesson ID отличается от deployment baseline",))

    baseline_live_fp_raw = baseline.get("confirmed_live_fingerprint")
    baseline_live_fp = str(baseline_live_fp_raw) if isinstance(baseline_live_fp_raw, str) else None

    # If canonical content has not changed since the proven baseline, a new Stepik
    # representation-only rewrite is allowed only when the full lesson remains transport-equivalent.
    if desired == baseline_fp and transport_match:
        return SyncAssessment(
            canonical_id,
            "IN_SYNC",
            desired,
            live,
            baseline_fp,
            (),
            ("канон не изменился; Stepik read-back транспортно эквивалентен подтверждённому содержанию",),
        )

    proven_live_fp = baseline_live_fp or baseline_fp
    if live != proven_live_fp:
        return SyncAssessment(canonical_id, "DRIFT_BLOCKED", desired, live, baseline_fp, tuple(changed_positions), ("Stepik изменён после последнего подтверждённого sync или sync journal устарел",))

    metadata_diffs = [field for field in ("title", "language", "is_public") if desired_payload.get(field) != live_payload.get(field)]
    unsafe_metadata = [field for field in metadata_diffs if field != "title"]
    if unsafe_metadata:
        return SyncAssessment(
            canonical_id,
            "METADATA_UPDATE_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            ("изменились lesson metadata, для которых безопасный update route не разрешён: " + ", ".join(unsafe_metadata),),
        )
    desired_positions = _positions(desired_payload)
    live_positions = _positions(live_payload)
    append_only_growth = (
        len(desired_positions) > len(live_positions)
        and live_positions == list(range(1, len(live_positions) + 1))
        and desired_positions == list(range(1, len(desired_positions) + 1))
        and desired_positions[: len(live_positions)] == live_positions
    )
    if desired_positions != live_positions and not append_only_growth:
        return SyncAssessment(
            canonical_id,
            "STRUCTURAL_UPDATE_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            (
                f"изменилась структура steps: desired positions={desired_positions}, "
                f"live positions={live_positions}; разрешён только append-only рост, "
                "DELETE/reorder автоматически запрещены",
            ),
        )
    if metadata_diffs == ["title"]:
        return SyncAssessment(
            canonical_id,
            "UPDATE_REQUIRED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            ("канонический title изменился, а live полностью совпадает с подтверждённым baseline; guarded title PUT разрешён внутри того же deployment event",),
        )
    reason = (
        "канон расширяет topology только хвостовыми steps, а Stepik совпадает "
        "с последним подтверждённым live baseline; guarded append-only sync разрешён"
        if append_only_growth
        else "канон изменился, а Stepik всё ещё совпадает с последним подтверждённым live baseline"
    )
    return SyncAssessment(
        canonical_id,
        "UPDATE_REQUIRED",
        desired,
        live,
        baseline_fp,
        tuple(changed_positions),
        (reason,),
    )


def build_record(*, canonical_id: str, stepik_lesson_id: int, expected_title: str, expected_steps: Iterable[Any], source_sha: str, step_ids: Iterable[int], source_git_paths: Iterable[str], applied_at: str | None = None, confirmed_live_fingerprint: str | None = None) -> dict[str, Any]:
    expected_steps_list = list(expected_steps)
    timestamp = applied_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record = {
        "canonical_id": canonical_id,
        "stepik_lesson_id": int(stepik_lesson_id),
        "applied_source_sha": source_sha,
        "applied_at": timestamp,
        "applied_fingerprint": compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps_list),
        "step_ids": [int(value) for value in step_ids],
        "source_git_paths": sorted(set(str(value) for value in source_git_paths)),
    }
    if confirmed_live_fingerprint is not None:
        _fingerprint(confirmed_live_fingerprint, field=f"{canonical_id}.confirmed_live_fingerprint")
        record["confirmed_live_fingerprint"] = confirmed_live_fingerprint
    return record


def with_record(state: dict[str, Any], *, canonical_id: str, record: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(validate_state(state, course_id=int(state["course_id"])))
    next_state.setdefault("lessons", {})[canonical_id] = record
    next_state["updated_at"] = record.get("applied_at")
    return validate_state(next_state, course_id=int(next_state["course_id"]))


def with_asset_record(state: dict[str, Any], *, source_path: str, record: dict[str, Any]) -> dict[str, Any]:
    normalized_path = _asset_path(source_path, field="source_path")
    next_state = deepcopy(validate_state(state, course_id=int(state["course_id"])))
    next_state.setdefault("assets", {})[normalized_path] = deepcopy(record)
    next_state["updated_at"] = record.get("materialized_at")
    return validate_state(next_state, course_id=int(next_state["course_id"]))
