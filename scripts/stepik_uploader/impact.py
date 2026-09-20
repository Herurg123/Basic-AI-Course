from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlsplit

LESSON_FILE_RE = re.compile(r"^04_course/(M\d{2})/(M\d{2}-L\d{2})/(lesson\.md|stepik-plan\.md)$")
ASSET_RE = re.compile(r"^05_assets/(M\d{2})/(M\d{2}-L\d{2})/")
CANONICAL_SOURCE_RE = LESSON_FILE_RE
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
COURSE_PAGE = "04_course/stepik/course-page.md"
SHARED_PREFIX = "04_course/stepik/"
GLOBAL_LEARNER_RENDER_PATHS = {
    "scripts/stepik_uploader/canonical.py",
    "scripts/stepik_uploader/general_content.py",
    "scripts/stepik_uploader/rendering.py",
    "scripts/stepik_uploader/verified_rendering.py",
}


class ImpactError(RuntimeError):
    pass


@dataclass(frozen=True)
class Change:
    status: str
    old_path: str | None
    new_path: str | None

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(path for path in (self.old_path, self.new_path) if path))


def parse_changes(lines: Iterable[str]) -> list[Change]:
    changes: list[Change] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        code = status[0]
        if code in {"R", "C"}:
            if len(parts) != 3:
                raise ImpactError(f"Некорректная rename/copy строка git diff --name-status: {line}")
            changes.append(Change(status=code, old_path=parts[1], new_path=parts[2]))
        elif code in {"A", "M", "D", "T"}:
            if len(parts) != 2:
                raise ImpactError(f"Некорректная строка git diff --name-status: {line}")
            path = parts[1]
            changes.append(Change(status=code, old_path=path if code in {"M", "D", "T"} else None, new_path=path if code in {"A", "M", "T"} else None))
        else:
            raise ImpactError(f"Неподдерживаемый git change status: {status}")
    return changes


def _repo_relative_target(source_path: str, raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target or target.startswith("#"):
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if " " in target and not target.startswith(("http://", "https://")):
        target = target.split(" ", 1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path or path.startswith("/"):
        return None
    normalized = posixpath.normpath(str(PurePosixPath(source_path).parent / path))
    if normalized == ".." or normalized.startswith("../"):
        raise ImpactError(f"{source_path}: dependency link выходит за пределы репозитория: {raw_target}")
    return normalized


def build_dependency_graph(repo_root: Path) -> dict[str, set[str]]:
    root = repo_root.resolve()
    graph: dict[str, set[str]] = {}
    course_root = root / "04_course"
    if not course_root.exists():
        return graph
    for source in sorted(course_root.glob("M??/M??-L??/*.md")):
        rel = source.relative_to(root).as_posix()
        match = CANONICAL_SOURCE_RE.fullmatch(rel)
        if not match:
            continue
        lesson_id = match.group(2)
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise ImpactError(f"Не удалось прочитать canonical dependency source {rel}: {exc}") from exc
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = _repo_relative_target(rel, raw_target)
            if target is not None:
                graph.setdefault(target, set()).add(lesson_id)
    return graph


def _is_shared_learner_candidate(path: str) -> bool:
    return path.startswith(SHARED_PREFIX) and path != COURSE_PAGE and not path.startswith("04_course/stepik/automation/") and path.endswith(".md")


def _canonical_lesson_ids(repo_root: Path) -> list[str]:
    root = repo_root.resolve() / "04_course"
    return sorted(
        path.parent.name
        for path in root.glob("M??/M??-L??/lesson.md")
        if re.fullmatch(r"M\d{2}-L\d{2}", path.parent.name)
    )


def _add_reason(affected: set[str], paths: dict[str, set[str]], reasons: dict[str, set[str]], *, lesson_id: str, changed_path: str, reason: str) -> None:
    affected.add(lesson_id)
    paths.setdefault(lesson_id, set()).add(changed_path)
    reasons.setdefault(lesson_id, set()).add(reason)


def assess_changes(changes: Iterable[Change], *, repo_root: Path, base_repo_root: Path) -> dict:
    head_graph = build_dependency_graph(repo_root)
    base_graph = build_dependency_graph(base_repo_root)
    affected: set[str] = set()
    paths_by_lesson: dict[str, set[str]] = {}
    reasons_by_lesson: dict[str, set[str]] = {}
    course_page_paths: set[str] = set()
    blockers: list[str] = []
    change_summaries: list[dict[str, object]] = []

    for change in changes:
        sides: list[tuple[str, dict[str, set[str]], str]] = []
        if change.old_path:
            sides.append((change.old_path, base_graph, "before"))
        if change.new_path:
            sides.append((change.new_path, head_graph, "after"))

        global_render_paths = [path for path in change.paths if path in GLOBAL_LEARNER_RENDER_PATHS]
        if global_render_paths:
            lesson_ids = sorted(set(_canonical_lesson_ids(repo_root)) | set(_canonical_lesson_ids(base_repo_root)))
            if not lesson_ids:
                blockers.append("global-learner-renderer-changed:no-canonical-lessons-found")
            for lesson_id in lesson_ids:
                for changed_path in global_render_paths:
                    _add_reason(
                        affected,
                        paths_by_lesson,
                        reasons_by_lesson,
                        lesson_id=lesson_id,
                        changed_path=changed_path,
                        reason="global-learner-renderer",
                    )

        shared_paths = [path for path in change.paths if _is_shared_learner_candidate(path)]
        shared_consumers: set[str] = set()
        for path, graph, _side in sides:
            shared_consumers.update(graph.get(path, set()))
        if shared_paths and not shared_consumers:
            blockers.append("unknown-learner-facing-dependency:" + ",".join(shared_paths) + ": canonical Lesson ID mapping не найден")

        if change.status == "R" and change.new_path and _is_shared_learner_candidate(change.new_path):
            if not head_graph.get(change.new_path, set()):
                blockers.append(f"renamed-shared-dependency-unmapped:{change.new_path}: новый canonical mapping отсутствует")
        if change.status == "D" and change.old_path and _is_shared_learner_candidate(change.old_path):
            stale_consumers = head_graph.get(change.old_path, set())
            if stale_consumers:
                blockers.append(f"deleted-shared-dependency-still-referenced:{change.old_path}: " + ",".join(sorted(stale_consumers)))

        for path, graph, _side in sides:
            direct = LESSON_FILE_RE.fullmatch(path)
            if direct:
                _add_reason(affected, paths_by_lesson, reasons_by_lesson, lesson_id=direct.group(2), changed_path=path, reason="direct-lesson-source")
            asset = ASSET_RE.match(path)
            if asset:
                _add_reason(affected, paths_by_lesson, reasons_by_lesson, lesson_id=asset.group(2), changed_path=path, reason="lesson-asset")
            if path == COURSE_PAGE:
                course_page_paths.add(path)
            for dependent in graph.get(path, set()):
                _add_reason(affected, paths_by_lesson, reasons_by_lesson, lesson_id=dependent, changed_path=path, reason="shared-learner-dependency")

        change_summaries.append({"status": change.status, "old_path": change.old_path, "new_path": change.new_path})

    return {
        "affected_lessons": sorted(affected),
        "paths_by_lesson": {key: sorted(value) for key, value in sorted(paths_by_lesson.items())},
        "reasons_by_lesson": {key: sorted(value) for key, value in sorted(reasons_by_lesson.items())},
        "course_page_changed": bool(course_page_paths),
        "course_page_paths": sorted(course_page_paths),
        "stepik_content_impact": bool(affected or course_page_paths),
        "blockers": sorted(set(blockers)),
        "changes": change_summaries,
    }


def assess_paths(paths: Iterable[str]) -> dict:
    affected: set[str] = set()
    reasons: dict[str, list[str]] = {}
    reason_codes: dict[str, list[str]] = {}
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
            code = "direct-lesson-source" if LESSON_FILE_RE.match(path) else "lesson-asset"
            reason_codes.setdefault(lesson_id, []).append(code)
        elif path == COURSE_PAGE:
            course_page_changed = True
    return {
        "affected_lessons": sorted(affected),
        "paths_by_lesson": {key: sorted(set(value)) for key, value in sorted(reasons.items())},
        "reasons_by_lesson": {key: sorted(set(value)) for key, value in sorted(reason_codes.items())},
        "course_page_changed": course_page_changed,
        "course_page_paths": [COURSE_PAGE] if course_page_changed else [],
        "stepik_content_impact": bool(affected or course_page_changed),
        "blockers": [],
        "changes": [],
    }


def render_markdown(payload: dict, *, source_sha: str) -> str:
    lines = [
        "### PENDING: изменения `main`, потенциально требующие синхронизации Stepik",
        "",
        f"SHA исходника: `{source_sha}`",
        "",
        "Машинно-читаемый список PENDING в описании issue обновлён. Эта запись остаётся неизменяемым журналом операции и не является источником содержания курса.",
    ]
    lessons = payload.get("affected_lessons", [])
    if lessons:
        lines.extend(["", "Кандидаты на обновление уроков:"])
        for lesson_id in lessons:
            paths = ", ".join(f"`{p}`" for p in payload.get("paths_by_lesson", {}).get(lesson_id, []))
            lines.append(f"- `{lesson_id}`: {paths}")
    if payload.get("course_page_changed"):
        lines.extend(["", "Также изменена страница курса Stepik: `04_course/stepik/course-page.md`."])
    lines.extend(["", "Повторное слияние изменения того же объекта обновляет его `latest_pending_*` и объединяет пути исходников; отдельная логическая очередь не создаётся.", "Перед записью ручная синхронизация обязана сравнить текущее состояние Stepik с последним подтверждённым базовым состоянием (`baseline`). Обнаруженное расхождение означает остановку без записи."])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changes", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--base-repo-root", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--occurred-at", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changes = parse_changes(args.changes.read_text(encoding="utf-8").splitlines())
        payload = assess_changes(changes, repo_root=args.repo_root, base_repo_root=args.base_repo_root)
        payload["source_sha"] = args.source_sha
        payload["occurred_at"] = args.occurred_at
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.markdown_output.write_text(render_markdown(payload, source_sha=args.source_sha), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 2 if payload["blockers"] else 0
    except (ImpactError, OSError, ValueError) as exc:
        print(f"ОСТАНОВЛЕНО: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
