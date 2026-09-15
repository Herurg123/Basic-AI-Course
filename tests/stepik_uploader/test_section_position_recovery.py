from __future__ import annotations

import unittest

from scripts.stepik_uploader.api import StepikWriteAmbiguousError
from scripts.stepik_uploader.deployment_history import (
    DeploymentRecorder,
    MemoryHistoryStore,
    event_identity_from_environment,
)
from scripts.stepik_uploader.history_runtime import find_object_events
from scripts.stepik_uploader.section_position_recovery import (
    COURSE_ID,
    MALFORMED_POSITIONS,
    RECOVERY_KIND,
    RECOVERY_OPERATION,
    RECOVERY_OPERATION_ID,
    SECTION_IDS,
    TARGET_POSITIONS,
    UNIT_LAYOUT,
    SectionRecoveryError,
    _fingerprint,
    _manifest_specs,
    _state,
    run_recovery,
)


class FakeRecoveryClient:
    def __init__(self) -> None:
        self.sections = {}
        self.units = {}
        self.write_calls: list[tuple[str, int]] = []
        self.ambiguous_section_id: int | None = None
        titles = {
            "M00": "Модуль 00",
            "M01": "Модуль 01",
            "M02": "Модуль 02",
            "M03": "Модуль 03",
            "M04": "Модуль 04",
            "M05": "Модуль 05",
            "M06": "Модуль 06",
            "M07": "Модуль 07",
            "M08": "M08 — Модуль 08",
        }
        for module_id, section_id in SECTION_IDS.items():
            unit_ids = [row[0] for row in UNIT_LAYOUT[module_id]]
            self.sections[section_id] = {
                "id": section_id,
                "title": titles[module_id],
                "position": MALFORMED_POSITIONS[module_id],
                "course": COURSE_ID,
                "units": unit_ids,
                "exam": False,
            }
            for unit_id, position, lesson_id in UNIT_LAYOUT[module_id]:
                self.units[unit_id] = {
                    "id": unit_id,
                    "position": position,
                    "lesson": lesson_id,
                    "section": section_id,
                }

    def fetch_one(self, resource: str, object_id: int):
        if resource == "sections":
            return dict(self.sections[object_id])
        if resource == "courses":
            return {
                "id": COURSE_ID,
                "title": "Курс",
                "language": "ru",
                "is_public": False,
                "sections": list(SECTION_IDS.values()),
            }
        raise AssertionError((resource, object_id))

    def fetch_many(self, resource: str, object_ids, *, chunk_size: int = 30):
        if resource == "units":
            return [dict(self.units[int(value)]) for value in object_ids]
        raise AssertionError(resource)

    def _request_options(self, path: str):
        return {
            "actions": {
                "PUT": {
                    "title": {"required": True},
                    "position": {"required": True},
                    "course": {"required": True},
                    "exam": {"required": False},
                    "id": {"read_only": True},
                    "units": {"read_only": True},
                }
            }
        }, "GET, PUT, OPTIONS"

    def _request_write(self, method: str, path: str, payload: dict):
        if method != "PUT" or "/api/sections/" not in path:
            raise AssertionError((method, path))
        section_id = int(path.rsplit("/", 1)[-1])
        self.write_calls.append((method, section_id))
        if self.ambiguous_section_id == section_id:
            raise StepikWriteAmbiguousError("synthetic ambiguous")
        body = payload["section"]
        current_units = self.sections[section_id]["units"]
        self.sections[section_id] = {
            "id": section_id,
            "title": body.get("title", ""),
            "position": int(body.get("position", 1)),
            "course": int(body.get("course", -1)),
            "units": current_units,
            "exam": bool(body.get("exam", False)),
        }
        return {"sections": [dict(self.sections[section_id])]}

    def inspect_course(self, course_id: int):
        if course_id != COURSE_ID:
            raise AssertionError(course_id)
        normalized = []
        for section_id, raw in self.sections.items():
            units = []
            for unit_id in raw["units"]:
                unit = self.units[unit_id]
                units.append(
                    {
                        "id": unit_id,
                        "position": unit["position"],
                        "lesson": {"id": unit["lesson"], "title": f"lesson-{unit['lesson']}"},
                    }
                )
            normalized.append(
                {
                    "id": section_id,
                    "title": raw["title"],
                    "position": raw["position"],
                    "units": sorted(units, key=lambda row: (row["position"], row["id"])),
                }
            )
        return {
            "course": {"id": COURSE_ID, "title": "Курс", "language": "ru", "is_public": False},
            "sections": sorted(normalized, key=lambda row: (row["position"], row["id"])),
        }


def manifest():
    return {
        "modules": [
            {
                "canonical_id": module_id,
                "title": f"Модуль {module_id[1:]}",
                "position": TARGET_POSITIONS[module_id],
                "lessons": [],
            }
            for module_id in SECTION_IDS
        ]
    }


class SectionPositionRecoveryTests(unittest.TestCase):
    def test_read_only_preflight_performs_zero_writes(self) -> None:
        client = FakeRecoveryClient()
        store = MemoryHistoryStore()
        report = run_recovery(
            client=client,
            store=store,
            manifest=manifest(),
            current_sha="1" * 40,
            confirm_write=False,
        )
        self.assertEqual(report["verdict"], "PREFLIGHT_PASS")
        self.assertEqual(report["stepik_writes"], 0)
        self.assertEqual(report["recovery_required"], [f"M0{i}" for i in range(1, 8)])
        self.assertEqual(client.write_calls, [])
        self.assertFalse(store.records)

    def test_recovery_writes_only_seven_damaged_sections_and_commits_history(self) -> None:
        client = FakeRecoveryClient()
        store = MemoryHistoryStore()
        report = run_recovery(
            client=client,
            store=store,
            manifest=manifest(),
            current_sha="2" * 40,
            confirm_write=True,
        )
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["stepik_writes"], 7)
        self.assertEqual(
            [section_id for _method, section_id in client.write_calls],
            [SECTION_IDS[f"M0{i}"] for i in range(1, 8)],
        )
        self.assertEqual(
            {module_id: client.sections[section_id]["position"] for module_id, section_id in SECTION_IDS.items()},
            TARGET_POSITIONS,
        )
        for module_id in [f"M0{i}" for i in range(1, 8)]:
            events = find_object_events(store, object_id=f"section-position:{module_id}")
            self.assertEqual(len(events), 1)
            _identity, _records, summary = events[0]
            self.assertTrue(summary["final_readback_confirmed"])
            self.assertTrue(summary["machine_state_committed"])
            self.assertEqual(summary["confirmed_operation_count"], 1)
            self.assertEqual(summary["committed_baseline_after"]["position"], TARGET_POSITIONS[module_id])

    def test_raw_section_course_drift_blocks_before_any_write(self) -> None:
        client = FakeRecoveryClient()
        client.sections[SECTION_IDS["M05"]]["course"] = 999999
        with self.assertRaises(SectionRecoveryError):
            run_recovery(
                client=client,
                store=MemoryHistoryStore(),
                manifest=manifest(),
                current_sha="3" * 40,
                confirm_write=True,
            )
        self.assertEqual(client.write_calls, [])

    def test_arbitrary_position_drift_blocks_before_any_write(self) -> None:
        client = FakeRecoveryClient()
        client.sections[SECTION_IDS["M04"]]["position"] = 4
        with self.assertRaises(SectionRecoveryError):
            run_recovery(
                client=client,
                store=MemoryHistoryStore(),
                manifest=manifest(),
                current_sha="4" * 40,
                confirm_write=True,
            )
        self.assertEqual(client.write_calls, [])

    def test_target_position_without_recovery_history_is_not_auto_adopted(self) -> None:
        client = FakeRecoveryClient()
        client.sections[SECTION_IDS["M03"]]["position"] = TARGET_POSITIONS["M03"]
        with self.assertRaises(SectionRecoveryError):
            run_recovery(
                client=client,
                store=MemoryHistoryStore(),
                manifest=manifest(),
                current_sha="5" * 40,
                confirm_write=True,
            )
        self.assertEqual(client.write_calls, [])

    def test_completed_write_crash_recovers_readback_without_repeating_put(self) -> None:
        client = FakeRecoveryClient()
        store = MemoryHistoryStore()
        sha = "6" * 40
        spec = next(value for value in _manifest_specs(manifest()) if value.canonical_id == "M01")
        baseline = _state(spec, position=spec.malformed_position)
        desired = _state(spec, position=spec.target_position)
        identity = event_identity_from_environment(
            course_id=COURSE_ID,
            object_id=spec.object_id,
            kind=RECOVERY_KIND,
            source_sha=sha,
            desired_fingerprint=_fingerprint(desired),
            baseline_fingerprint=_fingerprint(baseline),
            pending_first_sha=None,
        )
        recorder = DeploymentRecorder(store, identity)
        recorder.ensure_started(
            operation_type=RECOVERY_OPERATION,
            state_before=baseline,
            expected_state=desired,
            stepik_object_ids={"section_id": spec.section_id},
            fingerprint_before=_fingerprint(baseline),
        )
        recorder.write_intent(
            operation_id=RECOVERY_OPERATION_ID,
            method="PUT",
            target=f"sections/{spec.section_id}",
            fingerprint_before=_fingerprint(baseline),
            expected_fingerprint_after=_fingerprint(desired),
        )
        recorder.write_dispatch_started(operation_id=RECOVERY_OPERATION_ID)
        recorder.write_result(operation_id=RECOVERY_OPERATION_ID, status="COMPLETED")
        client.sections[spec.section_id]["position"] = spec.target_position

        report = run_recovery(
            client=client,
            store=store,
            manifest=manifest(),
            current_sha=sha,
            confirm_write=True,
        )
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["stepik_writes"], 6)
        self.assertNotIn(spec.section_id, [section_id for _method, section_id in client.write_calls])
        events = find_object_events(store, object_id=spec.object_id)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0][2]["final_readback_confirmed"])
        self.assertTrue(events[0][2]["machine_state_committed"])
        self.assertEqual(events[0][2]["confirmed_operation_count"], 1)

    def test_ambiguous_dispatch_is_not_blindly_retried(self) -> None:
        client = FakeRecoveryClient()
        store = MemoryHistoryStore()
        client.ambiguous_section_id = SECTION_IDS["M01"]
        with self.assertRaises(StepikWriteAmbiguousError):
            run_recovery(
                client=client,
                store=store,
                manifest=manifest(),
                current_sha="7" * 40,
                confirm_write=True,
            )
        self.assertEqual(client.write_calls, [("PUT", SECTION_IDS["M01"])])

        client.ambiguous_section_id = None
        with self.assertRaises(SectionRecoveryError):
            run_recovery(
                client=client,
                store=store,
                manifest=manifest(),
                current_sha="7" * 40,
                confirm_write=True,
            )
        self.assertEqual(client.write_calls, [("PUT", SECTION_IDS["M01"])])


if __name__ == "__main__":
    unittest.main()
