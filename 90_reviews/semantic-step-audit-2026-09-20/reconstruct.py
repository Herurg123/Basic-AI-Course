"""Восстановление ученических шагов для аудита без обращения к Stepik API.

Запуск из корня репозитория: python 90_reviews/semantic-step-audit-2026-09-20/reconstruct.py
Нужны зависимости scripts/stepik_uploader/requirements.txt (для этого пути — mistune).
Это инструмент аудита, он не меняет учебные исходники и не выполняет публикацию.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PIN = "d076dd06977ecc85db66abb1d3fc503eb7343d48"
sys.path.insert(0, str(ROOT))

import mistune
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import load_asset_publication_policy, assess_asset_publication
from scripts.stepik_uploader.verified_rendering import AssetBinding, build_rendering_plan, require_render_ready
from scripts.stepik_uploader.transport_equivalence import normalize_stepik_transport_html
from scripts.stepik_uploader.fingerprints import compiled_lesson_fingerprint


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    # Аудит нельзя незаметно пересобрать на изменённых источниках или другом коде.
    tracked = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", PIN, "04_course", "05_assets", "scripts/stepik_uploader"],
        cwd=ROOT, text=True,
    ).splitlines()
    for name in tracked:
        expected = subprocess.check_output(["git", "show", f"{PIN}:{name}"], cwd=ROOT)
        if (ROOT / name).read_bytes() != expected:
            raise RuntimeError(f"Исходник отличается от зафиксированного main: {name}")

    state_path = HERE / "evidence/machine-state-2026-09-20.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    manifest = build_structural_manifest(ROOT, source_sha=PIN)
    lessons = {lesson["canonical_id"]: lesson for module in manifest["modules"] for lesson in module["lessons"]}
    if set(lessons) != set(state["lessons"]):
        raise RuntimeError("Состав уроков manifest и сохранённого состояния не совпадает")
    compiled = compile_all_lesson_sources(ROOT, free_answer_source=EXPECTED_FREE_ANSWER_SOURCE, lesson_ids=lessons)
    inventory = build_asset_inventory(ROOT, manifest)
    policy = load_asset_publication_policy(ROOT / "04_course/stepik/automation/asset-publication.v1.json")
    assets = assess_asset_publication(repo_root=ROOT, inventory=inventory, policy=policy, course_id=299189)
    bindings = [AssetBinding(**{key: row[key] for key in ("source_path", "source_sha256", "url", "storage")}) for row in state["assets"].values()]

    report = {
        "source_sha": PIN,
        "state_source": "https://github.com/Herurg123/Basic-AI-Course/issues/54",
        "state_updated_at": state["updated_at"],
        "state_file_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
        "mistune_version": mistune.__version__,
        "scope": "Локальная точная сборка с сохранёнными URL и сверкой отпечатков; не новая проверка живого интерфейса.",
        "audit_status": "NOT_REVIEWED",
        "lessons": [],
    }
    for lesson_id, lesson in lessons.items():
        recorded = state["lessons"][lesson_id]
        if recorded["applied_source_sha"] != PIN:
            raise RuntimeError(f"{lesson_id}: сохранённое состояние относится к другому source SHA")
        plan = build_rendering_plan(repo_root=ROOT, lesson_id=lesson_id, source_steps=compiled[lesson_id], asset_report=assets, bindings=bindings)
        rendered = require_render_ready(plan)
        plan_rows = [row for row in lesson["steps"] if not row.get("author_only")]
        if not len(rendered) == len(recorded["step_ids"]) == len(plan_rows):
            raise RuntimeError(f"{lesson_id}: число шагов не совпадает")
        fingerprint = compiled_lesson_fingerprint(expected_title=lesson["title"], expected_steps=rendered)
        normalized = [replace(step, text=normalize_stepik_transport_html(step.text)) for step in rendered]
        transport_fp = compiled_lesson_fingerprint(expected_title=lesson["title"], expected_steps=normalized)
        summary = {
            "module_id": lesson_id.split("-")[0], "lesson_id": lesson_id,
            "title": lesson["title"], "stepik_lesson_id": recorded["stepik_lesson_id"],
            "step_count": len(rendered), "reconstructed_fingerprint": fingerprint,
            "recorded_applied_fingerprint": recorded["applied_fingerprint"],
            "matches_applied": fingerprint == recorded["applied_fingerprint"],
            "recorded_confirmed_live_fingerprint": recorded.get("confirmed_live_fingerprint"),
            "matches_recorded_live": fingerprint == recorded.get("confirmed_live_fingerprint"),
            "transport_normalized_fingerprint": transport_fp,
            "transport_normalized_matches_recorded_live": transport_fp == recorded.get("confirmed_live_fingerprint"),
        }
        report["lessons"].append(summary)
        rows = []
        for step, src, plan_row, step_id in zip(rendered, compiled[lesson_id], plan_rows, recorded["step_ids"], strict=True):
            title = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", step.text, re.S)
            rows.append({
                "step_key": f"{lesson_id}-S{step.position:02d}",
                "position": step.position, "stepik_step_id": step_id,
                "stepik_url": f"https://stepik.org/lesson/{recorded['stepik_lesson_id']}/step/{step.position}",
                "visible_title_html": title.group(1) if title else None,
                "platform_block_type": step.block_name, "platform_source": step.source,
                "plan_row": plan_row, "source_chunk_indexes": src.source_chunk_indexes,
                "source_headings": src.source_headings, "source_git_paths": step.source_git_paths,
                "html_sha256": hashlib.sha256(step.text.encode()).hexdigest(),
                "html": step.text,
                "semantic_audit_status": "NOT_REVIEWED",
            })
        write_json(HERE / f"rendered/{lesson_id}.json", {"source_sha": PIN, **summary, "steps": rows})

    report["module_count"] = len(manifest["modules"])
    report["lesson_count"] = len(lessons)
    report["step_count"] = sum(row["step_count"] for row in report["lessons"])
    report["all_match_applied"] = all(row["matches_applied"] for row in report["lessons"])
    write_json(HERE / "evidence/reconstruction-report.json", report)
    print(json.dumps({key: report[key] for key in ("module_count", "lesson_count", "step_count", "all_match_applied", "mistune_version")}, ensure_ascii=False))
    for row in report["lessons"]:
        if not row["matches_recorded_live"]:
            print(json.dumps(row, ensure_ascii=False))
    if not report["all_match_applied"]:
        raise RuntimeError("Есть несовпадения с применёнными отпечатками: нельзя объявлять восстановление точным")


if __name__ == "__main__":
    main()
