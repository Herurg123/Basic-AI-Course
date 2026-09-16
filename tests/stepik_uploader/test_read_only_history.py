from __future__ import annotations

import unittest

from scripts.stepik_uploader.deployment_history import DeploymentHistoryError
from scripts.stepik_uploader.read_only_history import ReadOnlyGitHubHistoryStore


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class RecordingSession:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.methods: list[str] = []

    def request(self, method: str, url: str, **kwargs):
        self.methods.append(method)
        return FakeResponse(self.status_code)


class ReadOnlyHistoryTests(unittest.TestCase):
    def _store(self, session: RecordingSession) -> ReadOnlyGitHubHistoryStore:
        return ReadOnlyGitHubHistoryStore(
            repository="owner/repo",
            token="token",
            source_sha="a" * 40,
            session=session,
        )

    def test_existing_history_branch_is_read_only_get(self) -> None:
        session = RecordingSession(200)
        store = self._store(session)
        store.ensure_branch()
        self.assertEqual(session.methods, ["GET"])
        self.assertTrue(store._branch_ready)

    def test_missing_history_branch_fails_closed_without_create(self) -> None:
        session = RecordingSession(404)
        store = self._store(session)
        with self.assertRaises(DeploymentHistoryError):
            store.ensure_branch()
        self.assertEqual(session.methods, ["GET"])
        self.assertFalse(store._branch_ready)


if __name__ == "__main__":
    unittest.main()
