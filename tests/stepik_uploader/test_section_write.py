from __future__ import annotations

import unittest

from scripts.stepik_uploader.section_write import (
    SectionWriteContractError,
    assert_section_readback,
    execute_section_put,
    prepare_section_put,
)


class FakeSectionClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, dict]] = []
        self.options_calls = 0

    def _request_options(self, path: str):
        self.options_calls += 1
        raise AssertionError(f"section PUT contract must not depend on OPTIONS: {path}")

    def _request_write(self, method: str, path: str, payload: dict):
        self.writes.append((method, path, payload))
        return {"sections": [{"id": 7}]}


class SectionWriteTests(unittest.TestCase):
    def _live(self):
        return {
            "id": 7,
            "title": "Старый заголовок",
            "course": 299189,
            "position": 5,
            "required_percent": 0,
            "required_section": None,
            "grading_policy": "halved",
            "description": "",
            "units": [11, 12],
            "progress": "123-7",
            "actions": {"test_section": "#"},
            "slug": "staryi-zagolovok-7",
            "update_date": "2026-09-15T00:00:00Z",
        }

    def test_prepare_put_copies_full_raw_get_and_never_calls_options(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        contract = prepare_section_put(
            client,
            before,
            overrides={"title": "Новый заголовок"},
        )

        expected = dict(before)
        expected["title"] = "Новый заголовок"
        self.assertEqual(contract.payload, expected)
        self.assertEqual(client.options_calls, 0)
        self.assertEqual(
            contract.as_dict()["contract_source"],
            "raw-get-full-object-read-modify-write",
        )
        self.assertTrue(contract.as_dict()["preserves_full_raw_get_payload"])
        self.assertFalse(contract.as_dict()["options_required"])

        execute_section_put(client, contract)
        self.assertEqual(len(client.writes), 1)
        method, path, payload = client.writes[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(path, "/api/sections/7")
        self.assertEqual(payload["section"], expected)
        self.assertEqual(payload["section"]["position"], 5)
        self.assertEqual(payload["section"]["course"], 299189)
        self.assertEqual(payload["section"]["units"], [11, 12])

    def test_missing_required_raw_field_blocks(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        del before["course"]
        with self.assertRaises(SectionWriteContractError):
            prepare_section_put(
                client,
                before,
                overrides={"title": "Новый заголовок"},
            )
        self.assertEqual(client.options_calls, 0)
        self.assertEqual(client.writes, [])

    def test_unknown_override_is_forbidden(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        with self.assertRaises(SectionWriteContractError):
            prepare_section_put(
                client,
                before,
                overrides={"required_percent": 50},
            )
        self.assertEqual(client.writes, [])

    def test_position_recovery_changes_only_requested_field_in_payload(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        before["position"] = 1
        contract = prepare_section_put(
            client,
            before,
            overrides={"position": 5},
        )
        expected = dict(before)
        expected["position"] = 5
        self.assertEqual(contract.payload, expected)
        self.assertEqual(contract.payload["title"], before["title"])
        self.assertEqual(contract.payload["course"], before["course"])
        self.assertEqual(contract.payload["required_percent"], before["required_percent"])
        self.assertEqual(contract.payload["units"], before["units"])

    def test_readback_detects_preserved_authored_field_drift(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        contract = prepare_section_put(
            client,
            before,
            overrides={"title": "Новый заголовок"},
        )
        after = {**before, "title": "Новый заголовок", "required_percent": 10}
        with self.assertRaises(SectionWriteContractError):
            assert_section_readback(before, after, contract)

    def test_readback_allows_server_managed_field_changes(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        contract = prepare_section_put(
            client,
            before,
            overrides={"title": "Новый заголовок"},
        )
        after = {
            **before,
            "title": "Новый заголовок",
            "progress": "different-viewer-state",
            "actions": {"edit": "#"},
            "slug": "novyi-zagolovok-7",
            "update_date": "2026-09-15T12:00:00Z",
        }
        assert_section_readback(before, after, contract)

    def test_readback_requires_override_to_land_exactly(self) -> None:
        client = FakeSectionClient()
        before = self._live()
        contract = prepare_section_put(
            client,
            before,
            overrides={"position": 8},
        )
        after = {**before, "position": 1}
        with self.assertRaises(SectionWriteContractError):
            assert_section_readback(before, after, contract)


if __name__ == "__main__":
    unittest.main()
