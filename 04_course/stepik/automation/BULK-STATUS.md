# Read-only preflight всего курса перед массовым Stepik upload

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Workflow:** `Stepik Bulk Status`  
**Источник содержания:** актуальный `main`

## Назначение

`bulk-status` нужен между проверенным single-lesson pilot и будущим `upload-remaining`. Он одним запуском читает фактический курс Stepik, deployment baseline из issue `#54`, структурный manifest, source-compiled learner steps, полный граф learner-facing local dependencies и утверждённую asset publication policy всех 21 уроков.

Этот режим **никогда не пишет в Stepik** и не изменяет issue `#54`. У него нет `confirm_write` и нет write-route.

## Что проверяется

Для каждого канонического Lesson ID фиксируются:

- точный Stepik lesson ID по section/unit position;
- текущий и ожидаемый title;
- число live steps и число строк `stepik-plan.md`;
- `compiler_status` и число source-compiled learner steps после удаления author-only rows;
- block sequence `text` / `free-answer`;
- repo-relative links, найденные source compiler;
- полный learner dependency graph, включая nested Markdown dependencies;
- разрешённый publication mode для каждой зависимости;
- assets, которые уже имеют confirmed URL;
- assets, которые требуют materialization внутри будущей write-транзакции;
- наличие deployment baseline;
- golden / independence-sensitive / F1-sensitive flags;
- Asset ID;
- текущий preflight status и следующий разрешённый шаг.

Два golden lessons остаются `READ_ONLY_GOLDEN`. Их canonical source может компилироваться для проверки production pipeline, но это **не** разрешает менять live golden representation.

Уже проверенный `M02-L01` по-прежнему оценивается тем же проверенным exploitation compiler и тройным сравнением `baseline ↔ live ↔ desired`, что и эксплуатационный sync. General source compiler не переписывает доказанный baseline пилота.

Остальные skeleton lessons имеют `compiler_status=SOURCE_COMPILED`. После закрытия asset route gate их статус всё равно остаётся `INITIAL_UPLOAD_REQUIRED`, пока не реализованы verified rendering и controlled first-upload writer. Route resolution не является разрешением на write.

Если в существующем non-golden lesson уже есть содержательный контент без подтверждённого baseline, статус остаётся `UNMANAGED_EXISTING_CONTENT_BLOCKED`: автоматизация не усыновляет неизвестное live-состояние молча.

## General source compiler

Source compiler работает для всех 21 canonical lessons и использует два разных слоя по назначению:

- `lesson.md` — единственный learner-facing source текста;
- `stepik-plan.md` — контракт числа, порядка, типа шагов и Exercise/Check границ.

Compiler не пересказывает lesson по кратким summary из Stepik-plan. Он сохраняет learner-facing source, использует Exercise/Check markers как alignment anchors, исключает author-only rows и fail-closed останавливается, если source невозможно согласовать с plan.

H2/H3 learner headings при source compilation превращаются в компактные жирные метки внутри будущего Stepik block. Exercise/Check HTML comments служат только production anchors и learner-facing текстом не становятся.

Текущий all-course contract:

- 21 canonical lessons;
- 150 structural plan rows;
- 2 author-only rows исключаются;
- 148 learner-facing source-compiled rows;
- весь learner-facing `lesson.md` сохраняется в исходном порядке без потери или дублирования;
- confirmed golden `free_answer_source` используется fail-closed;
- Stepik writer этим compiler **не включается**.

## Asset publication resolution

Asset inventory строится из Git-tracked источников и отслеживает не только Asset ID, а полный граф локальных learner-facing зависимостей.

Текущий утверждённый topology contract:

- 48 direct repo-relative links из learner source compiler;
- 49 dependency occurrences с учётом nested dependency;
- 43 уникальных source-файла;
- topology fingerprint `sha256:ecbb9f9b8426c5bd4bba9f07816ab0e647022c13c0f38b4c29d9debd6096c20d`.

Для каждого физического source-файла сохраняются точный Git path, расширение, размер и SHA-256 содержимого. Новый/перемещённый файл, новый локальный dependency edge или новый формат меняют topology и fail-closed блокируют старую policy.

Publication modes:

- `.md` → `inline-source`: canonical Markdown должен быть контекстно встроен verified rendering layer; blind string replacement запрещён;
- non-golden `.png` → `stepik-image-upload`;
- `.svg` → deterministic rasterization в PNG → `stepik-image-upload`;
- существующие golden `M00-L02` DOCX/PNG → `confirmed-url`, жёстко привязанный к точному source SHA-256;
- `M04-L01-A01.txt` → `stepik-attachment-upload`.

Маршрут `stepik-attachment-upload` принят владельцем как рабочее production-допущение D-2026-09-15-STEPIK-ATTACHMENTS. Основание: два существующих live attachments, read-only API discovery, `POST /api/attachments`, `multipart/form-data` и обязательное поле `file upload` подтверждены для бесплатного курса `299189`.

Это допущение fail-closed: если API перестаёт объявлять POST/upload capability, возвращает тарифный/permission blocker либо upload/read-back/download невозможно доказать, asset route снова считается незакрытым.

Текущий route gate:

- 49/49 dependency occurrences resolved;
- 43/43 unique source files resolved;
- unresolved sources: 0;
- 5 уникальных файлов потребуют materialization внутри будущей write-транзакции;
- `ready_for_bulk_write=false`.

`bulk-status` сохраняет отдельно:

- `repo_relative_links_detected` — что source compiler реально нашёл;
- `repo_relative_links_pending_asset_route` — только действительно неразрешённые routes;
- `asset_materialization_required_sources` — resolved routes, которые ещё нужно физически материализовать при write.

Таким образом resolved route не маскируется под уже загруженный файл, а materialization не маскируется под незакрытую архитектурную проблему.

## Статусы

- `READ_ONLY_GOLDEN` — golden lesson не изменяется.
- `IN_SYNC` — live, baseline и проверенный rendered desired совпадают.
- `UPDATE_REQUIRED` — tracked lesson требует обычного drift-guarded sync.
- `INITIAL_UPLOAD_REQUIRED` — source и asset routes определены, но существующий skeleton ждёт verified rendering, first upload и создания baseline.
- `BASELINE_PRESENT_RENDERING_PENDING_BLOCKED` — source и routes известны, но для объекта с baseline ещё нет общего доказанного rendered route; overwrite запрещён.
- `UNMANAGED_EXISTING_CONTENT_BLOCKED` — в Stepik найден содержательный non-golden lesson без baseline; требуется отдельное исследование.

Stale title не означает отсутствующий lesson. Он фиксируется отдельным `title_state=STALE_TITLE` и требует explicit metadata route, чтобы не создавать дубль.

## Условия перед будущим bulk write

Успешный `bulk-status` **не разблокирует запись**. Поле `ready_for_bulk_write` намеренно остаётся `false`.

General source compiler и `asset-publication-resolution` являются закрытыми gates. Следующий gate: `verified-rendering-and-first-upload`.

Перед `upload-remaining` всё ещё должны быть отдельно реализованы и проверены:

1. verified rendering, который контекстно заменяет все local learner dependencies на inline content или фактические Stepik URLs без потери педагогической структуры;
2. controlled first-upload writer, который материализует необходимые images/attachments только внутри защищённой транзакции, после каждого write делает read-back и создаёт baseline;
3. attachment capability preflight перед первым file upload и fail-closed STOP при расхождении с D-2026-09-15-STEPIK-ATTACHMENTS;
4. общий drift guard для последующих обновлений;
5. отдельный integrity pass для independence/F1-sensitive lessons;
6. explicit route для stale lesson titles без создания новых lessons;
7. запрет `DELETE` и fail-closed поведение при любой неоднозначности.

До выполнения этих условий массовый Stepik write остаётся закрытым.
