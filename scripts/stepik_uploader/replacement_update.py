from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from .api import StepikAPIError


class ReplacementUpdateError(StepikAPIError):
    """PUT replacement нельзя доказуемо собрать из live object + OPTIONS schema."""


@dataclass(frozen=True)
class ReplacementPlan:
    resource: str
    object_id: int
    payload_key: str
    before: dict[str, Any]
    payload: dict[str, Any]
    writable_fields: tuple[str, ...]
    allow: str


def _payload_key(resource: str) -> str:
    known = {
        "sections": "section",
        "lessons": "lesson",
    }
    try:
        return known[resource]
    except KeyError as exc:
        raise ReplacementUpdateError(f"Replacement PUT не разрешён для resource={resource!r}") from exc


def _allowed_methods(allow: str) -> set[str]:
    return {item.strip().upper() for item in str(allow).split(",") if item.strip()}


def _put_schema(metadata: dict[str, Any]) -> dict[str, Any]:
    actions = metadata.get("actions")
    if not isinstance(actions, dict):
        raise ReplacementUpdateError("OPTIONS не содержит actions; replacement PUT недоказуем")
    put = actions.get("PUT")
    if not isinstance(put, dict) or not put:
        raise ReplacementUpdateError("OPTIONS не содержит непустой actions.PUT schema")
    return put


def plan_replacement_put(
    client: Any,
    *,
    resource: str,
    object_id: int,
    changes: dict[str, Any],
    required_preserved_fields: Iterable[str] = (),
) -> ReplacementPlan:
    """Собирает read-modify-write PUT только из полей, которые Stepik объявил writable.

    Stepik PUT ведёт себя replacement-like, поэтому отправка одного изменяемого поля опасна.
    Мы сначала читаем live object и OPTIONS detail endpoint, сохраняем все writable поля из
    текущего объекта и лишь затем накладываем точечные изменения. Если schema/Allow/required
    fields не дают доказуемого replacement payload, операция fail-closed до dispatch.
    """
    payload_key = _payload_key(resource)
    object_id = int(object_id)
    before = client.fetch_one(resource, object_id)
    try:
        live_id = int(before.get("id", -1))
    except (TypeError, ValueError) as exc:
        raise ReplacementUpdateError(f"{resource}/{object_id}: live object не содержит корректный id") from exc
    if live_id != object_id:
        raise ReplacementUpdateError(f"{resource}/{object_id}: live object id mismatch")

    metadata, allow = client._request_options(f"/api/{resource}/{object_id}")
    if "PUT" not in _allowed_methods(allow):
        raise ReplacementUpdateError(f"{resource}/{object_id}: OPTIONS Allow не подтверждает PUT")
    put_schema = _put_schema(metadata)

    writable: list[str] = []
    body: dict[str, Any] = {}
    for field, description in put_schema.items():
        if not isinstance(field, str) or not field:
            raise ReplacementUpdateError(f"{resource}/{object_id}: OPTIONS содержит некорректное имя поля")
        if isinstance(description, dict) and description.get("read_only") is True:
            continue
        writable.append(field)
        if field in before:
            body[field] = deepcopy(before[field])
        elif isinstance(description, dict) and description.get("required") is True and field not in changes:
            raise ReplacementUpdateError(
                f"{resource}/{object_id}: required writable field {field!r} отсутствует в live object"
            )

    writable_set = set(writable)
    for field in changes:
        if field not in writable_set:
            raise ReplacementUpdateError(
                f"{resource}/{object_id}: поле {field!r} не подтверждено actions.PUT schema"
            )

    required = tuple(str(value) for value in required_preserved_fields)
    for field in required:
        if field not in writable_set:
            raise ReplacementUpdateError(
                f"{resource}/{object_id}: structural field {field!r} не подтверждено writable schema"
            )
        if field not in before and field not in changes:
            raise ReplacementUpdateError(
                f"{resource}/{object_id}: structural field {field!r} отсутствует в live object"
            )

    body.update(deepcopy(changes))
    if not body:
        raise ReplacementUpdateError(f"{resource}/{object_id}: пустой replacement payload запрещён")

    return ReplacementPlan(
        resource=resource,
        object_id=object_id,
        payload_key=payload_key,
        before=deepcopy(before),
        payload={payload_key: body},
        writable_fields=tuple(sorted(writable_set)),
        allow=str(allow),
    )


def dispatch_replacement_put(client: Any, plan: ReplacementPlan) -> None:
    """Единственная write-фаза: никаких GET/OPTIONS после WAL dispatch boundary."""
    client._request_write(
        "PUT",
        f"/api/{plan.resource}/{plan.object_id}",
        plan.payload,
    )


def execute_replacement_put(
    client: Any,
    *,
    resource: str,
    object_id: int,
    changes: dict[str, Any],
    required_preserved_fields: Iterable[str] = (),
) -> ReplacementPlan:
    """Удобный wrapper для routes без собственного WAL; guarded writers используют plan+dispatch."""
    plan = plan_replacement_put(
        client,
        resource=resource,
        object_id=object_id,
        changes=changes,
        required_preserved_fields=required_preserved_fields,
    )
    dispatch_replacement_put(client, plan)
    return plan
