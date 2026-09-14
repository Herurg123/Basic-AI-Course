from __future__ import annotations

import argparse
import json
from pathlib import Path

from stepik_uploader.sync_state import empty_state, validate_state

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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = args.body_file.read_text(encoding="utf-8")
    if args.command == "extract":
        state = extract_state(body, course_id=args.course_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    state = json.loads(args.state_file.read_text(encoding="utf-8"))
    next_body = replace_state(body, state, course_id=args.course_id)
    args.output_body.parent.mkdir(parents=True, exist_ok=True)
    args.output_body.write_text(next_body, encoding="utf-8")
    args.output_patch.write_text(json.dumps({"body": next_body}, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
