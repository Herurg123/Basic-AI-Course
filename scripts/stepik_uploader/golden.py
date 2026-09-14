from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GoldenProfileError(RuntimeError):
    pass


def load_golden_profile(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GoldenProfileError(f"Не найден golden profile: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GoldenProfileError(f"Golden profile не является корректным JSON: {path}: {exc}") from exc
    if payload.get("schema_version") != "1.0":
        raise GoldenProfileError("Поддерживается только golden profile schema_version=1.0")
    if payload.get("status") != "confirmed-read-only":
        raise GoldenProfileError("Golden profile должен иметь status=confirmed-read-only")
    return payload


def _live_lesson(snapshot: dict[str, Any], lesson_id: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    for section in snapshot.get("sections", []):
        for unit in section.get("units", []):
            lesson = unit.get("lesson", {})
            if lesson.get("id") == lesson_id:
                return section, unit, lesson
    return None


def validate_golden_profile(profile: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    course = snapshot.get("course", {})
    if course.get("id") != profile.get("course_id"):
        blockers.append(
            f"golden-profile: ожидается course_id={profile.get('course_id')}, прочитан course_id={course.get('id')}"
        )
        return blockers

    expected_free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source", {})
    for canonical_id, expected in profile.get("golden_lessons", {}).items():
        live = _live_lesson(snapshot, int(expected["stepik_lesson_id"]))
        if live is None:
            blockers.append(
                f"golden-profile:{canonical_id}: lesson_id={expected['stepik_lesson_id']} не найден в курсе"
            )
            continue
        section, unit, lesson = live
        if section.get("id") != expected.get("stepik_section_id"):
            blockers.append(f"golden-profile:{canonical_id}: изменился section_id")
        if unit.get("id") != expected.get("stepik_unit_id"):
            blockers.append(f"golden-profile:{canonical_id}: изменился unit_id")
        if section.get("position") != expected.get("section_position"):
            blockers.append(f"golden-profile:{canonical_id}: изменилась section position")
        if unit.get("position") != expected.get("unit_position"):
            blockers.append(f"golden-profile:{canonical_id}: изменилась unit position")

        steps = lesson.get("steps", [])
        sequence = [item.get("step_source", {}).get("block", {}).get("name") for item in steps]
        if sequence != expected.get("block_sequence"):
            blockers.append(
                f"golden-profile:{canonical_id}: block sequence изменилась: {sequence}"
            )
        if len(steps) != expected.get("step_count"):
            blockers.append(
                f"golden-profile:{canonical_id}: ожидалось {expected.get('step_count')} steps, найдено {len(steps)}"
            )

        for item in steps:
            source = item.get("step_source", {}).get("block", {}).get("source", {})
            position = item.get("step_source", {}).get("position")
            name = item.get("step_source", {}).get("block", {}).get("name")
            if name == "free-answer" and source != expected_free_answer_source:
                blockers.append(
                    f"golden-profile:{canonical_id}: free-answer source в position={position} изменился"
                )

    return blockers
