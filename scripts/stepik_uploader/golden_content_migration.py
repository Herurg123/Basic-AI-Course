from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import stepik_uploader.golden_content_migration_7to8 as legacy
else:
    from . import golden_content_migration_7to8 as legacy


# Keep the public/test surface stable while isolating the one-time 7→8 writer.
COURSE_ID = legacy.COURSE_ID
TARGET_ID = legacy.TARGET_ID
GOLDEN_PROFILE_PATH = legacy.GOLDEN_PROFILE_PATH
ASSET_POLICY_PATH = legacy.ASSET_POLICY_PATH
GoldenContentMigrationError = legacy.GoldenContentMigrationError
_fixture_fingerprint = legacy._fixture_fingerprint
_history_state = legacy._history_state
_next_profile = legacy._next_profile


def _current_fixture_noop(args: Any, profile: dict[str, Any]) -> int:
    """Confirm an already accepted 8-step golden fixture without Stepik writes.

    Once the post-release fixture PR has replaced the old 7-step observation,
    this entrypoint must remain reusable.  The current-fixture path therefore
    proves canonical == fixture == live == machine baseline and records a normal
    NOOP_CONFIRMED event only when --confirm-write is explicit.
    """
    repo_root = args.repo_root.resolve()
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    sha = legacy.source_sha(repo_root)
    report: dict[str, Any] = {
        "mode": "golden-content-migration",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": sha,
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
        "fixture_state": "already-8-step-current",
    }
    try:
        if args.course_id != COURSE_ID:
            raise GoldenContentMigrationError(
                f"golden content migration разрешён только для course_id={COURSE_ID}"
            )

        manifest = legacy.build_structural_manifest(repo_root, source_sha=sha)
        _module, target_manifest = legacy._manifest_target(manifest)
        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        if not isinstance(observed, dict) or int(observed.get("step_count", -1)) != 8:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: current-fixture no-op разрешён только для подтверждённого 8-step golden"
            )

        desired_steps, asset_report = legacy._compile_desired(repo_root, manifest, profile)
        if len(desired_steps) != 8 or len(target_manifest.get("steps", [])) != 8:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: canonical после принятия fixture должен содержать ровно 8 steps"
            )
        expected_title = str(target_manifest["title"])
        desired_fp = legacy.compiled_lesson_fingerprint(
            expected_title=expected_title,
            expected_steps=desired_steps,
        )
        legacy.write_json(report_dir / "asset-report.json", asset_report)

        state_path = args.sync_state if args.sync_state.is_absolute() else repo_root / args.sync_state
        state = legacy.load_state(state_path, course_id=COURSE_ID)
        pending = state.get("pending", {}).get("lessons", {}).get(TARGET_ID)
        existing_baseline = legacy.baseline_for(state, TARGET_ID)
        if pending is not None:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: 8-step golden fixture уже принят, но lesson всё ещё PENDING"
            )
        if not isinstance(existing_baseline, dict):
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: 8-step golden fixture требует confirmed machine baseline"
            )
        if len(existing_baseline.get("step_ids", [])) != 8:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: machine baseline не подтверждает 8 step IDs"
            )

        client_id, client_secret = legacy._credentials()
        client = legacy.StepikClient(client_id, client_secret, api_host=args.api_host)
        snapshot = client.inspect_course(COURSE_ID)
        legacy.write_json(report_dir / "course-snapshot.before.json", snapshot)
        course = snapshot.get("course", {})
        if course.get("is_public") is not False or course.get("language") != "ru":
            raise GoldenContentMigrationError(
                "Golden current-fixture confirmation разрешён только в private ru course"
            )
        fixture_blockers = legacy.validate_golden_profile(profile, snapshot)
        if fixture_blockers:
            raise legacy.GoldenProfileError(
                "Принятый 8-step golden fixture больше не совпадает с live: "
                + "; ".join(fixture_blockers)
            )

        lesson = legacy._live_target(snapshot, lesson_id=int(observed["stepik_lesson_id"]))
        if (
            lesson.get("title") != expected_title
            or lesson.get("is_public") is not False
            or lesson.get("language") != "ru"
        ):
            raise GoldenContentMigrationError(f"{TARGET_ID}: live metadata drift")
        live_fp = legacy.live_lesson_fingerprint(lesson)
        if live_fp != desired_fp:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: canonical, accepted fixture и live не образуют exact 8-step no-op"
            )
        final_ids = [
            int(item["step_source"]["id"])
            for item in sorted(
                lesson.get("steps", []),
                key=lambda item: int(item["step_source"]["position"]),
            )
        ]
        if final_ids != [int(value) for value in existing_baseline.get("step_ids", [])]:
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: live step IDs drifted относительно machine baseline"
            )
        if int(existing_baseline.get("stepik_lesson_id", -1)) != int(lesson["id"]):
            raise GoldenContentMigrationError(
                f"{TARGET_ID}: live lesson ID drifted относительно machine baseline"
            )

        source_paths = [path for step in desired_steps for path in step.source_git_paths]
        baseline = legacy.build_record(
            canonical_id=TARGET_ID,
            stepik_lesson_id=int(lesson["id"]),
            expected_title=expected_title,
            expected_steps=desired_steps,
            source_sha=sha,
            step_ids=final_ids,
            source_git_paths=source_paths,
        )
        baseline["confirmation_status"] = "NOOP_CONFIRMED"
        next_state = legacy.with_record(state, canonical_id=TARGET_ID, record=baseline)

        plan = {
            "old_fixture_steps": 8,
            "desired_steps": 8,
            "changed_existing_positions": [],
            "append_position": None,
            "desired_fingerprint": desired_fp,
            "live_fingerprint": live_fp,
            "history_state": "CURRENT_FIXTURE_NOOP",
            "deletes_allowed": False,
            "reorder_allowed": False,
        }
        legacy.write_json(report_dir / "migration-plan.json", plan)
        if not args.confirm_write:
            report.update(
                {
                    "verdict": "READY",
                    "status": "ALREADY_CURRENT",
                    "plan": plan,
                    "stepik_writes_planned": 0,
                    "readback_verified": True,
                    "blockers": [],
                }
            )
            legacy.write_json(report_dir / "run-report.json", report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        identity = legacy.event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=TARGET_ID,
            kind="golden-content-migration",
            source_sha=sha,
            desired_fingerprint=desired_fp,
            baseline_fingerprint=_fixture_fingerprint(profile),
            pending_first_sha=None,
        )
        store = legacy._history_store(sha)
        records = store.load(identity.event_id)
        history_state, recovered_baseline = _history_state(records, live_fp, desired_fp)
        if history_state == "FINAL_PROVEN":
            if not isinstance(recovered_baseline, dict):
                raise legacy.DeploymentHistoryError(
                    f"{TARGET_ID}: final NOOP history не содержит baseline"
                )
            baseline = recovered_baseline
            next_state = legacy.with_record(state, canonical_id=TARGET_ID, record=baseline)
        elif history_state in {"NEW", "STARTED_BEFORE_WRITE"}:
            recorder = legacy.DeploymentRecorder(store, identity)
            recorder.ensure_started(
                operation_type="golden-content-already-current-noop",
                state_before={"fixture_fingerprint": _fixture_fingerprint(profile)},
                expected_state={"desired_fingerprint": desired_fp, "step_count": 8},
                stepik_object_ids={"lesson_id": int(lesson["id"])},
                fingerprint_before=live_fp,
            )
            recorder.final_readback(
                fingerprint_after=live_fp,
                stepik_object_ids={"lesson_id": int(lesson["id"]), "step_ids": final_ids},
                status="NOOP_CONFIRMED",
                baseline_after=baseline,
            )
        else:
            raise legacy.DeploymentHistoryError(
                f"{TARGET_ID}: unexpected history state для current-fixture no-op: {history_state}"
            )

        legacy.write_json(report_dir / "golden-profile.next.json", deepcopy(profile))
        legacy.write_json(report_dir / "sync-state.next.json", next_state)
        legacy.write_json(
            report_dir / "golden-deployment-event.json",
            legacy._event_artifact(identity, baseline, "NOOP_CONFIRMED"),
        )
        (report_dir / "sync-journal.md").write_text(
            "\n".join(
                [
                    f"### GOLDEN_CONTENT_CONFIRMATION: `{TARGET_ID}`",
                    "",
                    f"- source main SHA: `{sha}`",
                    f"- Stepik lesson ID: `{lesson['id']}`",
                    "- accepted golden fixture: `8 steps`",
                    "- Stepik writes: `0`",
                    f"- event: `{identity.event_id}`",
                    f"- fingerprint: `{live_fp}`",
                    f"- step IDs: `{final_ids}`",
                    "",
                    "Current canonical, accepted golden fixture, live lesson and machine baseline were confirmed exact; no Stepik mutation was performed.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        report.update(
            {
                "verdict": "PASS",
                "status": "NOOP_CONFIRMED",
                "event_id": identity.event_id,
                "rendered_steps": 8,
                "step_ids": final_ids,
                "readback_verified": True,
                "golden_profile_update_required_after_run": False,
                "blockers": [],
            }
        )
        legacy.write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (
        GoldenContentMigrationError,
        legacy.GoldenProfileError,
        legacy.CanonicalBuildError,
        legacy.GeneralContentCompileError,
        legacy.AssetResolutionError,
        legacy.VerifiedRenderingError,
        legacy.DeploymentHistoryError,
        legacy.StepikAPIError,
        legacy.SyncStateError,
        OSError,
        ValueError,
    ) as exc:
        report.update(
            {
                "verdict": "BLOCKED",
                "blockers": [str(exc)],
                "write_retry_policy": "no blind retry; inspect durable history and live state",
            }
        )
        legacy.write_json(report_dir / "run-report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2


def main() -> int:
    args = legacy.parse_args()
    repo_root = args.repo_root.resolve()
    try:
        profile = legacy.load_golden_profile(repo_root / GOLDEN_PROFILE_PATH)
        observed = profile.get("golden_lessons", {}).get(TARGET_ID)
        step_count = int(observed.get("step_count", -1)) if isinstance(observed, dict) else -1
    except (legacy.GoldenProfileError, OSError, ValueError, TypeError):
        # Let the proven legacy route produce its normal fail-closed report.
        return legacy.main()

    if step_count == 7:
        return legacy.main()
    if step_count == 8:
        return _current_fixture_noop(args, profile)

    # Any other fixture shape is outside the owner-approved migration contract.
    report_dir = args.report_dir if args.report_dir.is_absolute() else repo_root / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "golden-content-migration",
        "course_id": args.course_id,
        "target": TARGET_ID,
        "source_main_sha": legacy.source_sha(repo_root),
        "confirm_write": bool(args.confirm_write),
        "stepik_writes": 0,
        "verdict": "BLOCKED",
        "blockers": [
            f"{TARGET_ID}: supported golden fixture step_count is only 7 (migration) or 8 (confirmed current), got {step_count}"
        ],
    }
    legacy.write_json(report_dir / "run-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
