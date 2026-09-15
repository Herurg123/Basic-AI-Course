from __future__ import annotations

import unittest

from scripts.stepik_uploader.replacement_update import (
    ReplacementUpdateError,
    dispatch_replacement_put,
    plan_replacement_put,
)


class FakeClient:
    def __init__(self, *, before: dict, schema: dict | None = None, allow: str = "GET, PUT, OPTIONS") -> None:
        self.before = dict(before)
        self.schema = schema or {
            "actions": {
                "PUT": {
                    "title": {"required": True},
                    "course": {"required": True},
                    "position": {"required": True},
                    "exam": {"required": False},
                    "id": {"read_only": True},
                }
            }
        }
        self.allow = allow
        self.calls: list[str] = []
        self.writes: list[tuple[str, str, dict]] = []

    def fetch_one(self, resource: str, object_id: int):
        self.calls.append("GET")
        return dict(self.before)

    def _request_options(self, path: str):
        self.calls.append("OPTIONS")
        return self.schema, self.allow

    def _request_write(self, method: str, path: str, payload: dict):
        self.calls.append("PUT")
        self.writes.append((method, path, payload))
        return {"sections": [dict(self.before)]}


class ReplacementUpdateTests(unittest.TestCase):
    def test_section_plan_preserves_all_writable_live_fields(self) -> None:
        client = FakeClient(
            before={
                "id": 755029,
                "title": "M04 — Решите задачу по материалу",
                "course": 299189,
                "position": 5,
                "exam": True,
                "read_only_noise": "do-not-copy",
            }
        )
        plan = plan_replacement_put(
            client,
            resource="sections",
            object_id=755029,
            changes={"title": "Решите задачу по своему материалу"},
            required_preserved_fields=("title", "course", "position"),
        )

        self.assertEqual(client.calls, ["GET", "OPTIONS"])
        self.assertEqual(client.writes, [])
        self.assertEqual(
            plan.payload,
            {
                "section": {
                    "title": "Решите задачу по своему материалу",
                    "course": 299189,
                    "position": 5,
                    "exam": True,
                }
            },
        )
        self.assertNotIn("id", plan.payload["section"])
        self.assertNotIn("read_only_noise", plan.payload["section"])

        dispatch_replacement_put(client, plan)
        self.assertEqual(client.calls, ["GET", "OPTIONS", "PUT"])
        self.assertEqual(len(client.writes), 1)
        method, path, payload = client.writes[0]
        self.assertEqual(method, "PUT")
        self.assertTrue(path.endswith("/api/sections/755029"))
        self.assertEqual(payload["section"]["position"], 5)

    def test_missing_structural_field_blocks_before_dispatch(self) -> None:
        client = FakeClient(
            before={"id": 755029, "title": "x", "course": 299189},
        )
        with self.assertRaises(ReplacementUpdateError):
            plan_replacement_put(
                client,
                resource="sections",
                object_id=755029,
                changes={"title": "y"},
                required_preserved_fields=("title", "course", "position"),
            )
        self.assertNotIn("PUT", client.calls)
        self.assertEqual(client.writes, [])

    def test_put_must_be_confirmed_by_options_allow(self) -> None:
        client = FakeClient(
            before={"id": 755029, "title": "x", "course": 299189, "position": 5},
            allow="GET, OPTIONS",
        )
        with self.assertRaises(ReplacementUpdateError):
            plan_replacement_put(
                client,
                resource="sections",
                object_id=755029,
                changes={"title": "y"},
                required_preserved_fields=("title", "course", "position"),
            )
        self.assertEqual(client.calls, ["GET", "OPTIONS"])
        self.assertEqual(client.writes, [])

    def test_put_schema_must_exist(self) -> None:
        client = FakeClient(
            before={"id": 755029, "title": "x", "course": 299189, "position": 5},
            schema={"actions": {}},
        )
        with self.assertRaises(ReplacementUpdateError):
            plan_replacement_put(
                client,
                resource="sections",
                object_id=755029,
                changes={"title": "y"},
                required_preserved_fields=("title", "course", "position"),
            )
        self.assertEqual(client.writes, [])


if __name__ == "__main__":
    unittest.main()
