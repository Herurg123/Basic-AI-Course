# General source compiler для Stepik

**Статус:** production source-compilation contract  
**Дата:** 15 сентября 2026 года  
**Курс Stepik:** `299189`  
**Источник learner-facing текста:** только `lesson.md` актуального `main`

## 1. Назначение

General source compiler закрывает отдельный production gate между проверенным single-lesson pilot `M02-L01` и будущим массовым заполнением Stepik.

Его задача — преобразовать все canonical learner lessons в упорядоченный набор будущих Stepik blocks **без записи в Stepik и без выдумывания asset URLs**.

Compiler сам по себе не является upload route и не переводит `ready_for_bulk_write` в `true`.

## 2. Источники и роли

Compiler сознательно разделяет два источника:

- `lesson.md` содержит learner-facing текст и является единственным источником того, что увидит ученик;
- `stepik-plan.md` задаёт production contract: число и порядок логических шагов, Exercise/Check IDs, тип шага и author-only границы.

Краткий summary из `stepik-plan.md` не используется как замена learner-facing текста. Это предотвращает машинный пересказ курса при публикации.

## 3. Source-preserving alignment

`lesson.md` разбивается на последовательные source chunks:

- обычные learner paragraphs;
- H2/H3 headings;
- Exercise/Check marker boundaries.

H2/H3 преобразуются в компактные жирные learner labels внутри будущего Stepik block. Production HTML comments `Exercise` / `Check` не публикуются ученику: они используются только как alignment anchors.

Далее compiler сопоставляет последовательные source chunks с learner rows `stepik-plan.md` при следующих жёстких условиях:

- порядок learner source не меняется;
- каждый source chunk используется ровно один раз;
- пустые learner steps запрещены;
- marker нельзя поместить в plan row, который не владеет соответствующим Exercise/Check ID;
- уникальный Exercise/Check marker обязан попасть в соответствующий plan row;
- author-only rows исключаются до learner compilation;
- Check-секция от `Check` marker до следующего H2/H3 неделима между Stepik steps;
- Stepik step, содержащий Check-секцию, обязан закончиться вместе с ней и не может захватить следующую смысловую H2/H3-секцию;
- если несколько разных разбиений имеют одинаковый лучший score, compiler не выбирает одно произвольно, а останавливается fail-closed;
- при невозможном alignment compiler также останавливается fail-closed.

Exercise-секция при этом может быть разделена на практику и последующее объяснение, если это прямо требуется `stepik-plan.md`. Это нужно для уроков, где после самостоятельного действия внутри той же Markdown-секции идёт отдельный instructional step.

Внутри допустимых вариантов используется детерминированный lexical/position score для выбора последовательной границы. Этот score не создаёт и не редактирует ученический текст; он только выбирает границу между уже существующими source chunks.

## 4. Block types

Compiler строит source-level block shape:

- обычные instructional/practice/recovery/transfer rows → `text`;
- check/rubric/evidence/reflection/explanation rows → `free-answer`.

Для `free-answer` разрешена только конфигурация, подтверждённая golden profile:

```json
{
  "is_attachments_enabled": false,
  "is_html_enabled": true,
  "manual_scoring": false
}
```

Иная конфигурация = STOP.

## 5. All-course contract

На каноне после педагогических исправлений:

- modules: `9`;
- canonical lessons: `21`;
- structural `stepik-plan.md` rows: `150`;
- author-only rows: `2`;
- learner-facing source-compiled rows: `148`.

Compiler покрывает в том числе:

- два golden lessons, остающиеся `READ_ONLY`;
- verified pilot `M02-L01`;
- branching/recovery lessons;
- independence-sensitive и F1-sensitive lessons;
- планы с повторным Check ID;
- планы с author-only строками.

Компиляция golden source не является разрешением менять live golden representation.

## 6. Pilot compatibility

Проверенный exploitation sync `M02-L01` пока сохраняет существующий специализированный rendered compiler и доказанный fingerprint.

General compiler строит source-level representation `M02-L01`, но не подменяет им confirmed baseline и не меняет writer route. Перевод пилота на общий rendered route допускается только после отдельной asset/rendering совместимости и fingerprint review.

## 7. Assets и repo-relative links

Source compiler намеренно **не** превращает repo-relative links в предполагаемые URLs.

Для каждого compiled step сохраняются:

- Asset IDs;
- repo-relative link targets;
- source Git paths.

Пока ссылка не получила подтверждённый Stepik URL либо утверждённую inline adaptation, она остаётся `repo_relative_links_pending_asset_route`.

Это следующий отдельный gate: `asset-publication-resolution`.

## 8. Проверки

Regression suite обязана подтверждать минимум:

- все 21 lessons компилируются;
- 150 structural rows → 148 learner rows после исключения двух author-only rows;
- весь learner-facing source сохраняется в исходном порядке;
- source chunks не теряются и не дублируются;
- Exercise/Check markers принадлежат допустимым plan rows;
- Check-step не захватывает recovery/transfer/closing section после своей рубрики;
- `M01-L02` сохраняет canonical порядок: вторая переносная ситуация → финальная C01 → backup/итог;
- sensitive/branching lessons сохраняют ожидаемый `text` / `free-answer` shape;
- free-answer source совпадает с golden convention;
- repo-relative links остаются явными до asset gate.

`compiler_report.py` формирует offline all-course audit report и никогда не вызывает Stepik API.

## 9. Что этот gate НЕ разрешает

General compiler не разрешает:

- initial bulk write;
- UPDATE существующих lessons;
- adoption неизвестного live content;
- изменение golden lessons;
- автоматическую публикацию assets;
- stale-title mutation;
- DELETE;
- изменение Issue `#54` baseline только по факту успешной компиляции.

## 10. Следующий gate

После подтверждения general compiler следующий production gate:

`asset-publication-resolution`.

Только после него отдельно проектируется verified first-upload writer с write-ahead history, per-operation read-back и созданием baseline.
