from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.writer import (
    ContentWriteError,
    classify_existing_steps,
    execute_content_test_one,
    html_fingerprint,
)

EXPECTED = [
    CompiledStep(
        1,
        "text",
        '<p>Первый <a href="https://example.org/">линк</a></p>',
        {},
        (),
    ),
    CompiledStep(
        2,
        "free-answer",
        "<p>Ответ</p>",
        {
            "is_attachments_enabled": False,
            "is_html_enabled": True,
            "manual_scoring": False,
        },
        (),
    ),
]


def skeleton() -> dict:
    return {
        "course": {"id": 299189, "is_public": False},
        "sections": [
            {
                "id": 11,
                "position": 3,
                "units": [
                    {
                        "id": 101,
                        "position": 1,
                        "lesson": {
                            "id": 201,
                            "title": "M02-L01 — Скажите, что получите и как это оцените",
                            "is_public": False,
                            "language": "ru",
                            "steps": [
                                {
                                    "id": 1,
                                    "step_source": {
                                        "id": 1,
                                        "lesson": 201,
                                        "position": 1,
                                        "block": {
                                            "name": "text",
                                            "text": "Урок сгенерирован роботом ;)",
                                            "source": {},
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


class FakeClient:
    def __init__(self) -> None:
        self.snapshot = skeleton()
        self.update_calls = 0
        self.create_calls = 0
        self.next_id = 2

    def _steps(self) -> list[dict]:
        return self.snapshot["sections"][0]["units"][0]["lesson"]["steps"]

    def update_step_source(self, *, step_id: int, lesson_id: int, position: int, block: dict) -> dict:
        self.update_calls += 1
        item = next(value for value in self._steps() if value["id"] == step_id)
        item["step_source"] = {
            "id": step_id,
            "lesson": lesson_id,
            "position": position,
            "block": copy.deepcopy(block),
        }
        return {"step-sources": [copy.deepcopy(item["step_source"])]}

    def create_step_source(self, *, lesson_id: int, position: int, block: dict) -> dict:
        self.create_calls += 1
        step_id = self.next_id
        self.next_id += 1
        source = {
            "id": step_id,
            "lesson": lesson_id,
            "position": position,
            "block": copy.deepcopy(block),
        }
        self._steps().append({"id": step_id, "step_source": source})
        return {"step-sources": [copy.deepcopy(source)]}

    def fetch_one(self, resource: str, object_id: int) -> dict:
        self.assert_resource(resource)
        return copy.deepcopy(next(value["step_source"] for value in self._steps() if value["id"] == object_id))

    @staticmethod
    def assert_resource(resource: str) -> None:
        if resource != "step-sources":
            raise AssertionError(resource)

    def inspect_course(self, course_id: int) -> dict:
        if course_id != 299189:
            raise AssertionError(course_id)
        return copy.deepcopy(self.snapshot)


class WriterTests(unittest.TestCase):
    def test_html_fingerprint_ignores_stepik_link_attributes(self) -> None:
        expected = '<p>Go <a href="https://x/">x</a></p>'
        readback = '<p>Go <a target="_new" rel="nofollow noopener" href="https://x/">x</a></p>'
        self.assertEqual(html_fingerprint(expected), html_fingerprint(readback))

    def test_placeholder_is_explicit_state(self) -> None:
        existing = skeleton()["sections"][0]["units"][0]["lesson"]["steps"]
        self.assertEqual(classify_existing_steps(existing, EXPECTED), ("skeleton-placeholder", 0))

    def test_skeleton_write_then_second_run_is_noop(self) -> None:
        client = FakeClient()
        result = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title="M02-L01 — Скажите, что получите и как это оцените",
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, 1)
        self.assertEqual(client.create_calls, 1)

        second = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title="M02-L01 — Скажите, что получите и как это оцените",
        )
        self.assertTrue(second.verified)
        self.assertEqual(client.update_calls, 1)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(second.operations[0]["action"], "NOOP_ALREADY_MATCHES")

    def test_public_target_lesson_blocks_before_write(self) -> None:
        client = FakeClient()
        client.snapshot["sections"][0]["units"][0]["lesson"]["is_public"] = True
        with self.assertRaisesRegex(ContentWriteError, "public"):
            execute_content_test_one(
                client,
                client.inspect_course(299189),
                expected_steps=EXPECTED,
                module_position=3,
                lesson_position=1,
                expected_title="M02-L01 — Скажите, что получите и как это оцените",
            )
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)

    def test_wrong_language_blocks_before_write(self) -> None:
        client = FakeClient()
        client.snapshot["sections"][0]["units"][0]["lesson"]["language"] = "en"
        with self.assertRaisesRegex(ContentWriteError, "language"):
            execute_content_test_one(
                client,
                client.inspect_course(299189),
                expected_steps=EXPECTED,
                module_position=3,
                lesson_position=1,
                expected_title="M02-L01 — Скажите, что получите и как это оцените",
            )
        self.assertEqual(client.update_calls, 0)
        self.assertEqual(client.create_calls, 0)

    def test_unexpected_existing_content_blocks(self) -> None:
        live = skeleton()
        live["sections"][0]["units"][0]["lesson"]["steps"][0]["step_source"]["block"]["text"] = (
            "<p>Чужой текст</p>"
        )
        with self.assertRaises(ContentWriteError):
            classify_existing_steps(live["sections"][0]["units"][0]["lesson"]["steps"], EXPECTED)


if __name__ == "__main__":
    unittest.main()
