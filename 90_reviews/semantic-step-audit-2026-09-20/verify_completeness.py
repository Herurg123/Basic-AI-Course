"""Проверяет полноту диагностического пакета; не оценивает смысл и не пишет в Stepik."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOT_ANCHOR = "4fb3791c3e38ddbfb0309dd9d4abb7c9cdf8842e"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).splitlines()


def main():
    inventory = json.loads((HERE / "step-inventory.json").read_text())
    findings = json.loads((HERE / "findings.json").read_text())
    coverage = json.loads((HERE / "coverage-summary.json").read_text())
    summary = inventory["summary"]
    pin = summary["source_sha"]
    assert findings["summary"] == coverage["summary"] == summary
    snapshots = [json.loads(p.read_text()) for p in sorted((HERE / "rendered").glob("*.json"))]
    actual = [step for lesson in snapshots for step in lesson["steps"]]
    assert len(actual) == len(inventory["steps"]) == 148
    assert len({s["step_key"] for s in actual}) == 148
    assert {s["step_key"] for s in actual} == {s["step_key"] for s in inventory["steps"]}
    assert len(snapshots) == 21 and len({s["module_id"] for s in inventory["steps"]}) == 9
    assert all(s["review_status"] == "REVIEWED" and s["semantic_type"] and s["required_fix"] for s in inventory["steps"])
    assert all(lesson["source_sha"] == pin for lesson in snapshots)
    assert all(hashlib.sha256(s["html"].encode()).hexdigest() == s["html_sha256"].removeprefix("sha256:") for s in actual)
    protected = ("04_course/", "05_assets/", "scripts/stepik_uploader/")
    changed = git("diff", "--name-only", pin, "--", *protected)
    untracked = [p for p in git("ls-files", "--others", "--exclude-standard") if p.startswith(protected)]
    assert not changed and not untracked, (changed, untracked)
    snapshot_delta = git("diff", "--name-only", SNAPSHOT_ANCHOR, "--", str(HERE.relative_to(ROOT) / "rendered"))
    assert not snapshot_delta, snapshot_delta
    patterns = defaultdict(set)
    for finding in findings["findings"]:
        assert finding["fix"] and finding["independence_guard"]
        patterns[finding["pattern"]].add(finding["lesson_id"])
    report = {
        "source_sha": pin,
        "status": "COMPLETENESS_PASS",
        "modules": 9, "lessons": 21, "steps": 148, "unique_step_keys": 148,
        "same_snapshot_inventory_step_set": True,
        "all_html_hashes_match": True,
        "all_steps_reviewed_typed_and_have_fix_disposition": True,
        "all_findings_have_fix_and_independence_guard": True,
        "counts": summary["counts"], "findings": len(findings["findings"]),
        "pattern_families": len(patterns),
        "cross_lesson_pattern_families": sum(len(v) > 1 for v in patterns.values()),
        "single_lesson_pattern_families": sum(len(v) == 1 for v in patterns.values()),
        "lessons_with_required_fixes": sum(any(l["counts"].get(k, 0) for k in ("CRITICAL", "BLOCKING", "MAJOR")) for l in coverage["lessons"]),
        "learner_layer_changed_paths": changed + untracked,
        "snapshot_immutability_anchor": SNAPSHOT_ANCHOR,
        "snapshot_changed_paths": snapshot_delta,
        "validation": "assemble_audit.py проверяет схему и связи оценок; verify_completeness.py — полные наборы, HTML-хеши и неизменность ученического слоя/снимков. Смысловые заключения остаются ручными.",
        "evidence_limit": "Восстановление по сохранённым отпечаткам публикации; не свежий Stepik read-back и не человеческое наблюдение.",
        "independent_critic": summary["independent_critic"],
        "independent_critic_report": summary.get("independent_critic_report"),
    }
    (HERE / "evidence/author-completeness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
