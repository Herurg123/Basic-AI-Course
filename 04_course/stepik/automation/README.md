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
- разрешать текущие learner asset routes через machine-readable `asset-publication.v1.json`;
- verified-render learner content всех 21 lessons / 148 learner steps без repo-relative links при наличии подтверждённых physical bindings;
- автоматически проверять, что в видимом learner-facing Markdown/HTML всех 148 steps не остаются внутренние Lesson/Asset/Exercise/Check ID;
- context-aware встраивать Markdown-материалы отдельными learner-facing блоками вместо blind string replacement;
- выполнять owner-only controlled first upload для `M04-L01` с `M04-L01-A01.txt`;
- capability-check `/api/attachments`, отправлять attachment одним multipart POST без blind retry и проверять фактические bytes скачиванием;
- хранить отдельные verified asset baselines и lesson baselines в machine state;
- распознавать `M00-L01/M00-L02` как `READ_ONLY_GOLDEN`;
- отдельно проверять live integrity golden sample и canonical-vs-golden divergence;
- вести confirmed baseline и machine-readable PENDING в Issue `#54`;
- выполнять guarded exploitation sync для tracked `M02-L01` с human-facing canonical title;
- выполнять отдельный owner-only learner-hygiene route для exact legacy title cleanup и tracked title/content migration;
- durable-журналировать deployment/recovery operations;
- восстанавливаться после доказуемого partial/state/history-commit gap без повторного Stepik write;
- выполнять read-only baseline reconcile classification.

**Live machine acceptance `M04-L01` выполнен успешно.** Owner-dispatched run `34969028781` на `main@de98e60b845b51eda4c551cdc55c0c7139c35a55` подтвердил attachment materialization, 6-step verified rendering, per-operation/final read-back, Issue schema v3 и immutable `MACHINE_STATE_COMMITTED` для asset/lesson events.

**Human Visual Validation после этого machine PASS дала `FAIL / RETEST REQUIRED`.** Функциональные элементы работали, но в sidebar, title и learner body были видны внутренние ID. Ремедиация описана в [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md). Фактологический record machine acceptance и human failure: [`M04-L01-LIVE-ACCEPTANCE-2026-09-15.md`](M04-L01-LIVE-ACCEPTANCE-2026-09-15.md).

Общий bulk write остаётся закрытым до оставшихся gates и повторной Human Validation.

## 2. Канонические источники и derived state

Learner-facing content берётся только из `main`, прежде всего из:

- `lesson.md`;
- `stepik-plan.md`;
- learner-facing assets;
- утверждённых production документов Stepik.

Operational state разделён на три слоя:

1. current machine state в Issue `#54`;
2. immutable deployment/recovery history в branch `stepik-deployment-history-v1`;
3. human-readable comments Issue `#54`.

Ни Issue, ни history branch не являются content source.

Подробности:

- [`SYNC-POLICY.md`](SYNC-POLICY.md);
- [`LIVE-SAFETY.md`](LIVE-SAFETY.md);
- [`DEPLOYMENT-HISTORY.md`](DEPLOYMENT-HISTORY.md);
- [`RECOVERY-RECONCILE.md`](RECOVERY-RECONCILE.md);
- [`BULK-STATUS.md`](BULK-STATUS.md);
- [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md);
- [`asset-publication.v1.json`](asset-publication.v1.json);
- [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

## 3. Golden sample

`M00-L01` и `M00-L02` остаются платформенным read-only эталоном. Обычный uploader/recovery и learner-hygiene writer не изменяют и не удаляют их.

Canonical `main` может развиваться после создания golden sample. Расхождение current canonical и подтверждённого live golden фиксируется как target-scoped `GOLDEN_OWNER_REQUIRED`, но не блокирует независимый non-golden guarded route при подтверждённой live golden integrity.

Текущий известный notice: canonical `M00-L02` содержит 8 steps, confirmed live golden — 7. Это не разрешает adoption, rebaseline или запись в golden.

Legacy ID-prefix в title `M00-L01/M00-L02` классифицируется отдельно как `GOLDEN_TITLE_OWNER_REQUIRED`. Автоматическое удаление этого prefix запрещено до отдельного owner-approved решения.

## 4. Безопасные режимы

### Inspect / dry-run

Только чтение и локальная компиляция. POST/PUT/DELETE отсутствуют.

### Bulk Status

`Stepik Bulk Status` читает весь курс и различает source dependencies, publication routes, verified physical bindings, human/legacy title state и оставшиеся materialization requirements. Точный legacy title считается миграционным состоянием, arbitrary title drift блокируется. Даже полностью разрешённый asset route не устанавливает `ready_for_bulk_write=true`.

### Impact after merge

Push в `main` не пишет в Stepik. Workflow dependency-aware определяет learner impact и обновляет PENDING Issue `#54` только через compare-before-PATCH guard.

### `first-upload-m04-l01`

Owner-only controlled write route для первого файлового non-golden lesson. Production machine acceptance этого route пройден run `34969028781`. После learner-hygiene migration этот исторический one-off route не является обычным способом дальнейшего обновления `M04-L01`.

Route требует:

- `workflow_dispatch`;
- `confirm_write=true`;
- current-main guard;
- общий mutex `stepik-live-course-299189`;
- private course и target lesson;
- exact title/language/position;
- доказуемый initial/recovery state;
- exact asset route `M04-L01-A01.txt → stepik-attachment-upload`;
- attachment capability preflight;
- WAL до каждого внешнего write;
- no blind retry;
- download/read-back attachment bytes;
- verified final lesson read-back;
- race-checked Issue state PATCH;
- `MACHINE_STATE_COMMITTED` только после PATCH.

Route не поддерживает DELETE, golden, произвольный lesson ID или массовую загрузку.

### Learner Hygiene

`.github/workflows/stepik-learner-hygiene.yml` является отдельным owner-only remediation route.

Он:

- принимает только fixed `course_id=299189`;
- требует `confirm_write=true`;
- использует тот же live mutex и current-main guard;
- меняет section/non-tracked lesson title только при точном legacy match;
- arbitrary/manual title drift блокирует;
- не использует CREATE/DELETE;
- для tracked `M02-L01/M04-L01` объединяет title и learner-content changes в один baseline-aware event;
- проверяет существующий M04 attachment baseline по metadata и downloaded bytes;
- обновляет Issue `#54` только после final read-back и race check;
- коммитит tracked history только после machine-state boundary;
- восстанавливает доказанный history-commit gap без повторного Stepik write;
- не меняет golden lesson titles автоматически;
- после успешного live run всё равно требует Human Visual Validation.

Полный contract: [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md).

### `sync-status`

Live read-only проверка tracked target против canonical desired state и confirmed baseline.

### `sync-reconcile`

Live read-only сопоставление current `main`, machine state, fresh live Stepik и immutable history. Automatic rebaseline отсутствует.

### `sync-changed`

Guarded exploitation write route для уже отслеживаемого `M02-L01`. Human-facing H1 из `lesson.md` является canonical expected title. Route требует owner dispatch, `confirm_write`, current-main guard, live mutex, baseline/history checks и verified read-back.

## 5. Verified rendering contract

General source compiler сохраняет canonical learner text. Verified rendering выполняется отдельным слоем.

All-course offline contract доказан для 21 lessons / 148 learner-facing steps:

- repo-relative learner links не остаются в финальном HTML;
- Markdown dependency не вставляется слепо внутрь предложения;
- исходная инструкция сохраняется, linked Markdown добавляется отдельным материалом в том же Stepik step;
- nested Markdown dependencies раскрываются рекурсивно;
- inline H1 learner-материалов получает смысловой заголовок без production ID;
- видимый итоговый HTML не содержит internal lesson/Asset/Exercise/Check IDs;
- confirmed external/Stepik URLs сохраняются ссылками;
- physical assets без verified binding дают `MaterializationRequired`;
- author-only материал не попадает в learner rendering;
- `free-answer` source берётся только из confirmed golden profile.

`M04-L01` machine read-back первого upload подтвердил learner block shape `text,text,text,text,free-answer,text` и fingerprint `sha256:e1633c610ca4e2b03d3b797b93baf2dc97d3e47c43f9fd4f34d809864697e538`. Этот старый fingerprint относится к состоянию до learner-hygiene remediation и не является целевым fingerprint после неё.

## 6. Attachment materialization

`M04-L01-A01.txt` использует owner-approved working assumption [D-2026-09-15-STEPIK-ATTACHMENTS](../../../00_governance/decision-log/2026-09-15-stepik-attachment-upload-assumption.md), подтверждённый production run `34969028781`.

Фактически подтверждено:

- `/api/attachments` поддержал необходимый POST contract;
- один multipart POST создал attachment ID `239272` в lesson `2591721`;
- response/read-back дал URL `https://stepik.org/media/attachments/lesson/2591721/M04-L01-A01.txt`;
- downloaded bytes совпали с canonical SHA-256 `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`;
- asset event `evt-e9a1d3f142cc3ff8d239b2e2d1cf898d` получил `APPLIED` и затем `MACHINE_STATE_COMMITTED`.

Learner-hygiene route не создаёт новый attachment: он повторно проверяет существующий binding и bytes. Автоматический POST retry по-прежнему отсутствует. Timeout/network/5xx после dispatch = ambiguous STOP.

## 7. Machine state schema

Issue `#54` фактически использует schema v3. Старые schema v1/v2 при чтении безопасно нормализуются с пустым `assets` без потери lesson baseline.

State хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — learner-facing изменения после baseline.

После run `34969028781` state содержит baseline `M04-L01` и verified binding `M04-L01-A01.txt`. При reuse automation повторно сверяет live attachment metadata и downloaded bytes с canonical SHA-256.

Learner-hygiene tracked migration формирует новый lesson baseline только после подтверждённого final read-back. Pending target закрывается только через `APPLIED`/`NOOP_CONFIRMED` и race-checked Issue update.

## 8. Durable deployment history и recovery

Asset materialization и lesson first upload являются разными logical events, потому что lesson fingerprint зависит от фактического verified attachment URL.

Штатный history contract:

`EVENT_STARTED → WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED`.

Recovery rules сохраняются:

- write не начинался: normal route возможен только при действующих guards;
- final read-back подтверждён, но Issue PATCH не состоялся: state восстанавливается из immutable history без повторного Stepik write;
- Issue PATCH состоялся, но tracked history commit не успел: следующий run завершает только доказанную history часть;
- title-only metadata с доказанным final read-back, но без `MACHINE_STATE_COMMITTED`, закрывает только history commit без повторного Stepik write, в том числе после продвижения `main`;
- partial prefix продолжается только если каждый ранее dispatch-нутый write имеет `WRITE_COMPLETED + OP_READBACK_CONFIRMED`, а fresh live совпадает с last confirmed intermediate fingerprint;
- ambiguous dispatch, known failed dispatch или failed read-back не разрешают blind continuation;
- manual/unproven live state = STOP.

## 9. Race guarantees

Сохраняются одновременно:

- fresh current-main guard;
- единый mutex `stepik-live-course-299189` для всех live write workflows;
- durable write-ahead history;
- per-operation и final read-back;
- Issue state guard `read expected → re-read current → compare → PATCH only if unchanged`;
- tracked `MACHINE_STATE_COMMITTED` только после успешного current-state boundary.

Unknown state = `STOP`.

## 10. API write policy

Автоматический write retry отсутствует для POST/PUT.

Write result классифицируется так:

- known 4xx failure: failed operation;
- timeout/network/HTTP 5xx/неоднозначный response: ambiguous outcome;
- HTTP success без подтверждённого read-back: не confirmed deployment.

`DELETE` не реализуется и не разрешается recovery route.

## 11. Что ещё закрывает bulk write

Machine acceptance первого `M04-L01` больше не является блокером, но его Human Visual Validation сейчас имеет `FAIL / RETEST REQUIRED`. До `upload-remaining` остаются:

1. merge и owner-dispatched live применение learner-hygiene remediation;
2. повторная Human Visual Validation `M04-L01` после remediation;
3. confirmed transactional materialization/read-back для PNG routes;
4. deterministic SVG→PNG route и visual/read-back verification;
5. общий initial-upload orchestration для remaining lessons вместо hard-coded pilot;
6. общий post-baseline drift guard для всех загруженных lessons;
7. integrity pass для independence/F1-sensitive lessons;
8. финальный all-course private staging verification;
9. Human Validation/Human Pilot по утверждённому production процессу.

Golden title cleanup `M00-L01/M00-L02` остаётся отдельным owner-required решением и не превращается в обычный bulk writer permission.

`ready_for_bulk_write=false`.

## 12. Что требуется от владельца

Владелец принимает только решения/действия, которые automation не должна принимать сама:

- запуск live write route;
- owner decision при ambiguous/manual/unknown provenance;
- отдельное решение для golden/structural/adoption cases;
- изменение/отмена D-2026-09-15-STEPIK-ATTACHMENTS;
- human visual/learner validation.

Для `M04-L01` machine acceptance первого upload пройден, но Human Visual Validation зафиксировала learner-ID regression. После learner-hygiene live migration требуется повторный человеческий visual check; API read-back его не заменяет.

## 13. Что этот контур не разрешает

- перепроектировать курс под удобство API;
- менять canonical IDs;
- превращать практику во фальшивый quiz;
- публиковать author-only recovery/rubric заранее;
- менять F1;
- считать API read-back Human Validation;
- считать successful upload доказательством PHONE/COMPUTER readiness;
- считать resolved asset route фактической materialization без verified binding;
- разблокировать общий bulk write одним успешным pilot result.
