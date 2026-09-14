from __future__ import annotations

import hashlib
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


def _manifest_lesson(manifest: dict[str, Any], canonical_id: str) -> dict[str, Any] | None:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == canonical_id:
                return lesson
    return None


def _text_sha256(item: dict[str, Any]) -> str:
    text = item.get("step_source", {}).get("block", {}).get("text") or ""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def validate_golden_profile(
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    *,
    allow_course_publication_change: bool = False,
) -> list[str]:
    """Проверяет неизменность golden lessons.

    По умолчанию курс обязан совпадать с исходным golden course_state целиком. Для
    exploitation-sync после публикации можно разрешить только изменение
    `course.is_public`: это ожидаемый жизненный цикл курса и не ослабляет проверку
    learner-visible HTML, step types, lesson visibility, IDs и позиций golden lessons.
    """
    blockers: list[str] = []
    course = snapshot.get("course", {})
    if course.get("id") != profile.get("course_id"):
        blockers.append(
            f"golden-profile: ожидается course_id={profile.get('course_id')}, прочитан course_id={course.get('id')}"
        )
        return blockers

    expected_course_state = profile.get("course_state", {})
    for field in ("language", "is_public"):
        if field == "is_public" and allow_course_publication_change:
            continue
        if field in expected_course_state and course.get(field) != expected_course_state.get(field):
            blockers.append(
                f"golden-profile: course.{field} изменился: ожидалось {expected_course_state.get(field)!r}, "
                f"прочитано {course.get(field)!r}"
            )

    expected_free_answer_source = profile.get("observed_conventions", {}).get("free_answer_source", {})
    for canonical_id, expected in profile.get("golden_lessons", {}).items():
        if manifest is not None:
            canonical = _manifest_lesson(manifest, canonical_id)
            if canonical is None:
                blockers.append(f"golden-profile:{canonical_id}: lesson отсутствует в derived manifest")
            elif len(canonical.get("steps", [])) != expected.get("plan_rows"):
                blockers.append(
                    f"golden-profile:{canonical_id}: Stepik-plan rows изменились: ожидалось {expected.get('plan_rows')}, "
                    f"получено {len(canonical.get('steps', []))}"
                )

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
        for field in ("language", "is_public"):
            if field in expected and lesson.get(field) != expected.get(field):
                blockers.append(
                    f"golden-profile:{canonical_id}: lesson.{field} изменился: ожидалось {expected.get(field)!r}, "
                    f"прочитано {lesson.get(field)!r}"
                )

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

        expected_hashes = expected.get("step_text_sha256", [])
        actual_hashes = [_text_sha256(item) for item in steps]
        if expected_hashes and actual_hashes != expected_hashes:
            blockers.append(f"golden-profile:{canonical_id}: learner-visible HTML golden lesson изменился")

        for item in steps:
            source = item.get("step_source", {}).get("block", {}).get("source", {})
            position = item.get("step_source", {}).get("position")
            name = item.get("step_source", {}).get("block", {}).get("name")
            if name == "free-answer" and source != expected_free_answer_source:
                blockers.append(
                    f"golden-profile:{canonical_id}: free-answer source в position={position} изменился"
                )

    return blockers
