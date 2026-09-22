# PRODUCTION HANDOFF — SOL / HIGH

## 0. Назначение

Следующий этап — production-исправление learner-facing курса по принятой архитектуре Шага 2.

Этот handoff **не является командой начать production сейчас**. Он используется только после явной команды владельца «продолжай» после завершения и merge Шага 2.

## 1. Канон и pins

Репозиторий: `Herurg123/Basic-AI-Course`.

Перед началом production обязательно проверить фактический `main`, актуальные:
- `AGENTS.md`;
- `00_governance/project-instructions/`;
- manifest;
- Semantic Step Contract;
- Lesson Standard.

Шаг 1:
- PR #116 merged;
- merge SHA `ad7f3645d4866fd1fb1569801f70a95b6b39e375`;
- learner source pin диагностики `d076dd06977ecc85db66abb1d3fc503eb7343d48`;
- critic round 2 PASS.

Принятая диагностика:
- 9 modules;
- 21 lessons;
- 148 learner-facing steps;
- 0 CRITICAL;
- 38 BLOCKING;
- 87 MAJOR;
- 19 POLISH;
- 4 CLEAN;
- 118 findings;
- 19 families.

Шаг 2 package после merge находится в:
`90_reviews/semantic-step-architecture-2026-09-22/`.

## 2. Что прочитать до production

Полностью:
1. `90_reviews/semantic-step-architecture-2026-09-22/README.md`;
2. `step-role-architecture-v1.0.md`;
3. `repair-mapping.json`;
4. `implementation-backlog.md`;
5. `production-batches.md`;
6. `regression-test-plan.md`;
7. `risk-calibrations.md`;
8. этот handoff;
9. `production-prompt-sol-high.md`.

Из Шага 1 использовать адресно:
- `90_reviews/semantic-step-audit-2026-09-20/findings.json`;
- `step-inventory.json`;
- `reviews/*.json`;
- `rendered/*.json`;
- `cross-course-patterns.md`;
- `critic-round2.md`.

Не перечитывать все исходные 148 HTML без причины. Для изменяемого batch читать полный контекст всех затронутых steps/lessons и их зависимости.

## 3. Обязательная производственная последовательность

Выполнять только:

`B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7`.

### B0
Compiler opt-in + regression harness, zero learner diff.

### B1
M00-L01..L03.

### B2
M01-L01..L02 + M02-L01..L02.

### B3
M03-L01..L02 + M04-L01..L03.

### B4
M05-L01..L02.

### B5
M06-L01..L04.

### B6
M07-L01..L02 + M08-L01.

### B7
Whole-course integration, remove legacy, guarded private release from accepted main.

Не объединять все learner edits в один giant PR.

## 4. Branch / PR discipline

Для каждого batch:
1. начать от актуального accepted main предыдущего batch;
2. создать отдельную branch;
3. внести только scope batch;
4. собрать final learner HTML;
5. machine regression;
6. авторская semantic check;
7. открыть PR;
8. запустить обычного independent critic;
9. отдельно ZERO-LEVEL audit;
10. отдельно PEDAGOGUE audit;
11. исправить обычные замечания самостоятельно;
12. повторить провалившийся audit;
13. merge только когда все применимые gates PASS.

Не просить владельца подтверждать рутинные исправления.

## 5. Compiler migration

Текущий root cause — universal frame в `general_content.py`.

Production не заменяет его новым универсальным шаблоном.

B0 вводит `authored-semantic-v1` opt-in:
- exact marker: `<!-- learner-render-contract: authored-semantic-v1 -->` в `stepik-plan.md`;
- каждый opt-in row получает non-visible колонку `Semantic type` с одним из 10 enum Semantic Step Contract;
- unmigrated lesson сохраняет legacy output;
- migrated lesson получает minimal deterministic framing;
- title берётся только из первого authored H2/H3 semantic span; отсутствие heading = compile error;
- purpose/place/action/completion/save/navigation не генерируются по regex;
- semantic type используется для validation, но не становится visible heading и не генерирует learner sentences.

При миграции lesson:
- source содержит нужный learner meaning;
- plan содержит production mapping;
- final HTML проверяется как фактический шаг.

После 21/21 migration B7 удаляет legacy path.

## 6. Layer rules

### lesson.md
Источник learner-facing смысла, порядка, помощи, условий, естественных переходов.

### stepik-plan.md
Production mapping, block types, author-only, render-contract metadata. Не скрывает необходимое ученику объяснение.

### learner assets
Только то, что ученик реально должен видеть/использовать. Author-only rubric/key не публикуется.

### compiler
Детерминированная сборка, не педагогический автор.

### verified renderer
Dependency/materialization/HTML transport, не semantic repair.

## 7. Independence protections

Особенно M03–M07.

До independent attempt нельзя выдавать проверяемый:
- method;
- source;
- deficiency;
- correction;
- status;
- content next step;
- detailed rubric.

Technical help допустима.

Навигация не автоматически нейтральна: ссылка на конкретный source/tool может раскрыть ответ.

## 8. Fixed calibrations

Сохранить без пересмотра:
- inline card = часть фактического шага;
- intentional learner error ≠ author defect;
- supported level 2 ≠ independent;
- support не снимать раньше;
- CLEAN/POLISH не обрастают практикой;
- good result не надо бессмысленно переделывать;
- bad result нельзя фиктивно применять;
- safe refusal допустим, но сам не закрывает B12/F1;
- natural trace можно пояснять после действия;
- late explanation не создаёт past action;
- content hint, реально повлиявший на attempt, требует новой substantively different attempt;
- отсутствие заранее предусмотренного поля ≠ отсутствие действия;
- M07-L02 — единственный F1;
- M07-L01 — rehearsal;
- M08 — reflection;
- SEM-117/118 обязательны;
- damaged canonical PNG ≠ fresh observation published version;
- tool failure ≠ universal service failure.

## 9. Special cases

### M04-L03
Independent check без ready method/source/order.

### M05-L02
B8 = actual edit existing image. Already-good image не заставляет выдумывать defect; новая ситуация может создать реальную цель изменения, не выдавая конкретную correction.

### M06-L04
Real suitable ground. Categories/check after own action. Safe refusal не заменяет application.

### M07-L02
Own new real task. A03/post-check only after work/application. A02 author-only. SEM-117/118 preserved.

### M08
No second exam.

## 10. Stepik policy during batches

B0–B6: no Stepik write.

Причина: shared compiler migration может создавать global impact; live private course не должен становиться смешанным migration-state.

B7 после final merge:
- use only existing guarded release workflow;
- current main only;
- no manual Stepik editing;
- reconcile read-back;
- then perform required HUMAN VISUAL/device/service gates.

Не объявлять их PASS заранее.

## 11. STOP conditions

Stop affected batch and report owner only if:
- clarity requires leaking tested substantive choice;
- two valid solutions require changing product/competence;
- required competence/level cannot be preserved;
- new paid/unavailable mandatory route is required;
- authentic evidence/asset cannot be obtained;
- F1/B3/B8/B10/B12 normative behavior becomes ambiguous;
- learner diff appears outside batch scope;
- author-only content leaks;
- architecture itself must be changed.

Обычный редакторский выбор не является STOP.

## 12. Definition of done production

Production stage не завершён, пока:
- B0–B7 PASS;
- 21/21 lessons authored-semantic-v1;
- 100% final plan rows (N/N; исходный baseline = 148) имеют валидный `Semantic type`;
- legacy universal frame removed;
- final whole-course HTML compiled;
- all relevant findings have disposition and acceptance evidence;
- каждый learner-content PR прошёл critic + scoped ZERO-LEVEL + scoped PEDAGOGUE;
- B7 отдельно прошёл ordinary critic + **full ZERO-LEVEL N/N final inventory** + **full PEDAGOGUE N/N final inventory** по final compiled HTML;
- final guarded private release reconciled if production command includes deployment;
- open HUMAN VISUAL/SERVICE/Human Pilot/Wave 0 states reported honestly.

## 13. Финальный отчёт production

Выдать владельцу:
- merged SHAs batch PRs;
- task/finding closure table;
- final counts/dispositions;
- changed step counts/IDs where applicable;
- Stepik release/reconciliation state;
- unresolved external gates;
- explicit statement that Human Pilot/Wave 0 are not closed unless actually performed.
