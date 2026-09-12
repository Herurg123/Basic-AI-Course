# Human Pilot

Этот каталог содержит архитектуру и operational-материалы проверки курса на реальных пользователях нулевого уровня.

## Текущий статус

`HUMAN PILOT DESIGNED / OPERATIONAL PACKAGE APPROVED / NOT YET PERFORMED`.

Human validation остаётся `NOT PERFORMED`: реальные human sessions ещё не проводились.

До фактического прохождения предусмотренных human waves:

- model/synthetic pre-pilot не считается human validation;
- фактическая длительность, понятность и самостоятельность реальных новичков не считаются подтверждёнными;
- переход к closed beta не разрешён.

## Документы

- [`human-pilot-architecture-v1.0.md`](human-pilot-architecture-v1.0.md) — утверждённые sample, waves, moderator/intervention rules, contamination/recovery, evidence, F1 protocol, severity, PASS/FAIL и retest rules; утверждена через PR #33.
- [`operational-package/`](operational-package/) — утверждённый через PR #35 набор для реального проведения Wave 0/Wave 1/Wave 2: screener, consent, staging/preflight, moderator/observer/F1 forms, logs, recovery/evidence rules, issue/retest tracking и report templates.

## До Wave 0

Сам факт утверждения package не означает готовность первого human session. До Wave 0 должны быть фактически закрыты:

- private Stepik staging и его checklist = `READY`;
- consent/data-minimization в реальной организационной среде;
- moderator rehearsal по N/P/T/C/S;
- recovery readiness;
- актуальный service preflight.

Только после подтверждения этих readiness-пунктов: Wave 0 → Wave 1 → подтверждённые fixes → Wave 2/retest → итоговый human-validation verdict.

Никакой документ в этом каталоге сам по себе не означает, что реальные участники уже прошли курс.
