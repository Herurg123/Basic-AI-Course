from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.api import StepikWriteAmbiguousError
from scripts.stepik_uploader.attachment_materialization import (
    AttachmentMaterializationError,
    file_sha256,
    materialize_attachment,
    verify_attachment_capability,
)
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    EventIdentity,
    MemoryHistoryStore,
    stable_event_id,
)
from scripts.stepik_uploader.history_runtime import validate_event_records

SOURCE_SHA = "1" * 40


class FakeAttachmentClient:
    api_host = "https://stepik.org"

    def __init__(self, content: bytes, *, existing: bool = False, ambiguous: bool = False) -> None:
        self.content = content
        self.ambiguous = ambiguous
        self.create_calls = 0
        self.record = {
            "id": 240001,
            "lesson": 2591724,
            "course": None,
            "name": "M04-L01-A01.txt",
            "size": len(content),
            "file": "/media/attachments/lesson/2591724/M04-L01-A01.txt",
        }
        self.attachments = [dict(self.record)] if existing else []

    def attachment_capability(self):
        return {
            "allow": "GET, POST, HEAD, OPTIONS",
            "metadata": {
                "parses": ["application/json", "multipart/form-data"],
                "actions": {
                    "POST": {
                        "file": {"required": True, "read_only": False, "type": "file upload"},
                        "lesson": {"required": False, "read_only": False, "type": "field"},
                    }
                },
            },
        }

    def list_attachments(self, *, lesson_id: int):
        self.assert_lesson(lesson_id)
        return [dict(item) for item in self.attachments]

    def download_attachment(self, _url: str):
        return self.content

    def create_attachment(self, *, lesson_id: int, file_path: Path):
        self.assert_lesson(lesson_id)
        self.create_calls += 1
        if self.ambiguous:
            raise StepikWriteAmbiguousError("ambiguous")
        self.attachments = [dict(self.record)]
        return dict(self.record)

    @staticmethod
    def assert_lesson(lesson_id: int) -> None:
        if int(lesson_id) != 2591724:
            raise AssertionError(lesson_id)


def recorder_for(source_sha256: str) -> tuple[MemoryHistoryStore, DeploymentRecorder]:
    object_id = "asset:05_assets/M04/M04-L01/M04-L01-A01.txt"
    event_id = stable_event_id(
        course_id=299189,
        object_id=object_id,
        kind="asset",
        source_sha=SOURCE_SHA,
        desired_fingerprint=source_sha256,
        baseline_fingerprint=None,
        pending_first_sha=None,
    )
    identity = EventIdentity(
        event_id=event_id,
        course_id=299189,
        object_id=object_id,
        kind="asset",
        source_sha=SOURCE_SHA,
        workflow_run_id="test",
        workflow_run_attempt="1",
        workflow_run_url=None,
        desired_fingerprint=source_sha256,
        baseline_fingerprint_before=None,
        pending_first_sha=None,
    )
    store = MemoryHistoryStore()
    return store, DeploymentRecorder(store, identity)


class AttachmentMaterializationTests(unittest.TestCase):
    def test_capability_preflight_fails_closed_without_post(self) -> None:
        client = FakeAttachmentClient(b"x")
        capability = client.attachment_capability()
        capability["allow"] = "GET, HEAD, OPTIONS"
        client.attachment_capability = lambda: capability
        with self.assertRaises(AttachmentMaterializationError):
            verify_attachment_capability(client)

    def test_existing_exact_attachment_is_noop_confirmed(self) -> None:
        content = b"safe training text\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "M04-L01-A01.txt"
            source.write_bytes(content)
            expected = file_sha256(source)
            store, recorder = recorder_for(expected)
            client = FakeAttachmentClient(content, existing=True)
            record, status = materialize_attachment(
                client,
                recorder=recorder,
                source_file=source,
                source_path="05_assets/M04/M04-L01/M04-L01-A01.txt",
                expected_source_sha256=expected,
                stepik_lesson_id=2591724,
            )
        self.assertEqual(status, "NOOP_CONFIRMED")
        self.assertEqual(client.create_calls, 0)
        self.assertEqual(record["source_sha256"], expected)
        records = recorder.records(refresh=True)
        validate_event_records(records, expected_event_id=recorder.identity.event_id)
        self.assertFalse(any(item.get("phase") == "WRITE_DISPATCH_STARTED" for item in records))

    def test_new_attachment_uses_one_post_and_verified_download_readback(self) -> None:
        content = b"safe training text\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "M04-L01-A01.txt"
            source.write_bytes(content)
            expected = file_sha256(source)
            store, recorder = recorder_for(expected)
            client = FakeAttachmentClient(content)
            record, status = materialize_attachment(
                client,
                recorder=recorder,
                source_file=source,
                source_path="05_assets/M04/M04-L01/M04-L01-A01.txt",
                expected_source_sha256=expected,
                stepik_lesson_id=2591724,
            )
        self.assertEqual(status, "APPLIED")
        self.assertEqual(client.create_calls, 1)
        self.assertEqual(record["stepik_attachment_id"], 240001)
        records = recorder.records(refresh=True)
        validate_event_records(records, expected_event_id=recorder.identity.event_id)
        self.assertEqual(sum(item.get("phase") == "WRITE_DISPATCH_STARTED" for item in records), 1)
        self.assertTrue(any(item.get("phase") == "OP_READBACK_CONFIRMED" for item in records))

    def test_ambiguous_post_is_not_retried_or_marked_readback_confirmed(self) -> None:
        content = b"safe training text\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "M04-L01-A01.txt"
            source.write_bytes(content)
            expected = file_sha256(source)
            _store, recorder = recorder_for(expected)
            client = FakeAttachmentClient(content, ambiguous=True)
            with self.assertRaises(StepikWriteAmbiguousError):
                materialize_attachment(
                    client,
                    recorder=recorder,
                    source_file=source,
                    source_path="05_assets/M04/M04-L01/M04-L01-A01.txt",
                    expected_source_sha256=expected,
                    stepik_lesson_id=2591724,
                )
        self.assertEqual(client.create_calls, 1)
        records = recorder.records(refresh=True)
        self.assertTrue(any(item.get("phase") == "WRITE_AMBIGUOUS" for item in records))
        self.assertFalse(any(item.get("phase") == "OP_READBACK_CONFIRMED" for item in records))
        self.assertFalse(any(item.get("phase") == "FINAL_READBACK_CONFIRMED" for item in records))


if __name__ == "__main__":
    unittest.main()
