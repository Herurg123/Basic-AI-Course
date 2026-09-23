from __future__ import annotations

import re
import unittest
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.verified_rendering import (
    AssetBinding,
    MaterializationRequired,
    build_rendering_plan,
    normalize_stepik_html,
    normalize_stepik_html_v1,
    require_render_ready,
)

REPO_LINK_RE = re.compile(r'href=["\'](?!https?://|mailto:|#)[^"\']+["\']')


class VerifiedRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.manifest = build_structural_manifest(cls.repo_root, source_sha="verified-rendering-test")
        cls.lesson_ids = [
            str(lesson["canonical_id"])
            for module in cls.manifest["modules"]
            for lesson in module["lessons"]
        ]
        cls.compiled = compile_all_lesson_sources(
            cls.repo_root,
            free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
            lesson_ids=cls.lesson_ids,
        )
        inventory = build_asset_inventory(cls.repo_root, cls.manifest)
        policy = load_asset_publication_policy(
            cls.repo_root / "04_course/stepik/automation/asset-publication.v1.json"
        )
        cls.asset_report = assess_asset_publication(
            repo_root=cls.repo_root,
            inventory=inventory,
            policy=policy,
            course_id=299189,
        )

    def _synthetic_bindings(self) -> list[AssetBinding]:
        bindings: dict[str, AssetBinding] = {}
        for row in self.asset_report["resolutions"]:
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
        return list(bindings.values())

    def test_without_runtime_bindings_exactly_five_unique_sources_require_materialization(self) -> None:
        requirements: dict[str, dict] = {}
        rendered_count = 0
        for lesson_id in self.lesson_ids:
            plan = build_rendering_plan(
                repo_root=self.repo_root,
                lesson_id=lesson_id,
                source_steps=self.compiled[lesson_id],
                asset_report=self.asset_report,
            )
            rendered_count += len(plan.rendered_steps)
            for item in plan.materialization_requirements:
                requirements[str(item["source_path"])] = item

        self.assertEqual(rendered_count, 148)
        self.assertEqual(
            set(requirements),
            {
                "05_assets/M03/M03-L02/M03-L02-A03-alice.png",
                "05_assets/M03/M03-L02/M03-L02-A03.png",
                "05_assets/M04/M04-L01/M04-L01-A01.txt",
                "05_assets/M04/M04-L02/M04-L02-A02.svg",
                "05_assets/M05/M05-L01/M05-L01-A02.svg",
            },
        )

    def test_all_21_lessons_render_with_verified_test_bindings_and_no_repo_relative_links(self) -> None:
        bindings = self._synthetic_bindings()
        total_steps = 0
        for lesson_id in self.lesson_ids:
            plan = build_rendering_plan(
                repo_root=self.repo_root,
                lesson_id=lesson_id,
                source_steps=self.compiled[lesson_id],
                asset_report=self.asset_report,
                bindings=bindings,
            )
            steps = require_render_ready(plan)
            total_steps += len(steps)
            for step in steps:
                self.assertIsNone(REPO_LINK_RE.search(step.text), f"{lesson_id} step {step.position}")
                self.assertNotIn("../../../", step.text)
                self.assertNotIn("../../stepik/", step.text)
                self.assertNotRegex(step.text, r"(?i)<hr\s*/?>")
        self.assertEqual(total_steps, 148)

    def test_m02_l01_material_card_does_not_depend_on_horizontal_rule(self) -> None:
        normalized = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M02-L01",
            source_steps=self.compiled["M02-L01"],
            asset_report=self.asset_report,
        )
        legacy = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M02-L01",
            source_steps=self.compiled["M02-L01"],
            asset_report=self.asset_report,
            apply_stepik_html_normalization=False,
        )
        legacy_html = "\n".join(step.text for step in legacy.rendered_steps)
        normalized_html = "\n".join(step.text for step in normalized.rendered_steps)
        self.assertNotRegex(legacy_html, r"(?i)<hr\s*/?>")
        self.assertNotRegex(normalized_html, r"(?i)<hr\s*/?>")
        self.assertEqual(
            [normalize_stepik_html_v1(step.text).strip() for step in legacy.rendered_steps],
            [step.text for step in normalized.rendered_steps],
        )

    def test_v1_normalizer_remains_frozen_for_immutable_event_reconstruction(self) -> None:
        raw = '<p>a\nb</p><hr /><br /><td style="text-align:right">1</td>'
        self.assertEqual(
            normalize_stepik_html_v1(raw),
            '<p>a\nb</p><br /><td style="text-align:right">1</td>',
        )

    def test_v2_normalizer_matches_observed_m06_stepik_canonicalization(self) -> None:
        raw = (
            '<p>Откройте <a href="https://example.invalid/source">карточку</a>.\n'
            'Там есть исходные данные и подготовленный расчёт.\n'
            'Сами выберите, какое число нужно проверить:</p>\n'
            '<hr />\n'
            '<table>\n<tr>\n<td style="text-align:right">4</td>\n</tr>\n</table>\n'
            '<blockquote>\n<p>Строка 1<br />\nСтрока 2</p>\n</blockquote>'
        )
        expected = (
            '<p>Откройте <a href="https://example.invalid/source">карточку</a>.</p>\n'
            '<p>Там есть исходные данные и подготовленный расчёт.</p>\n'
            '<p>Сами выберите, какое число нужно проверить:</p>\n\n'
            '<table>\n<tr>\n<td style="text-align:right;">4</td>\n</tr>\n</table>\n'
            '<blockquote>\n<p>Строка 1<br>\nСтрока 2</p>\n</blockquote>'
        )
        self.assertEqual(normalize_stepik_html(raw), expected)

    def test_v2_normalizer_does_not_broaden_unproven_markup(self) -> None:
        raw = (
            '<p>a\nb</p><hr class="keep"><p>x<br />\ny</p>'
            '<div style="text-align:right">keep</div>'
            '<td style="color:red;text-align:right">keep</td>'
        )
        normalized = normalize_stepik_html(raw)
        self.assertEqual(
            normalized,
            '<p>a</p>\n<p>b</p><hr class="keep"><p>x<br>\ny</p>'
            '<div style="text-align:right;">keep</div>'
            '<td style="color:red;text-align:right">keep</td>',
        )

    def test_m06_l02_real_step2_uses_stepik_v2_canonical_html(self) -> None:
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M06-L02",
            source_steps=self.compiled["M06-L02"],
            asset_report=self.asset_report,
        )
        step2 = plan.rendered_steps[1].text
        self.assertIn("<p>В самой карточке находятся данные, расчёт и задание.", step2)
        self.assertIn("<strong>Материал: Исходные данные и подготовленный расчёт</strong>", step2)
        self.assertIn("<blockquote>", step2)
        self.assertIn("</blockquote>", step2)
        self.assertIn('style="text-align:right;"', step2)
        self.assertIn("<br>", step2)
        self.assertNotIn("<br />", step2)
        self.assertNotRegex(step2, r"(?i)<hr\s*/?>")

    def test_m04_l01_requires_only_txt_before_materialization_and_keeps_author_key_hidden(self) -> None:
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M04-L01",
            source_steps=self.compiled["M04-L01"],
            asset_report=self.asset_report,
        )
        self.assertEqual(len(plan.rendered_steps), 6)
        self.assertEqual(
            [item["source_path"] for item in plan.materialization_requirements],
            ["05_assets/M04/M04-L01/M04-L01-A01.txt"],
        )
        self.assertEqual([step.block_name for step in plan.rendered_steps], ["text", "text", "text", "text", "free-answer", "text"])
        combined = "\n".join(step.text for step in plan.rendered_steps)
        self.assertNotIn("M04-L01-A02", combined)
        self.assertNotIn("M04-L01-A02.md", "\n".join(plan.dependency_source_paths))
        with self.assertRaises(MaterializationRequired):
            require_render_ready(plan)

    def test_m04_l01_verified_txt_binding_produces_real_link_and_render_ready_steps(self) -> None:
        row = next(
            item for item in self.asset_report["resolutions"]
            if item["source_path"] == "05_assets/M04/M04-L01/M04-L01-A01.txt"
        )
        binding = AssetBinding(
            source_path=str(row["source_path"]),
            source_sha256=str(row["source_sha256"]),
            url="https://stepik.org/media/attachments/lesson/2591724/M04-L01-A01.txt",
            storage="test-only-synthetic-stepik-binding",
            verified=True,
        )
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M04-L01",
            source_steps=self.compiled["M04-L01"],
            asset_report=self.asset_report,
            bindings=[binding],
        )
        steps = require_render_ready(plan)
        self.assertEqual(len(steps), 6)
        self.assertIn(binding.url, steps[1].text)
        self.assertEqual(steps[4].block_name, "free-answer")
        self.assertIn("В поле Stepik", steps[4].text)
        self.assertIn("найденные сведения относятся к выбранному утверждению", steps[4].text)
        self.assertNotIn("будет доступен после verified materialization", "\n".join(step.text for step in steps))

    def test_m05_l01_human_review_material_is_structurally_separated(self) -> None:
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M05-L01",
            source_steps=self.compiled["M05-L01"],
            asset_report=self.asset_report,
        )
        step2 = plan.rendered_steps[1].text
        self.assertIn("<strong>Материал: Картинка для вечера настольных игр</strong>", step2)
        self.assertIn("<blockquote>", step2)
        self.assertIn("</blockquote>", step2)
        self.assertIn("до просмотра готовых вариантов", step2.lower())
        self.assertLess(
            step2.index("<blockquote>"),
            step2.lower().index("после чтения"),
        )
        material_html = step2[step2.index("<blockquote>"):step2.index("</blockquote>")]
        self.assertNotIn("учебной заметке", material_html)
        self.assertNotIn("признака", material_html)

    def test_inline_markdown_is_placed_immediately_after_reference_paragraph(self) -> None:
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M01-L01",
            source_steps=self.compiled["M01-L01"],
            asset_report=self.asset_report,
        )
        step2 = plan.rendered_steps[1].text
        self.assertIn("мини-задачу", step2)
        self.assertIn("<strong>Материал: Короткое напоминание о встрече</strong>", step2)
        self.assertIn("<blockquote>", step2)
        self.assertIn("</blockquote>", step2)
        self.assertNotIn("M01-L01-A01 —", step2)
        self.assertIn("18:30", step2)
        self.assertLess(step2.index("Материал:"), step2.index("После чтения"))
        self.assertNotIn("STEPIK_INLINE_MATERIAL_", step2)

    def test_nested_m06_dependency_is_recursively_inlined_without_repo_link(self) -> None:
        plan = build_rendering_plan(
            repo_root=self.repo_root,
            lesson_id="M06-L04",
            source_steps=self.compiled["M06-L04"],
            asset_report=self.asset_report,
        )
        step3 = plan.rendered_steps[2]
        self.assertIn("05_assets/M06/M06-L04/M06-L04-A01.md", step3.source_git_paths)
        self.assertIn("05_assets/M06/M06-L04/M06-L04-A02.md", step3.source_git_paths)
        self.assertNotIn("M06-L04-A02.md)", step3.text)
        self.assertIn("Материал:", step3.text)
        self.assertGreaterEqual(step3.text.count("<blockquote>"), 2)

    def test_binding_with_stale_source_hash_is_rejected(self) -> None:
        binding = AssetBinding(
            source_path="05_assets/M04/M04-L01/M04-L01-A01.txt",
            source_sha256="sha256:" + "0" * 64,
            url="https://stepik.org/media/attachments/lesson/2591724/M04-L01-A01.txt",
            storage="test-only",
            verified=True,
        )
        with self.assertRaisesRegex(Exception, "другому source SHA-256"):
            build_rendering_plan(
                repo_root=self.repo_root,
                lesson_id="M04-L01",
                source_steps=self.compiled["M04-L01"],
                asset_report=self.asset_report,
                bindings=[binding],
            )


if __name__ == "__main__":
    unittest.main()
