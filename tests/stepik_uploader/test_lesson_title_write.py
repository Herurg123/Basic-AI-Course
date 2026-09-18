from __future__ import annotations

import copy
import unittest

from scripts.stepik_uploader.lesson_title_write import (
    LessonTitleWriteError,
    execute_lesson_title_update,
)


def lesson(title: str = "Old title") -> dict:
    return {
        "id": 42,
        "title": title,
        "is_public": False,
        "language": "ru",
        "steps": [
            {
                "step_source": {
                    "id": 101,
                    "position": 1,
                    "block": {"name": "text", "text": "<p>same</p>", "source": {}},
                }
            }
        ],
    }


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def write_intent(self, **kwargs) -> None:
        self.calls.append(("intent", kwargs))

    def write_dispatch_started(self, **kwargs) -> None:
        self.calls.append(("dispatch", kwargs))

    def write_result(self, **kwargs) -> None:
        self.calls.append(("result", kwargs))

    def operation_readback(self, **kwargs) -> None:
        self.calls.append(("readback", kwargs))

    def readback_failed(self, **kwargs) -> None:
        self.calls.append(("readback_failed", kwargs))


class Client:
    def __init__(self, current: dict) -> None:
        self.current = copy.deepcopy(current)
        self.writes = 0
        self.force_bad_readback = False

    def update_lesson_title(self, *, lesson_id: int, title: str) -> dict:
        self.writes += 1
        if lesson_id != self.current["id"]:
            raise AssertionError(lesson_id)
        self.current["title"] = title
        return {"lessons": [{"id": lesson_id, "title": title}]}

    def fetch_one(self, resource: str, object_id: int) -> dict:
        if resource != "lessons" or object_id != self.current["id"]:
            raise AssertionError((resource, object_id))
        result = {
            "id": self.current["id"],
            "title": self.current["title"],
            "is_public": self.current["is_public"],
            "language": self.current["language"],
        }
        if self.force_bad_readback:
            result["title"] = "unexpected"
        return result


class LessonTitleWriteTests(unittest.TestCase):
    def test_guarded_title_put_has_wal_and_readback(self) -> None:
        current = lesson()
        client = Client(current)
        recorder = Recorder()
        updated, operation = execute_lesson_title_update(
            client,
            current,
            expected_title="New title",
            recorder=recorder,
        )
        self.assertEqual(client.writes, 1)
        self.assertEqual(updated["title"], "New title")
        self.assertEqual(operation["action"], "UPDATE_LESSON_TITLE")
        self.assertEqual([name for name, _ in recorder.calls], ["intent", "dispatch", "result", "readback"])

    def test_already_current_title_is_noop(self) -> None:
        current = lesson("New title")
        client = Client(current)
        recorder = Recorder()
        updated, operation = execute_lesson_title_update(
            client,
            current,
            expected_title="New title",
            recorder=recorder,
        )
        self.assertEqual(client.writes, 0)
        self.assertIsNone(operation)
        self.assertEqual(updated["title"], "New title")
        self.assertEqual(recorder.calls, [])

    def test_readback_mismatch_is_not_silently_accepted(self) -> None:
        current = lesson()
        client = Client(current)
        client.force_bad_readback = True
        recorder = Recorder()
        with self.assertRaises(LessonTitleWriteError):
            execute_lesson_title_update(
                client,
                current,
                expected_title="New title",
                recorder=recorder,
            )
        self.assertEqual(client.writes, 1)
        self.assertEqual(recorder.calls[-1][0], "readback_failed")

    def test_public_or_non_ru_lesson_is_blocked_before_write(self) -> None:
        for mutation in ({"is_public": True}, {"language": "en"}):
            with self.subTest(mutation=mutation):
                current = lesson()
                current.update(mutation)
                client = Client(current)
                with self.assertRaises(LessonTitleWriteError):
                    execute_lesson_title_update(
                        client,
                        current,
                        expected_title="New title",
                        recorder=Recorder(),
                    )
                self.assertEqual(client.writes, 0)


if __name__ == "__main__":
    unittest.main()
