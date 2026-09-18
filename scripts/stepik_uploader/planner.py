from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

GOLDEN_IDS = ("M00-L01", "M00-L02")


@dataclass
class PlanResult:
    operations: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notices: list[dict[str, Any]] = field(default_factory=list)
    golden: dict[str, Any] = field(default_factory=dict)

    @property
    def write_count(self) -> int:
        return sum(1 for op in self.operations if op.get("action") in {"CREATE", "UPDATE", "DELETE"})


def _canonical_lessons(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (module, lesson)
        for module in manifest.get("modules", [])
        for lesson in module.get("lessons", [])
    ]


def _flat_live_lessons(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in snapshot.get("sections", []):
        for unit in section.get("units", []):
            lesson = unit.get("lesson", {})
            result.append(
                {
                    "section_id": section.get("id"),
                    "section_title": section.get("title"),
                    "section_position": section.get("position"),
                    "unit_id": unit.get("id"),
                    "unit_position": unit.get("position"),
                    "lesson_id": lesson.get("id"),
                    "lesson_title": lesson.get("title"),
                    "steps": lesson.get("steps", []),
                }
            )
    return result


def _accepted_live_titles(lesson: dict[str, Any]) -> set[str]:
    """Допустимые точные заголовки: канон и Stepik-формат со стабильным canonical ID."""
    canonical_id = str(lesson["canonical_id"])
    title = str(lesson["title"])
    return {title, f"{canonical_id} — {title}"}


def _title_matches(lesson: dict[str, Any], live_title: Any) -> bool:
    return isinstance(live_title, str) and live_title in _accepted_live_titles(lesson)


def _has_stable_id_prefix(lesson: dict[str, Any], live_title: Any) -> bool:
    if not isinstance(live_title, str):
        return False
    canonical_id = str(lesson["canonical_id"])
    return live_title.startswith(f"{canonical_id} — ")


def _same_id_prefix_but_title_drifted(lesson: dict[str, Any], live_title: Any) -> bool:
    return _has_stable_id_prefix(lesson, live_title) and not _title_matches(lesson, live_title)


def _matching_live_lessons(lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in live if _title_matches(lesson, item.get("lesson_title"))]


def _drifted_id_candidates(lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in live
        if _same_id_prefix_but_title_drifted(lesson, item.get("lesson_title"))
    ]


def _golden_identity_candidates(
    lesson: dict[str, Any],
    live: list[dict[str, Any]],
    *,
    golden_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Golden mapping не должен зависеть от текущего canonical title.

    Если доступен подтверждённый golden profile, immutable Stepik lesson_id является
    первичным identity key. Title/позиции/структура/HTML затем независимо проверяются
    validate_golden_profile(), поэтому profile-based identity не ослабляет integrity
    guard и не позволяет угадать другой lesson по похожему заголовку.

    Legacy title/prefix fallback сохраняется только для вызовов, где profile намеренно
    не передан (например, отдельные offline/unit сценарии).
    """
    canonical_id = str(lesson["canonical_id"])
    if isinstance(golden_profile, dict):
        expected = golden_profile.get("golden_lessons", {}).get(canonical_id)
        if isinstance(expected, dict):
            expected_lesson_id = expected.get("stepik_lesson_id")
            if isinstance(expected_lesson_id, int):
                return [item for item in live if item.get("lesson_id") == expected_lesson_id]

    return [
        item
        for item in live
        if _title_matches(lesson, item.get("lesson_title"))
        or _has_stable_id_prefix(lesson, item.get("lesson_title"))
    ]


def _exact_position(module: dict[str, Any], lesson: dict[str, Any], live: dict[str, Any]) -> bool:
    return (
        live.get("section_position") == module["position"]
        and live.get("unit_position") == lesson["position"]
    )


def _golden_canonical_notices(
    manifest: dict[str, Any],
    golden: dict[str, Any],
) -> list[dict[str, Any]]:
    canonical = {lesson["canonical_id"]: (module, lesson) for module, lesson in _canonical_lessons(manifest)}
    notices: list[dict[str, Any]] = []
    for canonical_id in GOLDEN_IDS:
        if canonical_id not in golden or canonical_id not in canonical:
            continue
        _module, lesson = canonical[canonical_id]
        live = golden[canonical_id]
        reason_codes: list[str] = []
        if not _title_matches(lesson, live.get("live_title")):
            reason_codes.append("CANONICAL_GOLDEN_TITLE_DIFFERS_FROM_CONFIRMED_LIVE")
        canonical_step_count = len(lesson.get("steps", []))
        live_step_count = len(live.get("steps", []))
        if canonical_step_count != live_step_count:
            reason_codes.append("CANONICAL_GOLDEN_STEP_COUNT_DIFFERS_FROM_CONFIRMED_LIVE")
        if not reason_codes:
            continue
        notices.append(
            {
                "classification": "GOLDEN_OWNER_REQUIRED",
                "scope": "golden-canonical-divergence",
                "canonical_id": canonical_id,
                "reason_codes": reason_codes,
                "canonical": {
                    "title": str(lesson.get("title", "")),
                    "step_count": canonical_step_count,
                },
                "live_golden": {
                    "title": live.get("live_title"),
                    "step_count": live_step_count,
                    "stepik_lesson_id": live.get("stepik_lesson_id"),
                },
                "automatic_write_allowed": False,
            }
        )
    return notices


def recognize_golden(
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    golden_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    canonical = {lesson["canonical_id"]: (module, lesson) for module, lesson in _canonical_lessons(manifest)}
    live = _flat_live_lessons(snapshot)
    blockers: list[str] = []
    golden: dict[str, Any] = {}

    for canonical_id in GOLDEN_IDS:
        module, lesson = canonical[canonical_id]
        candidates = _golden_identity_candidates(lesson, live, golden_profile=golden_profile)
        if len(candidates) != 1:
            profile_row = (
                golden_profile.get("golden_lessons", {}).get(canonical_id)
                if isinstance(golden_profile, dict)
                else None
            )
            if isinstance(profile_row, dict) and isinstance(profile_row.get("stepik_lesson_id"), int):
                expected = f"golden-profile lesson_id={profile_row['stepik_lesson_id']}"
                identity_mode = "confirmed golden-profile lesson ID"
            else:
                expected = " / ".join(sorted(_accepted_live_titles(lesson)))
                identity_mode = "canonical ID/title"
            blockers.append(
                f"golden:{canonical_id}: ожидался ровно один identity-candidate по {identity_mode} "
                f"(ориентир «{expected}»), найдено {len(candidates)}"
            )
            continue
        match = candidates[0]
        if not _exact_position(module, lesson, match):
            blockers.append(
                f"golden:{canonical_id}: identity-candidate найден, но позиция section/unit отличается от канона"
            )
            continue
        golden[canonical_id] = {
            "canonical_id": canonical_id,
            "stepik_lesson_id": match["lesson_id"],
            "stepik_unit_id": match["unit_id"],
            "stepik_section_id": match["section_id"],
            "live_title": match.get("lesson_title"),
            "steps": match["steps"],
            "status": "READ_ONLY_GOLDEN",
        }

    if len(golden) == 2:
        lesson_ids = [value["stepik_lesson_id"] for value in golden.values()]
        if len(set(lesson_ids)) != 2:
            blockers.append("golden: два канонических golden ID сопоставились одному Stepik lesson")
    return golden, blockers


def plan_dry_run(
    manifest: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
    *,
    golden_profile: dict[str, Any] | None = None,
) -> PlanResult:
    result = PlanResult()
    if snapshot is None:
        for module, lesson in _canonical_lessons(manifest):
            action = "READ_ONLY_GOLDEN" if lesson["canonical_id"] in GOLDEN_IDS else "PLANNED_AFTER_GOLDEN"
            result.operations.append(
                {
                    "action": action,
                    "module": module["canonical_id"],
                    "lesson": lesson["canonical_id"],
                    "reason": "offline structural dry-run; Stepik state not read",
                }
            )
        result.blockers.append("course-not-inspected")
        result.blockers.append("needs-golden-profile")
        return result

    golden, blockers = recognize_golden(manifest, snapshot, golden_profile)
    result.golden = golden
    result.blockers.extend(blockers)
    if blockers:
        return result

    result.notices.extend(_golden_canonical_notices(manifest, golden))
    live = _flat_live_lessons(snapshot)

    for module, lesson in _canonical_lessons(manifest):
        canonical_id = lesson["canonical_id"]
        if canonical_id in GOLDEN_IDS:
            result.operations.append(
                {
                    "action": "READ_ONLY_GOLDEN",
                    "module": module["canonical_id"],
                    "lesson": canonical_id,
                    "stepik_lesson_id": golden[canonical_id]["stepik_lesson_id"],
                    "reason": "golden sample protected",
                }
            )
            continue

        matches = _matching_live_lessons(lesson, live)
        drifted = _drifted_id_candidates(lesson, live)
        if drifted and matches:
            result.blockers.append(
                f"ambiguous-id:{canonical_id}: одновременно найдены канонический lesson и lesson с тем же стабильным ID, но другим заголовком"
            )
            continue
        if len(matches) > 1:
            result.blockers.append(
                f"duplicate:{canonical_id}: найдено {len(matches)} Stepik lessons с канонически допустимым заголовком"
            )
            continue
        if len(matches) == 1:
            match = matches[0]
            if not _exact_position(module, lesson, match):
                result.blockers.append(
                    f"ambiguous-existing:{canonical_id}: канонический заголовок существует, но позиция не совпадает с каноном"
                )
                continue
            result.operations.append(
                {
                    "action": "SKIP",
                    "module": module["canonical_id"],
                    "lesson": canonical_id,
                    "stepik_lesson_id": match.get("lesson_id"),
                    "reason": "existing canonical title+position candidate; no update in v1",
                }
            )
            continue

        if len(drifted) > 1:
            result.blockers.append(
                f"duplicate-id:{canonical_id}: найдено {len(drifted)} lessons с одинаковым стабильным canonical ID в заголовке"
            )
            continue
        if len(drifted) == 1:
            match = drifted[0]
            if not _exact_position(module, lesson, match):
                result.blockers.append(
                    f"ambiguous-title-drift:{canonical_id}: стабильный ID найден, но позиция section/unit не совпадает с каноном"
                )
                continue
            result.operations.append(
                {
                    "action": "SKIP_STALE_TITLE",
                    "module": module["canonical_id"],
                    "lesson": canonical_id,
                    "stepik_lesson_id": match.get("lesson_id"),
                    "current_title": match.get("lesson_title"),
                    "expected_title": f"{canonical_id} — {lesson['title']}",
                    "reason": "stable canonical ID + exact position identify existing skeleton; title update is deferred to an explicit write phase",
                }
            )
            continue

        result.operations.append(
            {
                "action": "PLANNED_CREATE",
                "module": module["canonical_id"],
                "lesson": canonical_id,
                "reason": "missing lesson; write still blocked until golden profile is approved",
            }
        )

    # Live dry-run всё ещё не разрешает запись. CLI снимет этот фазовый blocker только после
    # успешной проверки сохранённого golden profile.
    result.blockers.append("needs-golden-profile")
    return result


def learner_write_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Материал, который потенциально может попасть в learner route. Author-only исключается жёстко."""
    rows: list[dict[str, Any]] = []
    for module, lesson in _canonical_lessons(manifest):
        for step in lesson.get("steps", []):
            if step.get("author_only"):
                continue
            rows.append(
                {
                    "module": module["canonical_id"],
                    "lesson": lesson["canonical_id"],
                    **step,
                }
            )
    return rows
