from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

GOLDEN_IDS = ("M00-L01", "M00-L02")


@dataclass
class PlanResult:
    operations: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
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


def recognize_golden(manifest: dict[str, Any], snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    canonical = {lesson["canonical_id"]: (module, lesson) for module, lesson in _canonical_lessons(manifest)}
    live = _flat_live_lessons(snapshot)
    blockers: list[str] = []
    golden: dict[str, Any] = {}

    for canonical_id in GOLDEN_IDS:
        module, lesson = canonical[canonical_id]
        matches = [item for item in live if item.get("lesson_title") == lesson["title"]]
        if len(matches) != 1:
            blockers.append(
                f"golden:{canonical_id}: ожидался ровно один lesson с заголовком «{lesson['title']}», найдено {len(matches)}"
            )
            continue
        match = matches[0]
        if match.get("section_position") != module["position"] or match.get("unit_position") != lesson["position"]:
            blockers.append(
                f"golden:{canonical_id}: совпал заголовок, но позиция section/unit отличается от канона"
            )
            continue
        golden[canonical_id] = {
            "canonical_id": canonical_id,
            "stepik_lesson_id": match["lesson_id"],
            "stepik_unit_id": match["unit_id"],
            "stepik_section_id": match["section_id"],
            "steps": match["steps"],
            "status": "READ_ONLY_GOLDEN",
        }

    if len(golden) == 2:
        lesson_ids = [value["stepik_lesson_id"] for value in golden.values()]
        if len(set(lesson_ids)) != 2:
            blockers.append("golden: два канонических golden ID сопоставились одному Stepik lesson")
    return golden, blockers


def plan_dry_run(manifest: dict[str, Any], snapshot: dict[str, Any] | None = None) -> PlanResult:
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

    golden, blockers = recognize_golden(manifest, snapshot)
    result.golden = golden
    result.blockers.extend(blockers)
    if blockers:
        return result

    live = _flat_live_lessons(snapshot)
    title_index: dict[str, list[dict[str, Any]]] = {}
    for item in live:
        title_index.setdefault(str(item.get("lesson_title")), []).append(item)

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
        matches = title_index.get(lesson["title"], [])
        if len(matches) > 1:
            result.blockers.append(
                f"duplicate:{canonical_id}: найдено {len(matches)} Stepik lessons с одинаковым заголовком"
            )
            continue
        if len(matches) == 1:
            match = matches[0]
            exact_position = (
                match.get("section_position") == module["position"]
                and match.get("unit_position") == lesson["position"]
            )
            if not exact_position:
                result.blockers.append(
                    f"ambiguous-existing:{canonical_id}: заголовок существует, но позиция не совпадает с каноном"
                )
                continue
            result.operations.append(
                {
                    "action": "SKIP",
                    "module": module["canonical_id"],
                    "lesson": canonical_id,
                    "stepik_lesson_id": match.get("lesson_id"),
                    "reason": "existing exact title+position candidate; no update in v1",
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

    # Даже при корректном распознавании golden массовая запись не разрешается этой фазой.
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
