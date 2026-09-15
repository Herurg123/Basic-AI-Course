# Partial-write recovery и baseline reconcile

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Принцип:** происхождение live state должно быть доказано, а не угадано.

## 1. Источники evidence

Любое recovery/reconcile решение рассматривает одновременно:

1. canonical `main`;
2. current machine state Issue `#54`;
3. fresh live Stepik read-back;
4. immutable deployment history.

Если один из обязательных источников недоступен, history не проходит integrity gate или несколько объяснений одинаково возможны, результат = `STOP`.

## 2. Current-main и event source

Deployment event навсегда привязан к source SHA, с которым он был начат.

Новый merge в `main`:

- не меняет target уже начатого event;
- не позволяет старому event закрыть новый pending;
- блокирует continuation старого event до явного reconcile;
- не превращает old desired fingerprint в новый canonical target.

## 3. Recovery state machine

### R0. External write не начинался

Evidence: есть `EVENT_STARTED`, но нет `WRITE_DISPATCH_STARTED`.

`WRITE_INTENT` сам по себе не означает, что HTTP write был начат. Если intent сохранён, но dispatch отсутствует, normal write route может быть повторён при неизменном source SHA, baseline и live state. Semantic-identical intent переиспользуется без переписывания immutable record; конфликт intent fields = `STOP`.

Если `WRITE_DISPATCH_STARTED` существует, система больше не утверждает, что внешний write точно не начинался.

### R1. Final write/read-back подтверждён, machine-state PATCH отсутствует

Evidence:

- `FINAL_READBACK_CONFIRMED` существует;
- `MACHINE_STATE_COMMITTED` отсутствует;
- все начатые write operations имеют непротиворечивую completed + per-operation read-back evidence;
- fresh live fingerprint точно равен history-confirmed final fingerprint;
- event source SHA всё ещё текущий `main`;
- нет competing event.

Action: `AUTO_RECOVER_MACHINE_STATE`.

Stepik writes: `0`. Automation PATCH-ит только target baseline/pending через обычный compare-before-patch guard, затем append-ит `MACHINE_STATE_COMMITTED`.

Если Issue state уже фактически содержит этот baseline и target pending уже закрыт, recovery не конструирует более старый `updated_at`: current state сохраняется как есть, а завершается только history/state handshake.

Перед `MACHINE_STATE_COMMITTED` status и baseline-after из current machine state обязаны точно совпасть с `FINAL_READBACK_CONFIRMED`.

### R2. Подтверждённый partial write

Evidence:

- один или несколько `WRITE_DISPATCH_STARTED`;
- **каждый** уже начатый dispatch, относящийся к подтверждённому prefix, имеет единственный `WRITE_COMPLETED`;
- для каждого такого dispatch есть `OP_READBACK_CONFIRMED`;
- нет более позднего dispatch без подтверждённого read-back;
- fresh live fingerprint точно совпадает с последним подтверждённым intermediate fingerprint;
- нет ambiguous result/read-back failure/known-failure attempt;
- source SHA всё ещё текущий.

Action: `AUTO_CONTINUE_FROM_CONFIRMED_PREFIX` допустим только для operations, которые ещё **не имели dispatch**. Уже подтверждённые operations не повторяются.

Если после подтверждённого prefix уже существует следующий `WRITE_DISPATCH_STARTED`, но его outcome/read-back не доказан, совпадение live с prefix **не** разрешает continuation: результат = `WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX`/STOP. Иначе можно было бы повторить operation, которая фактически уже применена server-side.

Если live отличается от confirmed intermediate → `STOP_OWNER_DECISION`.

### R3. Ambiguous API result

Timeout/network error, HTTP 5xx после write dispatch, неожиданный client/runtime exception после durable dispatch или иной результат, при котором server-side commit нельзя доказать или опровергнуть, создаёт `WRITE_AMBIGUOUS`.

Action: `STOP_OWNER_DECISION` + read-only reconcile. Blind retry запрещён.

Даже если fresh live равен desired, одного совпадения недостаточно, чтобы доказать происхождение.

### R4. Known write failure

`WRITE_FAILED_KNOWN` означает, что конкретная dispatch-попытка доказанно получила API-отказ без server-side commit. Это не ambiguous state.

Однако history v1 моделирует одну dispatch-попытку под semantic operation ID. Поэтому повторный внешний write не маскируется под старую попытку и не запускается автоматически.

- live всё ещё равен последнему доказанному состоянию → `KNOWN_WRITE_FAILURE_OWNER_RETRY_REQUIRED`;
- live уже отличается от последнего доказанного состояния → `KNOWN_WRITE_FAILURE_WITH_LIVE_DIVERGENCE`.

Оба класса требуют owner decision. Будущий explicit retry route обязан создавать отдельную attempt identity, а не переписывать старые dispatch/result records.

### R5. Read-back недоступен или не совпал

Write нельзя считать confirmed. Baseline не меняется, pending не закрывается.

Action: `STOP_OWNER_DECISION`, пока происхождение live state не доказано достаточным evidence.

### R6. Process умер между operations

Следующий run читает immutable history и fresh live.

- intent сохранён, но dispatch для operation отсутствует → эта operation не считается начатой; normal guarded route может выполнить её;
- все предыдущие dispatch подтверждены read-back, следующего dispatch нет, live == last confirmed intermediate → можно продолжить remaining operations;
- live отличается → STOP;
- есть `WRITE_DISPATCH_STARTED` без подтверждённого результата/read-back → STOP, никакого blind retry;
- есть `WRITE_COMPLETED` без `OP_READBACK_CONFIRMED` → STOP; успешный HTTP не считается подтверждённым state.

### R7. Повторный recovery run

`event_id` стабилен для логической цели. Semantic records не переписываются. Run-specific reconcile/recovery records имеют attempt token и сохраняют `recorded_by_workflow` + relationship с исходным event.

После `MACHINE_STATE_COMMITTED` повторный recovery не выполняет Stepik write и не создаёт новый логический deployment event для той же цели.

### R8. Новый Git merge во время recovery

`event.source_sha != current main` → `STALE_SOURCE_SHA`.

Старый event нельзя продолжить автоматически и нельзя использовать для закрытия нового pending, даже если fresh live совпадает с intermediate fingerprint старого event.

### R9. Человек изменил Stepik после partial automation write

Если live больше не равен confirmed intermediate/final fingerprint event, automation не пытается разложить состояние на «нашу» и «ручную» части эвристикой.

Action: `STOP_OWNER_DECISION`.

### R10. History повреждена или противоречива

Перед recovery history проходит integrity gate: stable event identity, единая logical identity records, допустимая cardinality phases, write-chain intent→dispatch→result→read-back и exact final/committed relationship.

Ручная правка или внутреннее противоречие evidence не разрешаются эвристикой. Такой event = `STOP` до расследования/owner decision; automation не выбирает «более правдоподобную» запись.

## 4. Baseline reconcile classifications

`sync-reconcile` является read-only по отношению к Stepik. Он не выполняет Stepik write и не rebaseline-ит Issue автоматически, но durable-записывает `RECONCILE_CLASSIFIED` в operational history.

Минимальные классы:

- `VERIFIED_WRITE_STATE_PATCH_MISSING` → auto state-only recovery допустим;
- `CONFIRMED_PARTIAL_AUTOMATION_STATE` → continuation допустим только из полностью подтверждённого prefix без более позднего unresolved dispatch;
- `AMBIGUOUS_WRITE_RESULT` → owner decision;
- `KNOWN_WRITE_FAILURE_OWNER_RETRY_REQUIRED` → owner decision/new attempt route;
- `KNOWN_WRITE_FAILURE_WITH_LIVE_DIVERGENCE` → owner decision;
- `UNCONFIRMED_WRITE_READBACK_FAILED` → owner decision;
- `WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX` → owner decision;
- `HISTORY_EVIDENCE_INCONSISTENT` → owner decision/STOP;
- `MACHINE_STATE_DIVERGED_DURING_EVENT` → owner decision/STOP;
- `MANUAL_OR_UNKNOWN_DRIFT` → owner decision;
- `BASELINE_MISSING` → owner decision;
- `CANONICAL_MATCH_WITHOUT_PROVEN_EVENT` / `UNPROVEN_LIVE_EQUALS_CANONICAL` → owner decision;
- `STALE_MACHINE_BASELINE` → latest provable committed history подтверждает live, но current machine baseline ему не соответствует; owner decision;
- `METADATA_DIVERGENCE` → owner decision;
- `STRUCTURAL_DIVERGENCE` → owner decision;
- `GOLDEN_OWNER_REQUIRED` → owner decision;
- `CONFLICTING_EVENTS` → owner decision;
- `STALE_SOURCE_SHA` → STOP old event;
- `IN_SYNC` → no-op;
- `CANONICAL_CHANGE_PENDING` → обычный guarded sync route.

Для `STALE_MACHINE_BASELINE` учитывается только **последний доказуемый committed deployment state** объекта, а не любое старое историческое состояние, случайно совпавшее с live. Если несколько latest committed events невозможно однозначно упорядочить и они дают разные fingerprints, reconcile fail-closed как conflict.

## 5. Rebaseline/adoption

Автоматическое правило `live == новый baseline` запрещено.

Adoption/rebaseline допустим только отдельным явным owner-approved решением с:

- доказанным происхождением live state;
- fresh fingerprint;
- event/history link;
- canonical/source SHA;
- machine-readable reason;
- audit trail.

`STALE_MACHINE_BASELINE` также не вызывает автоматический rebaseline. Доказательство того, что baseline устарел, ещё не является разрешением молча переписать current state.

Текущий этап не добавляет универсальный automatic adoption route.

## 6. Golden, metadata и structure

- `M00-L01` и `M00-L02` остаются golden `READ_ONLY`;
- metadata update не проходит обычным content recovery;
- изменение количества/порядка steps не проходит обычным recovery;
- destructive rollback и `DELETE` запрещены.

## 7. Race rules

Сохраняются одновременно:

- единый live mutex `stepik-live-course-299189`;
- fresh current-main guard до live Stepik;
- `WRITE_INTENT`, затем `WRITE_DISPATCH_STARTED` непосредственно перед каждым Stepik write;
- current Issue state: read expected → re-read current → compare → PATCH only if unchanged;
- history `MACHINE_STATE_COMMITTED` только после успешного Issue PATCH и exact validation against final read-back.

Если Issue PATCH уже прошёл, а history commit не прошёл, следующий recovery сравнивает fresh current state, final event и live Stepik. Он не выполняет повторный Stepik write.

## 8. Ownership

Machine-checkable правила для классов событий находятся в [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

Unknown ownership/state = STOP.
