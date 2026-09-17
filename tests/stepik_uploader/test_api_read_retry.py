from __future__ import annotations

import unittest

import requests

from scripts.stepik_uploader.api import RetryPolicy, StepikAPIError, StepikClient


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, content: bytes = b""):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers: dict[str, str] = {}
        self.content = content

    def json(self):
        return self._payload


class SequenceSession:
    def __init__(self, get_results: list[object]):
        self.get_results = list(get_results)
        self.get_calls = 0
        self.request_calls = 0

    def post(self, *args, **kwargs):
        return FakeResponse(200, {"access_token": "test-token"})

    def get(self, *args, **kwargs):
        self.get_calls += 1
        result = self.get_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def request(self, *args, **kwargs):
        self.request_calls += 1
        raise AssertionError("write request не должен вызываться read-retry тестами")


class ReadRetryTests(unittest.TestCase):
    def _client(self, session: SequenceSession, *, attempts: int = 3) -> StepikClient:
        return StepikClient(
            "id",
            "credential",
            session=session,
            retry_policy=RetryPolicy(attempts=attempts, base_delay_seconds=0),
            sleep=lambda _: None,
        )

    def test_json_get_retries_read_timeout_then_succeeds(self) -> None:
        session = SequenceSession([
            requests.ReadTimeout("transient read timeout"),
            FakeResponse(200, {"courses": [{"id": 7}]}),
        ])
        course = self._client(session).fetch_one("courses", 7)
        self.assertEqual(course["id"], 7)
        self.assertEqual(session.get_calls, 2)
        self.assertEqual(session.request_calls, 0)

    def test_json_get_retries_connection_error_then_succeeds(self) -> None:
        session = SequenceSession([
            requests.ConnectionError("transient connection reset"),
            FakeResponse(200, {"courses": [{"id": 7}]}),
        ])
        course = self._client(session).fetch_one("courses", 7)
        self.assertEqual(course["id"], 7)
        self.assertEqual(session.get_calls, 2)

    def test_json_get_stops_after_bounded_network_retries(self) -> None:
        session = SequenceSession([
            requests.ReadTimeout("one"),
            requests.ReadTimeout("two"),
            requests.ReadTimeout("three"),
        ])
        with self.assertRaisesRegex(StepikAPIError, "after 3 attempts"):
            self._client(session, attempts=3).fetch_one("courses", 7)
        self.assertEqual(session.get_calls, 3)
        self.assertEqual(session.request_calls, 0)

    def test_attachment_get_retries_timeout_then_succeeds(self) -> None:
        session = SequenceSession([
            requests.ReadTimeout("transient attachment timeout"),
            FakeResponse(200, content=b"safe"),
        ])
        content = self._client(session).download_attachment("/media/attachments/lesson/1/safe.txt")
        self.assertEqual(content, b"safe")
        self.assertEqual(session.get_calls, 2)
        self.assertEqual(session.request_calls, 0)


if __name__ == "__main__":
    unittest.main()
