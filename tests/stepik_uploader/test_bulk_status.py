from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.bulk_status import BulkStatusError, build_bulk_status
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.content import compile_test_lesson
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint

FREE = {
    "is_attachments_enabled": False,
    "is_html_enabled": True,
    "manual_scoring": False,
}


def _asset_report(repo_root: Path) -> dict:
    manifest = build_structural_manifest(repo_root, source_sha="bulk-status-asset-test")
    inventory = build_asset_inventory(repo_root, manifest)
    policy = load_asset_publication_policy(
        repo_root / "04_course/stepik/automation/asset-publication.v1.json"
    )
    return assess_asset_publication(
        repo_root=repo_root,
        inventory=inventory,
        policy=policy,
        course_id=299189,
    )


def _compiled_live_lesson(repo_root: Path, *, human_title: bool = False) -> tuple[dict, str]:
    compiled = compile_test_lesson(repo_root, free_answer_source=FREE)
    canonical = "Скажите, что получите и как это оцените"
    title = canonical if human_title else f"M02-L01 — {canonical}"
    lesson = {
        "id": 301,
        "title": title,
        "language": "ru",
        "is_public": False,
        "steps": [
            {
                "id": 1000 + step.position,
                "step_source": {
                    "id": 1000 + step.position,
                    "position": step.position,
                    "block": step.block(),
                },
            }
            for step in compiled
        ],
    }
    fingerprint = compiled_lesson_fingerprint(expected_title=title, expected_steps=compiled)
    return lesson, fingerprint


def _placeholder(lesson_id: int, title: str) -> dict:
    return {
        "id": lesson_id,
        "title": title,
        "language": "ru",
        "is_public": False,
        "steps": [
            {
                "id": lesson_id * 10,
                "step_source": {
                    "id": lesson_id * 10,
                    "position": 1,
                    "block": {"name": "text", "source": {}, "text": "<p>Урок сгенерирован роботом ;)</p>"},
                },
            }
        ],
    }


def _pilot_manifest() -> dict:
    return {
        "modules": [
            {
                "canonical_id": "M02",
                "position": 3,
                "lessons": [
                    {
                        "canonical_id": "M02-L01",
                        "title": "Скажите, что получите и как это оцените",
                        "position": 1,
                        "golden_read_only": False,
                        "independence_sensitive": False,
                        "f1_sensitive": False,
                        "asset_ids": ["M02-L01-A01"],
                        "steps": [{"position": i} for i in range(1, 7)],
                    }
                ],
            }
        ]
    }


class BulkStatusTests(unittest.TestCase):
    def test_all_course_status_marks_legacy_tracked_pilot_for_hygiene_not_drift(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        asset_report = _asset_report(repo_root)
        m02, fingerprint = _compiled_live_lesson(repo_root)
        manifest = {
            "modules": [
                {
                    "canonical_id": "M00",
                    "position": 1,
                    "lessons": [
                        {
                            "canonical_id": "M00-L01",
                            "title": "Начните безопасный рабочий диалог",
                            "position": 1,
                            "golden_read_only": True,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        },
                        {
                            "canonical_id": "M00-L02",
                            "title": "Подготовьте и передайте безопасный учебный материал",
                            "position": 2,
                            "golden_read_only": True,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        },
                        {
                            "canonical_id": "M00-L03",
                            "title": "Откройте основание и вернитесь к работе",
                            "position": 3,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": ["M00-L03-A01"],
                            "steps": [{"position": 1}, {"position": 2}],
                        },
                    ],
                },
                _pilot_manifest()["modules"][0],
            ]
        }
        snapshot = {
            "course": {"id": 299189, "is_public": False},
            "sections": [
                {
                    "position": 1,
                    "units": [
                        {"position": 1, "lesson": _placeholder(101, "M00-L01 — Начните безопасный рабочий диалог")},
                        {"position": 2, "lesson": _placeholder(102, "M00-L02 — Подготовьте и передайте безопасный учебный материал")},
                        {"position": 3, "lesson": _placeholder(103, "M00-L03 — Откройте основание и вернитесь к работе")},
                    ],
                },
                {"position": 3, "units": [{"position": 1, "lesson": m02}]},
            ],
        }
        state = {
            "schema_version": 1,
            "course_id": 299189,
            "updated_at": "2026-09-14T00:00:00Z",
            "lessons": {
                "M02-L01": {
                    "canonical_id": "M02-L01",
                    "stepik_lesson_id": 301,
                    "applied_fingerprint": fingerprint,
                }
            },
        }
        profile = {"observed_conventions": {"free_answer_source": FREE}}
        plan = SimpleNamespace(
            operations=[
                {"lesson": "M00-L01", "action": "READ_ONLY_GOLDEN"},
                {"lesson": "M00-L02", "action": "READ_ONLY_GOLDEN"},
                {"lesson": "M00-L03", "action": "SKIP"},
                {"lesson": "M02-L01", "action": "SKIP"},
            ]
        )
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state=state,
            profile=profile,
            plan=plan,
            asset_report=asset_report,
        )
        by_id = {item["canonical_id"]: item for item in status["lessons"]}
        self.assertEqual(by_id["M00-L01"]["status"], "READ_ONLY_GOLDEN")
        self.assertEqual(by_id["M00-L02"]["status"], "READ_ONLY_GOLDEN")
        self.assertEqual(by_id["M00-L03"]["status"], "INITIAL_UPLOAD_REQUIRED")
        self.assertEqual(by_id["M02-L01"]["status"], "LEARNER_HYGIENE_REQUIRED")
        self.assertEqual(by_id["M02-L01"]["title_state"], "LEGACY_PREFIX_EXACT")
        self.assertEqual(by_id["M00-L03"]["asset_route_status"], "RESOLVED")
        self.assertEqual(status["hard_blockers"], [])
        self.assertTrue(status["asset_route_gate_passed"])
        self.assertEqual(status["next_gate"], "learner-hygiene-and-verified-rendering-first-upload")
        self.assertFalse(status["ready_for_bulk_write"])

    def test_human_title_tracked_pilot_is_in_sync(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        live, fingerprint = _compiled_live_lesson(repo_root, human_title=True)
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=_pilot_manifest(),
            snapshot={
                "course": {"id": 299189, "is_public": False},
                "sections": [{"position": 3, "units": [{"position": 1, "lesson": live}]}],
            },
            state={
                "schema_version": 1,
                "course_id": 299189,
                "updated_at": "2026-09-15T00:00:00Z",
                "lessons": {
                    "M02-L01": {
                        "canonical_id": "M02-L01",
                        "stepik_lesson_id": 301,
                        "applied_fingerprint": fingerprint,
                    }
                },
            },
            profile={"observed_conventions": {"free_answer_source": FREE}},
            plan=SimpleNamespace(operations=[{"lesson": "M02-L01", "action": "SKIP"}]),
            asset_report=_asset_report(repo_root),
        )
        record = status["lessons"][0]
        self.assertEqual(record["title_state"], "HUMAN_EXACT")
        self.assertEqual(record["status"], "IN_SYNC")
        self.assertEqual(status["hard_blockers"], [])

    def test_exact_legacy_title_is_pending_not_duplicate_create(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = {
            "modules": [
                {
                    "canonical_id": "M06",
                    "position": 7,
                    "lessons": [
                        {
                            "canonical_id": "M06-L02",
                            "title": "Новый заголовок",
                            "position": 2,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        }
                    ],
                }
            ]
        }
        snapshot = {
            "course": {"id": 299189, "is_public": False},
            "sections": [
                {
                    "position": 7,
                    "units": [
                        {"position": 2, "lesson": _placeholder(602, "M06-L02 — Новый заголовок")}
                    ],
                }
            ],
        }
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state={"schema_version": 1, "course_id": 299189, "updated_at": None, "lessons": {}},
            profile={"observed_conventions": {"free_answer_source": FREE}},
            plan=SimpleNamespace(operations=[{"lesson": "M06-L02", "action": "SKIP"}]),
            asset_report=_asset_report(repo_root),
        )
        record = status["lessons"][0]
        self.assertEqual(record["title_state"], "LEGACY_PREFIX_EXACT")
        self.assertEqual(record["status"], "INITIAL_UPLOAD_REQUIRED")
        self.assertIn("M06-L02:explicit-title-update-required", status["pending_requirements"])
        self.assertEqual(record["asset_route_status"], "RESOLVED")

    def test_arbitrary_same_id_title_drift_fails_closed(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        manifest = {
            "modules": [
                {
                    "canonical_id": "M06",
                    "position": 7,
                    "lessons": [
                        {
                            "canonical_id": "M06-L02",
                            "title": "Новый заголовок",
                            "position": 2,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        }
                    ],
                }
            ]
        }
        with self.assertRaises(BulkStatusError):
            build_bulk_status(
                repo_root=repo_root,
                manifest=manifest,
                snapshot={
                    "course": {"id": 299189, "is_public": False},
                    "sections": [
                        {
                            "position": 7,
                            "units": [
                                {"position": 2, "lesson": _placeholder(602, "M06-L02 — Ручной другой заголовок")}
                            ],
                        }
                    ],
                },
                state={"schema_version": 1, "course_id": 299189, "updated_at": None, "lessons": {}},
                profile={"observed_conventions": {"free_answer_source": FREE}},
                plan=SimpleNamespace(operations=[{"lesson": "M06-L02", "action": "SKIP_STALE_TITLE"}]),
                asset_report=_asset_report(repo_root),
            )

    def test_unresolved_asset_report_blocks_next_gate(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        asset_report = _asset_report(repo_root)
        asset_report["route_gate_passed"] = False
        target = next(item for item in asset_report["resolutions"] if item["lesson"] == "M06-L02")
        target["route_resolved"] = False
        manifest = {
            "modules": [
                {
                    "canonical_id": "M06",
                    "position": 7,
                    "lessons": [
                        {
                            "canonical_id": "M06-L02",
                            "title": "Новый заголовок",
                            "position": 2,
                            "golden_read_only": False,
                            "independence_sensitive": False,
                            "f1_sensitive": False,
                            "asset_ids": [],
                            "steps": [{"position": 1}],
                        }
                    ],
                }
            ]
        }
        snapshot = {
            "course": {"id": 299189, "is_public": False},
            "sections": [
                {
                    "position": 7,
                    "units": [
                        {"position": 2, "lesson": _placeholder(602, "M06-L02 — Новый заголовок")}
                    ],
                }
            ],
        }
        status = build_bulk_status(
            repo_root=repo_root,
            manifest=manifest,
            snapshot=snapshot,
            state={"schema_version": 1, "course_id": 299189, "updated_at": None, "lessons": {}},
            profile={"observed_conventions": {"free_answer_source": FREE}},
            plan=SimpleNamespace(operations=[{"lesson": "M06-L02", "action": "SKIP"}]),
            asset_report=asset_report,
        )
        self.assertIn("asset-publication-resolution:BLOCKED", status["hard_blockers"])
        self.assertEqual(status["next_gate"], "asset-publication-resolution")
        self.assertEqual(status["lessons"][0]["asset_route_status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
