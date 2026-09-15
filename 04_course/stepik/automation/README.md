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
- verified-render learner content всех 21 lessons / 148 learner steps без repo-relative links при наличии подтверждённых physical bindings;
- context-aware встраивать Markdown-материалы отдельными learner-facing блоками вместо blind string replacement;
- распознавать physical assets, для которых до rendering нужен подтверждённый Stepik URL;
- выполнять owner-only controlled first upload для `M04-L01` с `M04-L01-A01.txt`;
- capability-check `/api/attachments`, отправлять attachment одним multipart POST без blind retry и проверять фактические bytes скачиванием;
- хранить отдельные verified asset baselines и lesson baselines в machine state;
- распознавать два golden lessons `M00-L01/M00-L02` как `READ_ONLY`;
- отдельно проверять live integrity golden sample и canonical-vs-golden divergence;
- вести confirmed baseline и machine-readable PENDING в Issue `#54`;
- выполнять узкий guarded exploitation sync pilot lesson `M02-L01`;
- durable-журналировать deployment/recovery operations;
- восстанавливаться после доказуемого partial/state/history-commit gap без повторного Stepik write;
- выполнять read-only baseline reconcile classification.

**Важно:** engineering route `verified-rendering-and-first-upload` реализован, но live acceptance `M04-L01` ещё не выполнен. Общий bulk write остаётся закрытым до реального owner-dispatched pilot и оставшихся gates.

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

`M00-L01` и `M00-L02` остаются платформенным read-only эталоном. Обычный uploader/recovery не изменяет и не удаляет их.

Canonical `main` может развиваться после создания golden sample. Расхождение current canonical и подтверждённого live golden фиксируется как target-scoped `GOLDEN_OWNER_REQUIRED`, но не блокирует независимый non-golden read-only/guarded route при подтверждённой live golden integrity.

Такой notice не разрешает adoption, rebaseline или запись в golden.

## 4. Безопасные режимы

### Inspect / dry-run

Только чтение и локальная компиляция. POST/PUT/DELETE отсутствуют.

### Bulk Status

`Stepik Bulk Status` читает весь курс и различает:

- local learner dependency обнаружена source compiler;
- publication route архитектурно разрешён;
- physical materialization уже подтверждена или ещё требуется.

Даже полностью разрешённый asset route не устанавливает `ready_for_bulk_write=true`.

### Impact after merge

Push в `main` не пишет в Stepik. Workflow dependency-aware определяет learner impact и обновляет PENDING Issue `#54` только через compare-before-PATCH guard.

### `first-upload-m04-l01`

Owner-only controlled write route для первого файлового non-golden lesson.

Требует одновременно:

- запуск только из `workflow_dispatch`;
- `confirm_write=true`;
- current-main guard;
- общий live mutex `stepik-live-course-299189`;
- непубличный course и target lesson;
- точный target title/language/position;
- отсутствие существующего lesson baseline, кроме доказуемого recovery после state/history commit gap;
- точный asset route `M04-L01-A01.txt → stepik-attachment-upload`;
- attachment capability preflight;
- write-ahead history до каждого внешнего write;
- no blind retry;
- download/read-back фактических attachment bytes;
- verified final lesson read-back;
- race-checked Issue state PATCH;
- `MACHINE_STATE_COMMITTED` для asset и lesson events после PATCH.

Route не поддерживает DELETE, golden, произвольный lesson ID или массовую загрузку.

### `sync-status`

Live read-only проверка pilot target против canonical desired state и confirmed baseline.

### `sync-reconcile`

Live read-only сопоставление current `main`, machine state, fresh live Stepik и immutable history. Automatic rebaseline отсутствует.

### `sync-changed`

Guarded exploitation write route для уже отслеживаемого `M02-L01`. Требует owner dispatch, `confirm_write`, current-main guard, live mutex, baseline/history checks и verified read-back.

## 5. Verified rendering contract

General source compiler сохраняет canonical learner text. Verified rendering выполняется отдельным слоем.

Текущий offline contract доказан для всех 21 lessons / 148 learner-facing steps:

- repo-relative learner links не остаются в финальном HTML;
- Markdown dependency не вставляется слепо внутрь предложения;
- исходная инструкция сохраняется, ссылка заменяется указанием на материал ниже, а сам Markdown добавляется отдельным блоком в том же Stepik step;
- nested Markdown dependencies раскрываются рекурсивно;
- confirmed external/Stepik URLs сохраняются ссылками;
- physical assets без verified binding дают `MaterializationRequired`, а не фиктивный URL;
- author-only материал не попадает в learner rendering;
- `free-answer` source берётся только из подтверждённого golden profile.

Без runtime bindings сейчас остаются ровно 5 physical sources, требующих materialization. `M04-L01` проверяет attachment route; image/SVG routes остаются следующими gates перед bulk write.

## 6. Attachment materialization

`M04-L01-A01.txt` использует owner-approved working assumption [D-2026-09-15-STEPIK-ATTACHMENTS](../../../00_governance/decision-log/2026-09-15-stepik-attachment-upload-assumption.md).

Фактическая основа:

- в бесплатном курсе уже существуют lesson attachments;
- `/api/attachments` читает эти объекты;
- `OPTIONS /api/attachments` объявляет `GET, POST, HEAD, OPTIONS`;
- parser включает `multipart/form-data`;
- `file` writable, required и имеет type `file upload`;
- `lesson` writable.

Перед первым POST automation повторно проверяет этот capability contract. При расхождении route останавливается fail-closed.

Attachment transaction:

1. проверяет SHA-256 canonical source;
2. читает attachments target lesson;
3. существующий exact same-name attachment допускается только после download + exact hash read-back;
4. несколько same-name объектов или mismatch bytes = STOP;
5. до POST сохраняются `EVENT_STARTED`, `WRITE_INTENT`, `WRITE_DISPATCH_STARTED`;
6. POST выполняется ровно один раз;
7. timeout/network/5xx = `WRITE_AMBIGUOUS`, blind retry запрещён;
8. success подтверждается повторным list, created ID/name и скачиванием bytes;
9. URL берётся только из фактического Stepik response/read-back, не конструируется по шаблону;
10. asset baseline попадает в Issue state только вместе с подтверждённым lesson state.

## 7. Machine state schema

Issue `#54` использует текущую schema v3. При чтении schema v1/v2 безопасно нормализуется в v3 с пустым `assets`, поэтому существующий lesson baseline не теряется.

State хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — learner-facing изменения после baseline.

Asset baseline содержит как минимум:

- exact repo source path;
- source SHA-256;
- фактический HTTPS URL;
- storage kind;
- Stepik attachment ID;
- Stepik lesson ID;
- filename/size;
- materialization timestamp.

При каждом reuse automation повторно сверяет live attachment ID/name/size/path и скачанные bytes с canonical SHA-256.

## 8. Durable deployment history и recovery

До каждого внешнего write automation сохраняет intent отдельно от dispatch.

Asset materialization и lesson first upload являются **разными logical events**. Это необходимо, потому что финальный lesson fingerprint можно вычислить только после получения фактического verified attachment URL.

Основные recovery случаи:

- write не начинался: normal route возможен только при всё ещё действующих guards;
- asset/lesson final read-back подтверждён, но Issue PATCH не состоялся: next run восстанавливает state из immutable history без повторного Stepik write;
- Issue PATCH состоялся, но один из `MACHINE_STATE_COMMITTED` не успел записаться: next run сверяет state ↔ history ↔ live и завершает только history commit без повторного Stepik write;
- lesson partial prefix подтверждён и fresh live точно совпадает с last confirmed intermediate fingerprint: разрешается только remaining suffix;
- ambiguous dispatch или failed read-back: automatic continuation запрещён;
- manual/unproven live state: STOP.

## 9. Race guarantees

Сохраняются одновременно:

- fresh current-main guard;
- единый mutex `stepik-live-course-299189`;
- durable write-ahead history;
- per-operation и final read-back;
- Issue state guard `read expected → re-read current → compare → PATCH only if unchanged`;
- `MACHINE_STATE_COMMITTED` только после успешного current-state PATCH.

Unknown state = `STOP`.

## 10. API write policy

Автоматический write retry отсутствует для POST/PUT.

Write result классифицируется так:

- known 4xx failure: failed operation;
- timeout/network/HTTP 5xx/неоднозначный response: ambiguous outcome;
- HTTP success без подтверждённого read-back: не confirmed deployment.

`DELETE` не реализуется и не разрешается recovery route.

## 11. Что ещё закрывает bulk write

Engineering implementation first-upload route не означает готовность к массовой записи.

До `upload-remaining` всё ещё нужны:

1. реальный owner-dispatched acceptance `first-upload-m04-l01` на `main`;
2. confirmed materialization/read-back для PNG routes;
3. deterministic SVG→PNG route и visual read-back;
4. общий initial-upload orchestration для оставшихся lessons, а не hard-coded pilot;
5. общий drift guard после создания baseline;
6. отдельный integrity pass для independence/F1-sensitive lessons;
7. explicit stale-title metadata route без duplicate creation;
8. финальный all-course private staging verification.

`ready_for_bulk_write` остаётся `false`.

## 12. Что требуется от владельца

Владелец принимает только решения/действия, которые automation не должна принимать сама:

- запуск live write route;
- owner decision при ambiguous/manual/unknown provenance;
- отдельное решение для golden/structural/adoption cases;
- изменение/отмена D-2026-09-15-STEPIK-ATTACHMENTS;
- human visual/learner validation по production процессу.

Если Stepik API сам перестаёт подтверждать attachment capability, automation обязана остановиться без нового owner approval.

## 13. Что этот контур не разрешает

- перепроектировать курс под удобство API;
- менять canonical IDs;
- превращать практику во фальшивый quiz;
- публиковать author-only recovery/rubric заранее;
- менять F1;
- считать API read-back Human Validation;
- считать successful upload доказательством PHONE/COMPUTER readiness;
- считать resolved asset route фактической materialization;
- разблокировать общий bulk write одним успешным pilot result.
