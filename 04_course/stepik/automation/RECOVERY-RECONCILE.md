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

Если один из обязательных источников недоступен или несколько объяснений одинаково возможны, результат = `STOP`.

## 2. Current-main и event source

Deployment event навсегда привязан к source SHA, с которым он был начат.

Новый merge в `main`:

- не меняет target уже начатого event;
- не позволяет старому event закрыть новый pending;
- блокирует continuation старого event до явного reconcile;
- не превращает old desired fingerprint в новый canonical target.

## 3. Recovery state machine

### R0. External write не начинался

Evidence: есть `EVENT_STARTED`, нет `WRITE_INTENT`.

Допустимо начать normal write route заново при неизменном source SHA, baseline и live state. Если нельзя доказать, что write не начинался, этот state неприменим.

### R1. Final write/read-back подтверждён, machine-state PATCH отсутствует

Evidence:

- `FINAL_READBACK_CONFIRMED` существует;
- `MACHINE_STATE_COMMITTED` отсутствует;
- fresh live fingerprint точно равен history-confirmed final fingerprint;
- event source SHA всё ещё текущий `main`;
- нет competing event.

Action: `AUTO_RECOVER_MACHINE_STATE`.

Stepik writes: `0`. Automation PATCH-ит только target baseline/pending через обычный compare-before-patch guard, затем append-ит `MACHINE_STATE_COMMITTED`.

### R2. Подтверждённый partial write

Evidence:

- один или несколько `WRITE_INTENT`;
- соответствующие write results однозначны;
- для выполненного prefix есть `OP_READBACK_CONFIRMED`;
- fresh live fingerprint точно совпадает с последним подтверждённым intermediate fingerprint;
- нет ambiguous result/read-back failure;
- source SHA всё ещё текущий.

Action: `AUTO_CONTINUE_FROM_CONFIRMED_PREFIX` допустим только для remaining operations. Уже подтверждённые operations не повторяются.

Если live отличается от confirmed intermediate → `STOP_OWNER_DECISION`.

### R3. Ambiguous API result

Timeout/network error, HTTP 5xx после write request или иной результат, при котором server-side commit нельзя доказать или опровергнуть, создаёт `WRITE_AMBIGUOUS`.

Action: `STOP_OWNER_DECISION` + read-only reconcile. Blind retry запрещён.

Даже если fresh live равен desired, одного совпадения недостаточно, чтобы доказать происхождение.

### R4. Read-back недоступен или не совпал

Write нельзя считать confirmed. Baseline не меняется, pending не закрывается.

Action: `STOP_OWNER_DECISION`, пока происхождение live state не доказано достаточным evidence.

### R5. Process умер между operations

Следующий run читает immutable history и fresh live.

- live == last confirmed intermediate → можно продолжить только remaining operations;
- live отличается → STOP;
- есть unconfirmed `WRITE_INTENT` → STOP, никакого повторного write.

### R6. Повторный recovery run

`event_id` и `record_id` детерминированы. Уже существующий identical record не создаётся второй раз. Existing record с другим payload = STOP.

После `MACHINE_STATE_COMMITTED` повторный recovery не выполняет write и не создаёт новый логический deployment event для той же цели.

### R7. Новый Git merge во время recovery

`event.source_sha != current main` → `STALE_SOURCE_SHA`.

Старый event нельзя продолжить автоматически и нельзя использовать для закрытия нового pending.

### R8. Человек изменил Stepik после partial automation write

Если live больше не равен confirmed intermediate/final fingerprint event, automation не пытается разложить состояние на «нашу» и «ручную» части эвристикой.

Action: `STOP_OWNER_DECISION`.

## 4. Baseline reconcile classifications

`sync-reconcile` является read-only route. Он не пишет в Stepik и не rebaseline-ит Issue автоматически.

Минимальные классы:

- `VERIFIED_WRITE_STATE_PATCH_MISSING` → auto state-only recovery допустим;
- `CONFIRMED_PARTIAL_AUTOMATION_STATE` → continuation допустим только из подтверждённого prefix;
- `AMBIGUOUS_WRITE_RESULT` → owner decision;
- `UNCONFIRMED_WRITE_READBACK_FAILED` → owner decision;
- `WRITE_STARTED_WITHOUT_CONFIRMED_PREFIX` → owner decision;
- `MANUAL_OR_UNKNOWN_DRIFT` → owner decision;
- `BASELINE_MISSING` → owner decision;
- `CANONICAL_MATCH_WITHOUT_PROVEN_EVENT` / `UNPROVEN_LIVE_EQUALS_CANONICAL` → owner decision;
- `METADATA_DIVERGENCE` → owner decision;
- `STRUCTURAL_DIVERGENCE` → owner decision;
- `GOLDEN_OWNER_REQUIRED` → owner decision;
- `CONFLICTING_EVENTS` → owner decision;
- `STALE_SOURCE_SHA` → STOP old event;
- `IN_SYNC` → no-op;
- `CANONICAL_CHANGE_PENDING` → обычный guarded sync route.

## 5. Rebaseline/adoption

Автоматическое правило `live == новый baseline` запрещено.

Adoption/rebaseline допустим только отдельным явным owner-approved решением с:

- доказанным происхождением live state;
- fresh fingerprint;
- event/history link;
- canonical/source SHA;
- machine-readable reason;
- audit trail.

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
- write-ahead history до каждого Stepik write;
- current Issue state: read expected → re-read current → compare → PATCH only if unchanged;
- history `MACHINE_STATE_COMMITTED` только после успешного Issue PATCH.

Если Issue PATCH уже прошёл, а history commit не прошёл, следующий recovery видит confirmed final event и fresh current state и может безопасно завершить только history/state handshake без Stepik write.

## 8. Ownership

Machine-checkable правила для классов событий находятся в [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

Unknown ownership/state = STOP.
