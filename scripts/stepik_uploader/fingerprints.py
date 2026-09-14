from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from typing import Any, Iterable


class FingerprintError(RuntimeError):
    pass


class _FingerprintParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[tuple[Any, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept = tuple(sorted((key, value or "") for key, value in attrs if key not in {"rel", "target"}))
        self.tokens.append(("start", tag, kept))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept = tuple(sorted((key, value or "") for key, value in attrs if key not in {"rel", "target"}))
        self.tokens.append(("startend", tag, kept))

    def handle_endtag(self, tag: str) -> None:
        self.tokens.append(("end", tag))

    def handle_data(self, data: str) -> None:
        normalized = re.sub(r"\s+", " ", data).strip()
        if normalized:
            self.tokens.append(("data", normalized))


def html_fingerprint(text: str) -> tuple[tuple[Any, ...], ...]:
    parser = _FingerprintParser()
    parser.feed(text or "")
    parser.close()
    return tuple(parser.tokens)


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def compiled_step_payload(step: Any) -> dict[str, Any]:
    return {
        "position": int(step.position),
        "block_name": str(step.block_name),
        "source": dict(step.source),
        "html_tokens": html_fingerprint(str(step.text)),
    }


def live_step_payload(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("step_source")
    if not isinstance(source, dict):
        raise FingerprintError("В snapshot отсутствует step_source")
    block = source.get("block")
    if not isinstance(block, dict):
        raise FingerprintError("В step_source отсутствует block")
    position = source.get("position")
    if not isinstance(position, int):
        raise FingerprintError(f"У step_source нет целочисленной position: {position!r}")
    return {
        "position": position,
        "block_name": str(block.get("name") or ""),
        "source": dict(block.get("source") or {}),
        "html_tokens": html_fingerprint(str(block.get("text") or "")),
    }


def compiled_lesson_payload(
    *,
    expected_title: str,
    expected_steps: Iterable[Any],
    language: str = "ru",
    is_public: bool = False,
) -> dict[str, Any]:
    steps = sorted((compiled_step_payload(step) for step in expected_steps), key=lambda item: item["position"])
    return {
        "title": expected_title,
        "language": language,
        "is_public": is_public,
        "steps": steps,
    }


def live_lesson_payload(lesson: dict[str, Any]) -> dict[str, Any]:
    steps = sorted((live_step_payload(item) for item in lesson.get("steps", [])), key=lambda item: item["position"])
    return {
        "title": str(lesson.get("title") or ""),
        "language": lesson.get("language"),
        "is_public": lesson.get("is_public"),
        "steps": steps,
    }


def compiled_lesson_fingerprint(
    *,
    expected_title: str,
    expected_steps: Iterable[Any],
    language: str = "ru",
    is_public: bool = False,
) -> str:
    return canonical_hash(
        compiled_lesson_payload(
            expected_title=expected_title,
            expected_steps=expected_steps,
            language=language,
            is_public=is_public,
        )
    )


def live_lesson_fingerprint(lesson: dict[str, Any]) -> str:
    return canonical_hash(live_lesson_payload(lesson))


def step_equivalent(existing: dict[str, Any], expected: Any) -> bool:
    return live_step_payload(existing) == compiled_step_payload(expected)
