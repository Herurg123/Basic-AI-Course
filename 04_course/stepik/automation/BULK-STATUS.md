# Read-only preflight всего курса перед массовым Stepik upload

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Workflow:** `Stepik Bulk Status`  
**Источник содержания:** актуальный `main`

## Назначение

`bulk-status` нужен между проверенным single-lesson pilot и будущим `upload-remaining`. Он одним запуском читает фактический курс Stepik, deployment baseline из issue `#54`, структурный manifest, source-compiled learner steps и canonical assets всех 21 уроков.

Этот режим **никогда не пишет в Stepik** и не изменяет issue `#54`. У него нет `confirm_write` и нет write-route.

## Что проверяется

Для каждого канонического Lesson ID фиксируются:

- точный Stepik lesson ID по section/unit position;
- текущий и ожидаемый title;
- число live steps и число строк `stepik-plan.md`;
- `compiler_status` и число source-compiled learner steps после удаления author-only rows;
- block sequence `text` / `free-answer`;
- repo-relative links, которые ещё требуют asset-publication решения;
- наличие deployment baseline;
- golden / independence-sensitive / F1-sensitive flags;
- Asset ID;
- текущий preflight status и следующий разрешённый шаг.

Два golden lessons остаются `READ_ONLY_GOLDEN`. Их canonical source может компилироваться для проверки production pipeline, но это **не** разрешает менять live golden representation.

Уже проверенный `M02-L01` по-прежнему оценивается тем же проверенным exploitation compiler и тройным сравнением `baseline ↔ live ↔ desired`, что и эксплуатационный sync. General source compiler не переписывает доказанный baseline пилота.

Остальные skeleton lessons имеют `compiler_status=SOURCE_COMPILED`, но до разрешения assets и появления first-upload writer продолжают получать `INITIAL_UPLOAD_REQUIRED`, а не фиктивный `READY`.

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

## Asset inventory и следующий gate

Preflight строит `asset-inventory.json` только из Git-tracked источников. Для каждого physical asset-файла сохраняются:

- canonical Asset ID;
- точный Git path;
- имя и расширение;
- размер;
- SHA-256 содержимого.

Repo-relative ссылки из learner-facing `lesson.md` source compiler намеренно не маскирует. Они сохраняются в `repo_relative_links_pending_asset_route` и требуют явного решения на следующем gate:

- published Stepik URL; либо
- подтверждённая inline adaptation.

Это защищает от ситуации, когда DOCX/PNG/SVG изменился в GitHub, а URL в Stepik остался прежним: один неизменившийся HTML больше не может служить доказательством синхронизации бинарного asset.

## Статусы

- `READ_ONLY_GOLDEN` — golden lesson не изменяется.
- `IN_SYNC` — live, baseline и проверенный rendered desired совпадают.
- `UPDATE_REQUIRED` — tracked lesson требует обычного drift-guarded sync.
- `INITIAL_UPLOAD_REQUIRED` — source уже компилируется, но существующий skeleton ждёт asset resolution, verified first upload и создания baseline.
- `BASELINE_PRESENT_RENDERING_PENDING_BLOCKED` — source compiler доступен, но для объекта с baseline ещё нет общего доказанного rendered route; overwrite запрещён.
- `UNMANAGED_EXISTING_CONTENT_BLOCKED` — в Stepik найден содержательный non-golden lesson без baseline; требуется отдельное исследование.

Stale title не означает отсутствующий lesson. Он фиксируется отдельным `title_state=STALE_TITLE` и требует explicit metadata route, чтобы не создавать дубль.

## Условия перед будущим bulk write

Успешный `bulk-status` **не разблокирует запись**. Поле `ready_for_bulk_write` намеренно остаётся `false`.

General source compiler является закрытым gate. Следующий gate после него: `asset-publication-resolution`.

Перед `upload-remaining` всё ещё должны быть отдельно реализованы и проверены:

1. однозначное разрешение каждого learner-facing asset/repo-relative link в Stepik URL либо inline content;
2. first-upload writer, который после каждого write делает read-back и создаёт baseline;
3. общий drift guard для последующих обновлений;
4. отдельный integrity pass для independence/F1-sensitive lessons;
5. explicit route для stale lesson titles без создания новых lessons;
6. запрет `DELETE` и fail-closed поведение при любой неоднозначности.

До выполнения этих условий массовый Stepik write остаётся закрытым.
