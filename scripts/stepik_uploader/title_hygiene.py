from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .api import StepikAPIError, StepikWriteAmbiguousError
from .deployment_history import DeploymentHistoryError, DeploymentRecorder, summarize_event
from .fingerprints import canonical_hash

GOLDEN_LESSON_IDS = {"M00-L01", "M00-L02"}


class TitleHygieneError(RuntimeError):
    pass


@dataclass(frozen=True)
class TitleOperation:
    kind: str
    canonical_id: str
    stepik_id: int
    position: int
    live_title: str
    expected_title: str

    @property
    def object_id(self) -> str:
        return f"title:{self.kind}:{self.canonical_id}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": "UPDATE_TITLE",
            "kind": self.kind,
            "canonical_id": self.canonical_id,
            "stepik_id": self.stepik_id,
            "position": self.position,
            "current_title": self.live_title,
            "expected_title": self.expected_title,
            "delete_allowed": False,
            "create_allowed": False,
        }


@dataclass
class TitleHygienePlan:
    operations: list[TitleOperation] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    owner_required: list[dict[str, Any]] = field(default_factory=list)
    already_clean: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "operations": [item.as_dict() for item in self.operations],
            "blockers": list(self.blockers),
            "owner_required": list(self.owner_required),
            "already_clean": list(self.already_clean),
            "stepik_writes_planned": len(self.operations),
            "delete_allowed": False,
            "create_allowed": False,
        }


def legacy_title(canonical_id: str, human_title: str) -> str:
    return f"{canonical_id} — {human_title}"


def title_state(*, kind: str, stepik_id: int, title: str) -> dict[str, Any]:
    return {"kind": kind, "stepik_id": int(stepik_id), "title": str(title)}


def title_fingerprint(*, kind: str, stepik_id: int, title: str) -> str:
    return canonical_hash(title_state(kind=kind, stepik_id=stepik_id, title=title))


def _position_matches(items: list[dict[str, Any]], position: int) -> list[dict[str, Any]]:
    return [item for item in items if item.get("position") == position]


def _classify_title(
    plan: TitleHygienePlan,
    *,
    kind: str,
    canonical_id: str,
    position: int,
    stepik_id: Any,
    live_title: Any,
    expected_title: str,
    golden_read_only: bool = False,
) -> None:
    if not isinstance(stepik_id, int) or not isinstance(live_title, str):
        plan.blockers.append(f"{kind}:{canonical_id}: Stepik object не содержит однозначные id/title")
        return
    if live_title == expected_title:
        plan.already_clean.append(
            {
                "kind": kind,
                "canonical_id": canonical_id,
                "stepik_id": stepik_id,
                "title": live_title,
            }
        )
        return
    legacy = legacy_title(canonical_id, expected_title)
    if live_title != legacy:
        plan.blockers.append(
            f"{kind}:{canonical_id}: title drift не равен ни canonical title, ни точному legacy-prefix: {live_title!r}"
        )
        return
    if golden_read_only:
        plan.owner_required.append(
            {
                "classification": "GOLDEN_TITLE_OWNER_REQUIRED",
                "kind": kind,
                "canonical_id": canonical_id,
                "stepik_id": stepik_id,
                "current_title": live_title,
                "expected_title": expected_title,
                "automatic_write_allowed": False,
            }
        )
        return
    plan.operations.append(
        TitleOperation(
            kind=kind,
            canonical_id=canonical_id,
            stepik_id=stepik_id,
            position=position,
            live_title=live_title,
            expected_title=expected_title,
        )
    )


def plan_title_hygiene(manifest: dict[str, Any], snapshot: dict[str, Any]) -> TitleHygienePlan:
    """Планирует только доказуемое удаление exact legacy ID-prefix.

    Identity берётся из канонической section/unit position. Произвольный stale title не
    перезаписывается: такой случай блокирует route и требует разбора владельцем.
    Golden lesson title остаётся owner-only.
    """
    plan = TitleHygienePlan()
    sections = list(snapshot.get("sections", []))

    for module in manifest.get("modules", []):
        module_id = str(module["canonical_id"])
        module_position = int(module["position"])
        section_matches = _position_matches(sections, module_position)
        if len(section_matches) != 1:
            plan.blockers.append(
                f"section:{module_id}: ожидался один section position={module_position}, найдено {len(section_matches)}"
            )
            continue
        section = section_matches[0]
        _classify_title(
            plan,
            kind="section",
            canonical_id=module_id,
            position=module_position,
            stepik_id=section.get("id"),
            live_title=section.get("title"),
            expected_title=str(module["title"]),
        )

        units = list(section.get("units", []))
        for lesson in module.get("lessons", []):
            lesson_id = str(lesson["canonical_id"])
            lesson_position = int(lesson["position"])
            unit_matches = _position_matches(units, lesson_position)
            if len(unit_matches) != 1:
                plan.blockers.append(
                    f"lesson:{lesson_id}: ожидался один unit position={lesson_position}, найдено {len(unit_matches)}"
                )
                continue
            live_lesson = unit_matches[0].get("lesson")
            if not isinstance(live_lesson, dict):
                plan.blockers.append(f"lesson:{lesson_id}: unit не содержит lesson object")
                continue
            _classify_title(
                plan,
                kind="lesson",
                canonical_id=lesson_id,
                position=lesson_position,
                stepik_id=live_lesson.get("id"),
                live_title=live_lesson.get("title"),
                expected_title=str(lesson["title"]),
                golden_read_only=bool(lesson.get("golden_read_only")) or lesson_id in GOLDEN_LESSON_IDS,
            )

    return plan


def _resource_and_payload(operation: TitleOperation) -> tuple[str, str, dict[str, Any]]:
    if operation.kind == "lesson":
        return "lessons", "lesson", {"lesson": {"title": operation.expected_title}}
    if operation.kind == "section":
        return "sections", "section", {"section": {"title": operation.expected_title}}
    raise TitleHygieneError(f"Неподдерживаемый title kind: {operation.kind}")


def _read_title(client: Any, operation: TitleOperation) -> str:
    resource, _payload_key, _payload = _resource_and_payload(operation)
    obj = client.fetch_one(resource, operation.stepik_id)
    if int(obj.get("id", -1)) != operation.stepik_id or not isinstance(obj.get("title"), str):
        raise TitleHygieneError(f"{operation.object_id}: read-back не содержит ожидаемые id/title")
    return str(obj["title"])


def _write_title(client: Any, operation: TitleOperation) -> None:
    resource, _payload_key, payload = _resource_and_payload(operation)
    # _request_write — общий Stepik write primitive проекта: без автоматических retry и
    # с AMBIGUOUS-классификацией network/5xx. Здесь намеренно не вводится второй transport.
    client._request_write("PUT", f"/api/{resource}/{operation.stepik_id}", payload)


def execute_title_only_operation(
    client: Any,
    operation: TitleOperation,
    recorder: DeploymentRecorder,
) -> dict[str, Any]:
    """Выполняет один title-only PUT с WAL и read-back.

    Функция пригодна для section и для lesson без content baseline. Tracked lesson с
    deployment baseline должен обновляться отдельным content-aware route.
    """
    before_title = _read_title(client, operation)
    before_state = title_state(kind=operation.kind, stepik_id=operation.stepik_id, title=before_title)
    desired_state = title_state(
        kind=operation.kind,
        stepik_id=operation.stepik_id,
        title=operation.expected_title,
    )
    before_fp = title_fingerprint(kind=operation.kind, stepik_id=operation.stepik_id, title=before_title)
    desired_fp = title_fingerprint(
        kind=operation.kind,
        stepik_id=operation.stepik_id,
        title=operation.expected_title,
    )
    if recorder.identity.desired_fingerprint != desired_fp:
        raise DeploymentHistoryError(f"{operation.object_id}: event desired fingerprint не совпадает с title plan")

    records = recorder.records(refresh=True)
    summary = summarize_event(records) if records else None
    if summary and summary.get("machine_state_committed"):
        if before_title != operation.expected_title:
            raise TitleHygieneError(f"{operation.object_id}: committed title event, но live title снова drifted")
        return {"action": "NOOP_COMMITTED", "operation": operation.as_dict()}

    if summary:
        if summary.get("ambiguous") or summary.get("readback_failed") or summary.get("known_failed_writes"):
            raise TitleHygieneError(
                f"{operation.object_id}: незавершённая/неоднозначная write history запрещает blind retry"
            )
        if summary.get("final_readback_confirmed"):
            if before_title != operation.expected_title:
                raise TitleHygieneError(f"{operation.object_id}: final history не совпадает с live title")
            recorder.state_committed(
                baseline_after=desired_state,
                status=str(summary.get("final_status")),
            )
            return {"action": "RECOVER_COMMIT", "operation": operation.as_dict()}
        if summary.get("writes_started"):
            if summary.get("confirmed_operation_count") == 1 and before_title == operation.expected_title:
                recorder.final_readback(
                    fingerprint_after=desired_fp,
                    stepik_object_ids={f"{operation.kind}_id": operation.stepik_id},
                    status="APPLIED",
                    baseline_after=desired_state,
                )
                recorder.state_committed(baseline_after=desired_state, status="APPLIED")
                return {"action": "RECOVER_FINAL", "operation": operation.as_dict()}
            raise TitleHygieneError(
                f"{operation.object_id}: write dispatch без полного per-operation read-back; blind retry запрещён"
            )

    if before_title == operation.expected_title:
        # План мог устареть между inspect и dispatch. Без write просто фиксируем доказанный NOOP.
        recorder.ensure_started(
            operation_type="title-hygiene",
            state_before=desired_state,
            expected_state=desired_state,
            stepik_object_ids={f"{operation.kind}_id": operation.stepik_id},
            fingerprint_before=desired_fp,
        )
        recorder.final_readback(
            fingerprint_after=desired_fp,
            stepik_object_ids={f"{operation.kind}_id": operation.stepik_id},
            status="NOOP_CONFIRMED",
            baseline_after=desired_state,
        )
        recorder.state_committed(baseline_after=desired_state, status="NOOP_CONFIRMED")
        return {"action": "NOOP_ALREADY_CLEAN", "operation": operation.as_dict()}
    if before_title != operation.live_title:
        raise TitleHygieneError(
            f"{operation.object_id}: title изменился после planning: {before_title!r} != {operation.live_title!r}"
        )

    recorder.ensure_started(
        operation_type="title-hygiene",
        state_before=before_state,
        expected_state=desired_state,
        stepik_object_ids={f"{operation.kind}_id": operation.stepik_id},
        fingerprint_before=before_fp,
    )
    operation_id = "title-put"
    recorder.write_intent(
        operation_id=operation_id,
        method="PUT",
        target=f"{operation.kind}s/{operation.stepik_id}",
        fingerprint_before=before_fp,
        expected_fingerprint_after=desired_fp,
    )
    recorder.write_dispatch_started(operation_id=operation_id)
    try:
        _write_title(client, operation)
    except StepikWriteAmbiguousError:
        recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="title-write-ambiguous")
        raise
    except StepikAPIError:
        recorder.write_result(operation_id=operation_id, status="FAILED_KNOWN", reason_code="title-write-failed-known")
        raise
    except Exception:
        recorder.write_result(operation_id=operation_id, status="AMBIGUOUS", reason_code="title-write-exception-after-dispatch")
        raise
    recorder.write_result(operation_id=operation_id, status="COMPLETED")

    try:
        after_title = _read_title(client, operation)
        if after_title != operation.expected_title:
            raise TitleHygieneError(
                f"{operation.object_id}: title read-back {after_title!r} != {operation.expected_title!r}"
            )
    except Exception:
        recorder.readback_failed(operation_id=operation_id, reason_code="title-readback-unavailable-or-mismatch")
        raise

    recorder.operation_readback(operation_id=operation_id, expected_fingerprint_after=desired_fp)
    recorder.final_readback(
        fingerprint_after=desired_fp,
        stepik_object_ids={f"{operation.kind}_id": operation.stepik_id},
        status="APPLIED",
        baseline_after=desired_state,
    )
    recorder.state_committed(baseline_after=desired_state, status="APPLIED")
    return {"action": "UPDATE_TITLE", "operation": operation.as_dict()}
