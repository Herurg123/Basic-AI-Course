from __future__ import annotations

import json
import unittest
from urllib.error import URLError

from scripts.stepik_uploader.live_guard import (
    LiveSourceGuardError,
    fetch_remote_main_sha,
    validate_live_source,
)

SHA_A = "a" * 40
SHA_B = "b" * 40


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LiveGuardTests(unittest.TestCase):
    def test_matching_current_main_passes(self) -> None:
        result = validate_live_source(
            ref="refs/heads/main",
            run_sha=SHA_A,
            remote_main_sha=SHA_A,
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["remote_main_sha"], SHA_A)

    def test_feature_branch_is_blocked(self) -> None:
        with self.assertRaisesRegex(LiveSourceGuardError, "live-source-not-main"):
            validate_live_source(
                ref="refs/heads/production/example",
                run_sha=SHA_A,
                remote_main_sha=SHA_A,
            )

    def test_stale_run_sha_is_blocked(self) -> None:
        with self.assertRaisesRegex(LiveSourceGuardError, "live-source-stale-main"):
            validate_live_source(
                ref="refs/heads/main",
                run_sha=SHA_A,
                remote_main_sha=SHA_B,
            )

    def test_remote_main_api_failure_is_fail_closed(self) -> None:
        def failing_opener(*args, **kwargs):
            raise URLError("temporary failure")

        with self.assertRaisesRegex(LiveSourceGuardError, "remote-main-check-failed"):
            fetch_remote_main_sha(
                repository="Herurg123/Basic-AI-Course",
                token="test-token",
                opener=failing_opener,
            )

    def test_remote_main_sha_is_read_from_api_payload(self) -> None:
        def opener(*args, **kwargs):
            return _Response({"object": {"sha": SHA_A}})

        result = fetch_remote_main_sha(
            repository="Herurg123/Basic-AI-Course",
            token="test-token",
            opener=opener,
        )
        self.assertEqual(result, SHA_A)

    def test_missing_remote_sha_is_blocked(self) -> None:
        def opener(*args, **kwargs):
            return _Response({"object": {}})

        with self.assertRaisesRegex(LiveSourceGuardError, "object.sha"):
            fetch_remote_main_sha(
                repository="Herurg123/Basic-AI-Course",
                token="test-token",
                opener=opener,
            )


if __name__ == "__main__":
    unittest.main()
