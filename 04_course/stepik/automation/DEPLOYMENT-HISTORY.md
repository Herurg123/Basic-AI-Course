# Machine-readable deployment history GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Schema:** `history_schema_version=1`  
**Derived operational branch:** `stepik-deployment-history-v1`

## 1. Назначение

Deployment history хранит доказательства того, что automation собиралась сделать, что реально начала делать, что Stepik подтвердил read-back и был ли затем успешно обновлён current machine state.

History не является источником learner-facing содержания курса. Learner-facing source of truth остаётся только канонический `main`.

## 2. Три разных слоя состояния

Система намеренно разделяет:

1. **Current machine state** — компактный текущий baseline + PENDING в Issue `#54`.
2. **Immutable deployment/recovery history** — отдельные JSON records в derived branch `stepik-deployment-history-v1` под `.stepik-deployment-history/events/<event_id>/`.
3. **Human-readable comments Issue #54** — читаемый человеком журнал результатов и решений.

Issue body не превращается в бесконечный event log. Human comment не заменяет machine evidence. Derived history branch не используется компилятором курса.

## 3. Почему отдельная derived branch допустима

Эта branch содержит только эксплуатационные evidence records, которые появляются во время live/recovery runs и поэтому не могут проходить обычный content PR до внешнего write. Она не является конкурирующей версией проектных документов и не меняет `main`.

Workflow имеет `contents: write` только в live job и код history store жёстко ограничивает запись branch `stepik-deployment-history-v1` и префиксом `.stepik-deployment-history/events/`.

Branch protection, rulesets и GitHub Environment этим контрактом не меняются.

## 4. Stable event identity

`event_id` детерминирован из:

- `course_id`;
- canonical `object_id`;
- `kind`;
- source `main` SHA;
- desired fingerprint;
- baseline fingerprint before;
- `pending_first_sha`, если он существует.

Логический retry той же цели получает тот же `event_id`. Новая canonical цель, другой baseline или другой source SHA создают другой event.

Event identity также хранит:

- GitHub Actions `run_id`, `run_attempt`, run URL;
- retry/continuation relationship, если такой relationship создаётся отдельным будущим route;
- canonical object и source SHA.

## 5. Append-only records

Каждый transition — отдельный JSON-файл с детерминированным `record_id`.

Если тот же `record_id` уже существует:

- byte-equivalent payload считается idempotent retry;
- другой payload = `STOP`, переписывать историю запрещено.

Основные phases:

- `EVENT_STARTED`;
- `WRITE_INTENT`;
- `WRITE_COMPLETED`;
- `WRITE_FAILED_KNOWN`;
- `WRITE_AMBIGUOUS`;
- `OP_READBACK_CONFIRMED`;
- `READBACK_FAILED`;
- `FINAL_READBACK_CONFIRMED`;
- `MACHINE_STATE_COMMITTED`;
- `FAILED_BEFORE_WRITE` / `FAILED_AFTER_WRITE_STARTED`;
- `RECOVERY_CLASSIFIED`.

## 6. Write-ahead правило

До каждого внешнего Stepik write automation обязана durable-записать `WRITE_INTENT`.

Record содержит минимум:

- operation ID;
- method и target;
- lesson fingerprint before;
- expected lesson fingerprint after operation;
- признак `external_write_started=true`.

Если `WRITE_INTENT` сохранить не удалось, Stepik write запрещён.

После ответа:

- однозначный success → `WRITE_COMPLETED`;
- доказанный отказ без server-side commit → `WRITE_FAILED_KNOWN`;
- timeout/network failure/HTTP 5xx/неоднозначный успешный ответ → `WRITE_AMBIGUOUS`.

`WRITE_AMBIGUOUS` никогда не приводит к blind retry.

## 7. Read-back evidence

После каждой выполненной write-operation проверяется соответствующий Stepik object.

Подтверждённая operation создаёт `OP_READBACK_CONFIRMED` с expected intermediate fingerprint.

После всех operations выполняется full lesson read-back. Только он создаёт `FINAL_READBACK_CONFIRMED` и содержит:

- `confirmed_at`;
- final fingerprint;
- Stepik lesson/step IDs;
- status `APPLIED` или `NOOP_CONFIRMED`;
- snapshot baseline-after.

HTTP success без read-back не является confirmed deployment.

## 8. Machine state commit

После `FINAL_READBACK_CONFIRMED` workflow формирует следующий current machine state, повторно читает Issue `#54`, сравнивает expected/current и PATCH-ит только при совпадении.

Только после успешного PATCH history получает `MACHINE_STATE_COMMITTED`.

Если Stepik уже подтверждён, а Issue PATCH не состоялся, event остаётся намеренно незавершённым. Следующий recovery может восстановить machine state без повторного Stepik write, но только при доказуемом совпадении свежего live fingerprint с `FINAL_READBACK_CONFIRMED`.

## 9. Что event обязан позволять определить

Для recovery/reconcile event содержит или позволяет однозначно восстановить:

- stable `event_id`;
- canonical object ID и kind;
- source SHA;
- workflow/run identity;
- начало операции и время подтверждения;
- baseline/state before;
- expected state;
- confirmed state after;
- Stepik object IDs;
- fingerprints before/desired/after;
- operation type;
- был ли начат внешний write;
- write operations started/completed;
- read-back result;
- final status;
- failure/recovery reason;
- pending link через `pending_first_sha`;
- baseline before/after;
- recovery/reconcile state;
- retry/continuation relationship, если используется.

Secrets, OAuth tokens, cookies и credentials в history запрещены.

## 10. Legacy history до schema v1

До введения этого контракта Issue `#54` уже содержал подтверждённый baseline `M02-L01` и human-readable evidence раннего pilot write.

Система не выдумывает задним числом отсутствующие per-operation transitions. Допустима отдельная machine-readable **legacy baseline import** с явным признаком legacy provenance и уже committed current state, но такой import не используется как доказательство неизвестных partial-write деталей.

Новые live/recovery/reconcile события после включения history v1 обязаны использовать полный write-ahead contract.
