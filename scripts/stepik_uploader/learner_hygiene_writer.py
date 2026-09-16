from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Iterable

from .api import StepikAPIError, StepikWriteAmbiguousError
from .content import CompiledStep
from .deployment_history import DeploymentHistoryError, DeploymentRecorder, summarize_event, utc_now
from .fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint, live_lesson_payload
from .sync_state import build_record
from .writer import ContentWriteError, _assert_readback, _equivalent, _step_source


@dataclass
class LearnerHygieneWriteResult:
    lesson_id: int
    operations: list[dict[str, Any]] = field(default_factory=list)
    final_step_ids: list[int] = field(default_factory=list)
    verified: bool = False
    after_snapshot: dict[str, Any] | None = None
    state_record: dict[str, Any] | None = None
    history_status: str | None = None


@dataclass(frozen=True)
class _Operation:
    operation_id: str
    kind: str
    step_id: int | None
    expected_step: CompiledStep | None
    fingerprint_before: str
    fingerprint_after: str


def _target_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Не найден единственный section position={module_position}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1 or not isinstance(units[0].get("lesson"), dict):
        raise ContentWriteError(
            f"Не найден единственный lesson section={module_position} position={lesson_position}"
        )
    return units[0]["lesson"]


def _lesson_after_title(lesson: dict[str, Any], expected_title: str) -> dict[str, Any]:
    updated = deepcopy(lesson)
    updated["title"] = expected_title
    return updated


def _lesson_after_step(lesson: dict[str, Any], *, step_id: int, expected: CompiledStep) -> dict[str, Any]:
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
        raise ContentWriteError(f"Не найден step_id={step_id} для hygiene intermediate state")
    return updated


def _ordered_live_steps(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    ordered = sorted(lesson.get("steps", []), key=lambda item: _step_source(item).get("position", 10**9))
    positions = [_step_source(item).get("position") for item in ordered]
    if positions != list(range(1, len(ordered) + 1)):
        raise ContentWriteError(f"Step positions target lesson неоднозначны: {positions}")
    return ordered


def _planned_operations(
    baseline_lesson: dict[str, Any],
    *,
    expected_title: str,
    expected_steps: list[CompiledStep],
) -> tuple[list[_Operation], dict[str, Any]]:
    ordered = _ordered_live_steps(baseline_lesson)
    if len(ordered) != len(expected_steps):
        raise ContentWriteError(
            f"Learner hygiene не меняет структуру lesson: live steps={len(ordered)}, desired={len(expected_steps)}"
        )
    operations: list[_Operation] = []
    working = deepcopy(baseline_lesson)

    if str(working.get("title") or "") != expected_title:
        before_fp = live_lesson_fingerprint(working)
        after = _lesson_after_title(working, expected_title)
        operations.append(
            _Operation(
                operation_id="lesson-title",
                kind="title",
                step_id=None,
                expected_step=None,
                fingerprint_before=before_fp,
                fingerprint_after=live_lesson_fingerprint(after),
            )
        )
        working = after

    for baseline_item, expected in zip(ordered, expected_steps, strict=True):
        step_id = int(_step_source(baseline_item)["id"])
        current = next(
            item for item in working.get("steps", [])
            if int(_step_source(item).get("id", -1)) == step_id
        )
        if _equivalent(current, expected):
            continue
        before_fp = live_lesson_fingerprint(working)
        after = _lesson_after_step(working, step_id=step_id, expected=expected)
        operations.append(
            _Operation(
                operation_id=f"step-{expected.position:04d}-{step_id}",
                kind="step",
                step_id=step_id,
                expected_step=expected,
                fingerprint_before=before_fp,
                fingerprint_after=live_lesson_fingerprint(after),
            )
        )
        working = after

    return operations, working


def _fully_confirmed_dispatch_ids(records: list[dict[str, Any]]) -> set[str]:
    dispatch_ids = {
        str(item.get("operation_id")) for item in records
        if item.get("phase") == "WRITE_DISPATCH_STARTED" and item.get("operation_id")
    }
    completed_ids = {
        str(item.get("operation_id")) for item in records
        if item.get("phase") == "WRITE_COMPLETED" and item.get("operation_id")
    }
    confirmed_ids = {
        str(item.get("operation_id")) for item in records
        if item.get("phase") == "OP_READBACK_CONFIRMED" and item.get("operation_id")
    }
    if any(
        item.get("phase") in {"WRITE_AMBIGUOUS", "WRITE_FAILED_KNOWN", "READBACK_FAILED"}
        for item in records
    ):
        raise ContentWriteError("Learner hygiene history содержит ambiguous/failed write; blind retry запрещён")
    if dispatch_ids != completed_ids or dispatch_ids != confirmed_ids:
        raise ContentWriteError(
            "Learner hygiene history содержит dispatch без полностью подтверждённого COMPLETED + read-back"
        )
    return confirmed_ids


def _resume_index(
    *,
    records: list[dict[str, Any]],
    operations: list[_Operation],
    live_fingerprint: str,
    baseline_fingerprint: str,
    desired_fingerprint: str,
) -> int:
    summary = summarize_event(records)
    confirmed_ids = _fully_confirmed_dispatch_ids(records)
    all_ids = {item.operation_id for item in operations}

    if summary.get("machine_state_committed") or summary.get("final_readback_confirmed"):
        if live_fingerprint != desired_fingerprint:
            raise ContentWriteError("Learner hygiene final/committed history не совпадает с live fingerprint")
        if confirmed_ids != all_ids:
            raise ContentWriteError("Learner hygiene final history не подтверждает все planned writes")
        return len(operations)

    if live_fingerprint == baseline_fingerprint:
        if confirmed_ids:
            raise ContentWriteError("Learner hygiene: history подтверждает writes, но live откатился к baseline")
        return 0

    prefix_ids: set[str] = set()
    for index, operation in enumerate(operations, start=1):
        prefix_ids.add(operation.operation_id)
        if operation.fingerprint_after == live_fingerprint:
            if confirmed_ids != prefix_ids:
                raise ContentWriteError(
                    "Learner hygiene: live совпадает с intermediate state, но history не доказывает тот же prefix"
                )
            return index
    raise ContentWriteError("Learner hygiene: live fingerprint не является доказанным prefix текущего event")


def _ensure_event_and_baseline_snapshot(
    recorder: DeploymentRecorder,
    *,
    canonical_id: str,
    lesson_id: int,
    source_sha: str,
    baseline_fingerprint: str,
    desired_fingerprint: str,
    baseline_lesson: dict[str, Any],
) -> list[dict[str, Any]]:
    records = recorder.records(refresh=True)
    started = [item for item in records if item.get("phase") == "EVENT_STARTED"]
    dispatches = [item for item in records if item.get("phase") == "WRITE_DISPATCH_STARTED"]

    if not started:
        if dispatches:
            raise ContentWriteError("Learner hygiene history содержит dispatch без EVENT_STARTED")
        recorder.ensure_started(
            operation_type="learner-facing-hygiene-sync",
            state_before={
                "canonical_id": canonical_id,
                "stepik_lesson_id": lesson_id,
                "applied_fingerprint": baseline_fingerprint,
            },
            expected_state={"desired_fingerprint": desired_fingerprint, "source_sha": source_sha},
            stepik_object_ids={
                "lesson_id": lesson_id,
                "step_ids": [int(_step_source(item)["id"]) for item in _ordered_live_steps(baseline_lesson)],
            },
            fingerprint_before=baseline_fingerprint,
        )
        records = recorder.records(refresh=True)
    elif len(started) != 1:
        raise ContentWriteError("Learner hygiene history содержит несколько EVENT_STARTED")

    snapshots = [item for item in records if item.get("phase") == "BASELINE_SNAPSHOT_CAPTURED"]
    if not snapshots:
        if dispatches:
            raise ContentWriteError("Learner hygiene write уже начат без durable baseline snapshot")
        recorder._append(
            "BASELINE_SNAPSHOT_CAPTURED",
            {"recorded_at": utc_now(), "baseline_lesson_snapshot": deepcopy(baseline_lesson)},
            operation_id="baseline-snapshot",
        )
        records = recorder.records(refresh=True)
        snapshots = [item for item in records if item.get("phase") == "BASELINE_SNAPSHOT_CAPTURED"]
    if len(snapshots) != 1 or not isinstance(snapshots[0].get("baseline_lesson_snapshot"), dict):
        raise ContentWriteError("Learner hygiene history не содержит единственный durable baseline snapshot")
    captured = snapshots[0]["baseline_lesson_snapshot"]
    if live_lesson_fingerprint(captured) != baseline_fingerprint:
        raise ContentWriteError("Learner hygiene durable baseline snapshot не совпадает с machine baseline")
    return records


def _record_readback_diagnostic(
    recorder: DeploymentRecorder,
    *,
    operation_id: str | None,
    expected_fingerprint: str,
    actual_lesson: dict[str, Any] | None,
    reason_code: str,
) -> None:
    """Persist minimal semantic live state before recording READBACK_FAILED.

    Unknown history phases are intentionally allowed by the history validator. Keeping the
    normalized learner-content payload here makes a future recovery diagnosable without
    repeating a potentially successful write merely to discover what Stepik stored.
    """
    recorder._append(
        "READBACK_DIAGNOSTIC",
        {
            "recorded_at": utc_now(),
            "operation_id": operation_id,
            "reason_code": reason_code,
            "expected_fingerprint": expected_fingerprint,
            "actual_fingerprint": None if actual_lesson is None else live_lesson_fingerprint(actual_lesson),
            "actual_lesson_payload": None if actual_lesson is None else live_lesson_payload(actual_lesson),
        },
        operation_id=operation_id or "final-readback",
    )


def execute_tracked_learner_hygiene(
    client: Any,
    snapshot: dict[str, Any],
    *,
    canonical_id: str,
    expected_steps: Iterable[CompiledStep],
    module_position: int,
    lesson_position: int,
    expected_title: str,
    legacy_title: str,
    baseline: dict[str, Any],
    source_sha: str,
    recorder: DeploymentRecorder,
) -> LearnerHygieneWriteResult:
    """Мигрирует tracked lesson к human title + текущему learner content без structural writes.

    До первого write требуется точное совпадение live с подтверждённым baseline. Recovery
    разрешён только для prefix, доказанного immutable per-operation read-back history.
    """
    expected_steps_list = list(expected_steps)
    live_lesson = _target_lesson(snapshot, module_position=module_position, lesson_position=lesson_position)
    lesson_id = int(live_lesson.get("id", -1))
    if lesson_id <= 0 or int(baseline.get("stepik_lesson_id", -2)) != lesson_id:
        raise ContentWriteError("Learner hygiene target lesson ID отличается от deployment baseline")
    if live_lesson.get("language") != "ru":
        raise ContentWriteError("Learner hygiene target lesson language не ru")
    if str(live_lesson.get("title") or "") not in {legacy_title, expected_title}:
        raise ContentWriteError("Learner hygiene title не равен ни exact legacy title, ни canonical human title")

    baseline_fp = str(baseline.get("applied_fingerprint") or "")
    if not baseline_fp.startswith("sha256:"):
        raise ContentWriteError("Learner hygiene baseline fingerprint отсутствует или повреждён")
    desired_fp = compiled_lesson_fingerprint(expected_title=expected_title, expected_steps=expected_steps_list)
    if recorder.identity.desired_fingerprint != desired_fp:
        raise DeploymentHistoryError("Learner hygiene event desired fingerprint не совпадает с compiled lesson")
    if recorder.identity.baseline_fingerprint_before != baseline_fp:
        raise DeploymentHistoryError("Learner hygiene event baseline fingerprint не совпадает с machine baseline")

    live_fp = live_lesson_fingerprint(live_lesson)
    initial_records = recorder.records(refresh=True)
    snapshots = [item for item in initial_records if item.get("phase") == "BASELINE_SNAPSHOT_CAPTURED"]

    if not initial_records:
        if live_fp != baseline_fp:
            raise ContentWriteError("Learner hygiene: live lesson отличается от baseline до начала event")
        baseline_lesson = deepcopy(live_lesson)
    elif snapshots:
        if len(snapshots) != 1 or not isinstance(snapshots[0].get("baseline_lesson_snapshot"), dict):
            raise ContentWriteError("Learner hygiene history содержит повреждённый baseline snapshot")
        baseline_lesson = deepcopy(snapshots[0]["baseline_lesson_snapshot"])
    else:
        if any(item.get("phase") == "WRITE_DISPATCH_STARTED" for item in initial_records):
            raise ContentWriteError("Learner hygiene write начат без durable baseline snapshot")
        if live_fp != baseline_fp:
            raise ContentWriteError("Learner hygiene event без snapshot, а live уже не baseline")
        baseline_lesson = deepcopy(live_lesson)

    if live_lesson_fingerprint(baseline_lesson) != baseline_fp:
        raise ContentWriteError("Learner hygiene baseline snapshot не совпадает с machine baseline")

    operations, desired_lesson = _planned_operations(
        baseline_lesson,
        expected_title=expected_title,
        expected_steps=expected_steps_list,
    )
    if live_lesson_fingerprint(desired_lesson) != desired_fp:
        raise ContentWriteError("Learner hygiene planned final state не совпадает с desired fingerprint")

    records = _ensure_event_and_baseline_snapshot(
        recorder,
        canonical_id=canonical_id,
        lesson_id=lesson_id,
        source_sha=source_sha,
        baseline_fingerprint=baseline_fp,
        desired_fingerprint=desired_fp,
        baseline_lesson=baseline_lesson,
    )
    resume_from = _resume_index(
        records=records,
        operations=operations,
        live_fingerprint=live_fp,
        baseline_fingerprint=baseline_fp,
        desired_fingerprint=desired_fp,
    )
    result = LearnerHygieneWriteResult(lesson_id=lesson_id)

    final_records = [item for item in records if item.get("phase") == "FINAL_READBACK_CONFIRMED"]
    if final_records:
        if len(final_records) != 1:
            raise ContentWriteError("Learner hygiene history содержит несколько final read-back")
        recovered = final_records[0].get("actual_confirmed_state")
        if not isinstance(recovered, dict) or recovered.get("applied_fingerprint") != desired_fp:
            raise ContentWriteError("Learner hygiene final history baseline повреждён")
        result.operations.append({"action": "RECOVER_PROVEN_COMPLETE"})
        result.final_step_ids = [int(value) for value in recovered.get("step_ids", [])]
        result.verified = True
        result.after_snapshot = snapshot
        result.state_record = recovered
        result.history_status = str(final_records[0].get("status"))
        return result

    working_snapshot = snapshot
    working_lesson = live_lesson
    if resume_from:
        result.operations.append({"action": "RESUME_PROVEN_PREFIX", "confirmed_operations": resume_from})

    for operation in operations[resume_from:]:
        current_fp = live_lesson_fingerprint(working_lesson)
        if current_fp != operation.fingerprint_before:
            raise ContentWriteError(
                f"Learner hygiene {operation.operation_id}: live before write не совпадает с planned intermediate"
            )
        recorder.write_intent(
            operation_id=operation.operation_id,
            method="PUT",
            target=(f"lessons/{lesson_id}" if operation.kind == "title" else f"step-sources/{int(operation.step_id)}"),
            fingerprint_before=operation.fingerprint_before,
            expected_fingerprint_after=operation.fingerprint_after,
        )
        recorder.write_dispatch_started(operation_id=operation.operation_id)
        try:
            if operation.kind == "title":
                client._request_write("PUT", f"/api/lessons/{lesson_id}", {"lesson": {"title": expected_title}})
            else:
                if operation.expected_step is None or operation.step_id is None:
                    raise ContentWriteError("Learner hygiene step operation повреждена")
                client.update_step_source(
                    step_id=int(operation.step_id),
                    lesson_id=lesson_id,
                    position=int(operation.expected_step.position),
                    block=operation.expected_step.block(),
                )
        except StepikWriteAmbiguousError:
            recorder.write_result(operation_id=operation.operation_id, status="AMBIGUOUS", reason_code="learner-hygiene-write-ambiguous")
            raise
        except StepikAPIError:
            recorder.write_result(operation_id=operation.operation_id, status="FAILED_KNOWN", reason_code="learner-hygiene-write-failed-known")
            raise
        except Exception:
            recorder.write_result(operation_id=operation.operation_id, status="AMBIGUOUS", reason_code="learner-hygiene-exception-after-dispatch")
            raise
        recorder.write_result(operation_id=operation.operation_id, status="COMPLETED")

        actual_lesson: dict[str, Any] | None = None
        try:
            working_snapshot = client.inspect_course(int(snapshot["course"]["id"]))
            actual_lesson = _target_lesson(
                working_snapshot,
                module_position=module_position,
                lesson_position=lesson_position,
            )
            actual_fp = live_lesson_fingerprint(actual_lesson)
            if actual_fp != operation.fingerprint_after:
                raise ContentWriteError(
                    f"Learner hygiene {operation.operation_id}: full lesson read-back не совпал с expected intermediate"
                )
            if operation.kind == "step" and operation.expected_step is not None and operation.step_id is not None:
                _assert_readback(client.fetch_one("step-sources", int(operation.step_id)), operation.expected_step)
        except Exception:
            _record_readback_diagnostic(
                recorder,
                operation_id=operation.operation_id,
                expected_fingerprint=operation.fingerprint_after,
                actual_lesson=actual_lesson,
                reason_code="learner-hygiene-readback-unavailable-or-mismatch",
            )
            recorder.readback_failed(operation_id=operation.operation_id, reason_code="learner-hygiene-readback-unavailable-or-mismatch")
            raise
        recorder.operation_readback(
            operation_id=operation.operation_id,
            expected_fingerprint_after=operation.fingerprint_after,
        )
        working_lesson = actual_lesson
        result.operations.append(
            {
                "action": "UPDATE_TITLE" if operation.kind == "title" else "UPDATE_STEP",
                "operation_id": operation.operation_id,
                "step_id": operation.step_id,
            }
        )

    after = client.inspect_course(int(snapshot["course"]["id"]))
    after_lesson = _target_lesson(after, module_position=module_position, lesson_position=lesson_position)
    final_fp = live_lesson_fingerprint(after_lesson)
    if final_fp != desired_fp:
        _record_readback_diagnostic(
            recorder,
            operation_id=None,
            expected_fingerprint=desired_fp,
            actual_lesson=after_lesson,
            reason_code="learner-hygiene-final-readback-mismatch",
        )
        recorder.readback_failed(operation_id=None, reason_code="learner-hygiene-final-readback-mismatch")
        raise ContentWriteError("Learner hygiene final read-back не совпал с desired lesson")

    final_step_ids = [int(_step_source(item)["id"]) for item in _ordered_live_steps(after_lesson)]
    source_paths = [path for step in expected_steps_list for path in step.source_git_paths]
    state_record = build_record(
        canonical_id=canonical_id,
        stepik_lesson_id=lesson_id,
        expected_title=expected_title,
        expected_steps=expected_steps_list,
        source_sha=source_sha,
        step_ids=final_step_ids,
        source_git_paths=source_paths,
    )
    event_had_writes = any(item.get("phase") == "WRITE_DISPATCH_STARTED" for item in recorder.records(refresh=True))
    status = "APPLIED" if event_had_writes else "NOOP_CONFIRMED"
    recorder.final_readback(
        fingerprint_after=final_fp,
        stepik_object_ids={"lesson_id": lesson_id, "step_ids": final_step_ids},
        status=status,
        baseline_after=state_record,
    )

    result.final_step_ids = final_step_ids
    result.verified = True
    result.after_snapshot = after
    result.state_record = state_record
    result.history_status = status
    return result
