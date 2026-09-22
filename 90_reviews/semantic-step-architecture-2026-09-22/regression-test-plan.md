# Regression-test plan

Автоматические проверки ловят структурные регрессии. Они не могут определить, понял ли абсолютный новичок смысл шага и не заменяют ZERO-LEVEL/PEDAGOGUE audit.

## R01 — legacy parity during migration
До opt-in урока его normalized compiled HTML должен оставаться эквивалентным baseline текущего main.

## R02 — no synthetic universal frame in authored mode
В authored-semantic-v1 compiler не может самостоятельно вставить:
- Зачем;
- Где и с чем;
- Что сделать;
- Готово, если;
- Что сохранить;
- Что дальше.

Такая фраза допустима только если она реально authored в source и нужна текущей функции.

## R03 — no keyword save inference
Наличие слова «сохранить/сохранение» в body не создаёт отдельный save block.

## R04 — no location inference
URL, название сервиса, слово «чат», «Stepik», «файл» не определяют learner location автоматически.

## R05 — authored title
В authored mode каждый semantic span обязан иметь H2/H3. Title берётся только из первого authored heading. Отсутствие heading, пустой heading или production-ID-only heading = compile failure. Lesson-title/generated fallback запрещён.

## R05a — render marker and semantic type
Parser принимает exact marker `<!-- learner-render-contract: authored-semantic-v1 -->`. Для каждого row opt-in lesson обязателен `Semantic type` из 10 enum Semantic Step Contract; пропуск/неизвестное значение = failure. Type не может автоматически добавлять learner-facing секции.

## R06 — inline single-source
Один repo-relative learner Markdown source не встраивается более одного раза. Повторное обращение идёт по канонической HTTPS-ссылке.

## R07 — inline ordering fixtures
Для зарегистрированных regression cases обязательный inline material находится до completion своей функции. Отдельный fixture подтверждает обратное правило: post-action rubric F1 не может быть перемещена до independent action.

## R08 — check response
Free-answer fixtures имеют authored объяснение смысла ответа. Compiler не выдумывает его. Machine test проверяет наличие semantic marker/approved phrase only для адресных fixtures, не глобально.

## R09 — navigation integrity
После переразбиения:
- target lesson/step существует;
- номера/ссылки соответствуют compiled order;
- conditional return не ведёт в intro вместо нужной операции.

## R10 — author-only isolation
Author notes, A02/rubric и другие author-only sources не попадают в learner HTML до разрешённого момента.

## R11 — F1 temporal order
M07-L02:
- independent work и application предшествуют A03/public post-check;
- author A02 не появляется learner-facing;
- recovery не становится unconditional;
- M08 начинается только после завершённого F1 route.

## R12 — B8 actual edit
Структурный test не доказывает живой сервисный edit, но должен ловить source regression, где independent B8 описан только как новая генерация вместо изменения existing image.

## R13 — B10 real ground
Machine fixture проверяет, что M06-L04 independent route не содержит заранее названный правильный тип основания/статус и не заменяет external ground self-check ИИ.

## R14 — B12/F1 application
Registered source fixture требует явное actual-application state. Фразы о намерении не считаются completion marker.

## R15 — recovery states
Для M03-L02, M04-L02, M04-L03, M06-L04, M07-L02 fixtures различают:
- success;
- technical failure;
- contaminated practice;
- NOT PROVEN;
- incomplete.

Автотест проверяет наличие маршрутов/targets, но смысл их честности читает auditor.

## R16 — assets
Все required local assets:
- существуют;
- имеют ожидаемый MIME/extension;
- декодируются там, где это изображение;
- разрешаются verified renderer;
- не утекли из author-only layer.

Для M03-L02 Alice PNG отдельный decode regression обязателен.

## R17 — lesson inventory
После каждого batch:
- ожидаемое число lessons = 21;
- expected step count для затронутых уроков зафиксирован;
- если step count меняется, все changed IDs/URLs/links проходят reconciliation;
- незатронутые authored/legacy lessons не меняются неожиданно.

## R18 — compiler impact
B0 доказывает zero learner diff. B1–B6 отчётливо перечисляют lessons с learner diff. B7 подтверждает 21/21 authored mode и отсутствие legacy fallback.

## R19 — forbidden boilerplate scan
Heuristic scan может сигнализировать о:
- «готово, если всё понятно»;
- «сохраните то, что требуется ниже» без конкретного объекта;
- «вернитесь в Stepik» без фактического выхода;
- «выполните следующий шаг» без действия;
- duplicate frame labels.

Срабатывание — повод читать шаг, не автоматический verdict.

## R20 — semantic audit checklist

Для каждого изменённого final HTML модель/человек отвечает:

1. читать или действовать?
2. что требуется?
3. зачем это сейчас?
4. где работа?
5. какой объект?
6. какой наблюдаемый результат?
7. нужно ли сохранять?
8. что означает конец?
9. куда дальше?
10. не раскрыт ли проверяемый содержательный выбор?

Не каждый вопрос обязан иметь отдельный видимый блок.

## R21 — competence invariants
Batch-level report должен явно подтвердить:
- B0 остаётся level 2;
- B3 до передачи;
- B8 = real edit existing image;
- B10 = suitable real ground;
- B12 = actual application;
- M07-L02 = единственный F1;
- M07-L01 = rehearsal;
- M08 = reflection.

## R21a — final whole-course dual gate
B7 regression report обязан содержать отдельные coverage records ZERO-LEVEL 148/148 и PEDAGOGUE 148/148 по одному final compiled set. Batch-level PASS не засчитывается вместо final coverage.

## R22 — release gates remain open
Никакой unit/integration/model test не может автоматически записать PASS для HUMAN VISUAL, SERVICE, Human Pilot/HUMAN VALIDATION или Wave 0.
