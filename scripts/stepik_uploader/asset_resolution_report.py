from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from stepik_uploader.asset_inventory import build_asset_inventory
    from stepik_uploader.asset_resolution import assess_asset_publication, load_asset_publication_policy
    from stepik_uploader.canonical import build_structural_manifest
else:
    from .asset_inventory import build_asset_inventory
    from .asset_resolution import assess_asset_publication, load_asset_publication_policy
    from .canonical import build_structural_manifest

POLICY_PATH = Path("04_course/stepik/automation/asset-publication.v1.json")


def build_asset_resolution_report(repo_root: Path, *, course_id: int = 299189) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest = build_structural_manifest(repo_root, source_sha="asset-resolution-report")
    inventory = build_asset_inventory(repo_root, manifest)
    if inventory.get("missing_files"):
        raise RuntimeError(
            "asset inventory содержит отсутствующие source files: "
            + ", ".join(str(item) for item in inventory["missing_files"])
        )
    policy = load_asset_publication_policy(repo_root / POLICY_PATH)
    report = assess_asset_publication(
        repo_root=repo_root,
        inventory=inventory,
        policy=policy,
        course_id=course_id,
    )
    return {
        "schema_version": 1,
        "mode": "asset-resolution-report",
        "course_id": course_id,
        "policy_status": report.get("policy_status"),
        "decision": report.get("decision"),
        "route_gate_passed": report["route_gate_passed"],
        "summary": report["summary"],
        "blockers": report["blockers"],
        "unresolved_sources": report["unresolved_sources"],
        "topology_fingerprint": report["topology"]["fingerprint"],
        "stepik_writes": 0,
        "ready_for_bulk_write": False,
        "next_gate": report["next_gate"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline report для Stepik asset publication routes")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--course-id", type=int, default=299189)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_asset_resolution_report(args.repo_root, course_id=args.course_id)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else args.repo_root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["route_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
