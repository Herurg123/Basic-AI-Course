from __future__ import annotations

import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.verified_rendering import build_rendering_plan


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "04_course" / "stepik" / "automation" / "asset-publication.v1.json"


class B6SemanticRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_structural_manifest(ROOT, source_sha="b6-semantic-route-test")
        lesson_ids = [
            str(lesson["canonical_id"])
            for module in cls.manifest["modules"]
            for lesson in module["lessons"]
        ]
        cls.compiled = compile_all_lesson_sources(
            ROOT,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=lesson_ids,
        )
        inventory = build_asset_inventory(ROOT, cls.manifest)
        policy = load_asset_publication_policy(POLICY)
        cls.asset_report = assess_asset_publication(
            repo_root=ROOT,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )

    def _rendered(self, lesson_id: str):
        return build_rendering_plan(
            repo_root=ROOT,
            lesson_id=lesson_id,
            source_steps=self.compiled[lesson_id],
            asset_report=self.asset_report,
        ).rendered_steps

    def test_m07_l01_remains_rehearsal_and_keeps_change_after_application(self) -> None:
        steps = self._rendered("M07-L01")
        self.assertEqual(len(steps), 7)
        self.assertEqual(
            [step.block_name for step in steps],
            ["text", "text", "text", "text", "text", "free-answer", "text"],
        )
        self.assertIn("M07-L01-E01", steps[2].exercise_ids)
        self.assertIn("Учебная доска сообщений", steps[2].text)
        self.assertNotIn("начало переносится на 14:30", steps[2].text)
        self.assertIn("начало переносится на 14:30", steps[4].text)
        self.assertIn("не сам F1", steps[0].text)

    def test_m07_l02_f1_rubric_does_not_leak_before_attempt(self) -> None:
        steps = self._rendered("M07-L02")
        self.assertEqual(len(steps), 8)
        self.assertEqual(
            [step.block_name for step in steps],
            ["text", "text", "text", "text", "text", "free-answer", "text", "text"],
        )
        pre_check = "\n".join(step.text for step in steps[:5])
        self.assertNotIn("Авторская рубрика финальной работы", pre_check)
        self.assertNotIn("Как вы понимали, что результат подходит", pre_check)
        self.assertNotIn("Как вы оценили первую или промежуточную версию", pre_check)

        full = "\n".join(step.text for step in steps)
        self.assertNotIn("M07-L02-A02", full)
        self.assertNotIn("Авторская рубрика финальной работы", full)

    def test_m07_l02_a03_is_post_action_and_covers_sem117(self) -> None:
        steps = self._rendered("M07-L02")
        check = steps[5]
        self.assertEqual(check.block_name, "free-answer")
        self.assertEqual(check.check_ids, ("M07-L02-C01",))
        self.assertIn("Как вы понимали, что результат подходит", check.text)
        self.assertIn("Как вы оценили первую или промежуточную версию", check.text)
        self.assertIn("Отдельная заранее заполненная форма не требовалась", check.text)

    def test_m07_l02_recovery_covers_contamination_and_not_proven_without_ready_case(self) -> None:
        steps = self._rendered("M07-L02")
        recovery = steps[6].text
        self.assertIn("содержательная подсказка", recovery)
        self.assertIn("не подтверждается", recovery)
        self.assertIn("другую собственную новую посильную реальную задачу", recovery)
        self.assertIn("/lesson/2591731/step/6", recovery)
        self.assertNotIn("готовый запасной", recovery)
        self.assertIn("Успешную самостоятельную попытку повторять не нужно", recovery)

    def test_m08_is_reflection_only_and_requires_no_new_ai_work(self) -> None:
        steps = self._rendered("M08-L01")
        self.assertEqual(len(steps), 6)
        self.assertEqual(
            [step.block_name for step in steps],
            ["text", "text", "text", "text", "free-answer", "text"],
        )
        combined = "\n".join(step.text for step in steps)
        self.assertIn("не второй экзамен", combined)
        self.assertIn("Выполнять эту задачу сейчас", combined)
        self.assertIn("не нужно", combined)
        self.assertNotIn("alice.yandex.ru", combined)
        self.assertNotIn("giga.chat", combined)


if __name__ == "__main__":
    unittest.main()
