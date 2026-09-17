from __future__ import annotations

import re
from typing import Any, Iterable

from .fingerprints import html_fingerprint

# Transport-only canonicalization. These rules are intentionally narrower than a
# general HTML sanitizer: every rule below has been observed in Stepik write/read-back
# evidence for private course 299189. Deployment fingerprints remain untouched.
PLAIN_HORIZONTAL_RULE_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
BREAK_RE = re.compile(r"<br\s*/>", re.IGNORECASE)
TEXT_ALIGN_RE = re.compile(r'style="text-align:(left|right|center);?"', re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.IGNORECASE | re.DOTALL)
BLOCK_TAG_RE = re.compile(
    r"<(?:p|div|table|thead|tbody|tr|td|th|ul|ol|li|blockquote|pre|hr|h[1-6])\b",
    re.IGNORECASE,
)


class TransportEquivalenceError(RuntimeError):
    pass


def _split_multiline_inline_paragraph(match: re.Match[str]) -> str:
    body = match.group(1)
    if "\n" not in body or BREAK_RE.search(body) or BLOCK_TAG_RE.search(body):
        return match.group(0)
    lines = body.splitlines()
    if len(lines) < 2 or any(not line.strip() for line in lines):
        return match.group(0)
    return "\n".join(f"<p>{line.strip()}</p>" for line in lines)


def normalize_stepik_transport_html(html: str) -> str:
    """Normalize only proven representation-only transformations made by Stepik.

    This function exists solely for expected-vs-read-back comparison. It MUST NOT be
    used to calculate deployment event identities or historical applied fingerprints.

    Allowed transformations:
    - plain ``<hr>`` / ``<hr />`` removed by Stepik;
    - XHTML ``<br />`` represented as HTML ``<br>``;
    - exact ``text-align`` style receives a trailing semicolon;
    - newline-separated inline-only text inside one ``<p>`` is represented as
      separate paragraphs.

    Text, links, non-transport attributes, block order and learner task structure are
    deliberately preserved.
    """
    normalized = html or ""
    normalized = PARAGRAPH_RE.sub(_split_multiline_inline_paragraph, normalized)
    normalized = PLAIN_HORIZONTAL_RULE_RE.sub("", normalized)
    normalized = BREAK_RE.sub("<br>", normalized)
    normalized = TEXT_ALIGN_RE.sub(
        lambda match: f'style="text-align:{match.group(1).lower()};"',
        normalized,
    )
    return normalized


def transport_html_fingerprint(html: str) -> tuple[tuple[Any, ...], ...]:
    return html_fingerprint(normalize_stepik_transport_html(html))


def _step_source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("step_source")
    if not isinstance(source, dict):
        raise TransportEquivalenceError("В snapshot отсутствует step_source")
    return source


def step_transport_equivalent(existing: dict[str, Any], expected: Any) -> bool:
    """Compare one live Stepik step with compiled content modulo proven transport HTML rewrites."""
    source = _step_source(existing)
    block = source.get("block")
    if not isinstance(block, dict):
        return False
    return (
        source.get("position") == int(expected.position)
        and str(block.get("name") or "") == str(expected.block_name)
        and dict(block.get("source") or {}) == dict(expected.source)
        and transport_html_fingerprint(str(block.get("text") or ""))
        == transport_html_fingerprint(str(expected.text))
    )


def lesson_transport_equivalent(
    live_lesson: dict[str, Any],
    *,
    expected_title: str,
    expected_steps: Iterable[Any],
    language: str = "ru",
    is_public: bool = False,
) -> bool:
    """Compare a full lesson without weakening metadata or structural checks."""
    if str(live_lesson.get("title") or "") != expected_title:
        return False
    if live_lesson.get("language") != language:
        return False
    if live_lesson.get("is_public") is not is_public:
        return False

    expected_list = sorted(list(expected_steps), key=lambda step: int(step.position))
    live_list = sorted(
        list(live_lesson.get("steps", [])),
        key=lambda item: _step_source(item).get("position", 10**9),
    )
    if len(live_list) != len(expected_list):
        return False
    return all(
        step_transport_equivalent(existing, expected)
        for existing, expected in zip(live_list, expected_list, strict=True)
    )
