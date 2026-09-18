from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PlatformProfileError(RuntimeError):
    pass


def load_platform_profile(path: Path, *, course_id: int = 299189) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlatformProfileError(f"Не найден Stepik platform profile: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PlatformProfileError(f"Stepik platform profile не является корректным JSON: {path}: {exc}") from exc

    if payload.get("schema_version") != "1.0":
        raise PlatformProfileError("Поддерживается только Stepik platform profile schema_version=1.0")
    if payload.get("status") != "confirmed-platform-conventions":
        raise PlatformProfileError("Stepik platform profile должен иметь status=confirmed-platform-conventions")
    if int(payload.get("course_id", -1)) != int(course_id):
        raise PlatformProfileError(
            f"Stepik platform profile относится к course_id={payload.get('course_id')}, ожидается {course_id}"
        )
    text_source = payload.get("text_block_source")
    if text_source != {}:
        raise PlatformProfileError("Подтверждённый text_block_source должен оставаться пустым object")
    free_answer = payload.get("free_answer_source")
    expected = {
        "is_attachments_enabled": False,
        "is_html_enabled": True,
        "manual_scoring": False,
    }
    if free_answer != expected:
        raise PlatformProfileError(
            f"free_answer_source изменился: ожидалось {expected!r}, найдено {free_answer!r}"
        )
    return payload


def free_answer_source(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("free_answer_source")
    if not isinstance(value, dict):
        raise PlatformProfileError("Stepik platform profile не содержит free_answer_source")
    return dict(value)
