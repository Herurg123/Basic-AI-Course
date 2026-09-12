# Operational Human Pilot Package

**Статус:** рабочий package для реализации утверждённой Human Pilot Architecture v1.0. До отдельного критического аудита и merge не используется с реальными участниками.

**Human validation:** `NOT PERFORMED`.

## Назначение

Пакет превращает архитектуру human pilot в воспроизводимые формы и инструкции для Wave 0, Wave 1, fixes/retest и Wave 2. Он не меняет PASS/FAIL, independence, contamination, F1 или evidence contracts архитектуры.

## Состав

### Набор и участник
- [`recruitment-screener.md`](recruitment-screener.md) — проверка novice fit и среды.
- [`participant-information-consent.md`](participant-information-consent.md) — информационный лист и шаблон согласия.
- [`data-handling.md`](data-handling.md) — минимизация, редактирование и хранение данных.

### Подготовка среды
- [`stepik-staging-checklist.md`](stepik-staging-checklist.md) — проверка private Stepik staging.
- [`service-preflight-checklist.md`](service-preflight-checklist.md) — краткий preflight PRIMARY/BACKUP и обязательных функций.
- [`recovery-readiness.md`](recovery-readiness.md) — author-only реестр готовых recovery и правило запрета импровизированного зачётного re-check.

### Проведение
- [`pilot-runbook.md`](pilot-runbook.md) — последовательность подготовки и волн.
- [`moderator-guide.md`](moderator-guide.md) — правила поведения модератора, N/P/T/C/S и stuck protocol.
- [`privacy-safety-stop-protocol.md`](privacy-safety-stop-protocol.md) — приоритет безопасности и recovery после stop.
- [`observer-form.md`](observer-form.md) — форма наблюдения на участника/сессию.
- [`f1-observation-form.md`](f1-observation-form.md) — отдельная строгая форма F1.

### Журналы
- [`intervention-log.csv`](intervention-log.csv) — все вмешательства N/P/T/C/S.
- [`session-timing-log.csv`](session-timing-log.csv) — active/wait/break/admin/recovery/F1 timing.
- [`check-evidence-sheet.csv`](check-evidence-sheet.csv) — результаты independent checks.
- [`issue-log.csv`](issue-log.csv) — findings `HP-<wave>-NN`.
- [`fix-retest-tracker.csv`](fix-retest-tracker.csv) — fix → required retest → fresh confirmation.

### Отчётность
- [`wave-summary-template.md`](wave-summary-template.md) — итог одной волны.
- [`final-human-validation-report-template.md`](final-human-validation-report-template.md) — итоговый gate verdict.

## Жёсткие правила использования

1. Реальный человек, а не модель, является участником human validation.
2. Модератор не помогает получить PASS. Content help = `PRACTICE / CONTAMINATED` для текущей independent attempt.
3. Technical/interface help логируется отдельно и не превращается в content hint.
4. Safety/privacy stop имеет приоритет над чистотой попытки.
5. B3 — действие до transfer; B8 — реальный edit; B10 — реально открытое основание; B12/F1 — фактическое применение.
6. F1 не собирается модератором. Content hint во время F1 требует другой новой реальной задачи.
7. Human evidence хранится минимально и псевдонимно; чувствительный контент не коммитится в GitHub.
8. Content-only pilot без Stepik staging не может получить полный Human Pilot PASS.
9. Dropout/stop не удаляется из данных и не переклассифицируется как «не участвовал» после старта.
10. Компенсация/благодарность участнику, если она используется, не зависит от completion или PASS.

## Перед Wave 0

Пакет должен пройти отдельный branch → PR → critic → merge. Затем должны быть готовы private Stepik staging, consent/data-minimization, moderator rehearsal, recovery readiness и service preflight. Только после этого начинается первый human session.
