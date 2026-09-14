from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.sync_state import empty_state, validate_state, with_pending_impact
else:
    from .sync_state import empty_state, validate_state, with_pending_impact

BEGIN = "<!-- STEPIK_SYNC_STATE_V1_BEGIN -->"
END = "<!-- STEPIK_SYNC_STATE_V1_END -->"


class IssueStateError(RuntimeError):
    pass


def extract_state(body: str, *, course_id: int) -> dict:
    start = body.find(BEGIN)
    end = body.find(END)
    if start < 0 and end < 0:
        return empty_state(course_id)
    if start < 0 or end < 0 or end <= start:
        raise IssueStateError("Повреждены markers machine-readable Stepik sync state в issue body")
    raw = body[start + len(BEGIN) : end].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IssueStateError(f"Некорректный JSON в Stepik sync issue: {exc}") from exc
    return validate_state(payload, course_id=course_id)


def replace_state(body: str, state: dict, *, course_id: int) -> str:
    state = validate_state(state, course_id=course_id)
    block = BEGIN + "\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n" + END
    start = body.find(BEGIN)
    end = body.find(END)
    if start < 0 and end < 0:
        suffix = "\n\n" if body.strip() else ""
        return body.rstrip() + suffix + block + "\n"
    if start < 0 or end < 0 or end <= start:
        raise IssueStateError("Повреждены markers machine-readable Stepik sync state в issue body")
    return body[:start] + block + body[end + len(END) :]


def assert_expected_state(expected: dict, current: dict, *, course_id: int) -> None:
    expected_normalized = validate_state(expected, course_id=course_id)
    current_normalized = validate_state(current, course_id=course_id)
    if expected_normalized != current_normalized:
        raise IssueStateError("Machine-readable Stepik sync state изменился после чтения; PATCH остановлен во избежание race")


def state_with_impact(state: dict, impact: dict, *, course_id: int) -> dict:
    normalized = validate_state(state, course_id=course_id)
    blockers = impact.get("blockers", [])
    if blockers:
        raise IssueStateError("Impact содержит blockers: " + "; ".join(str(value) for value in blockers))
    source_sha = impact.get("source_sha")
    occurred_at = impact.get("occurred_at")
    if not isinstance(source_sha, str) or not isinstance(occurred_at, str):
        raise IssueStateError("Impact report не содержит source_sha/occurred_at")
    return with_pending_impact(
        normalized,
        source_sha=source_sha,
        occurred_at=occurred_at,
        paths_by_lesson={str(key): [str(value) for value in values] for key, values in impact.get("paths_by_lesson", {}).items()},
        reasons_by_lesson={str(key): [str(value) for value in values] for key, values in impact.get("reasons_by_lesson", {}).items()},
        course_page_paths=[str(value) for value in impact.get("course_page_paths", [])],
        course_page_reason_codes=["course-page-source"] if impact.get("course_page_changed") else [],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("--body-file", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--course-id", type=int, required=True)
    replace = sub.add_parser("replace")
    replace.add_argument("--body-file", type=Path, required=True)
    replace.add_argument("--state-file", type=Path, required=True)
    replace.add_argument("--output-body", type=Path, required=True)
    replace.add_argument("--output-patch", type=Path, required=True)
    replace.add_argument("--course-id", type=int, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--expected-state", type=Path, required=True)
    compare.add_argument("--current-state", type=Path, required=True)
    compare.add_argument("--course-id", type=int, required=True)
    impact = sub.add_parser("apply-impact")
    impact.add_argument("--state-file", type=Path, required=True)
    impact.add_argument("--impact-file", type=Path, required=True)
    impact.add_argument("--output", type=Path, required=True)
    impact.add_argument("--course-id", type=int, required=True)
    return parser.parse_args()


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IssueStateError(f"Не удалось прочитать JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IssueStateError(f"{path}: ожидается JSON object")
    return value


def main() -> int:
    args = parse_args()
    try:
        if args.command == "extract":
            body = args.body_file.read_text(encoding="utf-8")
            state = extract_state(body, course_id=args.course_id)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "compare":
            assert_expected_state(_load_json(args.expected_state), _load_json(args.current_state), course_id=args.course_id)
            return 0
        if args.command == "apply-impact":
            next_state = state_with_impact(_load_json(args.state_file), _load_json(args.impact_file), course_id=args.course_id)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(next_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        body = args.body_file.read_text(encoding="utf-8")
        state = _load_json(args.state_file)
        next_body = replace_state(body, state, course_id=args.course_id)
        args.output_body.parent.mkdir(parents=True, exist_ok=True)
        args.output_body.write_text(next_body, encoding="utf-8")
        args.output_patch.write_text(json.dumps({"body": next_body}, ensure_ascii=False), encoding="utf-8")
        return 0
    except (IssueStateError, OSError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
