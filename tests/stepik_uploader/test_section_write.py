from __future__ import annotations

import unittest

from scripts.stepik_uploader.section_write import (
    SectionWriteContractError,
    assert_section_readback,
    execute_section_put,
    prepare_section_put,
)


class FakeSectionClient:
    def __init__(self, put_fields: list[str]) -> None:
        self.put_fields = put_fields
        self.writes: list[tuple[str, str, dict]] = []

    def _request_options(self, path: str):
        return (
            {
                "actions": {
                    "PUT": {
                        field: {"required": field in {"title", "course", "position"}}
                        for field in self.put_fields
                    }
                }
            },
            "GET, PUT, HEAD, OPTIONS",
        )

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
            "units": [11, 12],
        }

    def test_prepare_put_preserves_every_declared_writable_field(self) -> None:
        client = FakeSectionClient(["title", "course", "position", "required_percent"])
        contract = prepare_section_put(
            client,
            self._live(),
            overrides={"title": "Новый заголовок"},
        )
        self.assertEqual(
            contract.payload,
            {
                "course": 299189,
                "position": 5,
                "required_percent": 0,
                "title": "Новый заголовок",
            },
        )

        execute_section_put(client, contract)
        self.assertEqual(len(client.writes), 1)
        method, path, payload = client.writes[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(path, "/api/sections/7")
        self.assertEqual(payload["section"]["position"], 5)

        after = {
            **self._live(),
            "title": "Новый заголовок",
        }
        assert_section_readback(self._live(), after, contract)

    def test_missing_declared_writable_field_blocks(self) -> None:
        client = FakeSectionClient(["title", "course", "position", "required_percent", "unknown_live_field"])
        with self.assertRaises(SectionWriteContractError):
            prepare_section_put(
                client,
                self._live(),
                overrides={"title": "Новый заголовок"},
            )
        self.assertEqual(client.writes, [])

    def test_title_put_requires_position_in_options_contract(self) -> None:
        client = FakeSectionClient(["title", "course"])
        with self.assertRaises(SectionWriteContractError):
            prepare_section_put(
                client,
                self._live(),
                overrides={"title": "Новый заголовок"},
            )

    def test_position_recovery_changes_only_requested_field(self) -> None:
        client = FakeSectionClient(["title", "course", "position", "required_percent"])
        before = self._live()
        before["position"] = 1
        contract = prepare_section_put(
            client,
            before,
            overrides={"position": 5},
        )
        self.assertEqual(contract.payload["position"], 5)
        self.assertEqual(contract.payload["title"], before["title"])
        self.assertEqual(contract.payload["course"], before["course"])
        self.assertEqual(contract.payload["required_percent"], before["required_percent"])

    def test_readback_detects_preserved_field_drift(self) -> None:
        client = FakeSectionClient(["title", "course", "position", "required_percent"])
        before = self._live()
        contract = prepare_section_put(
            client,
            before,
            overrides={"title": "Новый заголовок"},
        )
        after = {**before, "title": "Новый заголовок", "required_percent": 10}
        with self.assertRaises(SectionWriteContractError):
            assert_section_readback(before, after, contract)


if __name__ == "__main__":
    unittest.main()
