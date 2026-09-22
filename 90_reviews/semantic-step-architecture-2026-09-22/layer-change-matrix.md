# Layer-change matrix

Это классификация **будущих** production changes. На Шаге 2 перечисленные learner/production файлы не изменяются.

| Family / task | Renderer/compiler | lesson.md | stepik-plan.md | learner asset | Класс решения |
|---|:---:|:---:|:---:|:---:|---|
| UNIVERSAL_FRAME / ARCH-01 | **да** | **да** | **да** | по зависимости | системное + миграция 21 урока |
| CHUNK_BOUNDARY / ARCH-02 | validation | **да** | **да** | иногда | системное правило, адресные границы |
| FRAME_LOCATION_FROM_WORDS / ARCH-03 | **да** | **да** | иногда | нет | systemic inference removal + source |
| SUPPORT_AT_END / ARCH-04 | нет | **да** | **да** | support asset по необходимости | cross-course source pattern |
| INLINE_AT_END / ARCH-05 | нет | **да** | **да** | иногда | source/order |
| RECOVERY_ELIGIBILITY / ARCH-06 | нет | **да** | **да** | иногда | independence-sensitive source/plan |
| LIVE_OUTPUT_COMPLETION / ARCH-07 | нет | **да** | **да** | нет | local semantic branches |
| NAVIGATION_TARGET / ARCH-08 | test only | **да** | **да** | нет | local transitions + regression |
| UNDEFINED_CHECK_RESPONSE / ARCH-09 | нет | **да** | **да** | нет | local learner wording + plan |
| BACKUP_ROUTE_CONTEXT / ARCH-10 | нет | **да** | **да** | support link only | service-route wording |
| INLINE_NAVIGATION_CONFLICT / ARCH-11 | нет | **да** | **да** | existing source | local M00-L03 |
| INLINE_SCOPE_SPILL / ARCH-12 | inline contract unchanged | **да** | **да** | **да/разделение возможно** | scoped asset/source |
| UNTAUGHT_CHAT_OPERATION / TECH-01 | нет | **да** | иногда | support asset возможно | first-use technical support |
| ABSENCE_OF_EVIDENCE_ROUTE / LOCAL-01 | нет | **да** | **да** | нет | local M01-L02 |
| CHOICE_VS_WORDING / LOCAL-02 | нет | **да** | **да** | нет | local M02-L02 |
| ASSET_INTEGRITY / ASSET-01 | materialization validation | link/source only if path changes | publication mapping if needed | **да** | binary repair + later visual gate |
| INDEPENDENT_METHOD_RECIPE / LOCAL-03 | нет | **да** | **да** | post-action asset timing only | local M04-L03 |
| RECOVERY_DISCLOSURE / LOCAL-04 | нет | **да** | **да** | возможно | local M05-L02 |
| INCOMPLETE_CHECK_COVERAGE / F1-01 | no semantic generation | **да** | **да** | **A03** | local F1 post-check |

## Renderer/compiler must change

Только две смысловые причины требуют общей compiler architecture:

1. **UNIVERSAL_FRAME** — authored-semantic-v1 вместо heuristic frame.
2. **FRAME_LOCATION_FROM_WORDS** — убрать location inference в новом mode.

CHUNK_BOUNDARY требует compiler validation/explicit span support, но конкретные границы задаются source/plan. Compiler не должен выбирать педагогически «правильную» границу сам.

Inline-source renderer contract сохраняется: repo-relative learner Markdown встраивается один раз; проблема order/scope исправляется source/assets.

## Source must change

Адресные learner changes ожидаются во всех lessons, где есть MAJOR/BLOCKING findings. UNIVERSAL_FRAME migration затрагивает все 21 урока, но CLEAN/POLISH steps меняются только настолько, насколько нужно убрать legacy frame и сохранить их текущую функцию.

Полный exact step scope находится в `repair-mapping.json`.

## Stepik plan must change

Plan меняется, когда нужно:
- включить exact lesson marker `<!-- learner-render-contract: authored-semantic-v1 -->`;
- заполнить у каждого opt-in row отдельную колонку `Semantic type` одним из 10 enum Semantic Step Contract;
- исправить semantic span/row boundaries;
- согласовать block type/free-answer;
- зафиксировать recovery/check route;
- обновить material/action mapping.

Plan не становится скрытым learner explanation. `Semantic type` используется для validation/audit и не генерирует learner sentences.

## Assets must change

Обязательные asset-level candidates:

- **M03-L02 Alice PNG** — ASSET-01, confirmed corrupted canonical binary;
- **M02-L01 / M02-L02 / M06-L03** — INLINE_SCOPE_SPILL может потребовать splitting learner Markdown asset, если source relocation не решает scope;
- **M05-L02** — recovery assets могут потребовать rearrangement/splitting без раскрытия correction;
- **M07-L02 A03** — F1-01 требует post-action coverage SEM-117, не раннюю rubric.

Asset change не означает автоматически новый Asset ID; сначала сохранять existing identity, если content contract позволяет и project rules не требуют нового ID.

## Где достаточно локального текста

После systemic compiler capability локальным source/plan изменением должны закрываться:

- LOCAL-01 M01-L02;
- LOCAL-02 M02-L02;
- LOCAL-03 M04-L03;
- большая часть LIVE_OUTPUT_COMPLETION;
- NAVIGATION_TARGET;
- UNDEFINED_CHECK_RESPONSE;
- BACKUP_ROUTE_CONTEXT;
- TECH-01, если существующей support asset достаточно.

Эти задачи нельзя расширять на весь курс без evidence.

## Где нужно системное решение

Обязательно системные:

- authored semantic framing migration;
- regression harness;
- semantic boundary validation;
- single-source inline contract regression;
- no location/save/completion inference;
- final removal legacy after 21/21 migration.

## Где нужен внешний gate, а не текст

Текст/код не может закрыть:
- current SERVICE availability;
- actual B7/B8 service behavior;
- HUMAN VISUAL на current Stepik;
- phone/computer device route;
- Human Pilot/HUMAN VALIDATION;
- Wave 0.

ASSET-01 требует после release отдельного visual evidence опубликованного изображения.
