# Автоматизация переноса и эксплуатационной синхронизации курса в Stepik

**Статус:** production automation contract / implementation handoff  
**Дата актуализации статуса:** 16 сентября 2026 года  
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
- выполнять отдельный owner-approved golden-title route только для двух exact title migrations M00-L01/M00-L02;
- восстанавливать section positions отдельным guarded route без изменения lesson/unit/step content;
- durable-журналировать deployment/recovery operations;
- восстанавливаться после доказуемого partial/state/history-commit gap без повторного Stepik write;
- выполнять read-only baseline reconcile classification.

### Актуальный доказанный production state

**M04-L01 initial upload machine acceptance:** run `34969028781` на `main@de98e60b845b51eda4c551cdc55c0c7139c35a55` подтвердил attachment materialization, 6-step rendering, read-back, Issue schema v3 и `MACHINE_STATE_COMMITTED`. Исторический Human Visual Validation после этого первого upload дал `FAIL / RETEST REQUIRED` из-за learner-facing ID.

**Learner-hygiene remediation после инцидента:**

- section-position recovery run `35015060946` восстановил позиции sections `1..9` и подтвердил неизменность content invariant;
- partial-write M02 был восстановлен без blind retry run `35078545526`;
- M04 learner-hygiene run `35079859897` завершён `PASS`, final fingerprint `sha256:56aca7da0220b8dfba35f299a80f7324bca885f8ac70636e8f987167dde915c4`, machine state/history committed;
- owner Human Visual Validation после remediation подтвердила правильный order, human-facing M04/M07/M08 surfaces, working attachment/links/free-answer и отсутствие проверенных internal IDs.

**Golden title migration:** run `35086056899` выполнил ровно два owner-approved title PUT для `M00-L01/M00-L02`, не изменив structure/content. Post-write observation fixture принят отдельным PR #83 (`main@f16a20100e1933548d84c3706423764bb1e3d416`). Финальный owner HVA подтвердил human-facing titles без `M00-L01/M00-L02` prefixes.

Эти machine/HVA PASS относятся к конкретным проверенным surfaces и **не доказывают all-course equivalence текущему `main`**.

Current Issue #54 содержит confirmed tracked baselines `M02-L01` и `M04-L01`, но одновременно 18 `PENDING` lessons и отдельный pending course-page. Поэтому current private Stepik нельзя объявлять актуальным all-course staging только по успешности перечисленных workflows.

Общий bulk write остаётся закрытым: `ready_for_bulk_write=false`.

## 2. Канонические источники и derived state

Learner-facing content берётся только из `main`, прежде всего из:

- `lesson.md`;
- `stepik-plan.md`;
- learner-facing assets;
- утверждённых production документов Stepik.

Operational state разделён на слои:

1. current machine state в Issue `#54`;
2. immutable deployment/recovery history в branch `stepik-deployment-history-v1`;
3. strict observation fixture `golden-profile.v1.json` для read-only golden;
4. human-readable comments Issues и Human Visual Validation evidence.

Ни Issue, ни history branch, ни golden fixture не являются content source.

Подробности:

- [`SYNC-POLICY.md`](SYNC-POLICY.md);
- [`LIVE-SAFETY.md`](LIVE-SAFETY.md);
- [`DEPLOYMENT-HISTORY.md`](DEPLOYMENT-HISTORY.md);
- [`RECOVERY-RECONCILE.md`](RECOVERY-RECONCILE.md);
- [`BULK-STATUS.md`](BULK-STATUS.md);
- [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md);
- [`GOLDEN-TITLE-MIGRATION.md`](GOLDEN-TITLE-MIGRATION.md);
- [`SECTION-POSITION-RECOVERY-2026-09-15.md`](SECTION-POSITION-RECOVERY-2026-09-15.md);
- [`asset-publication.v1.json`](asset-publication.v1.json);
- [`ownership-matrix.v1.json`](ownership-matrix.v1.json).

## 3. Golden sample

`M00-L01` и `M00-L02` остаются платформенным `READ_ONLY_GOLDEN`. Обычный uploader/recovery и learner-hygiene writer не изменяют и не удаляют их.

Canonical `main` может развиваться после создания golden sample. Расхождение current canonical и подтверждённого live golden фиксируется target-scoped и не даёт права автоматического adoption/rebaseline.

Текущий известный content notice сохраняется: canonical `M00-L02` содержит 8 steps, confirmed live golden — 7. Успешная title migration этого расхождения не устраняет.

Legacy title prefixes `M00-L01/M00-L02` **больше не являются текущим blocker**: owner-approved migration run `35086056899` завершена, fixture обновлён PR #83, финальный HVA PASS. Это не ослабляет общий `READ_ONLY_GOLDEN` policy и не разрешает другие golden writes.

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
- mutating mode требует `confirm_write=true`;
- read-only preflight при `confirm_write=false` строит inspectable plan без Stepik writes и без mutating Issue/history side effects;
- использует тот же live mutex и current-main guard;
- меняет section/non-tracked lesson title только при точном legacy match;
- arbitrary/manual title drift блокирует;
- не использует CREATE/DELETE;
- для tracked `M02-L01/M04-L01` объединяет title и learner-content changes в один baseline-aware event;
- проверяет существующий M04 attachment baseline по metadata и downloaded bytes;
- обновляет Issue `#54` только после final read-back и race check;
- коммитит tracked history только после machine-state boundary;
- восстанавливает доказанный partial/history-commit gap без blind retry;
- не меняет golden lesson titles автоматически;
- после успешного live run требует Human Visual Validation.

Текущая production hygiene/recovery цепочка для известных M02/M04/title incidents завершена и прошла HVA; route остаётся guard для будущих изменений, а не доказательством current all-course sync.

Полный contract: [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md).

### Golden Title Migration

`.github/workflows/stepik-golden-title-migration.yml` — отдельный owner-approved route только для exact M00-L01/M00-L02 legacy→human title transition. Production migration уже выполнена run `35086056899`; automatic fixture rebaseline по-прежнему запрещён, обычный golden validator не ослаблен.

### Section Position Recovery

Исторический incident #74 восстановлен run `35015060946`; Human Visual Validation завершён PASS. Recovery workflow не является обычным structural writer и не разрешает произвольный reorder.

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

Offline/source regression — это `SOURCE/MACHINE PASS`, а не доказательство того, что весь текущий live Stepik уже обновлён. Human Pilot readiness требует final learner-facing UI check после актуальной staging-сборки.

`M04-L01` initial fingerprint `sha256:e1633c610ca4e2b03d3b797b93baf2dc97d3e47c43f9fd4f34d809864697e538` является историческим состоянием до learner-hygiene remediation. Текущий confirmed tracked fingerprint после run `35079859897`: `sha256:56aca7da0220b8dfba35f299a80f7324bca885f8ac70636e8f987167dde915c4`.

## 6. Attachment materialization

`M04-L01-A01.txt` использует owner-approved working assumption [D-2026-09-15-STEPIK-ATTACHMENTS](../../../00_governance/decision-log/2026-09-15-stepik-attachment-upload-assumption.md), подтверждённый production run `34969028781`.

Фактически подтверждено:

- `/api/attachments` поддержал необходимый POST contract;
- один multipart POST создал attachment ID `239272` в lesson `2591721`;
- response/read-back дал URL `https://stepik.org/media/attachments/lesson/2591721/M04-L01-A01.txt`;
- downloaded bytes совпали с canonical SHA-256 `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`;
- asset event `evt-e9a1d3f142cc3ff8d239b2e2d1cf898d` получил `APPLIED` и затем `MACHINE_STATE_COMMITTED`.

Learner-hygiene route не создаёт новый attachment: он повторно проверяет существующий binding и bytes. Автоматический POST retry по-прежнему отсутствует. Timeout/network/5xx после dispatch = ambiguous STOP.

Для all-course staging остаются отдельные physical materialization gates, включая два M03 PNG и два SVG-derived visual assets, перечисленные в [`BULK-STATUS.md`](BULK-STATUS.md). Наличие source файла не считается publication PASS.

## 7. Machine state schema

Issue `#54` фактически использует schema v3. Старые schema v1/v2 при чтении безопасно нормализуются с пустым `assets` без потери lesson baseline.

State хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — learner-facing изменения после baseline.

На baseline 16.09.2026 confirmed tracked lesson baselines существуют для `M02-L01` и `M04-L01`, а verified asset binding — для `M04-L01-A01.txt`.

Одновременно Issue #54 содержит 18 PENDING lessons: `M00-L02`, `M00-L03`, `M01-L01`, `M01-L02`, `M02-L02`, `M03-L01`, `M03-L02`, `M04-L02`, `M04-L03`, `M05-L01`, `M05-L02`, `M06-L01`, `M06-L02`, `M06-L03`, `M06-L04`, `M07-L01`, `M07-L02`, `M08-L01`; отдельно pending для `04_course/stepik/course-page.md`.

Это означает: current machine state **не подтверждает canonical GitHub ↔ live Stepik equivalence всего курса**. PENDING нельзя автоматически считать принятым baseline.

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
- safe platform normalization учитывается только через явно принятую normalization contract, а не ad hoc adoption;
- ambiguous dispatch, known failed dispatch или failed read-back не разрешают blind continuation;
- manual/unproven live state = STOP.

Production partial-write incident #80 восстановлен по этим принципам; его закрытие не ослабляет fail-closed policy.

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

## 11. Что ещё закрывает bulk write / Human Pilot staging

Уже закрыты как отдельные production incidents/gates:

- initial machine acceptance `M04-L01`;
- section-position recovery #74 и последующий HVA;
- partial-write recovery #80 для M02;
- M04 learner-hygiene production write + HVA;
- golden title cleanup M00-L01/M00-L02 + post-write fixture + HVA.

Но `ready_for_bulk_write=false`, потому что до сборки актуального all-course private staging остаются:

1. confirmed transactional materialization/read-back для remaining PNG routes;
2. deterministic SVG→PNG route и visual/read-back verification;
3. общий initial-upload orchestration для remaining lessons вместо hard-coded pilot;
4. общий post-baseline drift guard для всех загруженных lessons;
5. reconciliation 18 lesson PENDING + course-page относительно выбранного current `main` staging SHA;
6. integrity pass для independence/F1-sensitive lessons, включая Astra PED regressions;
7. финальный all-course private staging verification и Human Visual checks;
8. Human Pilot readiness по `06_testing/human-pilot/`, включая real device/service/moderator/consent/participant gates.

Успешный ограниченный workflow не закрывает эти пункты автоматически.

## 12. Что требуется от владельца

Владелец принимает только решения/действия, которые automation не должна принимать сама:

- запуск live write route;
- owner decision при ambiguous/manual/unknown provenance;
- отдельное решение для golden/structural/adoption cases;
- изменение/отмена D-2026-09-15-STEPIK-ATTACHMENTS;
- human visual/learner validation.

Для текущего Step 1 Human Pilot readiness reconciliation новые live Stepik действия не выполняются. Следующий production handoff должен отдельно собрать и доказать актуальный private staging; его write-dispatches, если потребуются, остаются owner-gated по существующим contracts.

## 13. Что этот контур не разрешает

- перепроектировать курс под удобство API;
- менять canonical IDs;
- превращать практику во фальшивый quiz;
- публиковать author-only recovery/rubric заранее;
- менять F1;
- считать API read-back Human Validation;
- считать successful upload доказательством PHONE/COMPUTER readiness;
- считать resolved asset route фактической materialization без verified binding;
- считать SOURCE PASS доказательством publication/service/human PASS;
- разблокировать общий bulk write одним успешным pilot result.
