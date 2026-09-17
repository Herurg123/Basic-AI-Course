from __future__ import annotations

import copy
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.content import CompiledStep
from scripts.stepik_uploader.deployment_history import DeploymentRecorder, EventIdentity, MemoryHistoryStore, summarize_event
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint, live_lesson_fingerprint
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.sync_state import assess_sync
from scripts.stepik_uploader.transport_equivalence import (
    lesson_transport_equivalent,
    normalize_stepik_transport_html,
    step_transport_equivalent,
)
from scripts.stepik_uploader.verified_rendering import AssetBinding, build_rendering_plan, require_render_ready


class TransportEquivalenceTests(unittest.TestCase):
    def _step(self, html: str, *, position: int = 1, source: dict | None = None) -> CompiledStep:
        return CompiledStep(
            position=position,
            block_name="text",
            text=html,
            source=source or {},
            source_git_paths=("04_course/test.md",),
        )

    def _live_item(self, step: CompiledStep, html: str, *, source: dict | None = None) -> dict:
        return {
            "step_source": {
                "id": 100 + int(step.position),
                "position": int(step.position),
                "block": {
                    "name": step.block_name,
                    "text": html,
                    "source": copy.deepcopy(step.source if source is None else source),
                },
            }
        }

    def _lesson(self, title: str, items: list[dict]) -> dict:
        return {
            "id": 2591999,
            "title": title,
            "language": "ru",
            "is_public": False,
            "steps": items,
        }

    def test_observed_stepik_rewrites_are_transport_equivalent_but_strict_fingerprint_can_differ(self) -> None:
        expected = self._step(
            '<p>Первая строка\nВторая строка</p><table><tr><td style="text-align:right">x<br /></td></tr></table><hr>'
        )
        live_html = normalize_stepik_transport_html(expected.text)
        live_item = self._live_item(expected, live_html)
        self.assertTrue(step_transport_equivalent(live_item, expected))

        expected_lesson = self._lesson("Тест", [self._live_item(expected, expected.text)])
        live_lesson = self._lesson("Тест", [live_item])
        desired_fp = compiled_lesson_fingerprint(expected_title="Тест", expected_steps=[expected])
        live_fp = live_lesson_fingerprint(live_lesson)
        self.assertNotEqual(desired_fp, live_fp)
        self.assertTrue(
            lesson_transport_equivalent(
                live_lesson,
                expected_title="Тест",
                expected_steps=[expected],
            )
        )

    def test_text_change_is_not_transport_equivalent(self) -> None:
        expected = self._step("<p>Сохраните безопасную копию.</p>")
        live = self._live_item(expected, "<p>Удалите исходный файл.</p>")
        self.assertFalse(step_transport_equivalent(live, expected))

    def test_link_change_is_not_transport_equivalent(self) -> None:
        expected = self._step('<p><a href="https://example.org/a">Материал</a></p>')
        live = self._live_item(expected, '<p><a href="https://example.org/b">Материал</a></p>')
        self.assertFalse(step_transport_equivalent(live, expected))

    def test_block_source_change_is_not_transport_equivalent(self) -> None:
        expected = self._step("<p>Ответ</p>", source={"is_always_correct": True})
        live = self._live_item(expected, expected.text, source={"is_always_correct": False})
        self.assertFalse(step_transport_equivalent(live, expected))

    def test_attributed_horizontal_rule_is_not_silently_removed(self) -> None:
        expected = self._step('<p>До</p><hr class="meaningful"><p>После</p>')
        live = self._live_item(expected, "<p>До</p><p>После</p>")
        self.assertFalse(step_transport_equivalent(live, expected))

    def test_legacy_baseline_stays_in_sync_when_only_stepik_transport_representation_changes(self) -> None:
        expected = self._step('<p>А\nБ</p><p>Строка<br /></p>')
        live = self._lesson("Урок", [self._live_item(expected, normalize_stepik_transport_html(expected.text))])
        desired = compiled_lesson_fingerprint(expected_title="Урок", expected_steps=[expected])
        live_fp = live_lesson_fingerprint(live)
        self.assertNotEqual(desired, live_fp)
        baseline = {
            "canonical_id": "M99-L01",
            "stepik_lesson_id": live["id"],
            "applied_fingerprint": desired,
        }
        assessment = assess_sync(
            canonical_id="M99-L01",
            live_lesson=live,
            expected_title="Урок",
            expected_steps=[expected],
            baseline=baseline,
        )
        self.assertEqual(assessment.status, "IN_SYNC")
        self.assertEqual(assessment.changed_step_positions, ())

    def test_confirmed_live_baseline_allows_real_canonical_update_but_manual_drift_still_blocks(self) -> None:
        old = self._step('<p>Старый текст<br /></p>')
        old_live = self._lesson("Урок", [self._live_item(old, normalize_stepik_transport_html(old.text))])
        old_desired = compiled_lesson_fingerprint(expected_title="Урок", expected_steps=[old])
        old_live_fp = live_lesson_fingerprint(old_live)
        baseline = {
            "canonical_id": "M99-L01",
            "stepik_lesson_id": old_live["id"],
            "applied_fingerprint": old_desired,
            "confirmed_live_fingerprint": old_live_fp,
        }
        new = self._step('<p>Новый текст<br /></p>')
        update = assess_sync(
            canonical_id="M99-L01",
            live_lesson=old_live,
            expected_title="Урок",
            expected_steps=[new],
            baseline=baseline,
        )
        self.assertEqual(update.status, "UPDATE_REQUIRED")
        self.assertEqual(update.changed_step_positions, (1,))

        drift = copy.deepcopy(old_live)
        drift["steps"][0]["step_source"]["block"]["text"] = "<p>Ручная правка</p>"
        blocked = assess_sync(
            canonical_id="M99-L01",
            live_lesson=drift,
            expected_title="Урок",
            expected_steps=[new],
            baseline=baseline,
        )
        self.assertEqual(blocked.status, "DRIFT_BLOCKED")

    def test_history_keeps_expected_identity_and_separately_exposes_observed_live_fingerprint(self) -> None:
        expected_fp = "sha256:" + "a" * 64
        observed_fp = "sha256:" + "b" * 64
        identity = EventIdentity(
            event_id="evt-" + "1" * 32,
            course_id=299189,
            object_id="M99-L01",
            kind="lesson",
            source_sha="1" * 40,
            workflow_run_id="1",
            workflow_run_attempt="1",
            workflow_run_url=None,
            desired_fingerprint=expected_fp,
            baseline_fingerprint_before=None,
            pending_first_sha="1" * 40,
        )
        store = MemoryHistoryStore()
        recorder = DeploymentRecorder(store, identity)
        recorder.operation_readback(
            operation_id="step-create-0001",
            expected_fingerprint_after=expected_fp,
            observed_live_fingerprint=observed_fp,
        )
        recorder.final_readback(
            fingerprint_after=expected_fp,
            observed_live_fingerprint=observed_fp,
            stepik_object_ids={"lesson_id": 1, "step_ids": [2]},
            status="NOOP_CONFIRMED",
            baseline_after={"applied_fingerprint": expected_fp, "confirmed_live_fingerprint": observed_fp},
        )
        summary = summarize_event(recorder.records(refresh=True))
        self.assertEqual(summary["final_fingerprint"], expected_fp)
        self.assertEqual(summary["final_live_fingerprint"], observed_fp)
        self.assertEqual(summary["last_confirmed_operation_expected_fingerprint"], expected_fp)
        self.assertEqual(summary["last_confirmed_operation_fingerprint"], observed_fp)

    def test_all_current_course_lessons_accept_only_transport_rewrites(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = build_structural_manifest(repo_root, source_sha="transport-equivalence-course-test")
        lessons = {
            str(lesson["canonical_id"]): lesson
            for module in manifest["modules"]
            for lesson in module["lessons"]
        }
        compiled = compile_all_lesson_sources(
            repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=list(lessons),
        )
        inventory = build_asset_inventory(repo_root, manifest)
        policy = load_asset_publication_policy(repo_root / "04_course/stepik/automation/asset-publication.v1.json")
        asset_report = assess_asset_publication(
            repo_root=repo_root,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )
        bindings: dict[str, AssetBinding] = {}
        for row in asset_report["resolutions"]:
            if row.get("materialization_required_at_write") is not True:
                continue
            source_path = str(row["source_path"])
            if source_path in bindings:
                continue
            filename = Path(source_path).name
            if row["mode"] == "rasterize-png-stepik-image":
                filename = Path(filename).stem + ".png"
            bindings[source_path] = AssetBinding(
                source_path=source_path,
                source_sha256=str(row["source_sha256"]),
                url=f"https://stepik.org/media/attachments/lesson/999999/{filename}",
                storage="test-only-synthetic-stepik-binding",
                verified=True,
            )

        strict_delta_lessons: set[str] = set()
        for lesson_id, lesson in lessons.items():
            plan = build_rendering_plan(
                repo_root=repo_root,
                lesson_id=lesson_id,
                source_steps=compiled[lesson_id],
                asset_report=asset_report,
                bindings=list(bindings.values()),
            )
            steps = list(require_render_ready(plan))
            live_items: list[dict] = []
            for step in steps:
                rewritten = normalize_stepik_transport_html(step.text)
                if rewritten != step.text:
                    strict_delta_lessons.add(lesson_id)
                live_items.append(self._live_item(step, rewritten))
            live_lesson = {
                "id": 900000 + int(lesson_id[1:3]) * 100 + int(lesson_id[-2:]),
                "title": str(lesson["title"]),
                "language": "ru",
                "is_public": False,
                "steps": live_items,
            }
            self.assertTrue(
                lesson_transport_equivalent(
                    live_lesson,
                    expected_title=str(lesson["title"]),
                    expected_steps=steps,
                ),
                lesson_id,
            )

        # M06-L02 is already rendered through the proven v2 writer contract, so the
        # generic transport layer has no additional strict delta there. These are the
        # remaining current lessons whose strict HTML representation can differ while
        # the learner-visible content remains transport-equivalent.
        self.assertEqual(strict_delta_lessons, {"M01-L01", "M01-L02", "M06-L04"})


if __name__ == "__main__":
    unittest.main()
