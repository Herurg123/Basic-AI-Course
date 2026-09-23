from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.step_model import RenderedStep
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint
from scripts.stepik_uploader.writer import (
    ContentWriteError,
    classify_existing_steps,
    execute_content_sync_one,
    execute_content_test_one,
    html_fingerprint,
)

TITLE = "M02-L01 — Скажите, что получите и как это оцените"
EXPECTED = [
    RenderedStep(
        1,
        "text",
        '<p>Первый <a href="https://example.org/">линк</a></p>',
        {},
        ("04_course/M02/M02-L01/lesson.md",),
    ),
    RenderedStep(
        2,
        "free-answer",
        "<p>Ответ</p>",
        {
            "is_attachments_enabled": False,
            "is_html_enabled": True,
            "manual_scoring": False,
        },
        ("04_course/M02/M02-L01/lesson.md",),
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
                            "title": TITLE,
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
        self.title_update_calls = 0
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

    def update_lesson_title(self, *, lesson_id: int, title: str) -> dict:
        self.title_update_calls += 1
        lesson = self.snapshot["sections"][0]["units"][0]["lesson"]
        if lesson_id != lesson["id"]:
            raise AssertionError(lesson_id)
        lesson["title"] = title
        return {"lessons": [{"id": lesson_id, "title": title}]}

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
        if resource == "step-sources":
            return copy.deepcopy(next(value["step_source"] for value in self._steps() if value["id"] == object_id))
        if resource == "lessons":
            lesson = self.snapshot["sections"][0]["units"][0]["lesson"]
            if object_id != lesson["id"]:
                raise AssertionError(object_id)
            return {
                "id": lesson["id"],
                "title": lesson["title"],
                "is_public": lesson["is_public"],
                "language": lesson["language"],
            }
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
            expected_title=TITLE,
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
            expected_title=TITLE,
        )
        self.assertTrue(second.verified)
        self.assertEqual(client.update_calls, 1)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(second.operations[0]["action"], "NOOP_ALREADY_MATCHES")

    def test_tracked_content_change_updates_only_changed_step_then_becomes_noop(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        }
        updated = [
            RenderedStep(1, "text", "<p>Исправленный текст</p>", {}, EXPECTED[0].source_git_paths),
            EXPECTED[1],
        ]
        before_updates = client.update_calls
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=updated,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=baseline,
            source_sha="new-sha",
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, before_updates + 1)
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(result.operations, [{"action": "UPDATE_STEP", "step_id": 1, "position": 1}])
        self.assertIsNotNone(result.state_record)

        second = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=updated,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=result.state_record,
            source_sha="new-sha",
        )
        self.assertEqual(second.operations[0]["action"], "NOOP_ALREADY_IN_SYNC")
        self.assertEqual(client.update_calls, before_updates + 1)

    def test_tracked_topology_growth_updates_prefix_and_appends_only_tail(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(
                expected_title=TITLE,
                expected_steps=EXPECTED,
            ),
        }
        grown = [
            EXPECTED[0],
            RenderedStep(
                2,
                "text",
                "<p>Новый промежуточный шаг</p>",
                {},
                EXPECTED[0].source_git_paths,
            ),
            RenderedStep(
                3,
                EXPECTED[1].block_name,
                EXPECTED[1].text,
                EXPECTED[1].source,
                EXPECTED[1].source_git_paths,
            ),
        ]

        before_updates = client.update_calls
        before_creates = client.create_calls
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=grown,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=baseline,
            source_sha="growth-sha",
        )

        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, before_updates + 1)
        self.assertEqual(client.create_calls, before_creates + 1)
        self.assertEqual(
            [item["action"] for item in result.operations],
            ["UPDATE_STEP", "CREATE_STEP"],
        )
        self.assertEqual(
            [item["step_source"]["position"] for item in client._steps()],
            [1, 2, 3],
        )
        self.assertEqual(
            client._steps()[1]["step_source"]["block"]["text"],
            "<p>Новый промежуточный шаг</p>",
        )
        self.assertEqual(
            client._steps()[2]["step_source"]["block"]["text"],
            EXPECTED[1].text,
        )

    def test_tracked_topology_shrink_is_blocked_without_writes(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(
                expected_title=TITLE,
                expected_steps=EXPECTED,
            ),
        }
        before_updates = client.update_calls
        before_creates = client.create_calls
        with self.assertRaisesRegex(ContentWriteError, "STRUCTURAL_UPDATE_BLOCKED"):
            execute_content_sync_one(
                client,
                client.inspect_course(299189),
                canonical_id="M02-L01",
                expected_steps=[EXPECTED[0]],
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
                baseline=baseline,
                source_sha="shrink-sha",
            )
        self.assertEqual(client.update_calls, before_updates)
        self.assertEqual(client.create_calls, before_creates)

    def test_exploitation_sync_allows_published_course_when_baseline_matches(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        }
        client.snapshot["course"]["is_public"] = True
        updated = [
            RenderedStep(1, "text", "<p>Исправление после публикации</p>", {}, EXPECTED[0].source_git_paths),
            EXPECTED[1],
        ]
        before_updates = client.update_calls
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=updated,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
            baseline=baseline,
            source_sha="published-fix-sha",
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.update_calls, before_updates + 1)
        self.assertEqual(result.operations[0]["action"], "UPDATE_STEP")

    def test_tracked_title_change_updates_title_inside_same_sync(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        }
        renamed = TITLE + " — новый"
        before_step_updates = client.update_calls
        result = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=renamed,
            baseline=baseline,
            source_sha="a" * 40,
        )
        self.assertTrue(result.verified)
        self.assertEqual(client.title_update_calls, 1)
        self.assertEqual(client.update_calls, before_step_updates)
        self.assertEqual(result.operations[0]["action"], "UPDATE_LESSON_TITLE")
        self.assertEqual(client.snapshot["sections"][0]["units"][0]["lesson"]["title"], renamed)

        second = execute_content_sync_one(
            client,
            client.inspect_course(299189),
            canonical_id="M02-L01",
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=renamed,
            baseline=result.state_record,
            source_sha="b" * 40,
        )
        self.assertTrue(second.verified)
        self.assertEqual(client.title_update_calls, 1)
        self.assertEqual(second.operations[0]["action"], "NOOP_ALREADY_IN_SYNC")

    def test_manual_stepik_drift_blocks_before_overwrite(self) -> None:
        client = FakeClient()
        initial = execute_content_test_one(
            client,
            client.inspect_course(299189),
            expected_steps=EXPECTED,
            module_position=3,
            lesson_position=1,
            expected_title=TITLE,
        )
        baseline = {
            "stepik_lesson_id": initial.lesson_id,
            "applied_fingerprint": compiled_lesson_fingerprint(expected_title=TITLE, expected_steps=EXPECTED),
        }
        client._steps()[0]["step_source"]["block"]["text"] = "<p>Ручная правка в Stepik</p>"
        updated = [RenderedStep(1, "text", "<p>Новый канон</p>", {}, EXPECTED[0].source_git_paths), EXPECTED[1]]
        before_updates = client.update_calls
        with self.assertRaisesRegex(ContentWriteError, "DRIFT_BLOCKED"):
            execute_content_sync_one(
                client,
                client.inspect_course(299189),
                canonical_id="M02-L01",
                expected_steps=updated,
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
                baseline=baseline,
                source_sha="new-sha",
            )
        self.assertEqual(client.update_calls, before_updates)

    def test_public_target_lesson_blocks_initial_content_test(self) -> None:
        client = FakeClient()
        client.snapshot["sections"][0]["units"][0]["lesson"]["is_public"] = True
        with self.assertRaisesRegex(ContentWriteError, "непубличного target lesson"):
            execute_content_test_one(
                client,
                client.inspect_course(299189),
                expected_steps=EXPECTED,
                module_position=3,
                lesson_position=1,
                expected_title=TITLE,
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
                expected_title=TITLE,
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
