from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class SectionWriteContractError(RuntimeError):
    pass


def _allow_methods(raw: str) -> frozenset[str]:
    return frozenset(part.strip().upper() for part in str(raw or "").split(",") if part.strip())


@dataclass(frozen=True)
class SectionPutContract:
    section_id: int
    writable_fields: tuple[str, ...]
    payload: dict[str, Any]
    overrides: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "method": "PUT",
            "target": f"sections/{self.section_id}",
            "writable_fields": list(self.writable_fields),
            "override_fields": sorted(self.overrides),
            "payload_fields": sorted(self.payload),
            "preserves_all_declared_writable_fields": True,
        }


def prepare_section_put(
    client: Any,
    live_section: dict[str, Any],
    *,
    overrides: dict[str, Any],
) -> SectionPutContract:
    """Build a PUT that preserves every field Stepik declares writable for sections.

    A short/partial section PUT is forbidden: production evidence showed that an omitted
    writable ``position`` field can be reset server-side. The OPTIONS metadata is therefore
    treated as the runtime write contract, and every declared PUT field must either be
    copied from the live GET object or supplied explicitly as an override.
    """
    if not isinstance(live_section, dict):
        raise SectionWriteContractError("section GET должен быть JSON object")
    section_id = live_section.get("id")
    if not isinstance(section_id, int):
        raise SectionWriteContractError("section GET не содержит целочисленный id")
    if not isinstance(overrides, dict) or not overrides:
        raise SectionWriteContractError("section PUT требует явный непустой overrides")

    metadata, allow = client._request_options(f"/api/sections/{section_id}")
    methods = _allow_methods(allow)
    if "PUT" not in methods:
        raise SectionWriteContractError(
            f"section:{section_id}: OPTIONS Allow не подтверждает PUT: {sorted(methods)}"
        )

    actions = metadata.get("actions")
    if not isinstance(actions, dict) or not isinstance(actions.get("PUT"), dict):
        raise SectionWriteContractError(
            f"section:{section_id}: OPTIONS не содержит actions.PUT"
        )
    put_fields = actions["PUT"]
    writable_fields = tuple(sorted(str(name) for name in put_fields))
    if not writable_fields:
        raise SectionWriteContractError(f"section:{section_id}: actions.PUT пуст")

    unknown_overrides = sorted(set(overrides) - set(writable_fields))
    if unknown_overrides:
        raise SectionWriteContractError(
            f"section:{section_id}: override не объявлен writable в OPTIONS: {unknown_overrides}"
        )

    missing = sorted(
        field
        for field in writable_fields
        if field not in overrides and field not in live_section
    )
    if missing:
        raise SectionWriteContractError(
            f"section:{section_id}: нельзя доказуемо сохранить writable fields из OPTIONS: {missing}"
        )

    payload: dict[str, Any] = {}
    for field in writable_fields:
        if field in overrides:
            payload[field] = deepcopy(overrides[field])
        else:
            payload[field] = deepcopy(live_section[field])

    if "title" in overrides and "position" not in writable_fields:
        raise SectionWriteContractError(
            f"section:{section_id}: OPTIONS PUT не объявляет position; title PUT заблокирован"
        )

    return SectionPutContract(
        section_id=section_id,
        writable_fields=writable_fields,
        payload=payload,
        overrides=deepcopy(overrides),
    )


def execute_section_put(client: Any, contract: SectionPutContract) -> dict[str, Any]:
    return client._request_write(
        "PUT",
        f"/api/sections/{contract.section_id}",
        {"section": deepcopy(contract.payload)},
    )


def assert_section_readback(
    before: dict[str, Any],
    after: dict[str, Any],
    contract: SectionPutContract,
) -> None:
    """Require exact preservation of all declared writable fields except overrides."""
    if not isinstance(after, dict) or int(after.get("id", -1)) != contract.section_id:
        raise SectionWriteContractError(
            f"section:{contract.section_id}: read-back не содержит ожидаемый id"
        )

    for field in contract.writable_fields:
        expected = contract.payload[field]
        actual = after.get(field)
        if actual != expected:
            raise SectionWriteContractError(
                f"section:{contract.section_id}: read-back field {field!r}={actual!r} "
                f"!= отправленного {expected!r}"
            )

    for field in ("course", "units"):
        if field in before and after.get(field) != before.get(field):
            raise SectionWriteContractError(
                f"section:{contract.section_id}: read-back неожиданно изменил {field}"
            )
