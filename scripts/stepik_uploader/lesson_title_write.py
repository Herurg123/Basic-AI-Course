from __future__ import annotations

from copy import deepcopy
from typing import Any

from .api import StepikAPIError, StepikWriteAmbiguousError
from .fingerprints import live_lesson_fingerprint


class LessonTitleWriteError(RuntimeError):
    pass


def execute_lesson_title_update(
    client: Any,
    lesson: dict[str, Any],
    *,
    expected_title: str,
    recorder: Any | None,
    operation_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Guarded lesson-title PUT inside the same lesson deployment event.

    The caller must prove before entering this helper that the current normalized
    lesson is either the confirmed baseline state or a history-proven intermediate
    state. This helper only performs the title mutation, WAL/read-back, and returns
    a normalized working lesson with the original normalized steps preserved.
    """
    lesson_id = lesson.get("id")
    if not isinstance(lesson_id, int):
        raise LessonTitleWriteError("Lesson title update требует integer lesson id")
    current_title = lesson.get("title")
    if not isinstance(current_title, str) or not current_title:
        raise LessonTitleWriteError("Lesson title update требует непустой current title")
    if not isinstance(expected_title, str) or not expected_title:
        raise LessonTitleWriteError("Lesson title update требует непустой expected title")
    if lesson.get("is_public") is not False or lesson.get("language") != "ru":
        raise LessonTitleWriteError("Lesson title update разрешён только для private ru lesson")
    if current_title == expected_title:
        return deepcopy(lesson), None

    op_id = operation_id or f"lesson-title-{lesson_id}"
    before_fp = live_lesson_fingerprint(lesson)
    expected_model = deepcopy(lesson)
    expected_model["title"] = expected_title
    expected_after_fp = live_lesson_fingerprint(expected_model)

    if recorder is not None:
        recorder.write_intent(
            operation_id=op_id,
            method="PUT",
            target=f"lessons/{lesson_id}",
            fingerprint_before=before_fp,
            expected_fingerprint_after=expected_after_fp,
        )
        recorder.write_dispatch_started(operation_id=op_id)

    try:
        client.update_lesson_title(lesson_id=lesson_id, title=expected_title)
    except StepikWriteAmbiguousError:
        if recorder is not None:
            recorder.write_result(
                operation_id=op_id,
                status="AMBIGUOUS",
                reason_code="lesson-title-put-ambiguous",
            )
        raise
    except StepikAPIError:
        if recorder is not None:
            recorder.write_result(
                operation_id=op_id,
                status="FAILED_KNOWN",
                reason_code="lesson-title-put-failed-known",
            )
        raise
    except Exception:
        if recorder is not None:
            recorder.write_result(
                operation_id=op_id,
                status="AMBIGUOUS",
                reason_code="lesson-title-put-unclassified-after-dispatch",
            )
        raise

    if recorder is not None:
        recorder.write_result(operation_id=op_id, status="COMPLETED")

    try:
        readback = client.fetch_one("lessons", lesson_id)
        if int(readback.get("id", -1)) != lesson_id:
            raise LessonTitleWriteError("Lesson title read-back вернул другой lesson id")
        if readback.get("title") != expected_title:
            raise LessonTitleWriteError("Lesson title read-back не подтвердил canonical title")
        if readback.get("is_public") is not False or readback.get("language") != "ru":
            raise LessonTitleWriteError("Lesson title read-back изменил private/ru metadata")
    except Exception:
        if recorder is not None:
            recorder.readback_failed(
                operation_id=op_id,
                reason_code="lesson-title-put-readback-mismatch",
            )
        raise

    observed_model = deepcopy(lesson)
    observed_model["title"] = str(readback["title"])
    observed_model["is_public"] = readback.get("is_public")
    observed_model["language"] = readback.get("language")
    observed_after_fp = live_lesson_fingerprint(observed_model)

    if recorder is not None:
        recorder.operation_readback(
            operation_id=op_id,
            expected_fingerprint_after=expected_after_fp,
            observed_live_fingerprint=observed_after_fp,
        )

    return observed_model, {
        "action": "UPDATE_LESSON_TITLE",
        "lesson_id": lesson_id,
        "old_title": current_title,
        "new_title": expected_title,
    }
