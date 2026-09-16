from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import DeploymentHistoryError
    from stepik_uploader.learner_hygiene_entrypoint import (
        HygieneEntrypointError,
        _history_store,
        _paths,
        _requested_course_id,
        commit_proven_title_history_boundaries,
        main as normal_entrypoint_main,
        title_history_object_ids,
    )
    from stepik_uploader.learner_hygiene_recovery import (
        build_normalization_recovery_plan,
        client_from_environment,
        execute_normalization_recovery,
    )
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, load_state
    from stepik_uploader.writer import ContentWriteError
else:
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import DeploymentHistoryError
    from .learner_hygiene_entrypoint import (
        HygieneEntrypointError,
        _history_store,
        _paths,
        _requested_course_id,
        commit_proven_title_history_boundaries,
        main as normal_entrypoint_main,
        title_history_object_ids,
    )
    from .learner_hygiene_recovery import (
        build_normalization_recovery_plan,
        client_from_environment,
        execute_normalization_recovery,
    )
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, load_state
    from .writer import ContentWriteError

COURSE_ID = 299189


def _write_recovery_artifacts(
    *,
    report_dir: Path,
    result: object,
    title_history_recovered: list[dict],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    plan = result.plan
    write_json(report_dir / "normalization-recovery-plan.json", plan.as_dict())
    write_json(report_dir / "sync-state.next.json", result.next_state)
    write_json(report_dir / "course-snapshot.after.json", result.final_snapshot)
    (report_dir / "state-update-required.flag").write_text("true\n", encoding="utf-8")
    tracked_dir = report_dir / "tracked-events"
    tracked_dir.mkdir(parents=True, exist_ok=True)
    write_json(tracked_dir / "M02-L01.json", result.event_artifact())
    if title_history_recovered:
        write_json(report_dir / "title-history-recovery.json", title_history_recovered)

    journal_lines = [
        "### LEARNER_HYGIENE_RECOVERY: Stepik HTML normalization incident #80",
        "",
        f"- event: `{plan.event_id}`",
        f"- event source SHA: `{plan.identity.source_sha}`",
        f"- current main SHA: `{plan.current_source_sha}`",
        f"- normalization contract: `{plan.as_dict()['normalization_contract']}`",
        f"- previously dispatched operation confirmed by normalized read-back: `{plan.unresolved_operation.operation_id}`",
        f"- remaining Stepik writes executed: `{result.stepik_writes}`",
        "- blind retry of the already accepted failed-readback operation: `0`",
        "- creates/deletes/structural writes: `0`",
        f"- title-metadata history boundaries closed without Stepik writes: `{len(title_history_recovered)}`",
        "",
        "Recovery завершает только доказанный M02 event. Следующий learner-hygiene этап обязан снова пройти read-only preflight.",
        "",
    ]
    (report_dir / "sync-journal.md").write_text("\n".join(journal_lines), encoding="utf-8")
    report = {
        "mode": "learner-hygiene-normalization-recovery",
        "course_id": COURSE_ID,
        "source_main_sha": plan.current_source_sha,
        "verdict": "PASS",
        "blockers": [],
        "stepik_writes": result.stepik_writes,
        "stepik_writes_planned": plan.stepik_writes_planned,
        "normalization_recovery": plan.as_dict(),
        "state_update_required": True,
        "ready_for_bulk_write": False,
        "next_action": "rerun-read-only-learner-hygiene-preflight",
        "human_visual_validation": "RETEST_REQUIRED",
    }
    write_json(report_dir / "run-report.json", report)
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
        client = client_from_environment()
        plan = build_normalization_recovery_plan(
            client=client,
            repo_root=repo_root,
            state=state,
            store=store,
            current_source_sha=current_sha,
        )
        if plan is None:
            return normal_entrypoint_main(args)

        result = execute_normalization_recovery(
            client=client,
            plan=plan,
            store=store,
            state=state,
        )
        _write_recovery_artifacts(
            report_dir=report_dir,
            result=result,
            title_history_recovered=title_history_recovered,
        )
        return 0
    except (
        CanonicalBuildError,
        HygieneEntrypointError,
        DeploymentHistoryError,
        SyncStateError,
        ContentWriteError,
        RuntimeError,
        OSError,
        ValueError,
    ) as exc:
        try:
            _repo_root, report_dir, _state_path = _paths(args)
            report_dir.mkdir(parents=True, exist_ok=True)
            report = {
                "mode": "learner-hygiene-recovery-entrypoint",
                "course_id": COURSE_ID,
                "verdict": "BLOCKED",
                "blockers": [f"learner-hygiene-recovery-entrypoint:{exc}"],
                "stepik_writes": 0,
                "ready_for_bulk_write": False,
            }
            write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception:
            print(f"STOP: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
