from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.canonical import build_structural_manifest
    from stepik_uploader.general_content import (
        GeneralContentCompileError,
        compile_all_lesson_sources,
    )
    from stepik_uploader.platform_profile import PLATFORM_PROFILE_PATH, free_answer_source, load_platform_profile
else:
    from .canonical import build_structural_manifest
    from .general_content import GeneralContentCompileError, compile_all_lesson_sources
    from .platform_profile import PLATFORM_PROFILE_PATH, free_answer_source, load_platform_profile



def _source_sha(repo_root: Path) -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_report(repo_root: Path) -> dict[str, Any]:
    source_sha = _source_sha(repo_root)
    manifest = build_structural_manifest(repo_root, source_sha=source_sha)
    profile = load_platform_profile(repo_root / PLATFORM_PROFILE_PATH)
    free_answer = free_answer_source(profile)

    lesson_ids = [
        str(lesson["canonical_id"])
        for module in manifest.get("modules", [])
        for lesson in module.get("lessons", [])
    ]
    compiled = compile_all_lesson_sources(
        repo_root,
        free_answer_source=free_answer,
        lesson_ids=lesson_ids,
    )

    per_lesson: list[dict[str, Any]] = []
    all_repo_links: list[dict[str, str]] = []
    all_asset_ids: set[str] = set()
    text_steps = 0
    free_answer_steps = 0
    for lesson_id in lesson_ids:
        steps = compiled[lesson_id]
        for step in steps:
            if step.block_name == "free-answer":
                free_answer_steps += 1
            else:
                text_steps += 1
            all_asset_ids.update(step.asset_ids)
            for link in step.unresolved_repo_links:
                all_repo_links.append(
                    {"canonical_id": lesson_id, "position": str(step.position), "target": link}
                )
        per_lesson.append(
            {
                "canonical_id": lesson_id,
                "compiled_learner_steps": len(steps),
                "block_sequence": [step.block_name for step in steps],
                "asset_ids": sorted({asset for step in steps for asset in step.asset_ids}),
                "repo_relative_links": sorted(
                    {link for step in steps for link in step.unresolved_repo_links}
                ),
                "alignment": [
                    {
                        "position": step.position,
                        "headings": list(step.source_headings),
                        "exercise_ids": list(step.exercise_ids),
                        "check_ids": list(step.check_ids),
                        "source_chunk_indexes": list(step.source_chunk_indexes),
                    }
                    for step in steps
                ],
            }
        )

    structural_rows = sum(
        len(lesson.get("steps", []))
        for module in manifest.get("modules", [])
        for lesson in module.get("lessons", [])
    )
    author_only_rows = sum(
        1
        for module in manifest.get("modules", [])
        for lesson in module.get("lessons", [])
        for step in lesson.get("steps", [])
        if step.get("author_only")
    )
    compiled_rows = sum(len(steps) for steps in compiled.values())

    return {
        "schema_version": 1,
        "source_main_sha": source_sha,
        "scope": "all-21-lessons-source-preserving-compiler",
        "lessons": per_lesson,
        "summary": {
            "lessons": len(lesson_ids),
            "structural_plan_rows": structural_rows,
            "author_only_rows_excluded": author_only_rows,
            "compiled_learner_steps": compiled_rows,
            "text_steps": text_steps,
            "free_answer_steps": free_answer_steps,
            "referenced_asset_ids": len(all_asset_ids),
            "repo_relative_links_pending_asset_route": len(all_repo_links),
        },
        "referenced_asset_ids": sorted(all_asset_ids),
        "repo_relative_links_pending_asset_route": all_repo_links,
        "stepik_writes": 0,
        "writer_enabled": False,
        "next_gate": "asset-publication-resolution",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline audit of the all-course Stepik source compiler")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    report = build_report(repo_root)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = args.output if args.output.is_absolute() else repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
