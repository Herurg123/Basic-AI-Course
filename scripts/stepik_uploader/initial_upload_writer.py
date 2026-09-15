from __future__ import annotations

from copy import deepcopy
from typing import Any

from .api import StepikAPIError, StepikWriteAmbiguousError
from .content import CompiledStep
from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from .sync_state import build_record
from .writer import (
    ContentWriteError,
    SyncWriteResult,
    _assert_readback,
    _created_id,
    _step_source,
    _target_lesson,
    classify_existing_steps,
)


def _lesson_after_created_step(lesson: dict[str, Any], expected: CompiledStep) -> dict[str, Any]:
    updated = deepcopy(lesson)
    updated.setdefault("steps", []).append(
        {
            "step_source": {
                "id": -int(expected.position),
                "position": int(expected.position),
                "block": expected.block(),
            }
        }
    )
    return updated


def _lesson_after_updated_first_step(
    lesson: dict[str, Any],
    *,
    step_id: int,
    expected: CompiledStep,
) -> dict[str, Any]:
    updated = deepcopy(lesson)
    matched = False
    for item in updated.get("steps", []):
        source = item.get("step_source")
        if isinstance(source, dict) and int(source.get("id", -1)) == int(step_id):
            source["position"] = int(expected.position)
            source["block"] = expected.block()
            matched = True
            break
    if not matched:
        raise ContentWriteError("Не удалось вычислить intermediate state после placeholder update")
    return updated


def _history_dispatches_are_fully_confirmed(records: list[dict[str, Any]]) -> bool:
    dispatch_ids = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_DISPATCH_STARTED" and item.get("operation_id")
    }
    if not dispatch_ids:
        return False
    completed_ids = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_COMPLETED" and item.get("operation_id")
    }
    readback_ids = {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "OP_READBACK_CONFIRMED" and item.get("operation_id")
    }
    if any(item.get("phase") in {"WRITE_AMBIGUOUS", "WRITE_FAILED_KNOWN", "READBACK_FAILED"} for item in records):
        return False
    return dispatch_ids == completed_ids == readback_ids


def _dispatch_ids(records: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("operation_id"))
        for item in records
        if item.get("phase") == "WRITE_DISPATCH_STARTED" and item.get("operation_id")
    }


def execute_initial_upload_one(
    client: Any,
    snapshot: dict[str, Any],
    *,
    canonical_id: str,
    expected_steps: list[CompiledStep],
    module_position: int,
    lesson_position: int,
    expected_title: str,
    source_sha: str,
    recorder: Any,
    allow_partial_resume: bool = False,
    allow_complete_recovery: bool = False,
) -> SyncWriteResult:
    """Заполняет один существующий draft skeleton с WAL/read-back после каждого write.

    DELETE не используется. Частичный/полный matching state без доказанной recovery history
    не усыновляется как новый baseline.
    """
    lesson = _target_lesson(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    lesson_id = int(lesson["id"])
    existing = list(lesson.get("steps", []))
    state, matched = classify_existing_steps(existing, expected_steps)
    result = SyncWriteResult(lesson_id=lesson_id)
    ordered = sorted(existing, key=lambda item: _step_source(item).get("position", 10**9))
    history_before = recorder.records(refresh=True)
    prior_dispatch_ids = _dispatch_ids(history_before)

    if state == "partial":
        if not allow_partial_resume:
            raise ContentWriteError(
                "Initial upload обнаружил partial matching prefix без доказанной recovery history; автоматическое продолжение запрещено"
            )
        if not _history_dispatches_are_fully_confirmed(history_before):
            raise ContentWriteError(
                "Initial upload partial recovery содержит dispatch без полностью подтверждённого COMPLETED + per-operation read-back; "
                "blind retry/continuation запрещён"
            )
        if len(prior_dispatch_ids) != matched:
            raise ContentWriteError(
                "Initial upload partial recovery: число подтверждённых writes не совпадает с live matching prefix"
            )
        live_fp = live_lesson_fingerprint(lesson)
        confirmed_fingerprints = {
            str(item.get("fingerprint_after"))
            for item in history_before
            if item.get("phase") == "OP_READBACK_CONFIRMED" and item.get("fingerprint_after")
        }
        if live_fp not in confirmed_fingerprints:
            raise ContentWriteError(
                "Initial upload partial recovery: live fingerprint не доказан per-operation read-back history"
            )
    if state == "complete":
        if not allow_complete_recovery or not _history_dispatches_are_fully_confirmed(history_before):
            raise ContentWriteError(
                "Initial upload обнаружил complete matching live content без полностью подтверждённой write history; automatic adoption запрещён"
            )
        if len(prior_dispatch_ids) != len(expected_steps):
            raise ContentWriteError(
                "Initial upload complete recovery: число подтверждённых writes не совпадает с числом rendered steps"
            )
    if state == "skeleton-placeholder" and prior_dispatch_ids:
        raise ContentWriteError(
            "Initial upload видит исходный skeleton, но history уже содержит write dispatch; blind retry запрещён"
        )

    working_lesson = deepcopy(lesson)
    if state == "complete":
        result.operations.append({"action": "RESUME_PROVEN_COMPLETE", "steps": len(expected_steps)})
    elif state == "skeleton-placeholder":
        if not ordered:
            raise ContentWriteError("Skeleton placeholder отсутствует")
        expected = expected_steps[0]
        first_id = int(_step_source(ordered[0])["id"])
        operation_id = f"step-{expected.position:04d}-{first_id}"
        before_fp = live_lesson_fingerprint(working_lesson)
        expected_lesson = _lesson_after_updated_first_step(
            working_lesson,
            step_id=first_id,
            expected=expected,
        )
        expected_after_fp = live_lesson_fingerprint(expected_lesson)
        recorder.write_intent(
            operation_id=operation_id,
            method="PUT",
            target=f"step-sources/{first_id}",
            fingerprint_before=before_fp,
            expected_fingerprint_after=expected_after_fp,
        )
        recorder.write_dispatch_started(operation_id=operation_id)
        try:
            client.update_step_source(
                step_id=first_id,
                lesson_id=lesson_id,
                position=1,
                block=expected.block(),
            )
        except StepikWriteAmbiguousError:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="initial-placeholder-write-ambiguous",
            )
            raise
        except StepikAPIError:
            recorder.write_result(
                operation_id=operation_id,
                status="FAILED_KNOWN",
                reason_code="initial-placeholder-write-failed-known",
            )
            raise
        except Exception:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="initial-placeholder-exception-after-dispatch",
            )
            raise
        recorder.write_result(operation_id=operation_id, status="COMPLETED")
        try:
            readback = client.fetch_one("step-sources", first_id)
            _assert_readback(readback, expected)
        except Exception:
            recorder.readback_failed(
                operation_id=operation_id,
                reason_code="initial-placeholder-readback-unavailable-or-mismatch",
            )
            raise
        recorder.operation_readback(
            operation_id=operation_id,
            expected_fingerprint_after=expected_after_fp,
        )
        working_lesson = expected_lesson
        result.operations.append({"action": "UPDATE_PLACEHOLDER", "step_id": first_id, "position": 1})
        matched = 1
    elif state == "partial":
        result.operations.append({"action": "RESUME_PROVEN_PARTIAL", "matching_prefix": matched})

    for expected in expected_steps[matched:]:
        operation_id = f"step-create-{expected.position:04d}"
        before_fp = live_lesson_fingerprint(working_lesson)
        expected_lesson = _lesson_after_created_step(working_lesson, expected)
        expected_after_fp = live_lesson_fingerprint(expected_lesson)
        recorder.write_intent(
            operation_id=operation_id,
            method="POST",
            target="step-sources",
            fingerprint_before=before_fp,
            expected_fingerprint_after=expected_after_fp,
        )
        recorder.write_dispatch_started(operation_id=operation_id)
        try:
            payload = client.create_step_source(
                lesson_id=lesson_id,
                position=expected.position,
                block=expected.block(),
            )
        except StepikWriteAmbiguousError:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="initial-create-step-ambiguous",
            )
            raise
        except StepikAPIError:
            recorder.write_result(
                operation_id=operation_id,
                status="FAILED_KNOWN",
                reason_code="initial-create-step-failed-known",
            )
            raise
        except Exception:
            recorder.write_result(
                operation_id=operation_id,
                status="AMBIGUOUS",
                reason_code="initial-create-step-exception-after-dispatch",
            )
            raise
        step_id = _created_id(payload)
        recorder.write_result(operation_id=operation_id, status="COMPLETED")
        try:
            readback = client.fetch_one("step-sources", step_id)
            _assert_readback(readback, expected)
        except Exception:
            recorder.readback_failed(
                operation_id=operation_id,
                reason_code="initial-create-step-readback-unavailable-or-mismatch",
            )
            raise
        recorder.operation_readback(
            operation_id=operation_id,
            expected_fingerprint_after=expected_after_fp,
        )
        working_lesson = deepcopy(expected_lesson)
        working_lesson["steps"][-1]["step_source"] = readback
        result.operations.append({"action": "CREATE_STEP", "step_id": step_id, "position": expected.position})

    try:
        after = client.inspect_course(int(snapshot["course"]["id"]))
        after_lesson = _target_lesson(
            after,
            module_position=module_position,
            lesson_position=lesson_position,
            expected_title=expected_title,
        )
        state_after, matched_after = classify_existing_steps(
            list(after_lesson.get("steps", [])),
            expected_steps,
        )
        if state_after != "complete" or matched_after != len(expected_steps):
            raise ContentWriteError("Финальный read-back initial upload не совпал с rendered content")
        desired_fp = compiled_lesson_fingerprint(
            expected_title=expected_title,
            expected_steps=expected_steps,
        )
        live_fp = live_lesson_fingerprint(after_lesson)
        if live_fp != desired_fp:
            raise ContentWriteError("Финальный fingerprint initial upload не совпал с desired")
    except Exception:
        recorder.readback_failed(
            operation_id=None,
            reason_code="initial-upload-final-readback-unavailable-or-mismatch",
        )
        raise

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
    event_records = recorder.records(refresh=True)
    event_had_writes = any(item.get("phase") == "WRITE_DISPATCH_STARTED" for item in event_records)
    recorder.final_readback(
        fingerprint_after=live_fp,
        stepik_object_ids={"lesson_id": lesson_id, "step_ids": final_step_ids},
        status="APPLIED" if event_had_writes else "NOOP_CONFIRMED",
        baseline_after=result.state_record,
    )
    return result
