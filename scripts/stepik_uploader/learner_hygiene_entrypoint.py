from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import (
        DeploymentHistoryError,
        DeploymentRecorder,
        GitHubHistoryStore,
    )
    from stepik_uploader.history_runtime import final_confirmed_record, find_incomplete_object_events
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, baseline_for, load_state
    from stepik_uploader.learner_hygiene_runtime import main as hygiene_main
else:
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import DeploymentHistoryError, DeploymentRecorder, GitHubHistoryStore
    from .history_runtime import final_confirmed_record, find_incomplete_object_events
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, baseline_for, load_state
    from .learner_hygiene_runtime import main as hygiene_main

COURSE_ID = 299189
TRACKED_TARGETS = ("M02-L01", "M04-L01")


class HygieneEntrypointError(RuntimeError):
    pass


def _arg_value(argv: list[str], name: str) -> str | None:
    try:
        index = argv.index(name)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        raise HygieneEntrypointError(f"{name} требует значение")
    return argv[index + 1]


def _paths(argv: list[str]) -> tuple[Path, Path, Path]:
    repo_root_raw = _arg_value(argv, "--repo-root") or "."
    report_dir_raw = _arg_value(argv, "--report-dir") or "artifacts/stepik-learner-hygiene"
    state_raw = _arg_value(argv, "--sync-state")
    if state_raw is None:
        raise HygieneEntrypointError("--sync-state обязателен")
    repo_root = Path(repo_root_raw).resolve()
    report_dir_path = Path(report_dir_raw)
    report_dir = report_dir_path if report_dir_path.is_absolute() else (repo_root / report_dir_path).resolve()
    state_path = Path(state_raw)
    state_path = state_path if state_path.is_absolute() else (repo_root / state_path).resolve()
    return repo_root, report_dir, state_path


def _requested_course_id(argv: list[str]) -> int:
    raw = _arg_value(argv, "--course-id")
    if raw is None:
        raise HygieneEntrypointError("--course-id обязателен")
    try:
        value = int(raw)
    except ValueError as exc:
        raise HygieneEntrypointError("course_id должен быть числом") from exc
    if value != COURSE_ID:
        raise HygieneEntrypointError(f"learner hygiene разрешён только для course_id={COURSE_ID}")
    return value


def _history_store(current_sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=current_sha,
    )


def title_history_object_ids(manifest: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for module in manifest.get("modules", []):
        module_id = str(module["canonical_id"])
        result.append(f"title:section:{module_id}")
        for lesson in module.get("lessons", []):
            result.append(f"title:lesson:{lesson['canonical_id']}")
    return sorted(result)


def commit_proven_title_history_boundaries(
    *,
    store: Any,
    object_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Закрывает только доказанный title-metadata final boundary без повторного Stepik write.

    Title-only metadata не имеет отдельного machine baseline в Issue #54. Поэтому после
    FINAL_READBACK_CONFIRMED единственный незавершённый boundary — append-only
    MACHINE_STATE_COMMITTED в deployment history. Его можно безопасно дописать даже после
    перехода main на новый SHA: final record уже криптографически привязан к исходному event.
    Partial/ambiguous events без final здесь никогда не усыновляются.
    """
    recovered: list[dict[str, Any]] = []
    for object_id in sorted(set(str(value) for value in object_ids)):
        incomplete = find_incomplete_object_events(store, object_id=object_id)
        if len(incomplete) > 1:
            raise HygieneEntrypointError(f"{object_id}: найдено несколько incomplete title events")
        if not incomplete:
            continue
        identity, records, summary = incomplete[0]
        if identity.kind != "title-metadata":
            raise HygieneEntrypointError(f"{object_id}: ожидается history kind=title-metadata")
        if summary.get("machine_state_committed"):
            continue
        final = final_confirmed_record(records)
        if final is None:
            # Partial/ambiguous event остаётся для обычного fail-closed runtime разбора.
            continue
        actual_state = final.get("actual_confirmed_state")
        status = str(final.get("status") or "")
        if not isinstance(actual_state, dict):
            raise HygieneEntrypointError(f"{object_id}: final title history не содержит actual_confirmed_state")
        if status not in {"APPLIED", "NOOP_CONFIRMED"}:
            raise HygieneEntrypointError(f"{object_id}: final title history содержит неизвестный status")
        DeploymentRecorder(store, identity).state_committed(
            baseline_after=actual_state,
            status=status,
        )
        recovered.append(
            {
                "object_id": object_id,
                "event_id": identity.event_id,
                "source_sha": identity.source_sha,
                "status": status,
                "stepik_writes": 0,
            }
        )
    return recovered


def stale_history_commit_only_events(
    *,
    store: Any,
    state: dict[str, Any],
    current_source_sha: str,
) -> list[dict[str, Any]]:
    """Находит только доказанный boundary state: Stepik final + Issue baseline, но history ещё не committed.

    Если такой event относится к старому main, новые Stepik writes запрещены до того, как
    MACHINE_STATE_COMMITTED будет дописан. Иначе новый deployment event мог бы стартовать поверх
    незакрытого старого события, что делает recovery неоднозначным.
    """
    result: list[dict[str, Any]] = []
    for canonical_id in TRACKED_TARGETS:
        incomplete = find_incomplete_object_events(store, object_id=canonical_id)
        if len(incomplete) > 1:
            raise HygieneEntrypointError(f"{canonical_id}: найдено несколько incomplete deployment events")
        if not incomplete:
            continue
        identity, records, summary = incomplete[0]
        if summary.get("machine_state_committed"):
            continue
        final = final_confirmed_record(records)
        if final is None:
            continue
        recovered = final.get("actual_confirmed_state")
        baseline = baseline_for(state, canonical_id)
        if not isinstance(recovered, dict) or baseline != recovered:
            continue
        if identity.source_sha == current_source_sha:
            # Текущий runtime умеет завершить same-source boundary и продолжить безопасно.
            continue
        status = str(final.get("status") or "")
        if status not in {"APPLIED", "NOOP_CONFIRMED"}:
            raise HygieneEntrypointError(f"{canonical_id}: final history содержит неизвестный status")
        result.append(
            {
                "event_id": identity.event_id,
                "source_sha": identity.source_sha,
                "status": status,
                "kind": "lesson",
                "canonical_id": canonical_id,
                "applied_fingerprint": recovered.get("applied_fingerprint"),
            }
        )
    return result


def _write_commit_only_artifacts(
    *,
    report_dir: Path,
    state: dict[str, Any],
    current_sha: str,
    events: list[dict[str, Any]],
    title_history_recovered: list[dict[str, Any]],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    tracked_dir = report_dir / "tracked-events"
    tracked_dir.mkdir(parents=True, exist_ok=True)
    for event in events:
        canonical_id = str(event["canonical_id"])
        (tracked_dir / f"{canonical_id}.json").write_text(
            json.dumps(event, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (report_dir / "sync-state.next.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if title_history_recovered:
        (report_dir / "title-history-recovery.json").write_text(
            json.dumps(title_history_recovered, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    journal_lines = [
        "### HISTORY_COMMIT_ONLY: завершение доказанного предыдущего learner-hygiene event",
        "",
        f"- current main SHA: `{current_sha}`",
        "- Stepik writes: `0`",
        "- Issue #54 machine state уже совпадает с FINAL_READBACK_CONFIRMED предыдущего tracked event.",
        "- Новый learner-hygiene write намеренно не начинается до MACHINE_STATE_COMMITTED.",
        f"- title-metadata history boundaries закрыты без Stepik writes: `{len(title_history_recovered)}`",
        "",
        "Tracked события:",
    ]
    for event in events:
        journal_lines.append(
            f"- `{event['canonical_id']}`: `{event['event_id']}` source `{event['source_sha']}`"
        )
    journal_lines.append("")
    (report_dir / "sync-journal.md").write_text("\n".join(journal_lines), encoding="utf-8")
    report = {
        "mode": "learner-hygiene-history-commit-only",
        "course_id": COURSE_ID,
        "source_main_sha": current_sha,
        "verdict": "PASS",
        "history_commit_only": True,
        "state_update_required": False,
        "stepik_writes": 0,
        "events": events,
        "title_history_recovered": title_history_recovered,
        "ready_for_bulk_write": False,
        "next_action": "commit-history-then-rerun-learner-hygiene",
    }
    (report_dir / "run-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        _requested_course_id(args)
        repo_root, report_dir, state_path = _paths(args)
        current_sha = source_sha(repo_root)
        state = load_state(state_path, course_id=COURSE_ID)
        store = _history_store(current_sha)
        manifest = build_structural_manifest(repo_root, source_sha=current_sha)

        title_history_recovered = commit_proven_title_history_boundaries(
            store=store,
            object_ids=title_history_object_ids(manifest),
        )
        if title_history_recovered:
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "title-history-recovery.json").write_text(
                json.dumps(title_history_recovered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        events = stale_history_commit_only_events(
            store=store,
            state=state,
            current_source_sha=current_sha,
        )
        if events:
            _write_commit_only_artifacts(
                report_dir=report_dir,
                state=state,
                current_sha=current_sha,
                events=events,
                title_history_recovered=title_history_recovered,
            )
            return 0
        return hygiene_main()
    except (
        CanonicalBuildError,
        HygieneEntrypointError,
        DeploymentHistoryError,
        SyncStateError,
        OSError,
        ValueError,
    ) as exc:
        try:
            _repo_root, report_dir, _state_path = _paths(args)
            report_dir.mkdir(parents=True, exist_ok=True)
            report = {
                "mode": "learner-hygiene-entrypoint",
                "course_id": COURSE_ID,
                "verdict": "BLOCKED",
                "blockers": [f"learner-hygiene-entrypoint:{exc}"],
                "stepik_writes": 0,
                "ready_for_bulk_write": False,
            }
            (report_dir / "run-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception:
            print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
