# Synthetic pre-pilot M07–M08 — 2026-09-12

**Статус:** `SIMULATED / MODEL-BASED — NOT HUMAN PILOT`  
**Human validation:** `NOT PERFORMED`.

## 1. Цель

Adversarial-проверка production M07-L01, M07-L02 и M08-L01 до независимого аудита. Симуляция ищет false PASS, hidden scaffold, ослабление B12, high-stakes leakage и превращение M08 в новый gate или upsell.

Она не доказывает понятность, длительность, workload или успешность курса на реальных новичках.

## 2. Сценарии абсолютных новичков

| Профиль | Атака | Ожидаемая реакция production | Результат |
|---|---|---|---|
| Просит готовый план финала | «Скажите по шагам» | только техническая помощь; содержательный план загрязняет attempt и требует другую own task | PASS |
| Выбрал слишком большую задачу | большой проект вместо малой задачи | до старта проверяется только посильность; задача отклоняется без проектирования маршрута | PASS |
| Выбрал слишком простую задачу | нет наблюдаемого завершения | пустая демонстрация не закрывает F1; нужны completion + application | PASS |
| Идёт по чек-листу всех функций | форсирует file/image/search/calculator | lesson/A01 запрещают лишнее; отсутствие опциональных действий не снижает F1 | PASS |
| Не хочет реального применения | «ответ готов» | actual B12 обязателен; намерение или чат = NOT COMPLETED | PASS |
| Выбрал risky/high-stakes | реальное медицинское/юридическое/финансовое решение | задача отклоняется по допустимости; safe workflow внутри неё не проектируется | PASS |
| Поиск не нужен | собственная текстовая задача без существенного внешнего факта | search/B10 не навязываются | PASS |
| Картинка не нужна | текстовая задача | B7/B8 не навязываются | PASS |
| Правильно остановился после плохой версии | безопасный отказ | решение корректно, но F1 остаётся NOT COMPLETED до завершения и применения | PASS |
| Считает M08 новым экзаменом | пытается «сдать следующий уровень» | lesson прямо говорит, что база уже завершена; M08 только REUSE/reflection | PASS |

## 3. False-PASS probes M07-L01

- A02 прочитана сверху вниз: не образует последовательность и разрешает неприменимость пунктов. `PASS`.
- A01 решена без file/search/image/calculator: допустимо. `PASS`.
- E02: новая информация дана без названия нужного приёма. `PASS`.
- Финальный результат остался в чате: C01 должен отклонить. `PASS`.
- Урок объявлен финальным F1: learner text явно говорит обратное. `PASS`.

## 4. False-PASS probes M07-L02

- Ready-made exam case: отсутствует; A01 даёт только классы. `PASS`.
- Rubric leaks workflow: A02 author-only и outcome/evidence-based. `PASS`.
- Evidence form leaks workflow: A03 post-action; порядок полей прямо объявлен непроцедурным. `PASS`.
- Content hint ignored: author-notes переводят attempt в PRACTICE и требуют другую own new task. `PASS`.
- Retroactive explanation: A02/author-notes требуют pre-rubric trace. `PASS`.
- Unfinished task with good refusal: `NOT COMPLETED`. `PASS`.
- «Я бы применил»: fail actual B12. `PASS`.
- Significant unchecked fact applied: critical fail. `PASS`.
- Forced file/search/image/second service: запрещено. `PASS`.
- High-stakes final: отклоняется до начала. `PASS`.
- New competency inside F1: не обнаружена. `PASS`.

## 5. M08 probes

- Новый competency gate: отсутствует. `PASS`.
- Второй экзамен: learner-facing текст отрицает. `PASS`.
- Покупка/регистрация как завершение: отсутствуют. `PASS`.
- «Следующий уровень = бренд/модель»: прямо запрещено. `PASS`.
- База обесценена: нет, база объявлена завершённой. `PASS`.
- Итог «мне достаточно практики базы»: явно разрешён. `PASS`.

## 6. Lesson Gate model walkthrough

### M07-L01
- G1: наблюдается интеграция и application, не красота выдачи. `PASS`.
- G2: только ранее освоенные действия; новых prerequisites нет. `PASS`.
- G3: практика начинается сразу; support level 2; E02 требует собственного выбора. `PASS`.
- G4: фиктивные данные; проверка существенного только по потребности. `PASS`.
- G5: сервис не является навыком; второй сервис не навязан. `PASS`.
- G6: E01/E02/C01 и A01/A02 стабильны; Stepik не раскрывает workflow. `PASS`.

### M07-L02
- G1: F1 подтверждается process evidence + completion + B12. `PASS`.
- G2: prerequisites уже закрыты до F1; новых технических зависимостей нет. `PASS`.
- G3: own new task, only technical help; contamination recovery определён. `PASS`.
- G4: privacy before transfer; high-stakes excluded; real basis сохраняется. `PASS`.
- G5: PRIMARY/BACKUP наследуются; optional tools не форсируются. `PASS`.
- G6: E01/C01/A01–A03 существуют; false PASS и Stepik advisory определены. `PASS`.

### M08-L01
- G1: REUSE/reflection наблюдается, нового экзамена нет. `PASS`.
- G2: F1 prerequisite; новые сервисы или навыки не требуются. `PASS`.
- G3: ранняя активность; осмысленный перенос. `PASS`.
- G4: нового рискованного действия нет; high-stakes распознаётся как граница. `PASS`.
- G5: next level определяется задачей, не брендом. `PASS`.
- G6: E01/E02/C01/A01 стабильны; Stepik прост. `PASS`.

## 7. Pilot-critical hypotheses

### M07-L01
- не слишком ли A02 абстрактна;
- не читают ли её как скрытый рецепт;
- понимает ли новичок, что не обязан использовать все изученные действия.

### M07-L02
- способен ли абсолютный новичок выбрать посильную own task;
- не слишком ли широк выбор;
- хватает ли safety-рамки без содержательной помощи;
- понимает ли ученик «задача завершена»;
- умеет ли показать actual application без чувствительных данных;
- сколько времени реально занимает F1;
- как часто требуется новая попытка после contamination или ошибки.

### M08
- различает ли ученик простую новую задачу и существенное усложнение;
- не воспринимает ли M08 как рекламу или второй экзамен;
- ощущается ли база завершённой до M08.

## 8. Verdict

`MODEL-BASED PASS — READY FOR INDEPENDENT AUDIT, NOT HUMAN-VALIDATED`.

Это не human pilot. Нельзя утверждать, что длительность, понятность, workload или реальная проходимость F1 новичками подтверждены.
