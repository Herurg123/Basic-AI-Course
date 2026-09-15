from __future__ import annotations

import unittest

from scripts.stepik_uploader.sync_state import (
    SyncStateError,
    asset_binding_for,
    empty_state,
    validate_state,
    with_asset_record,
)


class AssetStateTests(unittest.TestCase):
    def _record(self) -> dict:
        return {
            "source_path": "05_assets/M04/M04-L01/M04-L01-A01.txt",
            "source_sha256": "sha256:" + "a" * 64,
            "url": "https://stepik.org/media/attachments/lesson/2591724/M04-L01-A01.txt",
            "storage": "stepik-attachment",
            "stepik_attachment_id": 240001,
            "stepik_lesson_id": 2591724,
            "filename": "M04-L01-A01.txt",
            "size": 123,
            "materialized_at": "2026-09-15T11:00:00Z",
        }

    def test_schema_v2_upgrades_with_empty_assets(self) -> None:
        old = {
            "schema_version": 2,
            "course_id": 299189,
            "updated_at": None,
            "lessons": {},
            "pending": {"lessons": {}, "course_page": None},
        }
        state = validate_state(old, course_id=299189)
        self.assertEqual(state["schema_version"], 3)
        self.assertEqual(state["assets"], {})

    def test_verified_asset_record_roundtrip(self) -> None:
        source_path = "05_assets/M04/M04-L01/M04-L01-A01.txt"
        state = with_asset_record(
            empty_state(299189),
            source_path=source_path,
            record=self._record(),
        )
        self.assertEqual(asset_binding_for(state, source_path), self._record())
        self.assertEqual(state["updated_at"], "2026-09-15T11:00:00Z")

    def test_asset_record_rejects_non_https_url(self) -> None:
        record = self._record()
        record["url"] = "http://stepik.org/file.txt"
        with self.assertRaises(SyncStateError):
            with_asset_record(
                empty_state(299189),
                source_path=record["source_path"],
                record=record,
            )

    def test_asset_record_rejects_path_escape(self) -> None:
        record = self._record()
        record["source_path"] = "../secret.txt"
        with self.assertRaises(SyncStateError):
            with_asset_record(
                empty_state(299189),
                source_path="../secret.txt",
                record=record,
            )


if __name__ == "__main__":
    unittest.main()
