# Private Stepik Staging Checklist — Human Pilot

**Цель:** подтвердить, что human pilot наблюдает реальный целевой UX, а не только Markdown-файлы или частично обновлённый live course.

## A. Идентификация сборки

- Staging course/link ID:
- Проверяемая GitHub production commit SHA:
- Issue #54 / machine-state snapshot reference:
- Дата сборки:
- Проверил:
- Статус: `READY / BLOCKED`

В GitHub не сохранять private access tokens или секретные invite links, если они дают нежелательный доступ.

## B. Эквивалентность canonical source ↔ live staging

Перед Wave 0 проверить:

- [ ] course остаётся private и имеет ожидаемый язык;
- [ ] exact source `main` SHA зафиксирован до проверки;
- [ ] Issue #54 и deployment evidence не содержат необъяснённого `PENDING` относительно предъявляемого staging SHA;
- [ ] присутствуют M00–M08 и все 21 canonical lessons в правильном порядке;
- [ ] learner-facing `lesson.md` перенесены без содержательных импровизаций;
- [ ] `stepik-plan.md` реализован настолько, насколько позволяет Stepik;
- [ ] machine/read-back evidence охватывает **весь проверяемый staging**, а не только отдельные migrated lessons;
- [ ] physical learner assets материализованы и фактически открываются/показываются;
- [ ] current canonical divergence для golden/read-only объектов либо устранена, либо staging не объявляется equivalent;
- [ ] author-only rubrics/recovery/answer material не видны участнику раньше разрешённого момента;
- [ ] F1 не превращён в пошаговый рецепт;
- [ ] M08 не превращён во второй экзамен;
- [ ] privacy warning появляется до соответствующего transfer action;
- [ ] рекомендательная последовательность и recovery wording соответствуют D-2026-09-12-STEPIK-FLOW.

`workflow=success` или успешная миграция ограниченного набора объектов **не** является all-course equivalence proof.

## C. Learner-facing UX и PED-07

На PHONE и COMPUTER проверить:

- [ ] вход в курс;
- [ ] открытие урока;
- [ ] переход между шагами;
- [ ] section/module order соответствует canonical sequence;
- [ ] learner-facing lesson/section titles не содержат internal `Mxx/Lxx` prefixes;
- [ ] body/link labels не показывают Asset/Exercise/Check ID или производственный жаргон;
- [ ] отображение длинного текста/таблиц/изображений;
- [ ] доступность внешних ссылок;
- [ ] отсутствие learner-visible author notes;
- [ ] понятность рекомендованной последовательности;
- [ ] возврат после открытия внешнего сервиса;
- [ ] сохранение прогресса после выхода/возврата;
- [ ] отсутствие обязательной функции Stepik, которая технически недоступна целевой среде.

Offline learner-ID regression = `SOURCE/MACHINE PASS`; этот раздел требует фактического `HUMAN VISUAL PASS` по предъявляемому staging.

## D. PED-01: реальный файловый маршрут

Отдельно на **COMPUTER** и **PHONE** пройти без скрытой содержательной помощи:

- [ ] получить учебный файл на устройство;
- [ ] найти его после получения;
- [ ] прикрепить/использовать в требуемом действии;
- [ ] сохранить результат/заметку;
- [ ] снова найти сохранённый результат;
- [ ] техническая помощь не раскрывала, что именно считать содержательным ответом.

Source existence памятки не является PASS этого раздела.

## E. Independent-attempt integrity / PED-02 / PED-04 / PED-05

Для каждого места, где temporal order важен:

- [ ] participant может выполнить действие до раскрытия ответа/rubric;
- [ ] learner-facing интерфейс не раскрывает содержательную подсказку автоматически;
- [ ] если платформенную блокировку обеспечить нельзя, текст честно предупреждает о последствиях раннего просмотра;
- [ ] предусмотренный recovery доступен после contamination, но не выдаётся заранее;
- [ ] observer может зафиксировать момент открытия learner-visible hint/check;
- [ ] M03 recovery остаётся содержательно отличной новой ситуацией, а не повтором знакомого кейса;
- [ ] до first trace requirement ученик понимает, зачем сохраняет решения;
- [ ] перед independent `M06-L04-E01` **не повторяются** точные категории PED-04; CRIT-C-01 не регрессировал;
- [ ] категории `внешнее основание не установлено / переданный материал / наблюдаемое использование поиска` появляются как обучение раньше и/или post-action check, но не как ранняя подсказка independent attempt.

## F. PED-06: две реальные interface branches

В фактически собранном M03-L02:

- [ ] ветка после работы в Алисе показывает реальный GigaChat asset;
- [ ] ветка после работы в GigaChat показывает реальный Alice asset;
- [ ] оба visual assets физически опубликованы и видимы/открываются;
- [ ] branch mapping не перепутан;
- [ ] второй аккаунт для сравнения не требуется;
- [ ] source filenames/наличие PNG не используются как единственное доказательство publication PASS.

## G. F1

- [ ] F1 learner view не содержит готовых задач как обязательный выбор;
- [ ] нет списка обязательных шагов решения;
- [ ] нет подсказки «что проверить» до самостоятельного решения;
- [ ] форма evidence не вынуждает раскрывать чувствительное содержимое;
- [ ] фактическое применение можно зафиксировать отдельно от chat answer;
- [ ] после content contamination возможно начать новую F1-задачу без ложного зачёта старой.

## H. Blockers

`BLOCKED`, если хотя бы одно:

- source SHA не зафиксирован или staging не доказанно соответствует ему;
- machine state показывает необъяснённый PENDING по предъявляемой версии;
- canonical и staging содержательно расходятся;
- physical asset не материализован/не виден;
- author-only material виден участнику до независимой попытки;
- CRIT-C-01 или иной early content cue возвращён;
- PED-06 branch publication не подтверждена;
- learner-facing UI показывает production ID/жаргон;
- F1 превращён платформой/формой в пошаговый маршрут;
- privacy-before-transfer невозможно соблюсти из-за sequencing;
- обязательное действие нельзя выполнить/зафиксировать в целевой среде;
- staging требует плату/VPN/иное запрещённое обязательное условие.

Все отклонения получают issue ID до Wave 0.

## I. Ready declaration

- [ ] Production `main` SHA зафиксирован.
- [ ] Canonical ↔ live equivalence PASS.
- [ ] Issue #54/PENDING reconciliation PASS для выбранного staging SHA.
- [ ] Physical assets/materialization PASS.
- [ ] PHONE smoke + PED-01 route PASS.
- [ ] COMPUTER smoke + PED-01 route PASS.
- [ ] PED-06 publication branches PASS.
- [ ] PED-07 learner-facing HUMAN VISUAL PASS.
- [ ] Independent-attempt integrity PASS.
- [ ] F1 integrity PASS.
- [ ] Нет open blocker.

Итог: `READY / BLOCKED`  
Проверивший:  
Дата:
