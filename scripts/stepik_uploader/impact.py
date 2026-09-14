from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

LESSON_FILE_RE = re.compile(r"^04_course/(M\d{2})/(M\d{2}-L\d{2})/(lesson\.md|stepik-plan\.md)$")
ASSET_RE = re.compile(r"^05_assets/(M\d{2})/(M\d{2}-L\d{2})/")
COURSE_PAGE = "04_course/stepik/course-page.md"


def assess_paths(paths: Iterable[str]) -> dict:
    affected: set[str] = set()
    reasons: dict[str, list[str]] = {}
    course_page_changed = False
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        match = LESSON_FILE_RE.match(path) or ASSET_RE.match(path)
        if match:
            lesson_id = match.group(2)
            affected.add(lesson_id)
            reasons.setdefault(lesson_id, []).append(path)
        elif path == COURSE_PAGE:
            course_page_changed = True
    return {
        "affected_lessons": sorted(affected),
        "paths_by_lesson": {key: sorted(set(value)) for key, value in sorted(reasons.items())},
        "course_page_changed": course_page_changed,
        "stepik_content_impact": bool(affected or course_page_changed),
    }


def render_markdown(payload: dict, *, source_sha: str) -> str:
    lines = [
        "### PENDING: изменения `main`, потенциально требующие синхронизации Stepik",
        "",
        f"Source SHA: `{source_sha}`",
        "",
        "Эта запись **не означает**, что Stepik уже изменён. Автоматический live-write не запускается при merge.",
    ]
    lessons = payload.get("affected_lessons", [])
    if lessons:
        lines.extend(["", "Кандидаты на обновление уроков:"])
        for lesson_id in lessons:
            paths = ", ".join(f"`{p}`" for p in payload.get("paths_by_lesson", {}).get(lesson_id, []))
            lines.append(f"- `{lesson_id}`: {paths}")
    if payload.get("course_page_changed"):
        lines.extend(["", "Также изменена Stepik course page: `04_course/stepik/course-page.md`."])
    lines.extend(
        [
            "",
            "Перед записью manual sync обязан сравнить live Stepik с последним подтверждённым baseline. Drift = STOP.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = args.changed_files.read_text(encoding="utf-8").splitlines()
    payload = assess_paths(paths)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(payload, source_sha=args.source_sha), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
