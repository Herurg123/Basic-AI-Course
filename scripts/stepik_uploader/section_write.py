from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


class SectionWriteContractError(RuntimeError):
    pass


# Stepik detail OPTIONS for sections is not usable in production (HTTP 500 was
# reproduced twice by read-only recovery run 35013088945).  Section PUT is
# therefore treated as a full-object replacement: start from the raw GET object,
# override one explicitly supported authored field, and send the complete object
# back.  These fields are server-/viewer-derived and may legitimately differ on
# the immediate read-back even when authored section state was preserved.
_SERVER_MANAGED_READBACK_FIELDS = frozenset(
    {
        "actions",
        "exam_session",
        "is_active",
        "is_proctoring_can_be_scheduled",
        "is_requirement_satisfied",
        "proctor_session",
        "progress",
        "slug",
        "update_date",
    }
)
_REQUIRED_RAW_FIELDS = frozenset({"id", "course", "units", "position", "title"})
_ALLOWED_OVERRIDES = frozenset({"position", "title"})


@dataclass(frozen=True)
class SectionPutContract:
    section_id: int
    payload: dict[str, Any]
    overrides: dict[str, Any]
    preserved_readback_fields: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "method": "PUT",
            "target": f"sections/{self.section_id}",
            "contract_source": "raw-get-full-object-read-modify-write",
            "override_fields": sorted(self.overrides),
            "payload_fields": sorted(self.payload),
            "preserved_readback_fields": list(self.preserved_readback_fields),
            "server_managed_readback_exclusions": sorted(_SERVER_MANAGED_READBACK_FIELDS),
            "preserves_full_raw_get_payload": True,
            "options_required": False,
        }


def prepare_section_put(
    client: Any,
    live_section: dict[str, Any],
    *,
    overrides: dict[str, Any],
) -> SectionPutContract:
    """Build a fail-closed raw-GET read-modify-write contract for a section PUT.

    Production evidence showed that a short section PUT can reset omitted fields
    (notably ``position``).  Stepik's detail OPTIONS endpoint for sections also
    returns HTTP 500 in production, so OPTIONS cannot be the safety oracle.

    The safe contract is instead: fetch the raw section object, require the
    identity/structure fields needed to prove what object is being edited, copy
    the *entire* raw object into the PUT payload, and change only the explicitly
    supported authored field (``title`` or ``position``).
    """
    # Keep the client argument for the existing call surface.  Contract building
    # is deliberately read-only and must not call OPTIONS or any write method.
    del client

    if not isinstance(live_section, dict):
        raise SectionWriteContractError("section GET должен быть JSON object")
    section_id = live_section.get("id")
    if not isinstance(section_id, int):
        raise SectionWriteContractError("section GET не содержит целочисленный id")
    if not isinstance(overrides, dict) or not overrides:
        raise SectionWriteContractError("section PUT требует явный непустой overrides")

    missing_required = sorted(_REQUIRED_RAW_FIELDS - set(live_section))
    if missing_required:
        raise SectionWriteContractError(
            f"section:{section_id}: raw GET не содержит обязательные поля: {missing_required}"
        )
    if not isinstance(live_section.get("course"), int):
        raise SectionWriteContractError(f"section:{section_id}: raw course не целочисленный")
    if not isinstance(live_section.get("units"), list):
        raise SectionWriteContractError(f"section:{section_id}: raw units не список")
    if not isinstance(live_section.get("position"), int):
        raise SectionWriteContractError(f"section:{section_id}: raw position не целочисленная")
    if not isinstance(live_section.get("title"), str):
        raise SectionWriteContractError(f"section:{section_id}: raw title не строка")

    unsupported = sorted(set(overrides) - _ALLOWED_OVERRIDES)
    if unsupported:
        raise SectionWriteContractError(
            f"section:{section_id}: запрещённые override fields: {unsupported}"
        )
    missing_override_fields = sorted(set(overrides) - set(live_section))
    if missing_override_fields:
        raise SectionWriteContractError(
            f"section:{section_id}: override отсутствует в raw GET: {missing_override_fields}"
        )
    if "position" in overrides and (
        not isinstance(overrides["position"], int) or int(overrides["position"]) < 1
    ):
        raise SectionWriteContractError(f"section:{section_id}: position override должен быть int >= 1")
    if "title" in overrides and not isinstance(overrides["title"], str):
        raise SectionWriteContractError(f"section:{section_id}: title override должен быть строкой")

    payload = deepcopy(live_section)
    for field, value in overrides.items():
        payload[field] = deepcopy(value)

    preserved_readback_fields = tuple(
        sorted(
            field
            for field in live_section
            if field not in overrides and field not in _SERVER_MANAGED_READBACK_FIELDS
        )
    )
    return SectionPutContract(
        section_id=section_id,
        payload=payload,
        overrides=deepcopy(overrides),
        preserved_readback_fields=preserved_readback_fields,
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
    """Require exact authored-state preservation after a full-object section PUT."""
    if not isinstance(before, dict) or int(before.get("id", -1)) != contract.section_id:
        raise SectionWriteContractError(
            f"section:{contract.section_id}: before state не содержит ожидаемый id"
        )
    if not isinstance(after, dict) or int(after.get("id", -1)) != contract.section_id:
        raise SectionWriteContractError(
            f"section:{contract.section_id}: read-back не содержит ожидаемый id"
        )

    for field in contract.overrides:
        expected = contract.payload[field]
        if field not in after or after.get(field) != expected:
            raise SectionWriteContractError(
                f"section:{contract.section_id}: read-back override {field!r}={after.get(field)!r} "
                f"!= отправленного {expected!r}"
            )

    for field in contract.preserved_readback_fields:
        expected = before[field]
        if field not in after or after.get(field) != expected:
            raise SectionWriteContractError(
                f"section:{contract.section_id}: read-back неожиданно изменил preserved field "
                f"{field!r}: {after.get(field)!r} != {expected!r}"
            )
