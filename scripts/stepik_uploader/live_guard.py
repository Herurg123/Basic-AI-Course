from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAIN_REF = "refs/heads/main"


class LiveSourceGuardError(RuntimeError):
    pass


def _validate_sha(value: str, *, label: str) -> str:
    normalized = (value or "").strip().lower()
    if not SHA_RE.fullmatch(normalized):
        raise LiveSourceGuardError(f"{label} не является полным 40-символьным Git SHA")
    return normalized


def validate_live_source(*, ref: str, run_sha: str, remote_main_sha: str) -> dict[str, str]:
    if ref != MAIN_REF:
        raise LiveSourceGuardError(
            f"live-source-not-main: ожидалось {MAIN_REF}, получено {ref!r}"
        )
    checked_run_sha = _validate_sha(run_sha, label="GITHUB_SHA")
    checked_remote_sha = _validate_sha(remote_main_sha, label="remote main HEAD")
    if checked_run_sha != checked_remote_sha:
        raise LiveSourceGuardError(
            "live-source-stale-main: "
            f"run_sha={checked_run_sha}, remote_main_sha={checked_remote_sha}"
        )
    return {
        "verdict": "PASS",
        "ref": ref,
        "run_sha": checked_run_sha,
        "remote_main_sha": checked_remote_sha,
    }


def fetch_remote_main_sha(
    *,
    repository: str,
    token: str,
    api_url: str = "https://api.github.com",
    opener: Callable[..., Any] = urlopen,
) -> str:
    repository = (repository or "").strip()
    token = (token or "").strip()
    if not repository or "/" not in repository:
        raise LiveSourceGuardError("GITHUB_REPOSITORY отсутствует или имеет неверный формат")
    if not token:
        raise LiveSourceGuardError("GITHUB_TOKEN/GH_TOKEN отсутствует; remote main проверить нельзя")

    url = f"{api_url.rstrip('/')}/repos/{repository}/git/ref/heads/main"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "basic-ai-course-stepik-live-guard",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LiveSourceGuardError(
            f"remote-main-check-failed: GitHub API недоступен или вернул некорректный ответ ({type(exc).__name__})"
        ) from exc

    try:
        sha = payload["object"]["sha"]
    except (KeyError, TypeError) as exc:
        raise LiveSourceGuardError("remote-main-check-failed: GitHub API не вернул object.sha") from exc
    return _validate_sha(str(sha), label="remote main HEAD")


def _write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed guard: live Stepik workflow разрешён только из текущего HEAD main"
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--api-url", default=os.getenv("GITHUB_API_URL", "https://api.github.com"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ref = os.getenv("GITHUB_REF", "")
    run_sha = os.getenv("GITHUB_SHA", "")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""

    try:
        remote_main_sha = fetch_remote_main_sha(
            repository=repository,
            token=token,
            api_url=args.api_url,
        )
        report = validate_live_source(
            ref=ref,
            run_sha=run_sha,
            remote_main_sha=remote_main_sha,
        )
        report["repository"] = repository
        _write_report(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except LiveSourceGuardError as exc:
        report = {
            "verdict": "BLOCKED",
            "ref": ref,
            "run_sha": run_sha,
            "repository": repository,
            "blocker": str(exc),
        }
        _write_report(args.output, report)
        print(f"LIVE SOURCE GUARD BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
