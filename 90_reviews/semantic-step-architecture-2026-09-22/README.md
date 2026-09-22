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
2. Все 21 lessons завершили миграцию в exact `authored-semantic-v1`.
3. Production compiler больше не имеет legacy fallback: отсутствие authored contract = compile error.
4. Текущий канон: 150 structural rows, из них 2 author-only и **148 learner-facing steps**.
5. `Semantic type` обязателен для всех production rows; learner block type определяется semantic role и явным владением Check ID у `COMPOSITE`, а не угадывается по словам в logical type.
6. Stepik write разрешается только после whole-course B7 integration/audits и merge в `main`.
7. Автотесты ловят структуру, но не заменяют 100% semantic ZERO-LEVEL и PEDAGOGUE reading финального курса.
8. M07-L02 остаётся единственным F1; M07-L01 rehearsal; M08 reflection.
9. HUMAN VISUAL, SERVICE, Human Pilot и Wave 0 не закрываются compiler migration или B7 source PASS.

## Step 2 gate

Перед merge архитектурного PR нужен отдельный adversarial critic. Если он находит обычные исправимые замечания — исправить и повторить critic. Реальное противоречие обязательному принципу передаётся владельцу.
