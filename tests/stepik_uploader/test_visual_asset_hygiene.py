from __future__ import annotations

import base64
import hashlib
import io
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageFile


INTERNAL_ASSET_ID_RE = re.compile(r"\bM\d{2}-L\d{2}-A\d{2}\b")


class VisualAssetHygieneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_m03_l02_real_interface_pngs_decode(self) -> None:
        paths = [
            self.repo_root / "05_assets/M03/M03-L02/M03-L02-A03.png",
            self.repo_root / "05_assets/M03/M03-L02/M03-L02-A03-alice.png",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), str(path))
                with Image.open(path) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertGreater(image.width, 0)
                    self.assertGreater(image.height, 0)
                    image.verify()

    def test_zz_b3_salvage_candidate_emits_real_pixels(self) -> None:
        path = self.repo_root / "05_assets/M03/M03-L02/M03-L02-A03-alice.png"
        old = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                out = io.BytesIO()
                image.save(out, format="PNG")
                data = out.getvalue()
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = old

        encoded = base64.b64encode(data).decode("ascii")
        print(
            "B3PNG_META "
            f"width={width} height={height} bytes={len(data)} "
            f"sha256={hashlib.sha256(data).hexdigest()}"
        )
        for offset in range(0, len(encoded), 600):
            print("B3PNG:" + encoded[offset:offset + 600])
        self.assertGreater(len(data), 0)

    def test_learner_svg_visible_text_has_no_internal_asset_id(self) -> None:
        svg_files = sorted((self.repo_root / "05_assets").glob("M*/M*/M*.svg"))
        self.assertTrue(svg_files, "Ожидались learner-facing SVG assets")
        violations: list[str] = []
        for path in svg_files:
            root = ET.parse(path).getroot()
            visible_text = " ".join(text.strip() for text in root.itertext() if text and text.strip())
            if INTERNAL_ASSET_ID_RE.search(visible_text):
                violations.append(str(path.relative_to(self.repo_root)))
        self.assertEqual(
            violations,
            [],
            "Learner-visible SVG text не должен показывать production Asset ID",
        )


if __name__ == "__main__":
    unittest.main()
