from __future__ import annotations

import unittest

from scripts.stepik_uploader.rendering import UnresolvedAssetError, render_markdown


class RenderingTests(unittest.TestCase):
    def test_external_link_survives_and_asset_link_is_rewritten(self) -> None:
        source = "[Алиса](https://alice.yandex.ru/) и [карточка](../../../05_assets/M00/M00-L01/M00-L01-A01.md)"
        html = render_markdown(
            source,
            asset_url_map={"M00-L01-A01": {"url": "https://example.org/assets/a01"}},
        )
        self.assertIn('href="https://alice.yandex.ru/" target="_blank" rel="noopener noreferrer"', html)
        self.assertIn('href="https://example.org/assets/a01" target="_blank" rel="noopener noreferrer"', html)

    def test_stepik_navigation_link_opens_in_new_tab(self) -> None:
        html = render_markdown(
            "[памятка](https://stepik.org/lesson/2591710/step/2)",
            asset_url_map={},
        )
        self.assertIn(
            'href="https://stepik.org/lesson/2591710/step/2" target="_blank" rel="noopener noreferrer"',
            html,
        )

    def test_same_asset_id_can_resolve_distinct_physical_files(self) -> None:
        source = "[часть 1](../../../05_assets/M05/M05-L02/M05-L02-A01-part1.md) [часть 2](../../../05_assets/M05/M05-L02/M05-L02-A01-part2.md)"
        html = render_markdown(
            source,
            asset_url_map={
                "M05-L02-A01": {
                    "files": {
                        "M05-L02-A01-part1.md": {"url": "https://example.org/p1"},
                        "M05-L02-A01-part2.md": {"url": "https://example.org/p2"},
                    }
                }
            },
        )
        self.assertIn('href="https://example.org/p1"', html)
        self.assertIn('href="https://example.org/p2"', html)

    def test_unresolved_asset_blocks_render(self) -> None:
        source = "[карточка](../../../05_assets/M00/M00-L01/M00-L01-A01.md)"
        with self.assertRaisesRegex(UnresolvedAssetError, "M00-L01-A01"):
            render_markdown(source, asset_url_map={})


if __name__ == "__main__":
    unittest.main()
