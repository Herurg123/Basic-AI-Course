from __future__ import annotations

import unittest

import requests

from scripts.stepik_uploader.api import RetryPolicy, StepikAPIError, StepikClient, StepikWriteAmbiguousError


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class BadJSONResponse(FakeResponse):
    def json(self):
        raise ValueError("bad json")


class FakeSession:
    def __init__(self):
        self.get_responses = []
        self.request_responses = []
        self.request_exception: Exception | None = None
        self.get_calls = 0
        self.request_calls = 0
        self.post_calls = 0
        self.last_request = None

    def post(self, *args, **kwargs):
        self.post_calls += 1
        return FakeResponse(200, {"access_token": "test-token"})

    def get(self, *args, **kwargs):
        self.get_calls += 1
        return self.get_responses.pop(0)

    def request(self, *args, **kwargs):
        self.request_calls += 1
        self.last_request = (args, kwargs)
        if self.request_exception is not None:
            raise self.request_exception
        return self.request_responses.pop(0)


class APITests(unittest.TestCase):
    def test_get_retries_transient_failure(self) -> None:
        session = FakeSession()
        session.get_responses = [
            FakeResponse(503),
            FakeResponse(200, {"courses": [{"id": 7}]}),
        ]
        client = StepikClient(
            "id",
            "credential",
            session=session,
            retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0),
            sleep=lambda _: None,
        )
        course = client.fetch_one("courses", 7)
        self.assertEqual(course["id"], 7)
        self.assertEqual(session.get_calls, 2)

    def test_post_is_never_retried_automatically(self) -> None:
        session = FakeSession()
        session.request_responses = [FakeResponse(503), FakeResponse(201, {"lessons": [{"id": 1}]})]
        client = StepikClient("id", "credential", session=session, sleep=lambda _: None)
        with self.assertRaises(StepikWriteAmbiguousError):
            client.create_lesson("x")
        self.assertEqual(session.request_calls, 1)

    def test_network_failure_after_write_request_is_ambiguous_and_not_retried(self) -> None:
        session = FakeSession()
        session.request_exception = requests.Timeout("timeout after send")
        client = StepikClient("id", "credential", session=session, sleep=lambda _: None)
        with self.assertRaises(StepikWriteAmbiguousError):
            client.create_lesson("x")
        self.assertEqual(session.request_calls, 1)

    def test_success_http_with_unreadable_json_is_ambiguous(self) -> None:
        session = FakeSession()
        session.request_responses = [BadJSONResponse(200)]
        client = StepikClient("id", "credential", session=session, sleep=lambda _: None)
        with self.assertRaises(StepikWriteAmbiguousError):
            client.create_lesson("x")
        self.assertEqual(session.request_calls, 1)

    def test_known_4xx_is_not_ambiguous(self) -> None:
        session = FakeSession()
        session.request_responses = [FakeResponse(400)]
        client = StepikClient("id", "credential", session=session, sleep=lambda _: None)
        with self.assertRaises(StepikAPIError) as ctx:
            client.create_lesson("x")
        self.assertNotIsInstance(ctx.exception, StepikWriteAmbiguousError)
        self.assertEqual(session.request_calls, 1)

    def test_update_step_source_uses_single_put(self) -> None:
        session = FakeSession()
        session.request_responses = [FakeResponse(200, {"step-sources": [{"id": 17}]})]
        client = StepikClient("id", "credential", session=session, sleep=lambda _: None)
        result = client.update_step_source(
            step_id=17,
            lesson_id=23,
            position=1,
            block={"name": "text", "text": "<p>x</p>", "source": {}},
        )
        self.assertEqual(result["step-sources"][0]["id"], 17)
        self.assertEqual(session.request_calls, 1)
        args, kwargs = session.last_request
        self.assertEqual(args[0], "PUT")
        self.assertTrue(args[1].endswith("/api/step-sources/17"))
        self.assertEqual(kwargs["json"]["stepSource"]["lesson"], 23)

    def test_error_does_not_echo_credentials(self) -> None:
        session = FakeSession()
        session.get_responses = [FakeResponse(403)]
        marker = "credential-marker-value"
        client = StepikClient(
            "visible-id",
            marker,
            session=session,
            retry_policy=RetryPolicy(attempts=1),
        )
        with self.assertRaises(StepikAPIError) as ctx:
            client.fetch_one("courses", 7)
        self.assertNotIn(marker, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
