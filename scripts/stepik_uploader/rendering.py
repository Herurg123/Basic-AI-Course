from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import mistune

ASSET_LINK_RE = re.compile(r"\]\(([^)]*?(M\d{2}-L\d{2}-A\d{2})(?:-[^/)]+)?\.[A-Za-z0-9]+)\)")
ABSOLUTE_LINK_RE = re.compile(r'<a href="(https?://[^"]+)"(?![^>]*\\btarget=)')


class UnresolvedAssetError(RuntimeError):
    pass


def resolve_asset_links(markdown_text: str, asset_url_map: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        original_target = match.group(1)
        asset_id = match.group(2)
        record = asset_url_map.get(asset_id)
        if not isinstance(record, dict):
            raise UnresolvedAssetError(
                f"Asset {asset_id} требуется learner-facing тексту, но запись отсутствует в asset-url-map"
            )
        url = record.get("url")
        if not url:
            filename = PurePosixPath(original_target).name
            files = record.get("files", {})
            file_record = files.get(filename) if isinstance(files, dict) else None
            if isinstance(file_record, str):
                url = file_record
            elif isinstance(file_record, dict):
                url = file_record.get("url")
        if not url:
            raise UnresolvedAssetError(
                f"Asset {asset_id} ({PurePosixPath(original_target).name}) требуется learner-facing тексту, "
                "но точный URL отсутствует в asset-url-map"
            )
        url = str(url)
        return match.group(0).replace(original_target, url)

    return ASSET_LINK_RE.sub(replace, markdown_text)


def _open_absolute_links_in_new_tab(html: str) -> str:
    """Не даёт внешней навигации увести ученика из текущего шага Stepik.

    Все абсолютные HTTP(S)-ссылки открываются отдельно. Это относится и к ссылкам
    на другие Stepik-шаги: ученик сохраняет текущую точку прохождения и может
    закрыть справочную вкладку после использования.
    """
    return ABSOLUTE_LINK_RE.sub(
        r'<a href="\1" target="_blank" rel="noopener noreferrer"',
        html,
    )


def markdown_to_html(markdown_text: str) -> str:
    """Render Markdown that has already passed dependency/link resolution."""
    renderer = mistune.create_markdown(escape=False, plugins=["table", "strikethrough"])
    return _open_absolute_links_in_new_tab(renderer(markdown_text))


def render_markdown(markdown_text: str, *, asset_url_map: dict[str, Any] | None = None) -> str:
    """Legacy renderer: resolve Asset-ID links first, then convert Markdown to HTML."""
    resolved = resolve_asset_links(markdown_text, asset_url_map or {})
    return markdown_to_html(resolved)
