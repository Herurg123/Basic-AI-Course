# Response to independent architectural critic — round 1

Проверенный critic report: `critic-round1.md`.

## CR2-01 — fixed

Зафиксирован exact opt-in contract:

`<!-- learner-render-contract: authored-semantic-v1 -->`

Он хранится только в `stepik-plan.md`, до таблицы, и не попадает learner-facing.

Title contract теперь детерминирован:
- только первый authored H2/H3 semantic span из `lesson.md`;
- отсутствие authored heading = compile error;
- lesson-title/generated/parallel production-title fallback запрещены.

Таким образом, production executor больше не выбирает metadata syntax или title source.

## CR2-02 — fixed

Для каждого row opt-in lesson введена отдельная non-visible колонка `Semantic type`.

Допустимы только 10 enum Semantic Step Contract:
EXPLANATION, DEMONSTRATION, GUIDED_ACTION, INDEPENDENT_PRACTICE, CHECK, REFLECTION, NAVIGATION, TECHNICAL_SUPPORT, RECOVERY, COMPOSITE.

Правила:
- missing/unknown type = compile error;
- type используется для validation/tests/audit;
- type не генерирует learner-facing текст и не создаёт visible sections;
- COMPOSITE не является fallback для неясной границы.

Это не второй canonical learner source: смысл остаётся в `lesson.md`, production mapping — в `stepik-plan.md`.

## CR2-03 — fixed

B7 теперь требует три отдельных PASS:
1. ordinary independent critic;
2. full ZERO-LEVEL audit по **100% final learner inventory N/N**;
3. full PEDAGOGUE audit по **100% final learner inventory N/N**.

Исходный baseline до production = 148 steps. Жёстко требовать 148 после boundary repair было бы ошибкой: обоснованная коррекция semantic boundaries может изменить N. Поэтому при любом изменении step count сначала обязательна полная old→new reconciliation IDs/URLs/links, затем оба финальных аудита покрывают N/N.

Scoped audits B1–B6 не заменяют final whole-course dual gate.

## Синхронизированные документы

Исправления внесены в:
- `step-role-architecture-v1.0.md`;
- `implementation-backlog.md`;
- `production-batches.md`;
- `regression-test-plan.md`;
- `layer-change-matrix.md`;
- `PRODUCTION-HANDOFF.md`;
- `production-prompt-sol-high.md`.

Текущий head после исправлений: `85fe3ed7e3b43256eb5f2d5b77eb38d08c536e13`.

Learner-facing course не менялся.
