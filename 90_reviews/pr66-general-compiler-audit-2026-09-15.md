# PR #66 — adversarial audit general source compiler

**Дата:** 15 сентября 2026 года  
**PR:** #66 `Stepik: general source compiler для всех 21 урока`  
**Ветка:** `production/stepik-general-content-compiler`  
**Base SHA:** `7519493d5eed6fbf8f48b89081e8cbcf473216c8`  
**Проверенный code head:** `250d63408c29f939ee3615d14fd748160b194c4b`  
**Scope:** только source compilation / preflight. Stepik writer и bulk write не открываются.

## 1. Что проверялось

Аудит выполнялся не как повтор unit tests, а как adversarial review границ между canonical learner source и будущими Stepik steps.

Проверено:

- learner-facing source остаётся только `lesson.md`;
- `stepik-plan.md` используется как production contract, а не как источник пересказа;
- все 21 canonical lessons компилируются;
- 150 structural rows дают 148 learner-facing rows после исключения двух author-only строк;
- source chunks не теряются, не дублируются и не меняют порядок;
- Exercise/Check anchors не попадают в несовместимые plan rows;
- Check/rubric не разделяется между Stepik steps;
- Check-step не захватывает recovery/transfer/closing section после своей рубрики;
- independence/F1-sensitive границы проверены отдельно;
- golden lessons остаются READ_ONLY;
- verified `M02-L01` exploitation compiler/fingerprint не заменяется general compiler автоматически;
- repo-relative links/Asset ID остаются нерешёнными до отдельного asset-publication gate;
- `ready_for_bulk_write` остаётся `false`;
- compiler report не может объявить writer enabled;
- ни один путь этого PR не выполняет Stepik write.

## 2. Найденные дефекты и исправления

### A — HIGH — Check-step мог поглотить следующую смысловую секцию

**Проблема.** Marker мог принадлежать правильному plan row, а весь compiled step после Check-секции всё равно мог захватить следующий H2/H3. На полном alignment audit это проявилось, в частности, вокруг:

- `M05-L02-C02` → `Повторная ситуация для редактирования`;
- `M07-L02-C01` → `Если попытка стала тренировочной`;
- `M08-L01-C01` → `Важная граница`.

Такое разбиение сохраняло весь текст формально, но меняло педагогическую последовательность: recovery/closing попадал внутрь free-answer check step.

**Исправление.** В general compiler добавлен fail-closed инвариант: если span содержит Check-секцию, Stepik step обязан закончиться вместе с этой секцией и не может захватить следующий semantic section. Внутренний разрез Check-секции также запрещён.

**Regression.** `test_check_steps_do_not_absorb_following_semantic_sections` фиксирует три реальные границы `M05-L02`, `M07-L02`, `M08-L01`.

**Статус:** FIXED.

### B — HIGH — `M01-L02` production plan противоречил canonical lesson order

**Проблема.** В `lesson.md` порядок был:

1. E01;
2. E02;
3. вторая transfer-ситуация;
4. финальная `C01`;
5. backup/итог.

В старом `stepik-plan.md` строки 4 и 5 стояли наоборот: C01 раньше transfer. Source-preserving compiler поэтому вынужденно объединял transfer content с free-answer C01 step.

**Исправление.** Learner-facing `lesson.md` не менялся. В production `stepik-plan.md` переставлены только строки 4/5, чтобы plan следовал canonical learner source: transfer → C01.

**Regression.** `test_m01_l02_transfer_precedes_final_check_as_in_canonical_lesson` фиксирует реальный порядок.

**Статус:** FIXED.

### C — MEDIUM — диагностический alignment dump не являлся долговечным контрактом

**Проблема.** Временный `GENERAL_COMPILER_ALIGNMENT=...` помог найти реальные границы, но большой log dump не защищает от регрессий и загрязняет CI.

**Исправление.** Временный dump удалён; вместо него добавлены точечные semantic regression assertions на реальные чувствительные границы.

**Статус:** FIXED.

### D — LOW — `compiler_report.py` не имел отдельного contract test

**Проблема.** Utility использовал реальный канон, но его итоговые safety-поля не были отдельно зафиксированы тестом.

**Исправление.** Добавлен `test_compiler_report.py`, который на реальном курсе требует:

- 21 lesson;
- 150 structural rows;
- 2 author-only rows;
- 148 compiled learner steps;
- `stepik_writes == 0`;
- `writer_enabled == false`;
- `next_gate == asset-publication-resolution`;
- наличие нерешённых repo-relative links.

**Статус:** FIXED.

## 3. Финальные safety-инварианты

После исправлений:

- general compiler остаётся source-only;
- automatic asset URL guessing отсутствует;
- first-upload writer отсутствует;
- bulk writer отсутствует;
- `DELETE` не добавлен;
- golden write route не добавлен;
- verified pilot `M02-L01` не переопределён;
- unknown/unmanaged live content не усыновляется;
- Stepik write count для разработки и аудита PR #66: **0**.

## 4. Финальный CI

Проверенный code head: `250d63408c29f939ee3615d14fd748160b194c4b`.

GitHub Actions:

- workflow: `Stepik Uploader`;
- run: `34936015676`;
- tests job: `104273960510`;
- result: **SUCCESS**;
- unit tests: **152/152 OK**;
- structural dry-run: **SUCCESS**;
- owner live job: **SKIPPED**;
- post-merge impact job: **SKIPPED** на PR, как и должно быть.

Dry-run остаётся fail-closed относительно live deployment и не открывает write route.

## 5. Residual risks — не блокируют merge

1. **Heuristic alignment для будущих изменений канона.** Среди структурно допустимых вариантов границы выбираются lexical/position score. Exact-score ambiguity уже fail-closed, marker ownership и Check boundaries жёсткие, текущий полный канон покрыт regressions. Однако будущая крупная правка source/plan теоретически может дать единственный, но семантически неидеальный максимум. Это требует того же CI + semantic review при изменении lesson/plan, а не ослабления текущих guards.
2. **`source_main_sha` в PR audit report.** В PR CI GitHub checkout работает на synthetic merge SHA. Для offline compiler report это диагностическое поле, а не deployment provenance. Live deployment evidence этим report не создаётся.
3. **Node deprecation warnings GitHub Actions.** Пинованные actions сейчас принудительно исполняются на Node 24 и дают предупреждения о Node 20. CI зелёный; это эксплуатационный maintenance item, не дефект compiler semantics.

## 6. Вердикт

- **OPEN CRITICAL:** 0
- **OPEN HIGH:** 0
- **OWNER DECISION REQUIRED BEFORE MERGE:** 0
- **STEP 2 SOURCE-COMPILER GATE:** PASS
- **BULK WRITE:** CLOSED
- **NEXT GATE:** `asset-publication-resolution`

PR допускается к merge при условии, что после этого audit-only commit кодовый diff не изменился относительно проверенного code head `250d63408c29f939ee3615d14fd748160b194c4b`.
