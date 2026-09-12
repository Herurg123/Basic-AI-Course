# Human Pilot

Этот каталог содержит архитектуру и operational-материалы проверки курса на реальных пользователях нулевого уровня.

## Текущий статус

`HUMAN PILOT DESIGNED / NOT YET PERFORMED`.

До фактического прохождения предусмотренных human waves:

- human validation = `NOT PERFORMED`;
- model/synthetic pre-pilot не считается human validation;
- фактическая длительность, понятность и самостоятельность реальных новичков не считаются подтверждёнными;
- переход к closed beta не разрешён.

## Документы

- [`human-pilot-architecture-v1.0.md`](human-pilot-architecture-v1.0.md) — утверждённые sample, waves, moderator/intervention rules, contamination/recovery, evidence, F1 protocol, severity, PASS/FAIL и retest rules.
- [`operational-package/`](operational-package/) — формы и инструкции для реального проведения Wave 0/Wave 1/Wave 2: screener, consent, staging/preflight, moderator/observer/F1 forms, logs, issue/retest tracking и report templates. До отдельного audit + merge package не используется с участниками.

## Порядок запуска

Operational package проходит обычный project workflow `branch → PR → critic → merge`. После его утверждения до Wave 0 должны быть готовы private Stepik staging, consent/data-minimization, moderator rehearsal и service preflight.

Далее: Wave 0 → Wave 1 → подтверждённые fixes → Wave 2/retest → итоговый human-validation verdict.

Никакой документ в этом каталоге сам по себе не означает, что реальные участники уже прошли курс.
