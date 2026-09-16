# Operational Human Pilot Package

**Статус:** `APPROVED / MERGED` через PR #35. Пакет является каноническим operational-слоем Human Pilot Architecture v1.1, которая наследует неизменённые правила полного базового текста v1.0.

**Wave 0 readiness:** `NOT READY / BLOCKED FOR FIRST HUMAN SESSION` по current baseline [`../readiness/wave0-readiness-2026-09-16.md`](../readiness/wave0-readiness-2026-09-16.md).

**Human validation:** `NOT PERFORMED`.

## Назначение

Пакет превращает архитектуру human pilot в воспроизводимые формы и инструкции для Wave 0, Wave 1, fixes/retest и Wave 2. Он не меняет PASS/FAIL, independence, contamination, F1 или evidence contracts архитектуры.

Point update Architecture v1.1 дополнительно требует сохранять PED-01…PED-07 как regression/readiness gates и различать `SOURCE PASS`, `MACHINE PASS`, `HUMAN VISUAL PASS`, `SERVICE PASS` и `HUMAN VALIDATION PASS`. Эти статусы не подменяют друг друга.

## Состав

### Набор и участник
- [`recruitment-screener.md`](recruitment-screener.md) — проверка novice fit и среды.
- [`participant-information-consent.md`](participant-information-consent.md) — информационный лист и шаблон согласия.
- [`data-handling.md`](data-handling.md) — минимизация, редактирование и хранение данных.

### Подготовка среды
- [`stepik-staging-checklist.md`](stepik-staging-checklist.md) — проверка private Stepik staging, current-main equivalence и publication regression gates.
- [`service-preflight-checklist.md`](service-preflight-checklist.md) — краткий preflight PRIMARY/BACKUP и обязательных функций, включая PED-03 live generation + real edit.
- [`recovery-readiness.md`](recovery-readiness.md) — author-only реестр готовых recovery и правило запрета импровизированного зачётного re-check.

### Проведение
- [`pilot-runbook.md`](pilot-runbook.md) — последовательность подготовки и волн.
- [`moderator-guide.md`](moderator-guide.md) — правила поведения модератора, N/P/T/C/S и stuck protocol.
- [`privacy-safety-stop-protocol.md`](privacy-safety-stop-protocol.md) — приоритет безопасности и recovery после stop.
- [`observer-form.md`](observer-form.md) — форма наблюдения на участника/сессию.
- [`f1-observation-form.md`](f1-observation-form.md) — отдельная строгая форма F1.

### Evidence и журналы
- [`evidence-aggregation-rules.md`](evidence-aggregation-rules.md) — правила составного B10/C2 и запрет PASS по неполному evidence.
- [`intervention-log.csv`](intervention-log.csv) — все вмешательства N/P/T/C/S.
- [`session-timing-log.csv`](session-timing-log.csv) — active/wait/break/admin/recovery/F1 timing.
- [`check-evidence-sheet.csv`](check-evidence-sheet.csv) — результаты independent/contributing checks.
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
8. Content-only pilot без доказанного актуального private Stepik staging не может получить полный Human Pilot PASS.
9. Dropout/stop не удаляется из данных и не переклассифицируется как «не участвовал» после старта.
10. Компенсация/благодарность участнику, если она используется, не зависит от completion или PASS.
11. Составные B10 и C2 не получают PASS по одной поздней строке: требуется весь набор evidence из Coverage Matrix.
12. Source/tooling/read-back одной поверхности не закрывает real-world, publication, service или human gate другой поверхности.

## Перед Wave 0

PR #35 доказал готовность самого operational package, но не фактической среды Wave 0.

До первого human session всё равно должны быть **фактически** готовы и проверены:

- private Stepik staging, доказанно соответствующий выбранному актуальному `main` SHA;
- physical assets/materialization и publication checks;
- PED-01 desktop + phone route;
- PED-03 live generation + real edit на актуальных бесплатных PRIMARY/BACKUP;
- PED-06/PED-07 фактические publication/UI checks;
- author-only/recovery visibility и independence regression;
- consent/data-minimization в реальной организационной среде;
- moderator rehearsal;
- актуальный service preflight;
- два eligible Wave 0 participants после закрытия технических/операционных gates.

Пока эти пункты не закрыты evidence, Wave 0 не получает `READY`, а human validation остаётся `NOT PERFORMED`.
