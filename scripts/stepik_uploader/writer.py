from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from .content import CompiledStep

PLACEHOLDER_TEXT = "Урок сгенерирован роботом ;)"


class ContentWriteError(RuntimeError):
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


def _step_source(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("step_source")
    if not isinstance(source, dict):
        raise ContentWriteError("В snapshot отсутствует step_source")
    return source


def _equivalent(existing: dict[str, Any], expected: CompiledStep) -> bool:
    source = _step_source(existing)
    block = source.get("block", {})
    return (
        source.get("position") == expected.position
        and block.get("name") == expected.block_name
        and (block.get("source") or {}) == expected.source
        and html_fingerprint(str(block.get("text") or "")) == html_fingerprint(expected.text)
    )


def _placeholder(existing: dict[str, Any]) -> bool:
    source = _step_source(existing)
    block = source.get("block", {})
    text = str(block.get("text") or "").strip()
    plain = re.sub(r"</?p>", "", text).strip()
    return (
        source.get("position") == 1
        and block.get("name") == "text"
        and (block.get("source") or {}) == {}
        and plain == PLACEHOLDER_TEXT
    )


def _target_lesson(
    snapshot: dict[str, Any],
    *,
    module_position: int,
    lesson_position: int,
    expected_title: str,
) -> dict[str, Any]:
    course = snapshot.get("course", {})
    if course.get("is_public") is not False:
        raise ContentWriteError("content-test-one разрешён только для непубличного чернового курса")
    matching_sections = [s for s in snapshot.get("sections", []) if s.get("position") == module_position]
    if len(matching_sections) != 1:
        raise ContentWriteError(f"Не найден единственный section position={module_position}")
    matching_units = [u for u in matching_sections[0].get("units", []) if u.get("position") == lesson_position]
    if len(matching_units) != 1:
        raise ContentWriteError(
            f"Не найден единственный unit section={module_position} position={lesson_position}"
        )
    lesson = matching_units[0].get("lesson", {})
    if lesson.get("title") != expected_title:
        raise ContentWriteError(
            f"Target lesson title отличается: ожидается «{expected_title}», найдено «{lesson.get('title')}»"
        )
    return lesson


@dataclass
class WriteResult:
    lesson_id: int
    operations: list[dict[str, Any]] = field(default_factory=list)
    final_step_ids: list[int] = field(default_factory=list)
    verified: bool = False
    after_snapshot: dict[str, Any] | None = None


def classify_existing_steps(existing: list[dict[str, Any]], expected: list[CompiledStep]) -> tuple[str, int]:
    ordered = sorted(existing, key=lambda item: _step_source(item).get("position", 10**9))
    positions = [_step_source(item).get("position") for item in ordered]
    if positions != list(range(1, len(ordered) + 1)):
        raise ContentWriteError(f"Step positions target lesson неоднозначны: {positions}")
    if len(ordered) > len(expected):
        raise ContentWriteError(
            f"Target lesson содержит {len(ordered)} steps, ожидается не более {len(expected)}"
        )
    if len(ordered) == 1 and _placeholder(ordered[0]):
        return "skeleton-placeholder", 0
    matched = 0
    for index, item in enumerate(ordered):
        if not _equivalent(item, expected[index]):
            raise ContentWriteError(
                f"Target lesson step position={index + 1} не является ни подтверждённым compiled content, ни исходной заглушкой"
            )
        matched += 1
    return ("complete" if matched == len(expected) else "partial"), matched


def _assert_readback(readback: dict[str, Any], expected: CompiledStep) -> None:
    wrapped = {"step_source": readback}
    if not _equivalent(wrapped, expected):
        raise ContentWriteError(f"Read-back step position={expected.position} не совпал с compiled content")


def _created_id(payload: dict[str, Any]) -> int:
    for key in ("step-sources", "stepSources"):
        objects = payload.get(key)
        if isinstance(objects, list) and len(objects) == 1 and isinstance(objects[0], dict) and "id" in objects[0]:
            return int(objects[0]["id"])
    raise ContentWriteError("POST /api/step-sources завершился без однозначного созданного step ID")


def execute_content_test_one(
    client: Any,
    snapshot: dict[str, Any],
    *,
    expected_steps: list[CompiledStep],
    module_position: int,
    lesson_position: int,
    expected_title: str,
) -> WriteResult:
    lesson = _target_lesson(
        snapshot,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    lesson_id = int(lesson["id"])
    existing = list(lesson.get("steps", []))
    state, matched = classify_existing_steps(existing, expected_steps)
    result = WriteResult(lesson_id=lesson_id)

    ordered = sorted(existing, key=lambda item: _step_source(item).get("position", 10**9))
    if state == "complete":
        result.operations.append({"action": "NOOP_ALREADY_MATCHES", "steps": len(expected_steps)})
    elif state == "skeleton-placeholder":
        first_id = int(_step_source(ordered[0])["id"])
        client.update_step_source(
            step_id=first_id,
            lesson_id=lesson_id,
            position=1,
            block=expected_steps[0].block(),
        )
        _assert_readback(client.fetch_one("step-sources", first_id), expected_steps[0])
        result.operations.append({"action": "UPDATE_PLACEHOLDER", "step_id": first_id, "position": 1})
        matched = 1
    else:
        result.operations.append({"action": "RESUME_PARTIAL", "matching_prefix": matched})

    for expected in expected_steps[matched:]:
        payload = client.create_step_source(
            lesson_id=lesson_id,
            position=expected.position,
            block=expected.block(),
        )
        step_id = _created_id(payload)
        _assert_readback(client.fetch_one("step-sources", step_id), expected)
        result.operations.append({"action": "CREATE_STEP", "step_id": step_id, "position": expected.position})

    after = client.inspect_course(int(snapshot["course"]["id"]))
    after_lesson = _target_lesson(
        after,
        module_position=module_position,
        lesson_position=lesson_position,
        expected_title=expected_title,
    )
    state_after, matched_after = classify_existing_steps(list(after_lesson.get("steps", [])), expected_steps)
    if state_after != "complete" or matched_after != len(expected_steps):
        raise ContentWriteError("Финальный read-back target lesson не совпал с compiled content")
    result.final_step_ids = [int(_step_source(item)["id"]) for item in after_lesson.get("steps", [])]
    result.verified = True
    result.after_snapshot = after
    return result
