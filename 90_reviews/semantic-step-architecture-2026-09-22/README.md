# Шаг 2 — архитектура semantic-step repair

Дата: 22 сентября 2026 года.

## Состояние

Шаг 1 закрыт диагностическим PASS и merged:

- PR #116;
- Step 1 merge SHA: `ad7f3645d4866fd1fb1569801f70a95b6b39e375`;
- audited learner source pin: `d076dd06977ecc85db66abb1d3fc503eb7343d48`;
- 9 modules / 21 lessons / 148 steps;
- 0 CRITICAL / 38 BLOCKING / 87 MAJOR / 19 POLISH / 4 CLEAN;
- 118 findings / 19 families;
- critic round 2 PASS.

Шаг 2 не меняет learner-facing курс. Его результат — implementation design для следующего SOL/HIGH production stage.

## Артефакты

- [step-role-architecture-v1.0.md](step-role-architecture-v1.0.md) — окончательная архитектура ролей, границ, места/объекта/result/completion/save/transition/support/recovery/independence.
- [repair-mapping.json](repair-mapping.json) — 19 families → exact findings/steps → solution/layer/competence/guard/dependencies/acceptance.
- [implementation-backlog.md](implementation-backlog.md) — 22 production tasks.
- [production-batches.md](production-batches.md) — 8 безопасных batches B0–B7.
- [regression-test-plan.md](regression-test-plan.md) — machine + semantic regression contract.
- [layer-change-matrix.md](layer-change-matrix.md) — где нужны renderer/source/plan/assets/local/systemic changes.
- [risk-calibrations.md](risk-calibrations.md) — спорные зоны, которые нельзя механически «исправлять».
- [PRODUCTION-HANDOFF.md](PRODUCTION-HANDOFF.md) — полный handoff следующему этапу.
- [production-prompt-sol-high.md](production-prompt-sol-high.md) — самодостаточный prompt SOL/HIGH.
- [critic-round1.md](critic-round1.md) — REQUEST_CHANGES; [critic-response.md](critic-response.md) — адресные исправления; [critic-round2.md](critic-round2.md) — PASS; [critic-status.json](critic-status.json) — formal state.

## Главные решения

1. Старый universal frame не переписывается другим universal frame.
2. Новый compiler contract вводится opt-in как `authored-semantic-v1`.
3. Legacy output сохраняется для ещё не мигрированных уроков.
4. Уроки мигрируются batches, каждый с final HTML + critic + ZERO-LEVEL + PEDAGOGUE audit.
5. Stepik write откладывается до whole-course integration B7.
6. Все 21 lessons должны закончить миграцию в authored mode; затем legacy code удаляется.
7. Автотесты ловят структуру, но не заменяют semantic zero-level reading.
8. M07-L02 остаётся единственным F1; M07-L01 rehearsal; M08 reflection.
9. HUMAN VISUAL, SERVICE, Human Pilot и Wave 0 не закрываются Шагом 2.

## Step 2 gate

Перед merge архитектурного PR нужен отдельный adversarial critic. Если он находит обычные исправимые замечания — исправить и повторить critic. Реальное противоречие обязательному принципу передаётся владельцу.
