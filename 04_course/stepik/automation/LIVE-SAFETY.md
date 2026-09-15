# Защита live-синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Источник learner-facing содержания:** только текущий HEAD `main`

Этот документ фиксирует infrastructure guards для обращения production workflow к реальному Stepik API. Он не меняет learner-facing содержание и не разблокирует общий bulk write.

## 1. Current-main guard

Перед live-фазой production job запускает `scripts/stepik_uploader/live_guard.py`.

Guard разрешает live только если:

- `GITHUB_REF == refs/heads/main`;
- `GITHUB_SHA` является полным Git SHA;
- GitHub API возвращает current `refs/heads/main`;
- remote HEAD `main` точно совпадает с `GITHUB_SHA` run.

Feature branch, stale SHA, недоступный API или неоднозначный ответ = `STOP` до Stepik API.

Deployment/recovery event дополнительно навсегда связан со своим `source_sha`. Новый merge не меняет его target и не позволяет старому event закрыть новый pending.

## 2. Единый mutex курса

Все live jobs курса `299189` используют один concurrency group:

```yaml
concurrency:
  group: stepik-live-course-299189
  cancel-in-progress: false
```

Mutex фиксирован по реальному course ID. Offline PR tests и structural dry-run этот mutex не держат.

## 3. Current machine state и immutable history

Issue `#54` содержит compact current state: confirmed lesson baselines, `pending.lessons` и отдельный `pending.course_page`.

Отдельная derived branch `stepik-deployment-history-v1` хранит immutable deployment/recovery/reconcile evidence и не используется как content source.

До каждого Stepik write должен быть durable `WRITE_INTENT`. Этот record ещё **не** означает, что внешний write начался.

Непосредственно перед HTTP write должен быть durable `WRITE_DISPATCH_STARTED`. Только с этого момента history консервативно считает внешний write потенциально начатым.

Перед использованием как recovery evidence весь event проходит integrity gate: stable identity, единая logical identity, связная write-chain и непротиворечивые final/committed records. Повреждённая history = STOP.

## 4. Write result classification

Write не ретраится автоматически вслепую.

- `WRITE_INTENT` без dispatch можно переиспользовать при неизменных semantic fields и fresh baseline/live/source guards;
- только доказанный API-отказ без server-side commit фиксируется как `WRITE_FAILED_KNOWN`;
- timeout, network failure, HTTP 5xx, неожиданный runtime/client exception после durable dispatch или иной неизвестный server-side outcome фиксируется как `WRITE_AMBIGUOUS`.

`WRITE_AMBIGUOUS` = `STOP` + read-only reconcile. Blind retry запрещён.

`WRITE_FAILED_KNOWN` не считается ambiguous, но новый dispatch является новой внешней попыткой. History v1 не переиспользует старый dispatch/result record для неё. Поэтому текущий route возвращает `KNOWN_WRITE_FAILURE_OWNER_RETRY_REQUIRED`; live divergence после known failure возвращает отдельный owner blocker.

## 5. Read-back обязателен

HTTP success не является подтверждением deployment.

После каждого write automation читает изменённый Stepik object и durable-записывает подтверждённый intermediate fingerprint. После всех operations выполняется full lesson read-back.

Baseline/pending разрешено менять только после `FINAL_READBACK_CONFIRMED`. Failed/unavailable read-back не считается confirmed state.

## 6. Partial-write recovery

Recovery всегда сопоставляет event source `main` SHA, current machine state, fresh live Stepik и immutable event history.

### Write не начинался

Если есть `EVENT_STARTED`, но нет `WRITE_DISPATCH_STARTED`, automation может заново войти в normal route только при неизменных source/baseline/live guards. Старый semantic-identical `WRITE_INTENT` переиспользуется без переписывания immutable record.

### Final write подтверждён, state PATCH отсутствует

Если history содержит `FINAL_READBACK_CONFIRMED`, `MACHINE_STATE_COMMITTED` отсутствует, все dispatch operations полностью подтверждены per-operation read-back, source SHA актуален, а fresh live точно равен history-confirmed final fingerprint, разрешён `AUTO_RECOVER_MACHINE_STATE`.

Такой recovery выполняет **0 Stepik writes**. Если Issue уже содержит доказанный final baseline и target pending закрыт, current state сохраняется без регрессии `updated_at`, а завершается только history/state handshake.

### Partial prefix подтверждён

Continuation разрешён только если **каждый уже начатый dispatch** подтверждён `WRITE_COMPLETED` + `OP_READBACK_CONFIRMED`, fresh live точно равен last confirmed intermediate fingerprint и нет более позднего unresolved dispatch. Продолжать можно только operations, которые ещё не имели dispatch. Подтверждённые operations повторно не выполняются.

### Unknown/ambiguous partial state

Dispatch без доказанного outcome, `WRITE_COMPLETED` без per-operation read-back, ambiguous response, failed read-back, known-failure attempt или live divergence после partial automation write = `STOP_OWNER_DECISION`.

Automation не пытается угадать, какая часть live state принадлежит ей, а какая ручной правке.

## 7. Idempotent recovery

Logical event имеет stable `event_id`. Semantic transitions не переписываются.

`EVENT_STARTED` и `WRITE_INTENT` могут быть безопасно переиспользованы только если их значимые поля полностью совпадают. Run-specific `RECONCILE_CLASSIFIED` / `RECOVERY_CLASSIFIED` имеют attempt-specific record ID и сохраняют workflow identity текущего run.

После `MACHINE_STATE_COMMITTED` повторный recovery не выполняет Stepik write и не создаёт второй логический deployment event для той же цели.

## 8. Machine-state PATCH race

Mutation current state выполняется только так:

`read expected → compute next → re-read current → compare → PATCH only if unchanged`.

Если state изменился между чтениями, PATCH запрещён.

`MACHINE_STATE_COMMITTED` в history появляется только после успешного Issue PATCH и exact validation: committed status и baseline-after обязаны совпасть с `FINAL_READBACK_CONFIRMED`.

Если PATCH прошёл, а последующий history commit упал, повторный recovery завершает handshake без повторного Stepik write.

## 9. Pending closure

Pending lesson закрывается только после доказанного `APPLIED` или `NOOP_CONFIRMED`.

`APPLIED` обновляет baseline после final read-back. `NOOP_CONFIRMED` не выполняет фиктивный write. Другие lesson pending и `pending.course_page` не затрагиваются target sync/recovery.

## 10. Reconcile

`sync-reconcile` является read-only по отношению к Stepik. Он классифицирует mismatch между live, baseline, canonical и history, но сам не пишет в Stepik и не rebaseline-ит state.

Каждый reconcile run durable-записывает `RECONCILE_CLASSIFIED`. Reconcile-only observation без `EVENT_STARTED` не является незавершённым deployment event.

Для stale-baseline evidence используется только последний однозначно доказуемый committed deployment state объекта. Старый history event, случайно совпавший с live, не доказывает, что current Issue baseline устарел. Неоднозначность latest committed history = fail-closed conflict.

Manual/unknown drift, stale machine baseline, known-failure new attempt, corrupted/inconsistent history, conflicting events, golden lesson, structural/metadata divergence, missing baseline с неизвестным origin и auto-adoption case требуют owner decision.

Совпадение `live == canonical` без доказанного event не разрешает автоматически принять live как baseline.

## 11. DELETE, structure, golden и bulk

- `DELETE` запрещён;
- destructive rollback запрещён;
- неподтверждённые изменения количества/порядка steps и metadata блокируются;
- `M00-L01/M00-L02` остаются golden `READ_ONLY`;
- `M02-L01` остаётся pilot lesson с confirmed baseline;
- общий bulk write закрыт;
- Stepik Bulk Status остаётся read-only preflight.

## 12. Push в main

Push/merge в `main` dependency-aware impact job не обращается к Stepik API. Он строит before/after graph и обновляет PENDING с compare-before-PATCH guard.

Unknown learner-facing dependency = `STOP` и красный job.

## 13. Fail-closed rule

Если current-main guard, ownership, baseline comparison, history integrity/provenance, dependency mapping, write outcome, read-back или state race нельзя однозначно подтвердить, automation останавливается.

Ни live Stepik, ни current baseline не переписываются по предположению.

Подробная state machine: [`RECOVERY-RECONCILE.md`](RECOVERY-RECONCILE.md). History schema: [`DEPLOYMENT-HISTORY.md`](DEPLOYMENT-HISTORY.md).
