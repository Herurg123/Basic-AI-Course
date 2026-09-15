from __future__ import annotations

import unittest

from scripts.stepik_uploader.title_hygiene import plan_title_hygiene


class HistoricalTitleAliasTests(unittest.TestCase):
    def _manifest(self):
        return {
            "modules": [
                {
                    "canonical_id": "M06",
                    "title": "Решите, чему доверять и что применять",
                    "position": 7,
                    "lessons": [
                        {
                            "canonical_id": "M06-L02",
                            "title": "Проверьте исходные числа и расчёт",
                            "position": 2,
                            "golden_read_only": False,
                        }
                    ],
                },
                {
                    "canonical_id": "M07",
                    "title": "Завершите свою реальную задачу",
                    "position": 8,
                    "lessons": [
                        {
                            "canonical_id": "M07-L01",
                            "title": "Соберите знакомые действия в одну работу",
                            "position": 1,
                            "golden_read_only": False,
                        }
                    ],
                },
            ]
        }

    def _snapshot(self, *, m06_title: str, m07_title: str):
        return {
            "sections": [
                {
                    "id": 60,
                    "position": 7,
                    "title": "Решите, чему доверять и что применять",
                    "units": [
                        {
                            "id": 602,
                            "position": 2,
                            "lesson": {"id": 6002, "title": m06_title},
                        }
                    ],
                },
                {
                    "id": 70,
                    "position": 8,
                    "title": "Завершите свою реальную задачу",
                    "units": [
                        {
                            "id": 701,
                            "position": 1,
                            "lesson": {"id": 7001, "title": m07_title},
                        }
                    ],
                },
            ]
        }

    def test_two_observed_historical_titles_are_exactly_allowed(self) -> None:
        plan = plan_title_hygiene(
            self._manifest(),
            self._snapshot(
                m06_title="M06-L02 — Проверьте исходные числа и расчет",
                m07_title="M07-L01 — Соберите освоенные действия в одну работу",
            ),
        )
        self.assertEqual(plan.blockers, [])
        self.assertEqual(
            [(op.canonical_id, op.live_title, op.expected_title) for op in plan.operations],
            [
                (
                    "M06-L02",
                    "M06-L02 — Проверьте исходные числа и расчет",
                    "Проверьте исходные числа и расчёт",
                ),
                (
                    "M07-L01",
                    "M07-L01 — Соберите освоенные действия в одну работу",
                    "Соберите знакомые действия в одну работу",
                ),
            ],
        )

    def test_similar_but_unapproved_title_still_blocks(self) -> None:
        plan = plan_title_hygiene(
            self._manifest(),
            self._snapshot(
                m06_title="M06-L02 — Проверьте исходные числа и расчеты",
                m07_title="M07-L01 — Соберите освоенные действия в одну задачу",
            ),
        )
        self.assertEqual(len(plan.operations), 0)
        self.assertEqual(len(plan.blockers), 2)
        self.assertTrue(any("M06-L02" in item for item in plan.blockers))
        self.assertTrue(any("M07-L01" in item for item in plan.blockers))

    def test_alias_is_scoped_to_exact_canonical_id(self) -> None:
        manifest = self._manifest()
        manifest["modules"][0]["lessons"][0]["canonical_id"] = "M06-L99"
        plan = plan_title_hygiene(
            manifest,
            self._snapshot(
                m06_title="M06-L02 — Проверьте исходные числа и расчет",
                m07_title="Соберите знакомые действия в одну работу",
            ),
        )
        self.assertEqual(len(plan.operations), 0)
        self.assertEqual(len(plan.blockers), 1)
        self.assertIn("M06-L99", plan.blockers[0])


if __name__ == "__main__":
    unittest.main()
