# Live safety GitHub → Stepik

## Current-main guard

Перед live Stepik API workflow подтверждает, что run выполняется на актуальном HEAD `main`. Stale SHA, feature branch или недоступный GitHub state = STOP.

## Private course

Production staging course `299189` должен оставаться private во время write/recovery release.

## Mutex

Все live operations используют один concurrency group: `stepik-live-course-299189`.

## Baseline guard

Для lesson с baseline fresh live обязан совпасть с доказанным baseline или с доказанным recovery state. Совпадение с canonical само по себе не является доказательством происхождения.

## Write-ahead history

До внешнего write: `WRITE_INTENT`. Непосредственно перед HTTP dispatch: `WRITE_DISPATCH_STARTED`. После операции обязателен read-back. После всего объекта обязателен `FINAL_READBACK_CONFIRMED`.

Unknown result после dispatch = ambiguous и STOP. Blind retry запрещён.

## State commit

Machine state изменяется только после final read-back. Перед PATCH Issue #54 выполняется повторное чтение и exact compare. Затем history получает `MACHINE_STATE_COMMITTED`.

## Recovery

- final live уже подтверждён, state PATCH отсутствует → state-only recovery, 0 Stepik writes;
- подтверждён partial prefix → continuation только оставшихся operations;
- ambiguous/manual/unknown divergence → STOP и owner decision.

## Structure

Автоматический destructive change запрещён. Удаление/reorder неизвестной структуры требует отдельной доказанной миграции. `DELETE` не используется.

## Fail closed

Если identity, baseline, history, current source, write result или read-back нельзя однозначно доказать, automation не пишет.
