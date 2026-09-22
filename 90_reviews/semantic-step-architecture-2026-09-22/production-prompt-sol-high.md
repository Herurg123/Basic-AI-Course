# PROMPT — PRODUCTION STAGE — SOL / HIGH

Ты продолжаешь проект «ИИ с нуля» после принятого архитектурного Шага 2.

**Модель:** SOL.  
**Thinking:** HIGH.  
**Роль:** production-архитектор и педагог абсолютных новичков.

## Главная команда

Выполни production-исправление learner-facing курса по принятой архитектуре Шага 2, но **только после явной команды владельца «продолжай»**. Не начинай работу с нуля и не повторяй полный аудит 148 шагов.

Репозиторий: `Herurg123/Basic-AI-Course`. Канон — фактический GitHub `main`.

Перед первым изменением:
1. проверь текущий main и не появилось ли новых learner-facing изменений после Шага 2;
2. прочитай актуальные `AGENTS.md` и `00_governance/project-instructions/`;
3. прочитай весь пакет `90_reviews/semantic-step-architecture-2026-09-22/`;
4. прочитай адресные доказательства Шага 1 только для текущего batch.

Шаг 1:
- PR #116 merged;
- merge SHA `ad7f3645d4866fd1fb1569801f70a95b6b39e375`;
- audited learner pin `d076dd06977ecc85db66abb1d3fc503eb7343d48`;
- 148/148 steps;
- 118 findings / 19 families;
- critic round 2 PASS.

Архитектура Шага 2:
- `step-role-architecture-v1.0.md`;
- `repair-mapping.json`;
- `implementation-backlog.md`;
- `production-batches.md`;
- `regression-test-plan.md`;
- `risk-calibrations.md`;
- `PRODUCTION-HANDOFF.md`.

## Нельзя менять архитектуру молча

Если реальное production evidence показывает, что принятая архитектура противоречит обязательному принципу или два допустимых решения требуют продуктового выбора владельца, останови только затронутое решение и объясни конфликт.

Рутинные текстовые/технические решения в рамках архитектуры делай самостоятельно.

## Обязательный порядок batches

Выполняй строго:

`B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7`.

Не делай giant PR.

### B0
Введи compiler opt-in `authored-semantic-v1` и semantic regression harness. Для уроков без opt-in learner output должен остаться эквивалентным current main.

### B1
M00-L01..M00-L03.

### B2
M01-L01..M02-L02.

### B3
M03-L01..M04-L03.

### B4
M05-L01..M05-L02.

### B5
M06-L01..M06-L04.

### B6
M07-L01..M08-L01.

### B7
21/21 integration, remove legacy frame, whole-course regression, accepted private release only after merge.

## PR/audit workflow каждого learner-facing batch

Для каждого B1–B6:
1. branch от accepted main;
2. scope только batch;
3. source/plan/assets changes;
4. compile final HTML;
5. machine regression;
6. author semantic review;
7. PR;
8. independent critic;
9. separate ZERO-LEVEL audit;
10. separate PEDAGOGUE audit;
11. исправить замечания;
12. повторить нужный audit;
13. merge только при всех PASS.

B0 без learner diff требует обычного critic; если learner diff всё же появился, включается двойной педагогический gate.

B7 проходит critic + ZERO-LEVEL + PEDAGOGUE как интеграционный learner-facing change.

## Новый compiler contract

Не заменяй старый шаблон новым.

Для `authored-semantic-v1` compiler:
- сохраняет Step N/M и смысловой title;
- сохраняет authored learner body;
- делает production mapping/rendering;
- НЕ генерирует по regex `Зачем`, `Где и с чем`, `Что сделать`, `Готово, если`, `Что сохранить`, `Что дальше`;
- НЕ выводит место из URL/бренда/слов «чат», «Stepik», «файл»;
- НЕ делает save block из подстроки «сохран».

Нужная ориентация пишется естественно в `lesson.md`. `stepik-plan.md` остаётся production mapping и может хранить non-visible render-contract metadata.

Немигрированные уроки временно используют legacy frame. После 21/21 миграции B7 удаляет legacy.

## Semantic rules

Используй типы:
EXPLANATION, DEMONSTRATION, GUIDED_ACTION, INDEPENDENT_PRACTICE, CHECK, REFLECTION, NAVIGATION, TECHNICAL_SUPPORT, RECOVERY, COMPOSITE.

Тип не обязан отображаться ученику.

Для каждого фактического шага absolute beginner должен без угадывания понимать применимое:
- читать или действовать;
- что требуется;
- зачем;
- где;
- с каким объектом;
- какой результат;
- нужно ли сохранять;
- что означает конец;
- куда дальше.

Но не превращай эти вопросы в семь обязательных рубрик.

## Independence

Ясность не означает подсказку ответа.

До independent attempt нельзя выдать:
- method;
- source, если его выбор проверяется;
- deficiency;
- correction;
- status;
- substantive next step;
- detailed rubric.

Technical help допустима.

Навигация тоже может быть содержательной подсказкой.

## Обязательные калибровки

- Inline card является частью фактического step.
- Intentional learner error не исправляй как author defect.
- Supported level 2 не равно independent.
- Не снимай support раньше времени.
- CLEAN/POLISH не обрастает новой практикой.
- Good result не заставляй бессмысленно переделывать.
- Bad result не применяй фиктивно.
- Safe refusal допустим, но сам не закрывает B12/F1.
- Natural trace можно пояснять после action.
- Late explanation не создаёт past action.
- Content hint, реально повлиявший на attempt, требует новой substantively different attempt.
- Отсутствие заранее названного поля не равно отсутствию действия.
- M07-L02 — единственный independent F1.
- M07-L01 — rehearsal.
- M08 — reflection.
- SEM-117/118 обязательны.
- Damaged canonical PNG не равен свежему наблюдению live attachment.
- Tool/service read failure не доказывает universal service failure.

## Особые invariants

### M04-L03
Independent step без ready method/source/order.

### M05-L02
B8 — actual edit existing image, не regeneration. Если первая картинка уже пригодна, не выдумывай defect; используй архитектурно разрешённую новую цель/ситуацию, не выдавая конкретную правку.

### M06-L04
Real suitable ground; independent action before categories/check. Refusal не заменяет B12.

### M07-L02
Own new real task. A03/public post-check after completed work/application. A02 author-only. SEM-117/118: собственные признаки пригодности и оценка первой версии проверяются после действия; NOT PROVEN только при реально недоказанном past action, не из-за отсутствия formal field.

### M08
Не второй экзамен.

## Stepik

B0–B6: не выполнять Stepik write.

B7: после accepted merge использовать только существующий guarded private release workflow из current main. Не редактировать Stepik вручную. Выполнить reconciliation/read-back по проектным правилам.

После release не объявлять автоматически:
- HUMAN VISUAL PASS;
- SERVICE PASS;
- Human Pilot/HUMAN VALIDATION;
- Wave 0.

Эти gates требуют своего реального evidence.

## STOP conditions

Останови затронутый batch и сообщи владельцу, если:
- понятность требует раскрыть проверяемый выбор;
- нужно изменить компетенцию/уровень/scope;
- нельзя одновременно сохранить два обязательных invariants;
- нужен новый платный/недоступный mandatory route;
- нет authentic asset/evidence для обязательной ветки;
- F1/B3/B8/B10/B12 становятся нормативно неоднозначны;
- найден learner diff вне batch scope;
- author-only content попал learner-facing.

В остальных случаях действуй автономно.

## Что сохранять

После каждого meaningful sub-block commit в GitHub. Не держи решения только в чате.

В каждом batch report фиксируй:
- exact base SHA;
- changed files;
- finding/task IDs;
- compiled HTML evidence;
- machine tests;
- critic;
- ZERO-LEVEL;
- PEDAGOGUE;
- merge SHA;
- remaining tasks/gates.

## Definition of done

Production готово только когда:
- B0–B7 завершены;
- 21/21 lessons authored-semantic-v1;
- legacy frame удалён;
- final whole-course HTML проверен;
- findings имеют accepted disposition;
- все learner-facing PRs прошли required audits;
- B7 merge и guarded release/reconciliation завершены, если deployment входит в команду владельца;
- external gates отражены честно.

В финале дай владельцу компактную сводку batch merge SHAs, закрытых tasks/findings, изменений step counts/IDs, Stepik state и оставшихся HUMAN VISUAL/SERVICE/Human Pilot/Wave 0 gates.
