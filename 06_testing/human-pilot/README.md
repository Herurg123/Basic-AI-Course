# Human Pilot

Этот каталог содержит архитектуру и будущие operational-материалы проверки курса на реальных пользователях нулевого уровня.

## Текущий статус

`HUMAN PILOT DESIGNED / NOT YET PERFORMED` действует только после утверждения и merge архитектуры в `main`.

До фактического прохождения предусмотренных human waves:

- human validation = `NOT PERFORMED`;
- model/synthetic pre-pilot не считается human validation;
- фактическая длительность, понятность и самостоятельность реальных новичков не считаются подтверждёнными;
- переход к closed beta не разрешён.

## Документы

- [`human-pilot-architecture-v1.0.md`](human-pilot-architecture-v1.0.md) — sample, waves, moderator/intervention rules, contamination/recovery, evidence, F1 protocol, severity, PASS/FAIL и retest rules.

## Следующий deliverable после утверждения архитектуры

Отдельный production-исполнитель создаёт operational pilot package: screener, consent, moderator guide, observer/evidence forms, intervention/timing logs, F1 form, issue/retest tracking, data-minimization rules и service preflight checklist.

Operational package проходит обычный project workflow `branch → PR → critic → merge` до запуска Wave 0.

Никакой документ в этом каталоге сам по себе не означает, что реальные участники уже прошли курс.
