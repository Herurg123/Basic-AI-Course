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


def _accepted_live_titles(lesson: dict[str, Any]) -> set[str]:
    """Допустимые точные заголовки: канон и существующий Stepik-формат со стабильным ID."""
    canonical_id = str(lesson["canonical_id"])
    title = str(lesson["title"])
    return {title, f"{canonical_id} — {title}"}


def _title_matches(lesson: dict[str, Any], live_title: Any) -> bool:
    return isinstance(live_title, str) and live_title in _accepted_live_titles(lesson)


def _same_id_prefix_but_title_drifted(lesson: dict[str, Any], live_title: Any) -> bool:
    if not isinstance(live_title, str):
        return False
    canonical_id = str(lesson["canonical_id"])
    prefix = f"{canonical_id} — "
    return live_title.startswith(prefix) and live_title not in _accepted_live_titles(lesson)


def _matching_live_lessons(lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in live if _title_matches(lesson, item.get("lesson_title"))]


def _drifted_id_candidates(lesson: dict[str, Any], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in live
        if _same_id_prefix_but_title_drifted(lesson, item.get("lesson_title"))
    ]


def recognize_golden(manifest: dict[str, Any], snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    canonical = {lesson["canonical_id"]: (module, lesson) for module, lesson in _canonical_lessons(manifest)}
    live = _flat_live_lessons(snapshot)
    blockers: list[str] = []
    golden: dict[str, Any] = {}

    for canonical_id in GOLDEN_IDS:
        module, lesson = canonical[canonical_id]
        matches = _matching_live_lessons(lesson, live)
        drifted = _drifted_id_candidates(lesson, live)
        if len(matches) != 1:
            if not matches and drifted:
                blockers.append(
                    f"golden:{canonical_id}: найден lesson со стабильным ID в заголовке, но текст заголовка отличается от канона"
                )
            else:
                expected = " / ".join(sorted(_accepted_live_titles(lesson)))
                blockers.append(
                    f"golden:{canonical_id}: ожидался ровно один lesson с допустимым заголовком «{expected}», найдено {len(matches)}"
                )
            continue
        match = matches[0]
        if match.get("section_position") != module["position"] or match.get("unit_position") != lesson["position"]:
            blockers.append(
                f"golden:{canonical_id}: совпал канонический заголовок, но позиция section/unit отличается от канона"
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
        if len(matches) > 1:
            result.blockers.append(
                f"duplicate:{canonical_id}: найдено {len(matches)} Stepik lessons с канонически допустимым заголовком"
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
        if drifted:
            result.blockers.append(
                f"title-drift:{canonical_id}: найден lesson со стабильным ID в заголовке, но текст заголовка отличается от канона"
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
