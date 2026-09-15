# Автоматизация переноса и эксплуатационной синхронизации курса в Stepik

**Статус:** production automation contract / implementation handoff  
**Дата:** 14 сентября 2026 года  
**Курс Stepik:** `299189`  
**Источник learner-facing содержания:** только актуальный `main`

Этот каталог описывает технический контур GitHub → Stepik. Он не меняет педагогическую архитектуру курса, Lesson/Exercise/Check/Asset ID, F1, recovery для ученика или Human Pilot.

## 1. Текущий production scope

Автоматизация умеет:

- читать фактическую структуру существующего курса Stepik;
- строить derived structural/build representation из canonical GitHub files;
- выполнять offline dry-run и all-course read-only preflight;
- распознавать два golden lessons `M00-L01/M00-L02` как `READ_ONLY`;
- вести confirmed baseline и machine-readable PENDING в Issue `#54`;
- определять learner-facing impact dependency-aware способом;
- выполнять узкий guarded exploitation sync pilot lesson `M02-L01`;
- durable-журналировать deployment/recovery operations;
- восстанавливаться после доказуемого partial/state-patch failure без blind retry;
- выполнять read-only baseline reconcile classification;
- проверять эксплуатационную ownership matrix автоматическим completeness test.

Общий bulk write по-прежнему закрыт.

## 2. Канонические источники и derived state

Learner-facing content берётся только из `main`, прежде всего из:

- `lesson.md`;
- `stepik-plan.md`;
- learner-facing assets;
- утверждённых production документов Stepik.

Operational state разделён на три слоя:

1. current machine state в Issue `#54`;
2. immutable deployment/recovery history в derived branch `stepik-deployment-history-v1`;
3. human-readable comments Issue `#54`.

Ни Issue, ни history branch не являются content source.

Подробности:

- [`SYNC-POLICY.md`](SYNC-POLICY.md);
- [`LIVE-SAFETY.md`](LIVE-SAFETY.md);
- [`DEPLOYMENT-HISTORY.md`](DEPLOYMENT-HISTORY.md);
- [`RECOVERY-RECONCILE.md`](RECOVERY-RECONCILE.md);
- [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

## 3. Golden sample

Первые два вручную созданных урока остаются платформенным эталоном:

- `M00-L01`;
- `M00-L02`.

Обычный uploader/recovery не изменяет и не удаляет их. Если фактическая Stepik representation расходится с предположениями uploader, исправляется uploader, а не golden sample.

## 4. Безопасные режимы

### Inspect / dry-run

Только чтение и локальная компиляция. POST/PUT/DELETE отсутствуют.

### Bulk Status

`Stepik Bulk Status` читает весь курс и строит preflight для 21 canonical lessons. Даже зелёный preflight не устанавливает `ready_for_bulk_write=true` автоматически.

Подробный контракт: [`BULK-STATUS.md`](BULK-STATUS.md).

### Impact after merge

Push в `main` не пишет в Stepik. Workflow:

- строит before/after dependency graph;
- определяет direct/shared learner impact;
- обновляет PENDING Issue `#54` через compare-before-PATCH guard.

Unknown/ambiguous learner dependency = `STOP`.

### `sync-status`

Live read-only проверка pilot target против canonical desired state и confirmed baseline.

### `sync-reconcile`

Live **read-only** route для сопоставления:

- current `main`;
- current machine state;
- fresh live Stepik;
- immutable deployment history.

Reconcile классифицирует provenance и допустимое действие, но сам не пишет в Stepik и не делает automatic rebaseline.

### `sync-changed`

Единственный текущий exploitation write route для pilot `M02-L01`.

Требует owner dispatch, `confirm_write`, current-main guard, live mutex, baseline/history checks и verified read-back.

## 5. Durable deployment history

До каждого внешнего Stepik write automation сохраняет `WRITE_INTENT` в derived operational history.

Для logical event сохраняются минимум:

- stable event ID;
- canonical object/kind;
- source SHA;
- workflow/run identity;
- state/baseline before;
- desired fingerprint;
- Stepik object IDs;
- per-operation intent/result/read-back;
- final read-back;
- failure/recovery reason;
- machine-state commit.

History record append-only: identical retry является no-op, попытка переписать тот же record другим payload блокируется.

## 6. Partial-write recovery

Blind write retry запрещён.

Основные случаи:

- write не начинался: normal route возможен только если guards всё ещё подтверждены;
- final Stepik state уже verified, но Issue PATCH не состоялся: разрешён state-only recovery с `0` повторных Stepik writes;
- partial prefix verified и fresh live точно совпадает с last confirmed intermediate fingerprint: можно продолжить только remaining operations;
- timeout/network/HTTP 5xx с неизвестным server-side outcome: `WRITE_AMBIGUOUS`, STOP;
- failed read-back: state не считается confirmed;
- manual change после automation residue: owner decision;
- новый `main` после начала event: old event не может закрыть новый pending.

## 7. Pending и baseline

Issue `#54` использует sync state schema v2.

На Lesson ID существует один active pending object. Повторный merge:

- сохраняет `first_pending_sha/at`;
- обновляет `latest_pending_sha/at`;
- объединяет `source_paths/reason_codes`.

Pending закрывается только после:

- `APPLIED`; или
- `NOOP_CONFIRMED`.

`APPLIED` обновляет baseline только после final verified read-back. `NOOP_CONFIRMED` не выполняет фиктивный write.

## 8. Race guarantees

Сохраняются одновременно:

- fresh current-main guard;
- единый mutex `stepik-live-course-299189`;
- durable write-ahead history;
- per-operation и final read-back;
- Issue state guard `read expected → re-read current → compare → PATCH only if unchanged`;
- `MACHINE_STATE_COMMITTED` только после успешного current-state PATCH.

Unknown state = `STOP`.

## 9. API write policy

Автоматический write retry отсутствует.

Write result классифицируется так:

- known failure: failed operation;
- timeout/network failure/HTTP 5xx/неоднозначный response: ambiguous outcome;
- HTTP success без подтверждённого read-back: не confirmed deployment.

`DELETE` не реализуется и не разрешается recovery route.

## 10. Asset route

Предпочтительный route для assets остаётся Stepik Files, если он фактически и стабильно доступен.

Если стабильный upload API не подтверждён, automation не выдумывает endpoint. Используется skeleton/manual upload + non-secret Asset ID → URL map.

Fallback может использовать внешнее стабильное хранилище при условии, что ученик получает материал без специальных технических требований.

Asset URL никогда не конструируется по догадке.

## 11. Derived asset URL map

Карта Asset ID → фактический URL является derived operational data. Если URL неизвестен, поле не заполняется фиктивным значением, а зависимый content route блокируется.

Пример структуры:

```yaml
M00-L02-A01:
  storage: stepik-lesson-file
  lesson_id: 123456
  url: https://stepik.org/media/attachments/lesson/123456/M00-L02-A01.docx
  checked_at: 2026-09-14
```

## 12. Защита от дублей и destructive behavior

- существующие canonical mappings переиспользуются только при однозначном доказательстве;
- второй объект при неоднозначном совпадении не создаётся;
- existing manual/golden content автоматически не перезаписывается;
- structural divergence блокируется;
- `DELETE` запрещён;
- destructive rollback запрещён;
- unknown live provenance не принимается как baseline автоматически.

## 13. Ownership

Machine-checkable [`ownership-matrix.v1.json`](ownership-matrix.v1.json) задаёт для обязательных event classes:

- source of truth;
- detection/initiation/execution owner;
- approval;
- retry/partial/reconcile/rebaseline policy;
- mandatory STOP;
- required evidence;
- machine-state mutation;
- history event.

Матрица не является списком содержания курса.

## 14. Что требуется от владельца

От владельца нужны только действия, которые automation не может или не должна принимать сама:

- явный запуск live write route;
- owner decision при ambiguous/manual/unknown provenance;
- отдельное решение для golden/structural/adoption cases;
- ручная asset upload процедура, если стабильный API route отсутствует;
- финальный human visual review там, где он требуется production-процессом.

Чувствительные данные не передаются в чат и не фиксируются в deployment history.

## 15. Что этот контур не разрешает

- перепроектировать курс под удобство API;
- менять canonical IDs;
- превращать практику во фальшивый quiz;
- публиковать author-only recovery/rubric заранее;
- менять F1;
- считать API read-back Human Validation;
- считать successful upload доказательством PHONE/COMPUTER readiness;
- разблокировать общий bulk write одним успешным pilot/recovery result.
