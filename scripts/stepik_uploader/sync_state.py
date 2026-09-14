from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .fingerprints import (
    compiled_lesson_fingerprint,
    compiled_lesson_payload,
    live_lesson_fingerprint,
    live_lesson_payload,
)

SCHEMA_VERSION = 1
FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def empty_state(course_id: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "course_id": int(course_id),
        "updated_at": None,
        "lessons": {},
    }


def load_state(path: Path | None, *, course_id: int) -> dict[str, Any]:
    if path is None or not path.exists():
        return empty_state(course_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncStateError(f"Не удалось прочитать Stepik sync state: {exc}") from exc
    return validate_state(payload, course_id=course_id)


def validate_state(payload: Any, *, course_id: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SyncStateError("Stepik sync state должен быть JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SyncStateError(
            f"Неподдерживаемая schema_version sync state: {payload.get('schema_version')!r}"
        )
    try:
        state_course_id = int(payload.get("course_id", -1))
    except (TypeError, ValueError) as exc:
        raise SyncStateError(f"Некорректный course_id в sync state: {payload.get('course_id')!r}") from exc
    if state_course_id != int(course_id):
        raise SyncStateError(
            f"Sync state относится к course_id={payload.get('course_id')}, ожидается {course_id}"
        )
    lessons = payload.get("lessons")
    if not isinstance(lessons, dict):
        raise SyncStateError("В sync state отсутствует lessons object")
    for canonical_id, record in lessons.items():
        if not isinstance(canonical_id, str) or not isinstance(record, dict):
            raise SyncStateError("Некорректная запись lessons в sync state")
        if record.get("canonical_id") not in {None, canonical_id}:
            raise SyncStateError(f"{canonical_id}: canonical_id внутри record не совпадает с ключом")
        fingerprint = record.get("applied_fingerprint")
        if not isinstance(fingerprint, str) or not FINGERPRINT_RE.fullmatch(fingerprint):
            raise SyncStateError(f"{canonical_id}: некорректный applied_fingerprint")
        if not isinstance(record.get("stepik_lesson_id"), int):
            raise SyncStateError(f"{canonical_id}: отсутствует stepik_lesson_id")
        step_ids = record.get("step_ids")
        if step_ids is not None and (
            not isinstance(step_ids, list) or any(not isinstance(value, int) for value in step_ids)
        ):
            raise SyncStateError(f"{canonical_id}: step_ids должны быть списком integer")
    return payload


def baseline_for(state: dict[str, Any], canonical_id: str) -> dict[str, Any] | None:
    record = state.get("lessons", {}).get(canonical_id)
    return record if isinstance(record, dict) else None


def _positions(payload: dict[str, Any]) -> list[int]:
    return [int(step["position"]) for step in payload.get("steps", [])]


def assess_sync(
    *,
    canonical_id: str,
    live_lesson: dict[str, Any],
    expected_title: str,
    expected_steps: Iterable[Any],
    baseline: dict[str, Any] | None,
) -> SyncAssessment:
    expected_steps_list = list(expected_steps)
    desired_payload = compiled_lesson_payload(expected_title=expected_title, expected_steps=expected_steps_list)
    live_payload = live_lesson_payload(live_lesson)
    desired = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps_list)
    live = live_lesson_fingerprint(live_lesson)
    baseline_fp = None if baseline is None else str(baseline.get("applied_fingerprint"))

    changed_positions: list[int] = []
    live_by_position = {step["position"]: step for step in live_payload["steps"]}
    for step in desired_payload["steps"]:
        if live_by_position.get(step["position"]) != step:
            changed_positions.append(int(step["position"]))

    if baseline is None:
        if desired == live:
            return SyncAssessment(
                canonical_id,
                "BASELINE_BOOTSTRAP_REQUIRED",
                desired,
                live,
                None,
                tuple(changed_positions),
                ("live content совпадает с каноном, но подтверждённый deployment baseline ещё не записан",),
            )
        return SyncAssessment(
            canonical_id,
            "BASELINE_MISSING_BLOCKED",
            desired,
            live,
            None,
            tuple(changed_positions),
            ("нет подтверждённого baseline, поэтому существующий Stepik content нельзя перезаписывать автоматически",),
        )

    if int(baseline.get("stepik_lesson_id", -1)) != int(live_lesson.get("id", -2)):
        return SyncAssessment(
            canonical_id,
            "DRIFT_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            ("Stepik lesson ID отличается от deployment baseline",),
        )

    if live != baseline_fp:
        return SyncAssessment(
            canonical_id,
            "DRIFT_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            ("Stepik изменён после последнего подтверждённого sync или sync journal устарел",),
        )

    if desired == baseline_fp:
        return SyncAssessment(
            canonical_id,
            "IN_SYNC",
            desired,
            live,
            baseline_fp,
            (),
            ("канон, Stepik и последний подтверждённый baseline совпадают",),
        )

    metadata_diffs = [
        field
        for field in ("title", "language", "is_public")
        if desired_payload.get(field) != live_payload.get(field)
    ]
    if metadata_diffs:
        return SyncAssessment(
            canonical_id,
            "METADATA_UPDATE_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            ("изменились lesson metadata, для которых безопасный update route ещё не подтверждён: " + ", ".join(metadata_diffs),),
        )

    desired_positions = _positions(desired_payload)
    live_positions = _positions(live_payload)
    if desired_positions != live_positions:
        return SyncAssessment(
            canonical_id,
            "STRUCTURAL_UPDATE_BLOCKED",
            desired,
            live,
            baseline_fp,
            tuple(changed_positions),
            (
                f"изменилась структура steps: desired positions={desired_positions}, live positions={live_positions}; DELETE/reorder автоматически запрещены",
            ),
        )

    return SyncAssessment(
        canonical_id,
        "UPDATE_REQUIRED",
        desired,
        live,
        baseline_fp,
        tuple(changed_positions),
        ("канон изменился, а Stepik всё ещё точно совпадает с последним подтверждённым baseline",),
    )


def build_record(
    *,
    canonical_id: str,
    stepik_lesson_id: int,
    expected_title: str,
    expected_steps: Iterable[Any],
    source_sha: str,
    step_ids: Iterable[int],
    source_git_paths: Iterable[str],
    applied_at: str | None = None,
) -> dict[str, Any]:
    expected_steps_list = list(expected_steps)
    timestamp = applied_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "canonical_id": canonical_id,
        "stepik_lesson_id": int(stepik_lesson_id),
        "applied_source_sha": source_sha,
        "applied_at": timestamp,
        "applied_fingerprint": compiled_lesson_fingerprint(
            expected_title=expected_title,
            expected_steps=expected_steps_list,
        ),
        "step_ids": [int(value) for value in step_ids],
        "source_git_paths": sorted(set(str(value) for value in source_git_paths)),
    }


def with_record(state: dict[str, Any], *, canonical_id: str, record: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state)
    next_state.setdefault("lessons", {})[canonical_id] = record
    next_state["updated_at"] = record.get("applied_at")
    return next_state
