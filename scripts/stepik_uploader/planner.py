from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanResult:
    operations: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notices: list[dict[str, Any]] = field(default_factory=list)

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
    canonical_id = str(lesson["canonical_id"])
    title = str(lesson["title"])
    return {title, f"{canonical_id} — {title}"}


def _position_candidates(module: dict[str, Any], lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in live
        if item.get("section_position") == module["position"]
        and item.get("unit_position") == lesson["position"]
    ]


def _identity_candidates(lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical_id = str(lesson["canonical_id"])
    accepted = _accepted_live_titles(lesson)
    return [
        item
        for item in live
        if item.get("lesson_title") in accepted
        or (
            isinstance(item.get("lesson_title"), str)
            and item["lesson_title"].startswith(f"{canonical_id} — ")
        )
    ]


def plan_dry_run(manifest: dict[str, Any], snapshot: dict[str, Any] | None = None) -> PlanResult:
    """Build a uniform structural plan for all lessons.

    The planner no longer has protected lesson classes. It validates topology and
    reports title differences, while mutation authority remains target-scoped in
    the baseline/history-aware initial/refresh/recovery runtimes.
    """
    result = PlanResult()
    if snapshot is None:
        for module, lesson in _canonical_lessons(manifest):
            result.operations.append(
                {
                    "action": "PLANNED_AFTER_LIVE_GUARDS",
                    "module": module["canonical_id"],
                    "lesson": lesson["canonical_id"],
                    "reason": "offline structural dry-run; Stepik state not read",
                }
            )
        result.blockers.append("course-not-inspected")
        return result

    live = _flat_live_lessons(snapshot)
    for module, lesson in _canonical_lessons(manifest):
        canonical_id = str(lesson["canonical_id"])
        at_position = _position_candidates(module, lesson, live)
        identity = _identity_candidates(lesson, live)

        if len(at_position) > 1:
            result.blockers.append(
                f"duplicate-position:{canonical_id}: section/unit position содержит несколько lessons"
            )
            continue

        if len(at_position) == 1:
            match = at_position[0]
            other_identity = [item for item in identity if item.get("lesson_id") != match.get("lesson_id")]
            if other_identity:
                result.blockers.append(
                    f"ambiguous-identity:{canonical_id}: canonical identity одновременно обнаружена вне ожидаемой позиции"
                )
                continue

            live_title = match.get("lesson_title")
            if live_title in _accepted_live_titles(lesson):
                action = "SKIP"
                reason = "existing lesson at canonical position with accepted title"
            else:
                action = "SKIP_STALE_TITLE"
                reason = "existing lesson at canonical position; title migration is decided by target baseline-aware sync"
                result.notices.append(
                    {
                        "classification": "TITLE_DIFFERS_AT_CANONICAL_POSITION",
                        "canonical_id": canonical_id,
                        "stepik_lesson_id": match.get("lesson_id"),
                        "live_title": live_title,
                        "canonical_title": str(lesson["title"]),
                        "automatic_write_allowed": False,
                    }
                )

            result.operations.append(
                {
                    "action": action,
                    "module": module["canonical_id"],
                    "lesson": canonical_id,
                    "stepik_lesson_id": match.get("lesson_id"),
                    "current_title": live_title,
                    "expected_title": str(lesson["title"]),
                    "reason": reason,
                }
            )
            continue

        if identity:
            result.blockers.append(
                f"position-drift:{canonical_id}: lesson identity найдена вне canonical section/unit position"
            )
            continue

        result.operations.append(
            {
                "action": "PLANNED_CREATE",
                "module": module["canonical_id"],
                "lesson": canonical_id,
                "reason": "lesson отсутствует в canonical position; target initial route must prove a safe skeleton before write",
            }
        )

    return result


def learner_write_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
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
