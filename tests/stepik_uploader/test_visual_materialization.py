from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.deployment_history import DeploymentRecorder, MemoryHistoryStore, event_identity_from_environment
from scripts.stepik_uploader.visual_materialization import (
    materialize_visual,
    prepare_visual_file,
    verify_visual_binding,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeVisualClient:
    api_host = "https://stepik.org"

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.bytes_by_url: dict[str, bytes] = {}
        self.next_id = 9001

    def attachment_capability(self):
        return {
            "allow": "GET, POST, OPTIONS",
            "metadata": {
                "parses": ["multipart/form-data"],
                "actions": {
                    "POST": {
                        "file": {"required": True, "read_only": False, "type": "file upload"},
                        "lesson": {"required": False, "read_only": False, "type": "integer"},
                    }
                },
            },
        }

    def list_attachments(self, *, lesson_id: int):
        return [dict(item) for item in self.items if int(item["lesson"]) == int(lesson_id)]

    def create_attachment(self, *, lesson_id: int, file_path: Path):
        content = Path(file_path).read_bytes()
        file_value = f"/media/attachments/lesson/{lesson_id}/{Path(file_path).name}"
        item = {
            "id": self.next_id,
            "lesson": int(lesson_id),
            "name": Path(file_path).name,
            "size": len(content),
            "file": file_value,
        }
        self.next_id += 1
        self.items.append(item)
        self.bytes_by_url["https://stepik.org" + file_value] = content
        return dict(item)

    def download_attachment(self, url: str):
        return self.bytes_by_url[url]


def recorder_for(*, desired_fingerprint: str, object_id: str) -> DeploymentRecorder:
    identity = event_identity_from_environment(
        course_id=299189,
        object_id=object_id,
        kind="asset",
        source_sha="a" * 40,
        desired_fingerprint=desired_fingerprint,
        baseline_fingerprint=None,
        pending_first_sha="b" * 40,
    )
    return DeploymentRecorder(MemoryHistoryStore(), identity)


class VisualMaterializationTests(unittest.TestCase):
    def test_rasterization_is_repeatable_and_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="120" height="80" fill="#fff"/><circle cx="60" cy="40" r="20" fill="#000"/></svg>',
                encoding="utf-8",
            )
            from scripts.stepik_uploader.attachment_materialization import file_sha256

            source_sha = file_sha256(source)
            first, first_sha, first_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/X/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                work_dir=root / "one",
            )
            second, second_sha, second_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/X/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                work_dir=root / "two",
            )
            self.assertEqual(first.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(first_sha, second_sha)
            self.assertEqual(first_fp, second_fp)

    def test_direct_png_materialization_and_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.png"
            source.write_bytes(PNG_1X1)
            from scripts.stepik_uploader.attachment_materialization import file_sha256

            source_sha = file_sha256(source)
            _, _, materialization_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/X/asset.png",
                expected_source_sha256=source_sha,
                mode="stepik-image-upload",
                work_dir=root / "prepared",
            )
            client = FakeVisualClient()
            record, status = materialize_visual(
                client,
                recorder=recorder_for(desired_fingerprint=materialization_fp, object_id="asset:png"),
                source_file=source,
                source_path="05_assets/X/asset.png",
                expected_source_sha256=source_sha,
                mode="stepik-image-upload",
                stepik_lesson_id=123,
                work_dir=root / "materialized",
            )
            self.assertEqual(status, "APPLIED")
            self.assertEqual(record["source_sha256"], source_sha)
            self.assertEqual(record["materialized_sha256"], source_sha)
            binding = verify_visual_binding(
                client,
                record,
                source_path="05_assets/X/asset.png",
                expected_source_sha256=source_sha,
                expected_mode="stepik-image-upload",
                stepik_lesson_id=123,
            )
            self.assertEqual(binding.source_sha256, source_sha)
            self.assertTrue(binding.url.startswith("https://stepik.org/"))

    def test_svg_record_keeps_source_and_materialized_hashes_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><rect width="100" height="50" fill="#ddd"/></svg>',
                encoding="utf-8",
            )
            from scripts.stepik_uploader.attachment_materialization import file_sha256

            source_sha = file_sha256(source)
            _, materialized_sha, materialization_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/X/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                work_dir=root / "prepared",
            )
            client = FakeVisualClient()
            record, _ = materialize_visual(
                client,
                recorder=recorder_for(desired_fingerprint=materialization_fp, object_id="asset:svg"),
                source_file=source,
                source_path="05_assets/X/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                stepik_lesson_id=456,
                work_dir=root / "materialized",
            )
            self.assertEqual(record["source_sha256"], source_sha)
            self.assertEqual(record["materialized_sha256"], materialized_sha)
            self.assertNotEqual(record["source_sha256"], record["materialized_sha256"])
            verify_visual_binding(
                client,
                record,
                source_path="05_assets/X/asset.svg",
                expected_source_sha256=source_sha,
                expected_mode="rasterize-png-stepik-image",
                stepik_lesson_id=456,
            )


if __name__ == "__main__":
    unittest.main()
