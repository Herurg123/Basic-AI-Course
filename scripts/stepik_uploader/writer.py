from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .api import StepikWriteAmbiguousError
from .content import CompiledStep
from .fingerprints import compiled_lesson_fingerprint, html_fingerprint, live_lesson_fingerprint
from .sync_state import SyncAssessment, assess_sync, build_record

PLACEHOLDER_TEXT = "Урок сгенерирован роботом ;)"


class ContentWriteError(RuntimeError):
    pass


def _step_source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("step_source")
    if not isinstance(source, dict):
        raise ContentWriteError("В snapshot отсутствует step_source")
    return source


def _equivalent(existing: dict[str, Any], expected: CompiledStep) -> bool:
    source = _step_source(existing)
    block = source.get("block", {})
    return (
        source.get("position") == expected.position
        and block.get("name") == expected.block_name
        and (block.get("source") or {}) == expected.source
        and html_fingerprint(str(block.get("text") or "")) == html_fingerprint(expected.text)
    )


def _placeholder(existing: dict[str, Any]) -> bool:
    source = _step_source(existing)
    block = source.get("block", {})
    text = str(block.get("text") or "").strip()
    plain = re.sub(r"</?p>", "", text).strip()
    return (
        source.get("position") == 1
        and block.get("name") == "text"
        and (block.get("source") or {}) == {}
        and plain == PLACEHOLDER_TEXT
    )


def _target_lesson_by_position(
    snapshot: dict[str, Any],
    *,
    module_position: int,
    lesson_position: int,
    draft_only: bool,
) -> dict[str, Any]:
    course = snapshot.get("course", {})
    course_public = course.get("is_public")
    if not isinstance(course_public, bool):
        raise ContentWriteError(f"Не удалось подтвердить course.is_public: {course_public!r}")
    if draft_only and course_public is not False:
        raise ContentWriteError("Этот Stepik write-режим разрешён только для непубличного чернового курса")

    matching_sections = [s for s in snapshot.get("sections", []) if s.get("position") == module_position]
    if len(matching_sections) != 1:
        raise ContentWriteError(f"Не найден единственный section position={module_position}")
    matching_units = [u for u in matching_sections[0].get("units", []) if u.get("position") == lesson_position]
    if len(matching_units) != 1:
        raise ContentWriteError(
            f"Не найден единственный unit section={module_position} position={lesson_position}"
        )
    lesson = matching_units[0].get("lesson", {})
    lesson_public = lesson.get("is_public")
    if not isinstance(lesson_public, bool):
        raise ContentWriteError(f"Не удалось подтвердить target lesson.is_public: {lesson_public!r}")
    if draft_only and lesson_public is not False:
        raise ContentWriteError("Этот Stepik write-режим разрешён только для непубличного target lesson")
    if lesson.get("language") != "ru":
        raise ContentWriteError(
            f"Target lesson language отличается от ожидаемого ru: {lesson.get('language')}"
        )
    return lesson


def _target_lesson(
    snapshot: dict[str, Any],
    *,
    module_position: int,
    lesson_position: int,
    expected_title: str,
) -> dict[str, Any]:
    lesson = _target_lesson_by_position(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        draft_only=True,
    )
    if lesson.get("title") != expected_title:
        raise ContentWriteError(
            f"Target lesson title отличается: ожидается «{expected_title}», найдено «{lesson.get('title')}»"
        )
    return lesson


def _lesson_after_expected_step(lesson: dict[str, Any], *, step_id: int, expected: CompiledStep) -> dict[str, Any]:
    updated = deepcopy(lesson)
    matched = False
    for item in updated.get("steps", []):
        source = item.get("step_source")
        if isinstance(source, dict) and int(source.get("id", -1)) == int(step_id):
            source["position"] = expected.position
            source["block"] = expected.block()
            matched = True
            break
    if not matched:
        raise ContentWriteError(f"Не найден step_id={step_id} для вычисления intermediate fingerprint")
    return updated


@dataclass
class WriteResult:
    lesson_id: int
    operations: list[dict[str, Any]] = field(default_factory=list)
    final_step_ids: list[int] = field(default_factory=list)
    verified: bool = False
    after_snapshot: dict[str, Any] | None = None


@dataclass
class SyncWriteResult(WriteResult):
    assessment: SyncAssessment | None = None
    state_record: dict[str, Any] | None = None


def classify_existing_steps(existing: list[dict[str, Any]], expected: list[CompiledStep]) -> tuple[str, int]:
    ordered = sorted(existing, key=lambda item: _step_source(item).get("position", 10**9))
    positions = [_step_source(item).get("position") for item in ordered]
    if positions != list(range(1, len(ordered) + 1)):
        raise ContentWriteError(f"Step positions target lesson неоднозначны: {positions}")
    if len(ordered) > len(expected):
        raise ContentWriteError(
            f"Target lesson содержит {len(ordered)} steps, ожидается не более {len(expected)}"
        )
    if len(ordered) == 1 and _placeholder(ordered[0]):
        return "skeleton-placeholder", 0
    matched = 0
    for index, item in enumerate(ordered):
        if not _equivalent(item, expected[index]):
            raise ContentWriteError(
                f"Target lesson step position={index + 1} не является ни подтверждённым compiled content, ни исходной заглушкой"
            )
        matched += 1
    return ("complete" if matched == len(expected) else "partial"), matched


def _assert_readback(readback: dict[str, Any], expected: CompiledStep) -> None:
    wrapped = {"step_source": readback}
    if not _equivalent(wrapped, expected):
        raise ContentWriteError(f"Read-back step position={expected.position} не совпал с compiled content")


def _created_id(payload: dict[str, Any]) -> int:
    for key in ("step-sources", "stepSources"):
        objects = payload.get(key)
        if isinstance(objects, list) and len(objects) == 1 and isinstance(objects[0], dict) and "id" in objects[0]:
            return int(objects[0]["id"])
    raise ContentWriteError("POST /api/step-sources завершился без однозначного созданного step ID")


def execute_content_test_one(
    client: Any,
    snapshot: dict[str, Any],
    *,
    expected_steps: list[CompiledStep],
    module_position: int,
    lesson_position: int,
    expected_title: str,
) -> WriteResult:
    lesson = _target_lesson(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    lesson_id = int(lesson["id"])
    existing = list(lesson.get("steps", []))
    state, matched = classify_existing_steps(existing, expected_steps)
    result = WriteResult(lesson_id=lesson_id)

    ordered = sorted(existing, key=lambda item: _step_source(item).get("position", 10**9))
    if state == "complete":
        result.operations.append({"action": "NOOP_ALREADY_MATCHES", "steps": len(expected_steps)})
    elif state == "skeleton-placeholder":
        first_id = int(_step_source(ordered[0])["id"])
        client.update_step_source(
            step_id=first_id,
            lesson_id=lesson_id,
            position=1,
            block=expected_steps[0].block(),
        )
        _assert_readback(client.fetch_one("step-sources", first_id), expected_steps[0])
        result.operations.append({"action": "UPDATE_PLACEHOLDER", "step_id": first_id, "position": 1})
        matched = 1
    else:
        result.operations.append({"action": "RESUME_PARTIAL", "matching_prefix": matched})

    for expected in expected_steps[matched:]:
        payload = client.create_step_source(
            lesson_id=lesson_id,
            position=expected.position,
            block=expected.block(),
        )
        step_id = _created_id(payload)
        _assert_readback(client.fetch_one("step-sources", step_id), expected)
        result.operations.append({"action": "CREATE_STEP", "step_id": step_id, "position": expected.position})

    after = client.inspect_course(int(snapshot["course"]["id"]))
    after_lesson = _target_lesson(
        after,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    state_after, matched_after = classify_existing_steps(list(after_lesson.get("steps", [])), expected_steps)
    if state_after != "complete" or matched_after != len(expected_steps):
        raise ContentWriteError("Финальный read-back target lesson не совпал с compiled content")
    result.final_step_ids = [int(_step_source(item)["id"]) for item in after_lesson.get("steps", [])]
    result.verified = True
    result.after_snapshot = after
    return result


def execute_content_sync_one(
    client: Any,
    snapshot: dict[str, Any],
    *,
    canonical_id: str,
    expected_steps: list[CompiledStep],
    module_position: int,
    lesson_position: int,
    expected_title: str,
    baseline: dict[str, Any] | None,
    source_sha: str,
    recorder: Any | None = None,
    recovery_expected_live_fingerprint: str | None = None,
) -> SyncWriteResult:
    """Обновляет отслеживаемый урок с WAL-history перед каждым внешним write.

    Обычный route требует live == baseline. Recovery-continuation допускается только если
    caller уже доказал через immutable history, что текущий live fingerprint равен последнему
    подтверждённому intermediate fingerprint конкретного event.
    """
    lesson = _target_lesson_by_position(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        draft_only=False,
    )
    lesson_id = int(lesson["id"])
    assessment = assess_sync(
        canonical_id=canonical_id,
        live_lesson=lesson,
        expected_title=expected_title,
        expected_steps=expected_steps,
        baseline=baseline,
    )
    result = SyncWriteResult(lesson_id=lesson_id, assessment=assessment)

    if assessment.status == "IN_SYNC":
        result.operations.append({"action": "NOOP_ALREADY_IN_SYNC", "steps": len(expected_steps)})
        result.final_step_ids = [int(_step_source(item)["id"]) for item in lesson.get("steps", [])]
        result.verified = True
        result.after_snapshot = snapshot
        result.state_record = baseline
        return result

    live_before = live_lesson_fingerprint(lesson)
    recovery_continuation = recovery_expected_live_fingerprint is not None
    if recovery_continuation:
        if live_before != recovery_expected_live_fingerprint:
            raise ContentWriteError("Recovery continuation запрещён: live fingerprint уже не совпадает с подтверждённым intermediate state")
    elif assessment.status != "UPDATE_REQUIRED":
        raise ContentWriteError(
            f"sync status={assessment.status}: {'; '.join(assessment.reasons)}"
        )

    existing = sorted(lesson.get("steps", []), key=lambda item: _step_source(item).get("position", 10**9))
    if len(existing) != len(expected_steps):
        raise ContentWriteError("Update route не меняет количество steps")

    working_lesson = deepcopy(lesson)
    for current, expected in zip(existing, expected_steps, strict=True):
        if _equivalent(current, expected):
            continue
        step_id = int(_step_source(current)["id"])
        operation_id = f"step-{expected.position:04d}-{step_id}"
        before_fp = live_lesson_fingerprint(working_lesson)
        expected_lesson = _lesson_after_expected_step(working_lesson, step_id=step_id, expected=expected)
        expected_after_fp = live_lesson_fingerprint(expected_lesson)
        if recorder is not None:
            recorder.write_intent(
                operation_id=operation_id,
                method="PUT",
                target=f"step-sources/{step_id}",
                fingerprint_before=before_fp,
                expected_fingerprint_after=expected_after_fp,
            )
        try:
            client.update_step_source(
                step_id=step_id,
                lesson_id=lesson_id,
                position=expected.position,
                block=expected.block(),
            )
        except Exception as exc:
            if recorder is not None:
                recorder.write_result(
                    operation_id=operation_id,
                    status="AMBIGUOUS" if isinstance(exc, StepikWriteAmbiguousError) else "FAILED_KNOWN",
                    reason_code="stepik-write-ambiguous" if isinstance(exc, StepikWriteAmbiguousError) else "stepik-write-failed-known",
                )
            raise
        if recorder is not None:
            recorder.write_result(operation_id=operation_id, status="COMPLETED")
        try:
            readback = client.fetch_one("step-sources", step_id)
            _assert_readback(readback, expected)
        except Exception:
            if recorder is not None:
                recorder.readback_failed(operation_id=operation_id, reason_code="operation-readback-unavailable-or-mismatch")
            raise
        if recorder is not None:
            recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=expected_after_fp)
        working_lesson = expected_lesson
        result.operations.append({"action": "UPDATE_STEP", "step_id": step_id, "position": expected.position})

    try:
        after = client.inspect_course(int(snapshot["course"]["id"]))
    except Exception:
        if recorder is not None:
            recorder.readback_failed(operation_id=None, reason_code="final-readback-unavailable")
        raise
    after_lesson = _target_lesson_by_position(
        after,
        module_position=module_position,
        lesson_position=lesson_position,
        draft_only=False,
    )
    desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps)
    live_fp = live_lesson_fingerprint(after_lesson)
    if live_fp != desired_fp:
        if recorder is not None:
            recorder.readback_failed(operation_id=None, reason_code="final-readback-mismatch")
        raise ContentWriteError("Финальный read-back после update не совпал с новым compiled content")

    final_step_ids = [int(_step_source(item)["id"]) for item in after_lesson.get("steps", [])]
    source_paths = [path for step in expected_steps for path in step.source_git_paths]
    result.final_step_ids = final_step_ids
    result.verified = True
    result.after_snapshot = after
    result.state_record = build_record(
        canonical_id=canonical_id,
        stepik_lesson_id=lesson_id,
        expected_title=expected_title,
        expected_steps=expected_steps,
        source_sha=source_sha,
        step_ids=final_step_ids,
        source_git_paths=source_paths,
    )
    if recovery_continuation and not result.operations:
        result.operations.append({"action": "RECOVERY_FINALIZE_PRIOR_APPLIED", "stepik_writes": 0})
    if recorder is not None:
        recorder.final_readback(
            fingerprint_after=live_fp,
            stepik_object_ids={"lesson_id": lesson_id, "step_ids": final_step_ids},
            status="APPLIED" if result.operations else "NOOP_CONFIRMED",
            baseline_after=result.state_record,
        )
    return result
