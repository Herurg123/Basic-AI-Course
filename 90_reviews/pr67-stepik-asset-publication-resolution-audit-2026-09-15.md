# Adversarial audit PR #67 — Stepik asset publication resolution

**Дата:** 15 сентября 2026 года  
**PR:** #67 `Stepik: asset publication resolution для learner-facing материалов`  
**Base:** `main` @ `f65a5cd740533255ce13698e64af2b40eb2d0a2e`  
**Проверенный code+docs head:** `bc374e6f4b191537730c93e43b146473fac3406e`  
**Аудит:** отдельный критический проход после реализации, до merge

## 1. Итоговый вердикт

- **OPEN CRITICAL:** 0
- **OPEN HIGH:** 0
- **OWNER DECISION REQUIRED BEFORE MERGE:** 0
- **Stepik writes в PR:** 0
- **Bulk write:** остаётся закрытым
- **Merge recommendation:** PASS после зелёного CI на code+docs head и проверки, что audit-only commit не меняет production code/policy.

## 2. Что проверялось

Аудит намеренно искал не только синтаксические ошибки, но и способы получить ложный `route_gate_passed=true`:

1. неполный learner dependency graph;
2. скрытые nested local links внутри inline Markdown;
3. local links без Asset ID;
4. stale/missing source overrides;
5. topology drift после добавления/переноса learner dependency;
6. URL, не привязанный к точному source SHA-256;
7. слишком широкое разрешение `stepik-attachment-upload`;
8. смешение `route resolved` и `physically materialized`;
9. скрытое открытие first-upload/bulk write;
10. обход golden READ_ONLY;
11. несоответствие бесплатности курса и выбранного file route;
12. расхождение документации Stepik с фактическим API;
13. отсутствие fail-closed поведения при будущей потере attachment capability;
14. несогласованность `bulk-status` с новым asset gate.

## 3. Найденные в ходе Step 3 дефекты и их закрытие

### HIGH-01 — inventory видел только Asset ID links

Ранняя модель отслеживала в основном ссылки с canonical Asset ID. Это позволяло learner-facing repo-relative ссылке без Asset ID пройти мимо publication gate.

**Фактический пример:** три ссылки на `04_course/stepik/how-to-save-practice.md`.

**Исправление:** inventory schema v2 строится из всех repo-relative learner links, а direct inventory machine-checkably сравнивается с unresolved repo links general source compiler.

**Статус:** CLOSED.

### HIGH-02 — nested Markdown dependency не входила в route topology

`05_assets/M06/M06-L04/M06-L04-A01.md` содержит локальную learner dependency на `M06-L04-A02.md`. Ранняя direct-only инвентаризация могла объявить A01 inline-resolved и оставить A02 скрытой локальной ссылкой.

**Исправление:** `learner_dependency_links` рекурсивно раскрывает linked Markdown, topology учитывает `link_source_path` и `dependency_depth`; regression закрепляет `A01 → A02`.

**Статус:** CLOSED.

## 4. Финальный topology contract

Проверенная policy фиксирует:

- 48 direct repo-relative links source compiler;
- 49 dependency occurrences с nested dependency;
- 43 unique source files;
- `.md`: 42 occurrences;
- `.png`: 3;
- `.svg`: 2;
- `.docx`: 1;
- `.txt`: 1;
- fingerprint: `sha256:ecbb9f9b8426c5bd4bba9f07816ab0e647022c13c0f38b4c29d9debd6096c20d`.

Текущий route result:

- 49/49 occurrences resolved;
- 43/43 unique sources resolved;
- unresolved sources = 0;
- materialization required unique files = 5;
- `ready_for_bulk_write=false`;
- next gate = `verified-rendering-and-first-upload`.

## 5. Stepik attachment capability — отдельная проверка

### Документированное ограничение

Актуальная справка Stepik `Добавление файлов на Stepik` по состоянию на аудит говорит, что функция файлов доступна в платных курсах. `Настройки курса` повторяет это для раздела `Файлы`.

### Фактическое состояние курса 299189

Owner-approved decision `D-2026-09-15-STEPIK-ATTACHMENTS` основан на фактических read-only probes:

- course API: `is_paid=false`, `price=null`;
- course/lesson `actions.attachments` присутствуют;
- `GET /api/attachments?lesson=2591710` возвращает два реально загруженных владельцем attachments;
- `OPTIONS /api/attachments` → `Allow: GET, POST, HEAD, OPTIONS`;
- parsers включают `multipart/form-data`;
- metadata `POST.file`: `type=file upload`, `required=true`.

Runs: `34955808296`, `34955920959`, `34956046044`; во всех `stepik_content_writes=0`.

### Аудиторская оценка

Документированное тарифное утверждение и фактическая capability курса расходятся. Это не замаскировано как доказанный универсальный контракт Stepik. В проекте route имеет статус `owner-approved-working-assumption` и ограничен course `299189`.

Automation обязана вернуть STOP/reopen asset gate, если future preflight/write/read-back обнаружит тарифный blocker, исчезновение POST/multipart/file-upload schema либо недоказуемый learner download URL.

Автоматизированный POST attachment **не считается уже доказанным** и перенесён в следующий owner-dispatched write gate.

**Статус:** ACCEPTED OWNER DECISION; дополнительного owner decision перед merge не требуется.

## 6. Проверка ширины разрешения attachment route

`stepik-attachment-upload`:

- не включён как blanket `.txt` extension rule;
- для `M04-L01-A01.txt` задан точным `source_override`;
- требует ссылку на explicit capability `stepik_attachment_upload`;
- capability должна иметь `status=owner-approved-working-assumption`;
- source SHA-256 берётся из current canonical inventory и должен попасть в будущую write/history evidence;
- физическая загрузка не выполняется на route-resolution gate.

Regression tests отдельно запрещают включить этот route как безусловное правило для любого `.txt`.

**Вердикт:** чрезмерного расширения owner decision не найдено.

## 7. Golden и fixed URL bindings

Два существующих `M00-L02` attachment URL остаются `confirmed-url` только для точных физических source paths и точных SHA-256.

Изменение source content при неизменном URL приводит к fail-closed `confirmed URL source hash устарел`.

Golden binding scope остаётся `golden-read-only-live-observation`; он не даёт права перезаписывать golden object.

**Вердикт:** PASS.

## 8. Изображения и SVG

Для learner text Stepik официально поддерживает изображения; текущая policy оставляет non-golden PNG как будущую `stepik-image-upload`, а SVG как deterministic rasterization → PNG → Stepik image materialization.

В этом PR такие файлы не загружаются. Их физическая materialization остаётся частью следующего verified rendering/write gate и должна получить собственный read-back/history contract.

**Вердикт:** route-level решение допустимо; write capability не считается доказанной этим PR.

## 9. Bulk-status integration

Проверено разделение:

- `repo_relative_links_detected` — source-level discovery;
- `repo_relative_links_pending_asset_route` — только unresolved route;
- `asset_materialization_required_sources` — resolved, но ещё не загруженные/преобразованные sources.

При текущей policy asset route gate переводит `next_gate` на `verified-rendering-and-first-upload`, но `ready_for_bulk_write` остаётся `false`.

Искусственно unresolved asset report возвращает hard blocker `asset-publication-resolution:BLOCKED`.

**Вердикт:** PASS.

## 10. CI evidence

PR workflow run `34960437188` на code+docs head `bc374e6f4b191537730c93e43b146473fac3406e`:

- `Тесты и structural dry-run`: SUCCESS;
- 167 unit tests: PASS;
- structural dry-run: PASS;
- owner live job: SKIPPED;
- post-merge pending job: SKIPPED (ожидаемо для PR);
- Stepik writes: 0.

Среди новых regression tests есть:

- all-current-routes resolved;
- exact topology fingerprint;
- non-Asset help links;
- nested dependency;
- compiler direct-link equivalence;
- exact golden URL/hash binding;
- explicit attachment capability requirement;
- no blanket attachment extension rule;
- topology drift fail-closed;
- stale override fail-closed;
- offline report contract;
- bulk-status resolved/unresolved transition.

## 11. Non-blocking residual risks

1. Первый реальный automated `POST /api/attachments` ещё не выполнялся. Это сознательно перенесено в следующий owner-dispatched write gate, а не замаскировано route gate.
2. Документация Stepik продолжает говорить о paid-course restriction, поэтому attachment capability должна перепроверяться непосредственно перед write.
3. URL/visual correctness после materialization требует фактического learner-facing read-back/human visual review; source-only route gate не может это доказать.
4. Rasterization SVG→PNG ещё не реализована; route определён, реализация относится к следующему gate.

Ни один residual risk не требует открытия bulk write или изменения learner-facing канона на этом PR.

## 12. Финальное решение аудита

PR #67 корректно закрывает **architecture/routing layer** Step 3 и не выдаёт будущую materialization за уже выполненную.

**OPEN CRITICAL = 0**  
**OPEN HIGH = 0**  
**OWNER DECISION REQUIRED BEFORE MERGE = 0**  
**MERGE = ALLOWED после подтверждения, что этот audit commit является единственным изменением после последнего зелёного code+docs head.**
