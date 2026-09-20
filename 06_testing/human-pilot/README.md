# Human Pilot

Этот каталог содержит архитектуру и operational-материалы проверки курса на реальных пользователях нулевого уровня.

## Текущий статус

`HUMAN PILOT DESIGNED / OPERATIONAL PACKAGE APPROVED / NOT YET PERFORMED`.

**Current Wave 0 readiness:** `NOT READY / BLOCKED FOR FIRST HUMAN SESSION` по baseline от 20.09.2026. Технический private Stepik staging уже имеет `MACHINE PASS / ZERO-PENDING`; открыты реальные device/HUMAN VISUAL, service, operational privacy и moderator-rehearsal gates.

Human validation остаётся `NOT PERFORMED`: реальные human sessions ещё не проводились.

До фактического прохождения предусмотренных human waves:

- model/synthetic pre-pilot не считается human validation;
- SOURCE PASS, MACHINE PASS, HUMAN VISUAL PASS и SERVICE PASS не подменяют HUMAN VALIDATION PASS;
- фактическая длительность, понятность и самостоятельность реальных новичков не считаются подтверждёнными;
- переход к closed beta не разрешён.

## Документы

- [`human-pilot-architecture-v1.1.md`](human-pilot-architecture-v1.1.md) — текущий point update Human Pilot Architecture: наследует неизменённые правила v1.0, актуализирует нормативные ссылки и закрепляет PED-01…PED-07 как regression/readiness contract.
- [`human-pilot-architecture-v1.0.md`](human-pilot-architecture-v1.0.md) — исторический полный базовый текст sample, waves, moderator/intervention rules, contamination/recovery, evidence, F1 protocol, severity, PASS/FAIL и retest rules; утверждён через PR #33 и не переписывается задним числом.
- [`operational-package/`](operational-package/) — утверждённый через PR #35 набор для реального проведения Wave 0/Wave 1/Wave 2: screener, consent, staging/preflight, moderator/observer/F1 forms, logs, recovery/evidence rules, issue/retest tracking и report templates.
- [`readiness/wave0-readiness-2026-09-20.md`](readiness/wave0-readiness-2026-09-20.md) — **текущий** readiness record после полного private Stepik sync; verdict `NOT READY / BLOCKED FOR FIRST HUMAN SESSION`, но machine staging уже `PASS / ZERO-PENDING`.
- [`readiness/wave0-readiness-2026-09-16.md`](readiness/wave0-readiness-2026-09-16.md) — исторический readiness record до полного staging sync; сохраняется неизменным как evidence своей даты.
- [`readiness/wave0-readiness-2026-09-12.md`](readiness/wave0-readiness-2026-09-12.md) — исторический readiness record состояния на 12.09.2026; сохраняется неизменным как evidence своей даты.

## До Wave 0

Сам факт утверждения package или наличие Stepik tooling не означает готовность первой human session. До Wave 0 должны быть фактически закрыты:

- доказанная эквивалентность private Stepik staging выбранному актуальному `main` SHA — **закрыта на MACHINE-уровне**;
- physical asset materialization — **закрыта на MACHINE-уровне**, но publication/HUMAN VISUAL checks остаются открыты;
- PED-01 desktop + phone route;
- PED-03 live generation + real edit на актуальном бесплатном PRIMARY/BACKUP;
- PED-06 обе publication branches и PED-07 итоговый learner-facing Stepik UI;
- author-only/recovery visibility и independence regression, включая CRIT-C-01;
- consent/data-minimization в реальной организационной среде;
- moderator rehearsal по N/P/T/C/S;
- актуальный service preflight;
- два eligible Wave 0 participant после закрытия остальных readiness gates.

Только после подтверждения этих readiness-пунктов: Wave 0 → Wave 1 → подтверждённые fixes → Wave 2/retest → итоговый human-validation verdict.

Никакой документ в этом каталоге сам по себе не означает, что реальные участники уже прошли курс.
