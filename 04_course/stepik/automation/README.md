# Автоматизация переноса и эксплуатационной синхронизации курса в Stepik

**Статус:** production automation contract / implementation handoff  
**Дата:** 15 сентября 2026 года  
**Курс Stepik:** `299189`  
**Источник learner-facing содержания:** только актуальный `main`

Этот каталог описывает технический контур GitHub → Stepik. Он не меняет педагогическую архитектуру курса, Lesson/Exercise/Check/Asset ID, F1, recovery для ученика или Human Pilot.

## 1. Текущий production scope

Автоматизация умеет:

- читать фактическую структуру существующего курса Stepik;
- строить derived structural/build representation из canonical GitHub files;
- выполнять offline dry-run и all-course read-only preflight;
- source-compile learner-facing content всех 21 canonical lessons без потери порядка и author-only leakage;
- строить полный learner dependency graph, включая nested local links;
- разрешать все текущие learner asset routes через machine-readable `asset-publication.v1.json`;
- распознавать два golden lessons `M00-L01/M00-L02` как `READ_ONLY`;
- отдельно проверять live integrity golden sample и отдельно классифицировать canonical-vs-golden divergence;
- вести confirmed baseline и machine-readable PENDING в Issue `#54`;
- определять learner-facing impact dependency-aware способом;
- выполнять узкий guarded exploitation sync pilot lesson `M02-L01`;
- durable-журналировать deployment/recovery operations;
- восстанавливаться после доказуемого partial/state-patch failure без blind retry;
- выполнять read-only baseline reconcile classification;
- проверять эксплуатационную ownership matrix автоматическим completeness test.

Asset route gate закрыт, но общий bulk write по-прежнему закрыт. Следующий gate — verified rendering / controlled first upload.

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
- [`BULK-STATUS.md`](BULK-STATUS.md);
- [`asset-publication.v1.json`](asset-publication.v1.json);
- [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

## 3. Golden sample

Первые два вручную созданных урока остаются платформенным эталоном:

- `M00-L01`;
- `M00-L02`.

Обычный uploader/recovery не изменяет и не удаляет их. Если фактическая Stepik representation расходится с observation fixture, это live golden integrity blocker: исправляется/разбирается platform state, а не маскируется обновлением canonical данных.

При этом canonical `main` может законно развиваться после создания golden sample. Расхождение текущего canonical title/числа planned steps с подтверждённым неизменным live golden фиксируется как non-blocking `GOLDEN_OWNER_REQUIRED` notice. Оно относится только к соответствующему golden object и **не блокирует** read-only/guarded sync независимого non-golden lesson при подтверждённой live golden integrity.

Такой notice не разрешает adoption, rebaseline или запись в golden. Для изменения `M00-L01/M00-L02` всё ещё нужен отдельный owner-approved golden route, которого обычный sync не имеет.

## 4. Безопасные режимы

### Inspect / dry-run

Только чтение и локальная компиляция. POST/PUT/DELETE отсутствуют.

### Bulk Status

`Stepik Bulk Status` читает весь курс и строит preflight для 21 canonical lessons. Он различает три состояния, которые нельзя смешивать:

- local learner dependency обнаружена source compiler;
- publication route архитектурно разрешён;
- физическая materialization в Stepik ещё требуется при будущем write.

Даже полностью разрешённый asset route не устанавливает `ready_for_bulk_write=true` автоматически.

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

Canonical divergence unrelated golden lesson показывается в `run-report.json.notices`, но не превращается в target blocker, если live golden integrity подтверждена.

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

Полный learner dependency topology и publication policy описаны в [`asset-publication.v1.json`](asset-publication.v1.json) и [`BULK-STATUS.md`](BULK-STATUS.md).

Текущий route contract:

- Markdown source → contextual `inline-source` через будущий verified renderer;
- non-golden PNG → verified Stepik image materialization;
- SVG → deterministic PNG rasterization → Stepik image materialization;
- существующие golden M00-L02 attachments → exact confirmed URLs, привязанные к source SHA-256;
- обязательный реальный `M04-L01-A01.txt` → `stepik-attachment-upload`.

`stepik-attachment-upload` принят владельцем как рабочее production-допущение [D-2026-09-15-STEPIK-ATTACHMENTS](../../../00_governance/decision-log/2026-09-15-stepik-attachment-upload-assumption.md).

Фактическая основа решения:

- два файла уже успешно существуют как lesson attachments в бесплатном курсе;
- API курса подтверждает `is_paid=false`;
- `/api/attachments` читает эти объекты;
- `OPTIONS /api/attachments` объявляет `POST`;
- API принимает `multipart/form-data`;
- обязательное поле `file` объявлено как `file upload`.

Это не даёт writer права немедленно отправлять файл. Первый автоматизированный attachment POST должен идти только через будущий owner-dispatched write route с write-ahead history, capability preflight, no blind retry, read-back и доказательством learner-facing URL.

Если API/plan/permissions перестают подтверждать этот контракт, route fail-closed возвращается в `asset-publication-resolution`.

Asset URL никогда не конструируется по догадке.

## 11. Derived asset URL map

Карта physical source → фактический URL является derived operational data. Если materialization ещё не выполнена, URL не заполняется фиктивным значением. После успешного upload URL связывается с точным source SHA-256 и verified read-back.

Пример структуры:

```yaml
M04-L01-A01:
  storage: stepik-lesson-attachment
  lesson_id: 123456
  source_sha256: sha256:...
  url: https://stepik.org/media/attachments/lesson/123456/M04-L01-A01.txt
  checked_at: 2026-09-15
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

Отдельный class `golden_canonical_divergence` закрепляет target-scoped правило: owner decision обязателен для самого golden object, но unrelated non-golden read-only/guarded sync не блокируется только из-за pending canonical change golden lesson.

Матрица не является списком содержания курса.

## 14. Что требуется от владельца

От владельца нужны только действия, которые automation не может или не должна принимать сама:

- явный запуск live write route;
- owner decision при ambiguous/manual/unknown provenance;
- отдельное решение для golden/structural/adoption cases;
- изменение/отмена D-2026-09-15-STEPIK-ATTACHMENTS, если владелец больше не хочет использовать Stepik attachments;
- финальный human visual review там, где он требуется production-процессом.

Если Stepik API сам обнаружит ограничение attachment route, новое ручное решение владельца не требуется для STOP: automation обязана остановиться fail-closed и вернуть проблему в asset gate.

Чувствительные данные не передаются в чат и не фиксируются в deployment history.

## 15. Что этот контур не разрешает

- перепроектировать курс под удобство API;
- менять canonical IDs;
- превращать практику во фальшивый quiz;
- публиковать author-only recovery/rubric заранее;
- менять F1;
- считать API read-back Human Validation;
- считать successful upload доказательством PHONE/COMPUTER readiness;
- считать resolved asset route доказательством фактической materialization;
- разблокировать общий bulk write одним успешным pilot/recovery/attachment result.
