from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.api import StepikAPIError, StepikClient
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.canonical import CanonicalBuildError, build_structural_manifest
    from stepik_uploader.deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from stepik_uploader.fingerprints import live_lesson_fingerprint
    from stepik_uploader.history_runtime import find_incomplete_object_events, final_confirmed_record
    from stepik_uploader.reporting import write_json
    from stepik_uploader.stepik_uploader import source_sha
    from stepik_uploader.sync_state import SyncStateError, asset_binding_for, baseline_for, load_state
    from stepik_uploader.visual_materialization import VisualMaterializationError, verify_visual_binding
    from stepik_uploader.writer import ContentWriteError
else:
    from .api import StepikAPIError, StepikClient
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import AssetResolutionError, assess_asset_publication, load_asset_publication_policy
    from .canonical import CanonicalBuildError, build_structural_manifest
    from .deployment_history import DeploymentHistoryError, GitHubHistoryStore
    from .fingerprints import live_lesson_fingerprint
    from .history_runtime import find_incomplete_object_events, final_confirmed_record
    from .reporting import write_json
    from .stepik_uploader import source_sha
    from .sync_state import SyncStateError, asset_binding_for, baseline_for, load_state
    from .visual_materialization import VisualMaterializationError, verify_visual_binding
    from .writer import ContentWriteError


ASSET_POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")
VISUAL_MODES = {"stepik-image-upload", "rasterize-png-stepik-image"}
GOLDEN_IDS = {"M00-L01", "M00-L02"}


def _credentials() -> tuple[str, str]:
    client_id = os.getenv("STEPIC_CLIENT_ID", "").strip()
    client_secret = os.getenv("STEPIC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Для staging recovery нужны STEPIC_CLIENT_ID и STEPIC_CLIENT_SECRET")
    return client_id, client_secret


def _history_store(sha: str) -> GitHubHistoryStore:
    return GitHubHistoryStore(
        repository=os.getenv("GITHUB_REPOSITORY", ""),
        token=os.getenv("GITHUB_TOKEN", ""),
        source_sha=sha,
    )


def _manifest_lesson(manifest: dict[str, Any], target_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in manifest.get("modules", []):
        for lesson in module.get("lessons", []):
            if lesson.get("canonical_id") == target_id:
                return module, lesson
    raise ContentWriteError(f"В manifest отсутствует {target_id}")


def _live_lesson(snapshot: dict[str, Any], *, module_position: int, lesson_position: int) -> dict[str, Any]:
    sections = [item for item in snapshot.get("sections", []) if item.get("position") == module_position]
    if len(sections) != 1:
        raise ContentWriteError(f"Recovery: не найден exact section position={module_position}")
    units = [item for item in sections[0].get("units", []) if item.get("position") == lesson_position]
    if len(units) != 1 or not isinstance(units[0].get("lesson"), dict):
        raise ContentWriteError(f"Recovery: не найден exact target unit {module_position}/{lesson_position}")
    return units[0]["lesson"]


def _final_state(records: list[dict[str, Any]], *, label: str) -> tuple[dict[str, Any], str]:
    final = final_confirmed_record(records)
    if not isinstance(final, dict):
        raise DeploymentHistoryError(f"{label}: incomplete event не содержит FINAL_READBACK_CONFIRMED")
    status = final.get("status")
    state = final.get("actual_confirmed_state")
    if status not in {"APPLIED", "NOOP_CONFIRMED"} or not isinstance(state, dict):
        raise DeploymentHistoryError(f"{label}: final history не содержит допустимый status/baseline")
    return state, str(status)


def _event_artifact(identity: Any, *, status: str, kind: str, target_id: str, source_path: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": identity.event_id,
        "source_sha": identity.source_sha,
        "status": status,
        "kind": kind,
    }
    if kind == "asset":
        payload["source_path"] = source_path
    else:
        payload["canonical_id"] = target_id
    return payload


def _materialization_rows(asset_report: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in asset_report.get("resolutions", []):
        if row.get("lesson") != target_id or row.get("materialization_required_at_write") is not True:
            continue
        source_path = str(row.get("source_path") or "")
        if not source_path or row.get("mode") not in VISUAL_MODES:
            raise AssetResolutionError(f"{target_id}: recovery встретил неподдерживаемую physical dependency")
        rows[source_path] = row
    return [rows[key] for key in sorted(rows)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover Stepik staging machine-state/history commit gap without live write")
    parser.add_argument("--course-id", type=int, required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--sync-state", type=Path, required=True)
    parser.add_argument("--api-host", default="https://stepik.org")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report_dir = (repo_root / args.report_dir).resolve() if not args.report_dir.is_absolute() else args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    target_id = str(args.target_id).strip()
    sha = source_sha(repo_root)
    probe_path = report_dir / "commit-gap-recovery.json"

    try:
        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = load_state(state_path, course_id=args.course_id)
        baseline = baseline_for(state, target_id)
        if baseline is None:
            write_json(probe_path, {"applicable": False, "target_lesson": target_id, "reason": "lesson-baseline-absent"})
            return 0

        if target_id in GOLDEN_IDS:
            raise ContentWriteError("Staging commit-gap recovery не применяется к READ_ONLY_GOLDEN")
        if state.get("pending", {}).get("lessons", {}).get(target_id) is not None:
            raise SyncStateError(
                f"{target_id}: lesson baseline уже существует, но PENDING не закрыт; state противоречив, owner review required"
            )

        manifest = build_structural_manifest(repo_root, source_sha=sha)
        module, lesson_manifest = _manifest_lesson(manifest, target_id)
        expected_title = str(lesson_manifest["title"])
        client_id, client_secret = _credentials()
        client = StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(args.course_id)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False:
            raise ContentWriteError("Recovery разрешён только в private course")
        live_lesson = _live_lesson(
            snapshot,
            module_position=int(module["position"]),
            lesson_position=int(lesson_manifest["position"]),
        )
        if live_lesson.get("is_public") is not False or live_lesson.get("language") != "ru":
            raise ContentWriteError("Recovery target lesson перестал быть private/ru")
        if live_lesson.get("title") != expected_title:
            raise ContentWriteError("Recovery target title drifted относительно current canonical title")
        if int(baseline.get("stepik_lesson_id", -1)) != int(live_lesson.get("id", -2)):
            raise DeploymentHistoryError("Recovery lesson baseline относится к другому Stepik lesson")
        live_fp = live_lesson_fingerprint(live_lesson)
        if baseline.get("applied_fingerprint") != live_fp:
            raise DeploymentHistoryError("Recovery live lesson больше не совпадает с machine baseline")
        if baseline.get("applied_source_sha") != sha:
            raise DeploymentHistoryError("Recovery baseline относится не к current main SHA")

        store = _history_store(sha)
        incomplete_lessons = find_incomplete_object_events(store, object_id=target_id)
        if len(incomplete_lessons) != 1:
            raise DeploymentHistoryError(
                f"{target_id}: baseline существует, но найдено {len(incomplete_lessons)} incomplete lesson events вместо одного"
            )
        lesson_identity, lesson_records, lesson_summary = incomplete_lessons[0]
        if lesson_identity.source_sha != sha or lesson_identity.desired_fingerprint != live_fp:
            raise DeploymentHistoryError("Recovery lesson event identity не совпадает с current main/live fingerprint")
        if not lesson_summary.get("final_readback_confirmed") or lesson_summary.get("machine_state_committed"):
            raise DeploymentHistoryError("Recovery ожидает final-readback-confirmed event без MACHINE_STATE_COMMITTED")
        recovered_lesson, lesson_status = _final_state(lesson_records, label=target_id)
        if recovered_lesson != baseline:
            raise DeploymentHistoryError("Recovery lesson final history не совпадает с machine baseline")

        inventory = build_asset_inventory(repo_root, manifest)
        policy = load_asset_publication_policy(repo_root / ASSET_POLICY_PATH)
        asset_report = assess_asset_publication(
            repo_root=repo_root,
            inventory=inventory,
            policy=policy,
            course_id=args.course_id,
        )
        if asset_report.get("route_gate_passed") is not True or asset_report.get("blockers"):
            raise AssetResolutionError("Recovery asset publication gate не пройден")

        asset_artifacts: list[dict[str, Any]] = []
        for row in _materialization_rows(asset_report, target_id):
            source_path = str(row["source_path"])
            record = asset_binding_for(state, source_path)
            if record is None:
                raise DeploymentHistoryError(f"{source_path}: lesson baseline committed, но asset baseline отсутствует")
            verify_visual_binding(
                client,
                record,
                source_path=source_path,
                expected_source_sha256=str(row["source_sha256"]),
                expected_mode=str(row["mode"]),
                stepik_lesson_id=int(live_lesson["id"]),
            )
            incomplete_assets = find_incomplete_object_events(store, object_id=f"asset:{source_path}")
            if not incomplete_assets:
                continue
            if len(incomplete_assets) != 1:
                raise DeploymentHistoryError(f"{source_path}: несколько incomplete asset events")
            asset_identity, asset_records, asset_summary = incomplete_assets[0]
            if asset_identity.source_sha != sha:
                raise DeploymentHistoryError(f"{source_path}: incomplete asset event относится не к current main")
            if not asset_summary.get("final_readback_confirmed") or asset_summary.get("machine_state_committed"):
                raise DeploymentHistoryError(f"{source_path}: asset history gap имеет неожиданный phase state")
            recovered_asset, asset_status = _final_state(asset_records, label=source_path)
            if recovered_asset != record:
                raise DeploymentHistoryError(f"{source_path}: final asset history не совпадает с machine baseline")
            artifact = _event_artifact(
                asset_identity,
                status=asset_status,
                kind="asset",
                target_id=target_id,
                source_path=source_path,
            )
            asset_artifacts.append(artifact)
            safe_name = Path(source_path).name.replace(".", "-")
            write_json(report_dir / f"asset-deployment-event-{safe_name}.json", artifact)

        lesson_artifact = _event_artifact(
            lesson_identity,
            status=lesson_status,
            kind="lesson",
            target_id=target_id,
        )
        write_json(report_dir / "lesson-deployment-event.json", lesson_artifact)
        write_json(report_dir / "asset-deployment-events.json", {"events": asset_artifacts})
        write_json(report_dir / "sync-state.next.json", state)
        journal = "\n".join(
            [
                f"### STAGING_COMMIT_GAP_RECOVERY: `{target_id}`",
                "",
                f"- source main SHA: `{sha}`",
                f"- Stepik lesson ID: `{live_lesson['id']}`",
                f"- lesson event: `{lesson_identity.event_id}`",
                f"- asset events to commit: `{[item['event_id'] for item in asset_artifacts]}`",
                "- Stepik writes: `0`",
                "",
                "Machine state уже содержит final read-back baseline; recovery завершает только durable MACHINE_STATE_COMMITTED boundary.",
            ]
        ) + "\n"
        (report_dir / "sync-journal.md").write_text(journal, encoding="utf-8")
        write_json(
            report_dir / "run-report.json",
            {
                "mode": "staging-commit-gap-recovery",
                "source_main_sha": sha,
                "course_id": args.course_id,
                "target_lesson": target_id,
                "verdict": "RECOVERY_READY",
                "stepik_writes": 0,
                "lesson_event_id": lesson_identity.event_id,
                "asset_event_ids": [item["event_id"] for item in asset_artifacts],
                "blockers": [],
            },
        )
        write_json(
            probe_path,
            {
                "applicable": True,
                "target_lesson": target_id,
                "verdict": "RECOVERY_READY",
                "stepik_writes": 0,
            },
        )
        return 0
    except (
        RuntimeError,
        StepikAPIError,
        CanonicalBuildError,
        ContentWriteError,
        AssetResolutionError,
        DeploymentHistoryError,
        SyncStateError,
        VisualMaterializationError,
    ) as exc:
        write_json(
            probe_path,
            {
                "applicable": True,
                "target_lesson": target_id,
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "stepik_writes": 0,
            },
        )
        print(f"STAGING RECOVERY BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
