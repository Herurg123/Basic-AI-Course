# Read-only preflight всего курса перед массовым Stepik upload

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Workflow:** `Stepik Bulk Status`  
**Источник содержания:** актуальный `main`

## Назначение

`bulk-status` нужен между проверенным single-lesson pilot и будущим `upload-remaining`. Он одним запуском читает фактический курс Stepik, deployment baseline из issue `#54`, структурный manifest и canonical assets всех 21 уроков.

Этот режим **никогда не пишет в Stepik** и не изменяет issue `#54`. У него нет `confirm_write` и нет write-route.

## Что проверяется

Для каждого канонического Lesson ID фиксируются:

- точный Stepik lesson ID по section/unit position;
- текущий и ожидаемый title;
- число live steps и число строк `stepik-plan.md`;
- наличие deployment baseline;
- golden / independence-sensitive / F1-sensitive flags;
- Asset ID;
- текущий preflight status и следующий разрешённый шаг.

Два golden lessons остаются `READ_ONLY_GOLDEN`. Уже проверенный `M02-L01` оценивается тем же тройным сравнением `baseline ↔ live ↔ desired`, что и эксплуатационный sync. Остальные skeleton lessons до general compiler получают `INITIAL_UPLOAD_REQUIRED`, а не фиктивный `READY`.

Если в существующем non-golden lesson уже есть содержательный контент без подтверждённого baseline, статус становится `UNMANAGED_EXISTING_CONTENT_BLOCKED`: автоматизация не усыновляет неизвестное live-состояние молча.

## Asset inventory

Preflight строит `asset-inventory.json` только из Git-tracked источников. Для каждого physical asset-файла сохраняются:

- canonical Asset ID;
- точный Git path;
- имя и расширение;
- размер;
- SHA-256 содержимого.

Отдельно перечисляются repo-relative ссылки из learner-facing `lesson.md`. Такая ссылка считается требующей явного решения `published URL` или `inline adaptation` до массовой записи.

Это защищает от ситуации, когда DOCX/PNG/SVG изменился в GitHub, а URL в Stepik остался прежним: один неизменившийся HTML больше не может служить доказательством синхронизации бинарного asset.

## Статусы

- `READ_ONLY_GOLDEN` — golden lesson не изменяется.
- `IN_SYNC` — live, baseline и compiled desired совпадают.
- `UPDATE_REQUIRED` — tracked lesson требует обычного drift-guarded sync.
- `INITIAL_UPLOAD_REQUIRED` — существующий skeleton ждёт first verified content upload и создания baseline.
- `BASELINE_PRESENT_COMPILER_UNAVAILABLE_BLOCKED` — baseline уже есть, но общий compiler для этого урока ещё не утверждён; overwrite запрещён.
- `UNMANAGED_EXISTING_CONTENT_BLOCKED` — в Stepik найден содержательный non-golden lesson без baseline; требуется отдельное исследование.

Stale title не означает отсутствующий lesson. Он фиксируется отдельным `title_state=STALE_TITLE` и требует explicit metadata route, чтобы не создавать дубль.

## Условия перед будущим bulk write

Успешный `bulk-status` **не разблокирует запись**. Поле `ready_for_bulk_write` намеренно остаётся `false`.

Перед `upload-remaining` должны быть отдельно реализованы и проверены:

1. general content compiler для всех learner-facing lessons;
2. однозначное разрешение каждого learner-facing asset в Stepik URL либо inline content;
3. first-upload writer, который после каждого write делает read-back и создаёт baseline;
4. общий drift guard для последующих обновлений;
5. отдельный integrity pass для independence/F1-sensitive lessons;
6. explicit route для stale lesson titles без создания новых lessons;
7. запрет `DELETE` и fail-closed поведение при любой неоднозначности.

До выполнения этих условий массовый Stepik write остаётся закрытым.
