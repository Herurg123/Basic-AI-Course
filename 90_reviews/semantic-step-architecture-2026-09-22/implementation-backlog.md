# Implementation backlog

Шаг 2 проектирует 22 production tasks: INF-01/02, 19 family tasks из repair-mapping.json и DOC-01.

## Инфраструктура

### INF-01 — authored-semantic-v1
Добавить opt-in режим compiler. Точный marker в `stepik-plan.md`: `<!-- learner-render-contract: authored-semantic-v1 -->`. Урок без marker сохраняет прежний нормализованный HTML.

Для opt-in lesson каждый plan row обязан иметь колонку `Semantic type` с одним из 10 enum Semantic Step Contract. Новый режим берёт title только из первого authored H2/H3 своего semantic span; отсутствие heading или semantic type = compile error. Никаких lesson-title/generated fallback.

Новый режим оставляет только нумерацию/смысловой authored title и body; педагогические рубрики по текстовым эвристикам не генерируются.

Acceptance: до миграции уроков все 21 legacy outputs эквивалентны текущим; malformed/missing marker metadata fixtures fail deterministically.

### INF-02 — semantic regression harness
Добавить fixtures и проверки:
- authored mode не добавляет universal frame;
- save/location/completion не выводятся из слов/URL;
- inline-source не дублируется;
- completion не опережает обязательный inline material в известных fixtures;
- author-only не попадает ученику;
- F1/independence invariants проверяются там, где это возможно структурно.

Автотест не заменяет смысловое чтение.

## 19 family tasks

### ARCH-01 — UNIVERSAL_FRAME
21 урок / 133 шага. Переводить урок в authored mode только после source review. Никаких пустых обязательных рубрик.

### ARCH-02 — CHUNK_BOUNDARY
19 уроков / 63 шага. Собирать в одной функции условие, действие, объект, нужный material и completion. Post-action rubric не переносить раньше.

### ARCH-03 — FRAME_LOCATION_FROM_WORDS
17 уроков / 53 шага. Удалить inference места; писать место/объект только по фактической операции.

### ARCH-04 — SUPPORT_AT_END
15 уроков / 40 шагов. Помощь доступна до/в точке сбоя и возвращает к прерванному действию.

### ARCH-05 — INLINE_AT_END
15 уроков / 29 шагов. Inline material находится до completion своей функции; post-action формы остаются после самостоятельной работы.

### ARCH-06 — RECOVERY_ELIGIBILITY
M03-L02, M04-L02, M04-L03, M06-L04, M07-L02. Различить подтверждённый trace, поясняемый trace, NOT PROVEN, тренировочную попытку и незавершённую работу. Новая задача только когда это действительно нужно.

### ARCH-07 — LIVE_OUTPUT_COMPLETION
M02-L02, M04-L03, M05-L02. Хороший первый результат не требует фиктивной правки; плохой не применяется; completion определяется реальной задачей.

### ARCH-08 — NAVIGATION_TARGET
M03-L01, M06-L04, M07-L02. Возвраты ведут к фактической операции/check/application после окончательного переразбиения.

### ARCH-09 — UNDEFINED_CHECK_RESPONSE
M00-L02, M04-L02, M04-L03, M05-L02. Ясно указать короткий смысл ответа Stepik и что остаётся локальным.

### ARCH-10 — BACKUP_ROUTE_CONTEXT
M00-L02, M05-L02. Backup продолжает реальную операцию из корректного состояния, а не копирует основной маршрут механически.

### ARCH-11 — INLINE_NAVIGATION_CONFLICT
M00-L03. Один материал предъявляется одним согласованным способом: inline либо переход к каноническому экземпляру.

### ARCH-12 — INLINE_SCOPE_SPILL
M02-L01, M02-L02, M06-L03. Разделить/переставить слишком широкий learner asset так, чтобы он не раскрывал будущую фазу.

### TECH-01 — UNTAUGHT_CHAT_OPERATION
M00-L01/M00-L03. Новый/чистый диалог объясняется один раз перед первой потребностью; позже достаточно короткого напоминания.

### LOCAL-01 — ABSENCE_OF_EVIDENCE_ROUTE
M01-L02. Отсутствие относящегося основания — допустимый исход с понятным статусом и безопасным продолжением.

### LOCAL-02 — CHOICE_VS_WORDING
M02-L02. Проверять содержательный выбор, а не косметическую новизну формулировки.

### ASSET-01 — ASSET_INTEGRITY
M03-L02. Заменить повреждённый canonical PNG Алисы подлинным допустимым снимком; затем отдельно проверить materialization и HUMAN VISUAL.

### LOCAL-03 — INDEPENDENT_METHOD_RECIPE
M04-L03. Independent step не содержит готовый метод/основание/порядок; technical help остаётся допустимой.

### LOCAL-04 — RECOVERY_DISCLOSURE
M05-L02. В recovery сначала новый исходник/назначение и собственный выбор, затем только допустимая ограничивающая помощь и возврат к check.

### F1-01 — INCOMPLETE_CHECK_COVERAGE
M07-L02. После работы проверить смысл собственных критериев пригодности до оценки и собственной оценки первой версии по natural trace. Не показывать полную рубрику до E01.

## Финализация

### DOC-01 — remove legacy
Только после миграции всех 21 уроков:
- убрать legacy frame и мёртвые эвристики;
- обновить GENERAL-COMPILER.md;
- подтвердить 21/21 authored-semantic-v1;
- выполнить whole-course compile/regression и интеграционные аудиты.

## Общие ограничения

Нельзя менять состав компетенций, превращать POLISH/CLEAN в новую практику, переносить independent checks, заменять B8 новой генерацией, B10 самопроверкой ИИ или B12/F1 намерением вместо реального применения. Модельный аудит не закрывает HUMAN VISUAL, SERVICE, Human Pilot или Wave 0.
