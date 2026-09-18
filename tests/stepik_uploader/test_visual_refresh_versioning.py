from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from scripts.stepik_uploader.attachment_materialization import file_sha256
from scripts.stepik_uploader.visual_materialization import (
    VisualMaterializationError,
    prepare_visual_file,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class VisualRefreshVersioningTests(unittest.TestCase):
    def test_svg_version_suffix_preserves_bytes_but_changes_filename_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
                '<rect width="100" height="50" fill="#ddd"/></svg>',
                encoding="utf-8",
            )
            source_sha = file_sha256(source)
            plain, plain_sha, plain_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/M05/M05-L01/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                work_dir=root / "plain",
            )
            versioned, versioned_sha, versioned_fp = prepare_visual_file(
                source_file=source,
                source_path="05_assets/M05/M05-L01/asset.svg",
                expected_source_sha256=source_sha,
                mode="rasterize-png-stepik-image",
                work_dir=root / "versioned",
                filename_suffix="abc123def456",
            )
            self.assertEqual(plain_sha, versioned_sha)
            self.assertEqual(plain.read_bytes(), versioned.read_bytes())
            self.assertEqual(versioned.name, "asset-abc123def456.png")
            self.assertNotEqual(plain_fp, versioned_fp)

    def test_png_version_suffix_copies_exact_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.png"
            source.write_bytes(PNG_1X1)
            source_sha = file_sha256(source)
            versioned, materialized_sha, _ = prepare_visual_file(
                source_file=source,
                source_path="05_assets/X/asset.png",
                expected_source_sha256=source_sha,
                mode="stepik-image-upload",
                work_dir=root / "versioned",
                filename_suffix="deadbeefcafe",
            )
            self.assertEqual(versioned.name, "asset-deadbeefcafe.png")
            self.assertEqual(versioned.read_bytes(), PNG_1X1)
            self.assertEqual(materialized_sha, source_sha)

    def test_invalid_version_suffix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.png"
            source.write_bytes(PNG_1X1)
            with self.assertRaises(VisualMaterializationError):
                prepare_visual_file(
                    source_file=source,
                    source_path="05_assets/X/asset.png",
                    expected_source_sha256=file_sha256(source),
                    mode="stepik-image-upload",
                    work_dir=root / "versioned",
                    filename_suffix="Bad Suffix!",
                )


if __name__ == "__main__":
    unittest.main()
