from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.stepik_uploader.asset_inventory import build_asset_inventory
from scripts.stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
from scripts.stepik_uploader.canonical import build_structural_manifest
from scripts.stepik_uploader.general_content import EXPECTED_FREE_ANSWER_SOURCE, compile_all_lesson_sources
from scripts.stepik_uploader.verified_rendering import AssetBinding, build_rendering_plan


COURSE_ID = 299189


def build_snapshot(repo_root: Path, output_dir: Path) -> dict:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_structural_manifest(repo_root, source_sha="b7-final-render-snapshot")
    lessons = {
        lesson["canonical_id"]: lesson
        for module in manifest["modules"]
        for lesson in module["lessons"]
    }
    compiled = compile_all_lesson_sources(
        repo_root,
        free_answer_source=EXPECTED_FREE_ANSWER_SOURCE,
        lesson_ids=lessons,
    )

    inventory = build_asset_inventory(repo_root, manifest)
    policy_path = repo_root / "04_course/stepik/automation/asset-publication.v1.json"
    asset_report = assess_asset_publication(
        repo_root=repo_root,
        inventory=inventory,
        policy=load_asset_publication_policy(policy_path),
        course_id=COURSE_ID,
    )

    state_path = repo_root / "90_reviews/semantic-step-audit-2026-09-20/evidence/machine-state-2026-09-20.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    expected_hashes = {
        str(row["source_path"]): str(row["source_sha256"])
        for row in asset_report["resolutions"]
        if row.get("source_path") and row.get("source_sha256")
    }
    bindings = [
        AssetBinding(
            **{
                key: row[key]
                for key in ("source_path", "source_sha256", "url", "storage")
            }
        )
        for row in state["assets"].values()
        if expected_hashes.get(str(row.get("source_path"))) == row.get("source_sha256")
    ]

    index: dict = {
        "modules": len(manifest["modules"]),
        "lessons": len(lessons),
        "structural_rows": manifest["summary"]["logical_steps"],
        "learner_steps": 0,
        "materialization_requirements": [],
        "lesson_files": [],
    }
    all_requirements: dict[str, dict] = {}

    for lesson_id in sorted(lessons):
        plan = build_rendering_plan(
            repo_root=repo_root,
            lesson_id=lesson_id,
            source_steps=compiled[lesson_id],
            asset_report=asset_report,
            bindings=bindings,
        )
        steps = [
            {
                "position": step.position,
                "block_name": step.block_name,
                "source": step.source,
                "html": step.text,
                "source_git_paths": list(step.source_git_paths),
            }
            for step in plan.rendered_steps
        ]
        index["learner_steps"] += len(steps)
        for requirement in plan.materialization_requirements:
            all_requirements[str(requirement["source_path"])] = dict(requirement)

        payload = {
            "lesson_id": lesson_id,
            "title": lessons[lesson_id]["title"],
            "step_count": len(steps),
            "steps": steps,
            "materialization_requirements": list(plan.materialization_requirements),
        }
        filename = f"{lesson_id}.json"
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        index["lesson_files"].append(filename)

    index["materialization_requirements"] = [
        all_requirements[key] for key in sorted(all_requirements)
    ]
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only B7 final learner HTML snapshot")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    index = build_snapshot(Path(args.repo_root), Path(args.output_dir))
    print(json.dumps(index, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
