# Testing

Материалы пилота и бета-тестирования: сценарии, критерии, наблюдения, точки непонимания, технические барьеры и результаты проверки самостоятельности ученика.

## Текущие материалы

- [`service-acceptance/`](service-acceptance/) — Service Acceptance динамического сервисного маршрута.
- [`synthetic-prepilot-m00-m01/synthetic-prepilot-2026-09-11.md`](synthetic-prepilot-m00-m01/synthetic-prepilot-2026-09-11.md) — model-based synthetic pre-pilot M00–M01.
- [`synthetic-prepilot-m02-m03/synthetic-prepilot-2026-09-11.md`](synthetic-prepilot-m02-m03/synthetic-prepilot-2026-09-11.md) — model-based synthetic pre-pilot M02–M03.
- [`synthetic-prepilot-m04-m05/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m04-m05/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot M04–M05.
- [`synthetic-prepilot-m06/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m06/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot M06 с adversarial-проверкой false-pass, independence и фактического применения.
- [`synthetic-prepilot-m07-m08/synthetic-prepilot-2026-09-12.md`](synthetic-prepilot-m07-m08/synthetic-prepilot-2026-09-12.md) — model-based synthetic pre-pilot финального production batch M07–M08 с проверкой F1 false-PASS, actual application, contamination recovery и границы M08.

Все synthetic/model-based проверки являются дополнительной симуляцией и **не human pilot**. Они не заменяют обязательную проверку курса на настоящих новичках.

Human pilot пока не проведён. Его отсутствие по `D-2026-09-11-PILOT-DEFER` не блокировало production M02–M08, но human validation остаётся обязательным до beta / публичного выпуска.
