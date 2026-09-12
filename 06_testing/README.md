# Testing

Материалы pilot, human validation и beta-тестирования: архитектура проверки, сценарии, критерии, наблюдения, точки непонимания, технические барьеры и результаты проверки самостоятельности ученика.

## Текущие материалы

- [`human-pilot/`](human-pilot/) — утверждённые Human Pilot Architecture v1.0 и operational package для следующего обязательного gate HUMAN PILOT / HUMAN VALIDATION. Human sessions ещё не проводились; human validation остаётся `NOT PERFORMED`.
- [`service-acceptance/`](service-acceptance/) — Service Acceptance динамического сервисного маршрута.
- [`synthetic-prepilot-m00-m01/synthetic-prepilot-2026-09-11.md`](synthetic-prepilot-m00-m01/synthetic-prepilot-2026-09-11.md) — model-based synthetic pre-pilot M00–M01.
- [`synthetic-prepilot-m02-m03/synthetic-prepilot-2026-09-11.md`](synthetic-prepilot-m02-m03/synthetic-prepilot-2026-09-11.md) — model-based synthetic pre-pilot M02–M03.
- [`synthetic-prepilot-m04-m05/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m04-m05/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot M04–M05.
- [`synthetic-prepilot-m06/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m06/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot M06 с adversarial-проверкой false-pass, independence и фактического применения.
- [`synthetic-prepilot-m07-m08/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m07-m08/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot финального production batch M07–M08 с проверкой F1 false-PASS, actual application, contamination recovery и границы M08.
- [`../90_reviews/full-cumulative-audit-m00-m08-2026-09-12.md`](../90_reviews/full-cumulative-audit-m00-m08-2026-09-12.md) — полный независимый cumulative audit M00–M08 на `main` @ `de0c7cbd...`; verdict `PASS / CLEAN`, CRITICAL = 0, NONCRITICAL BLOCKING = 0.

Все synthetic/model-based проверки являются дополнительной симуляцией и **не human pilot**. Они не заменяют обязательную проверку курса на настоящих новичках.

Полный cumulative production gate M00–M08 пройден. Human Pilot Architecture v1.0 и operational package утверждены и смёржены. Текущий статус: `HUMAN PILOT DESIGNED / OPERATIONAL PACKAGE APPROVED / NOT YET PERFORMED`; human validation = `NOT PERFORMED`.

Следующий gate теперь не производство ещё одного документа, а **Wave 0 readiness**: private Stepik staging, consent/data-minimization в рабочей среде, moderator rehearsal, recovery readiness и актуальный service preflight. Пока эти пункты не подтверждены, Wave 0 не считается `READY`.

После readiness последовательность: Wave 0 → Wave 1 → подтверждённые fixes → Wave 2 / retest → итоговый human-validation verdict. Только после human validation возможен переход к closed beta; финальные динамические service/Stepik checks и public release остаются последующими gates.
