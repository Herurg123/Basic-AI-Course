"""Сводит вручную написанные заключения; не оценивает смысл автоматически."""
from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = ["CRITICAL", "BLOCKING", "MAJOR", "POLISH", "CLEAN"]
REQUIRED = {
    "position", "semantic_type", "learner_task", "work_location", "work_object",
    "observable_result", "save_requirement", "completion", "required_blocks",
    "superfluous_blocks", "ambiguous_pointers", "prerequisite_gap", "term_gap",
    "previous_link", "next_link", "severity", "finding_ids", "required_fix",
}
TYPES = {"EXPLANATION", "DEMONSTRATION", "GUIDED_ACTION", "INDEPENDENT_PRACTICE", "CHECK", "REFLECTION", "NAVIGATION", "TECHNICAL_SUPPORT", "RECOVERY", "COMPOSITE"}
PATTERNS = {
    "FRAME_LOCATION_FROM_WORDS": "Место работы ошибочно выводится из упомянутых слов",
    "UNIVERSAL_FRAME": "Одинаковые рубрики создают фиктивные действия, сохранение и завершение",
    "CHUNK_BOUNDARY": "Граница сборки разрывает связанную инструкцию",
    "INLINE_AT_END": "Нужный материал встроен после завершения и перехода",
    "SUPPORT_AT_END": "Техническая помощь появляется после места потребности",
    "UNTAUGHT_CHAT_OPERATION": "Операция нового диалога предполагается до первого объяснения",
    "UNDEFINED_CHECK_RESPONSE": "Поле проверки не имеет понятного требования к ответу",
    "BACKUP_ROUTE_CONTEXT": "Резерв не учитывает различие рабочей операции и состояния чата",
}


def write_json(name: str, value: object) -> None:
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    reconstruction = json.loads((HERE / "evidence/reconstruction-report.json").read_text())
    pin = reconstruction["source_sha"]
    reviews = {p.stem: json.loads(p.read_text()) for p in (HERE / "reviews").glob("*.json")}
    steps, findings, lessons = [], [], []
    for path in sorted((HERE / "rendered").glob("*.json")):
        source = json.loads(path.read_text())
        lesson_id = source["lesson_id"]
        review = reviews.get(lesson_id)
        if review:
            assert review["source_sha"] == pin and review["review_status"] == "REVIEWED"
            assert len(review["steps"]) == len(source["steps"]), lesson_id
            judgments = {row["position"]: row for row in review["steps"]}
            assert len(judgments) == len(source["steps"]), lesson_id
            for finding in review["findings"]:
                assert finding["severity"] in ORDER and finding["fix"]
                assert finding["pattern"] in PATTERNS
                findings.append({"lesson_id": lesson_id, **finding})
        else:
            judgments = {}
        counts = Counter()
        for actual in source["steps"]:
            position = actual["position"]
            row = {
                "module_id": lesson_id.split("-")[0], "lesson_id": lesson_id,
                "step_key": actual["step_key"], "position": position,
                "visible_title": html.unescape(re.sub(r"<[^>]+>", "", actual["visible_title_html"] or "")),
                "stepik_url": actual["stepik_url"], "platform_block_type": actual["platform_block_type"],
                "snapshot_path": str(path.relative_to(HERE)), "html_sha256": actual["html_sha256"],
                "review_status": "REVIEWED" if review else "NOT_REVIEWED",
            }
            if review:
                judgment = judgments[position]
                assert REQUIRED <= judgment.keys(), (lesson_id, position, REQUIRED - judgment.keys())
                assert judgment["semantic_type"] in TYPES and judgment["severity"] in ORDER
                row.update(judgment)
                counts[judgment["severity"]] += 1
            else:
                row.update({key: None for key in sorted(REQUIRED - {"position"})})
                counts["NOT_REVIEWED"] += 1
            steps.append(row)
        lessons.append({"lesson_id": lesson_id, "step_count": len(source["steps"]), "reviewed": bool(review), "counts": dict(counts), "summary": review["lesson_summary"] if review else "Индивидуальный аудит ещё не выполнен"})
    assert len({r["step_key"] for r in steps}) == len(steps) == reconstruction["step_count"]
    assert len(lessons) == reconstruction["lesson_count"] == 21
    assert len({r["module_id"] for r in steps}) == reconstruction["module_count"] == 9
    index = {r["id"]: r for r in findings}
    assert len(index) == len(findings), "Повтор ID находки"
    for step in steps:
        if step["review_status"] != "REVIEWED":
            continue
        affected = [f for f in findings if f["lesson_id"] == step["lesson_id"] and str(step["position"]) in f["steps"]]
        assert set(step["finding_ids"]) == {f["id"] for f in affected}, step["step_key"]
        if affected:
            worst = min((f["steps"][str(step["position"])] for f in affected), key=ORDER.index)
            assert worst == step["severity"], step["step_key"]
        else:
            assert step["severity"] == "CLEAN", step["step_key"]
    totals = Counter(r["severity"] if r["review_status"] == "REVIEWED" else "NOT_REVIEWED" for r in steps)
    summary = {"source_sha": pin, "status": "COMPLETE_AUTHOR_REVIEW" if not totals["NOT_REVIEWED"] else "PARTIAL", "modules_total": 9, "lessons_total": 21, "steps_total": len(steps), "lessons_reviewed": sum(r["reviewed"] for r in lessons), "steps_reviewed": len(steps) - totals["NOT_REVIEWED"], "counts": {key: totals[key] for key in [*ORDER, "NOT_REVIEWED"]}, "findings_total": len(findings), "independent_critic": "NOT_PERFORMED"}
    write_json("step-inventory.json", {"schema_version": 1, "summary": summary, "steps": steps})
    write_json("findings.json", {"summary": summary, "findings": findings})
    write_json("coverage-summary.json", {"summary": summary, "lessons": lessons})
    intro = f"Проверено по смыслу **{summary['steps_reviewed']} из {len(steps)} шагов**, **{summary['lessons_reviewed']} из 21 урока**. Остальные явно помечены NOT_REVIEWED. Независимый критик ещё не выполнен.\n"
    table = ["# Матрица уроков — рабочая сводка\n", intro, "\n| Урок | Шагов | CRITICAL | BLOCKING | MAJOR | POLISH | CLEAN | Не проверено |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for lesson in lessons:
        c = lesson["counts"]
        table.append(f"| {lesson['lesson_id']} | {lesson['step_count']} | " + " | ".join(str(c.get(k, 0)) for k in [*ORDER, "NOT_REVIEWED"]) + " |")
    table += ["\n## Смысловые заключения по прочитанным урокам\n"]
    for lesson in lessons:
        if lesson["reviewed"]:
            table.append(f"- **{lesson['lesson_id']}:** {lesson['summary']}")
    (HERE / "lesson-verdicts.md").write_text("\n".join(table) + "\n")
    lines = ["# Реестр находок — рабочий\n", intro, "Одной находке могут соответствовать несколько шагов с разными последствиями. В сводке шаг учитывается один раз по наибольшей серьёзности.\n"]
    for f in findings:
        lines += [f"## {f['id']} — {f['severity']} — {f['lesson_id']}\n", f"Общая причина: `{f['pattern']}` — {PATTERNS[f['pattern']]}.\n", "Шаги: " + ", ".join(f"{f['lesson_id']}-S{int(p):02d} ({s})" for p, s in f["steps"].items()) + ".\n", "Антипаттерны: " + ", ".join(f["antipatterns"]) + ".\n", f["problem"] + "\n", "Доказательства:\n", *[f"- {q}" for q in f["evidence"]], "\nТребование к исправлению: " + f["fix"] + "\n", "Защита самостоятельности: " + f["independence_guard"] + "\n"]
    (HERE / "findings.md").write_text("\n".join(lines) + "\n")
    grouped = defaultdict(list)
    for f in findings:
        grouped[f["pattern"]].append(f)
    lines = ["# Общие причины — рабочий реестр\n", intro, "Повтор внутри одного урока ещё не подтверждает межурочную распространённость. Область каждой причины расширяется только после индивидуального чтения новых шагов.\n"]
    for pattern, group in sorted(grouped.items()):
        addresses = sorted({f"{f['lesson_id']}-S{int(p):02d}" for f in group for p in f["steps"]})
        lesson_ids = sorted({f["lesson_id"] for f in group})
        lines += [f"## {pattern}\n", PATTERNS[pattern] + ".\n", f"Подтверждено в {len(addresses)} шагах / {len(lesson_ids)} уроках: " + ", ".join(addresses) + ".\n", "Находки: " + ", ".join(f["id"] for f in group) + ".\n"]
    (HERE / "cross-course-patterns.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
