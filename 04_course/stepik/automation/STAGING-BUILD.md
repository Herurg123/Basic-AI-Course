# Guarded private Stepik staging build

**Статус:** production route proposal для ШАГА 2 Human Pilot  
**Курс:** `299189`  
**Назначение:** безопасно довести private Stepik от skeleton/partial production state до доказуемой версии текущего `main`, не усыновляя неизвестный live state и не ослабляя golden/F1/independence gates.

## 1. Граница route

Workflow `Stepik Staging Build` работает **по одному non-golden Lesson ID за dispatch**.

Он не является bulk writer в смысле «записать всё за один запуск». Это намеренно: один target ограничивает blast radius и позволяет после каждого lesson получить отдельные durable history, read-back и machine-state evidence.

Route не имеет права:

- менять `M00-L01/M00-L02` golden content;
- автоматически усыновлять существующий content без deployment baseline/history;
- перезаписывать arbitrary/manual drift;
- использовать DELETE;
- делать blind retry после ambiguous write;
- закрывать Human Visual или Human Validation gates машинным успехом;
- менять course-page metadata.

`M00-L02` canonical-vs-golden content divergence и course-page PENDING остаются отдельными owner-scoped задачами после сборки обычных lessons.

## 2. Два запуска на target

### Read-only preflight

`confirm_write=false`.

Обязательные проверки до любого write:

1. workflow запущен из актуального `main`;
2. `course_id` точно `299189`;
3. course и target lesson private;
4. структура sections/units совпадает с manifest;
5. golden profile подтверждён;
6. target не golden;
7. target присутствует в Issue #54 как `PENDING`;
8. target не имеет confirmed lesson baseline;
9. live title точно равен current canonical human-facing title;
10. новый initial upload начинается только из exact skeleton placeholder; исключение — доказанная immutable recovery history;
11. physical visual assets либо имеют verified machine binding, либо отсутствуют в target lesson и готовы к materialization;
12. неизвестный same-name attachment без machine provenance блокирует route;
13. renderer может собрать все learner steps без unresolved dependency и с точным canonical step count.

Preflight не выполняет POST/PUT/DELETE в Stepik и не меняет Issue #54.

### Guarded write

`confirm_write=true` разрешён только после проверки preflight artifact того же target.

Write route повторяет fresh current-main/live guards и затем:

1. материализует необходимые visual assets;
2. выполняет byte-level read-back каждого нового physical asset;
3. собирает final learner rendering уже с фактическими Stepik URL;
4. заполняет existing skeleton через общий `execute_initial_upload_one`;
5. журналирует WAL до каждого PUT/POST;
6. проверяет каждую step operation и final lesson fingerprint read-back;
7. формирует `sync-state.next.json`, но сам runtime Issue не патчит;
8. workflow повторно читает Issue #54, проверяет race against `sync-state.previous.json`, затем PATCH-ит только доказанный next state;
9. только после successful machine-state boundary добавляет `MACHINE_STATE_COMMITTED` в durable history.

Если Issue race-check не проходит, Stepik write не повторяется автоматически: immutable final history используется для recovery следующего запуска.

## 3. Visual materialization

### Canonical PNG

Policy mode `stepik-image-upload` материализуется как Stepik lesson attachment с PNG bytes. Learner rendering использует подтверждённый абсолютный Stepik URL этого physical object.

Evidence включает:

- canonical source SHA-256;
- filename/size/attachment ID/lesson ID;
- downloaded-byte SHA-256;
- machine binding в Issue #54.

### Canonical SVG

Policy mode `rasterize-png-stepik-image` сначала детерминированно преобразует SVG в PNG pinned runtime `CairoSVG==2.9.1`, затем публикует PNG тем же verified physical route.

Для SVG намеренно сохраняются два разных hashes:

- `source_sha256` — canonical SVG bytes;
- `materialized_sha256` — фактически опубликованный PNG.

`materialization_fingerprint` связывает source path, source hash, publication mode, output filename и materialized hash. Благодаря этому PNG read-back не подменяет доказательство происхождения из текущего canonical SVG.

## 4. PED/Astra boundaries

Маршрут обязан сохранять:

- PED-02: recovery semantics не меняются writer-ом;
- PED-04/CRIT-C-01: Stepik sequence и learner content берутся из canonical lesson/plan без нового раннего cue;
- PED-05: порядок rationale-before-trace не меняется;
- PED-06: два M03 interface PNG должны быть реально materialized и затем пройти Human Visual branch check;
- PED-07: renderer/visual assets не должны возвращать internal IDs в learner-visible layer.

В рамках подготовки route найден и исправлен отдельный PED-07 source regression: learner-visible SVG `M05-L01-A02.svg` содержал текстовый internal Asset ID. Regression-test теперь проверяет learner-visible текст всех SVG assets.

Machine PASS после staging write **не** является PED-06/PED-07 Human Visual PASS.

## 5. Recovery contract

### Asset write

- POST не был dispatch-нут → новый guarded run возможен;
- final asset read-back существует, но Issue state не обновился → asset восстанавливается из immutable history без повторного POST;
- ambiguous/failed/read-back-failed asset event → automatic continuation запрещён;
- same-name live file без provenance → automatic adoption запрещён.

### Lesson write

Используется существующий `execute_initial_upload_one` contract:

- pristine skeleton → normal initial upload;
- partial prefix → продолжение только если каждый предыдущий dispatch имеет `WRITE_COMPLETED + OP_READBACK_CONFIRMED`, а live fingerprint равен последнему подтверждённому intermediate state;
- complete matching live → recovery только при полной подтверждённой write history;
- unknown partial/complete content → STOP;
- DELETE отсутствует.

## 6. Что будет считаться Step 2 machine completion

Для ordinary non-golden lessons:

- каждый target имеет confirmed baseline на одном принятом `main` SHA;
- соответствующий lesson PENDING закрыт через APPLIED/NOOP-confirmed boundary;
- все необходимые physical visual assets имеют verified bindings;
- read-only all-course status не показывает необъяснённого ordinary-lesson drift/PENDING;
- sections сохраняют positions `1..9`;
- course остаётся private.

После этого отдельно остаются:

1. owner-level решение по `M00-L02` canonical-vs-golden content divergence;
2. guarded course-page reconciliation;
3. all-course Human Visual proof, включая PED-06/PED-07;
4. PED-01 desktop/phone, PED-03 service preflight и остальные Human Pilot readiness gates.

Наличие этого route само по себе не означает `WAVE 0 READY`.
