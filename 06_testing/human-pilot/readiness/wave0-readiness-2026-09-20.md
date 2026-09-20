# Wave 0 readiness — 20.09.2026

**Дата baseline:** 20 сентября 2026 года  
**Проверенный canonical source SHA:** `1faeec8a42f0870f2a14cf0306b47ef4011e4e6a` (`main`)  
**Stepik course:** `299189`  
**Stepik release evidence:** run `35496592132`, artifact `10601686217`, digest `sha256:4e46226f0cc09811013b12aa41cbe4d7f2dc7cd3f6ce663de8115b98e6095fa4`  
**Итоговый verdict:** **NOT READY / BLOCKED FOR FIRST HUMAN SESSION**  
**Human Pilot:** **NOT STARTED**  
**Human validation:** **NOT PERFORMED**

Этот record не заменяет исторические readiness-записи от 12.09 и 16.09.2026. Они остаются доказательством состояния курса на свои даты.

## 1. Что изменилось после baseline 16.09

Крупный технический blocker private staging закрыт.

После 16.09 проект:

- довёл guarded Stepik release до единого private write-path;
- собрал и синхронизировал все 21 canonical lessons курса M00–M08;
- материализовал и привязал требуемые learner-facing assets в production staging через подтверждённые write/read-back маршруты;
- закрыл course-page backlog;
- устранил GigaChat-auth категоричность в learner-facing тексте;
- в ходе owner QA обнаружил и исправил повторное inline-встраивание технических памяток;
- повторно синхронизировал затронутые уроки;
- завершил текущий private release на exact `main` SHA;
- получил `PENDING lessons = 0`, `course_page = null`, baselines `21/21`;
- сохранил immutable deployment history с read-back и machine-state commit для реально записанных объектов.

Следовательно, старые blockers «18 PENDING lessons», «course page PENDING» и «private Stepik staging не доказанно эквивалентен current main» больше не являются актуальными.

## 2. Правило доказательств

Статусы не взаимозаменяемы:

- `SOURCE PASS` — канонический исходник соответствует требованию;
- `MACHINE PASS` — автоматизированный read-back/verification доказал конкретное машинное состояние;
- `HUMAN VISUAL PASS` — человек проверил фактически видимый learner-facing интерфейс;
- `SERVICE PASS` — требуемое действие реально выполнено в актуальном сервисе;
- `HUMAN VALIDATION PASS` — реальный screened novice выполнил требуемое действие с допустимой самостоятельностью.

Текущий private release закрывает MACHINE-слой, но не превращает его автоматически в HUMAN VISUAL, SERVICE или HUMAN VALIDATION PASS.

## 3. Current private Stepik staging

### MACHINE PASS

Для course `299189` на source SHA `1faeec8a42f0870f2a14cf0306b47ef4011e4e6a` подтверждено:

- release запущен из current `main`;
- `confirm_write=true`;
- private-course/private-lesson guards прошли;
- все запланированные preflight-проверки прошли до первой записи;
- source/scope recheck перед write прошёл;
- последняя очередь из 6 PENDING lessons закрыта;
- `M00-L02`, `M00-L03`, `M05-L02`, `M07-L01`, `M07-L02` получили `APPLIED`;
- `M06-L04` получил `NOOP_CONFIRMED`;
- итоговый machine state: `PENDING lessons = 0`;
- `course_page = null`;
- baselines присутствуют для всех 21 canonical lessons;
- у всех 21 baseline есть Stepik lesson ID и confirmed step IDs;
- deployment history для реальных writes содержит intent → dispatch → completed → operation read-back → final read-back → machine-state committed;
- для `M06-L04` подтверждён корректный no-op без лишней внешней записи.

### HUMAN VISUAL PASS всё ещё не доказан

Owner QA до последнего release обнаружил реальный UX-дефект в M00-L02: одна техническая памятка физически повторялась в нескольких шагах. Дефект исправлен PR #110 и после этого staging был пересобран.

Поэтому предыдущее ручное прохождение полезно как QA evidence, но **не является финальным HUMAN VISUAL PASS текущей принятой версии**. После последнего release нужен новый фактический проход видимого Stepik UI.

## 4. Readiness gates

| # | Gate | Статус 20.09.2026 | Blocker Wave 0 | Что осталось |
|---:|---|---|:---:|---|
| 1 | Canonical architecture / learner source | **SOURCE PASS** | нет | Не менять learner-facing content без обычного branch → PR → audits → merge. |
| 2 | Current private Stepik staging | **MACHINE PASS** | нет | Сохранять course private/unpublished до завершения manual readiness. |
| 3 | Canonical ↔ live machine reconciliation | **MACHINE PASS / ZERO-PENDING** | нет | Повторять только после нового content-impact merge. |
| 4 | 21 lesson baselines / IDs | **MACHINE PASS 21/21** | нет | Regression only. |
| 5 | Physical asset materialization / binding | **MACHINE PASS / HUMAN VISUAL OPEN** | **да** | На финальном staging фактически открыть/увидеть learner assets, особенно PED-06 branches и длинные/визуальные материалы. |
| 6 | Section/module/order integrity | **MACHINE PASS / FINAL HUMAN VISUAL RECHECK OPEN** | **да** | PHONE + COMPUTER визуально проверить порядок, переходы и сохранение прогресса. |
| 7 | Learner-facing ID hygiene / PED-07 | **SOURCE/MACHINE PASS / HUMAN VISUAL OPEN** | **да** | На текущем Stepik UI пройти learner titles/body/link labels и убедиться, что нет production IDs/жаргона. |
| 8 | PED-01 COMPUTER route | **NOT PERFORMED ON ACCEPTED VERSION** | **да** | Получить файл → найти → прикрепить/использовать → сохранить результат → снова найти. |
| 9 | PED-01 PHONE route | **NOT PERFORMED ON ACCEPTED VERSION** | **да** | Тот же полный маршрут на реальном телефоне. |
| 10 | PED-02 recovery distinction | **SOURCE PASS / LIVE SEQUENCING RECHECK OPEN** | **да** | В Stepik проверить, что recovery не раскрыт заранее и остаётся содержательно новой ситуацией. |
| 11 | PED-03 live image generation + real edit | **SERVICE PASS ABSENT** | **да** | Свежий бесплатный PRIMARY/BACKUP preflight: реальная генерация + реальный edit existing image. |
| 12 | PED-04 CRIT-C-01 / independent sequencing | **SOURCE PASS / LIVE RECHECK OPEN** | **да** | В M06-L04 проверить фактический порядок: E01 до post-action categories/check. |
| 13 | PED-05 trace rationale/order | **SOURCE PASS / LIVE RECHECK OPEN** | **да** | Проверить, что объяснение смысла сохранения решений появляется до требования вести trace. |
| 14 | PED-06 publication branches | **MACHINE ASSET PASS / HUMAN VISUAL OPEN** | **да** | Проверить обе M03-L02 branches: правильный другой интерфейс, видимость/кликабельность, без второго аккаунта. |
| 15 | F1 integrity | **SOURCE/MACHINE PASS / LIVE RECHECK OPEN** | **да** | Убедиться, что финальный learner view не превращает F1 в рецепт и не раскрывает проверки заранее. |
| 16 | Author-only/recovery leakage | **SOURCE/OFFLINE PASS / LIVE RECHECK OPEN** | **да** | Проверить текущий learner UI: author notes/rubrics/recovery не видны раньше допустимого момента. |
| 17 | Consent/data-minimization operational setup | **DOCUMENTED / NOT INSTANTIATED** | **да** | До Wave 0 выбрать реальные storage/retention правила, aliases и consent-before-collection процедуру. |
| 18 | Moderator rehearsal N/P/T/C/S | **NOT PERFORMED** | **да** | Провести rehearsal без участника и зафиксировать результат. |
| 19 | Current service preflight | **NOT PERFORMED AFTER ACCEPTED STAGING** | **да** | Пройти service-preflight checklist на текущих бесплатных routes. |
| 20 | Two eligible Wave 0 participants | **NOT YET ELIGIBILITY-CONFIRMED** | **да** | Отбирать только после закрытия остальных readiness blockers. |

## 5. PED-01…PED-07 matrix

| PED | Source/machine state | Обязательный реальный gate | Verdict |
|---|---|---|---|
| PED-01 | source готов; final Stepik собран | COMPUTER + PHONE полный файловый маршрут | **BLOCKED** |
| PED-02 | recovery source остаётся отдельной ситуацией | live sequencing / no early disclosure | **OPEN HUMAN VISUAL** |
| PED-03 | learner route готов | current free live generation + actual edit | **BLOCKED SERVICE** |
| PED-04 | M06-L04 source не выдаёт точные категории перед E01 | final Stepik sequencing | **OPEN HUMAN VISUAL** |
| PED-05 | rationale-before-trace сохранён в source | final Stepik sequencing | **OPEN HUMAN VISUAL** |
| PED-06 | assets материализованы machine-side | обе фактические interface branches | **BLOCKED HUMAN VISUAL** |
| PED-07 | source/render hygiene + regression PASS | final PHONE + COMPUTER learner UI | **BLOCKED HUMAN VISUAL** |

## 6. Что уже НЕ нужно повторять перед следующим ручным шагом

Без нового content-impact merge не нужно:

- снова запускать Stepik Private Course Release;
- повторно закрывать Issue #54;
- создавать новый baseline для тех же lesson fingerprints;
- повторять materialization только ради факта materialization;
- вручную редактировать Stepik;
- считать старые 18 PENDING актуальными.

Новый write-run нужен только если следующий QA найдёт дефект, дефект будет исправлен в canonical source и post-merge impact снова создаст PENDING.

## 7. Оставшиеся blockers до первой human session

До Wave 0 нужно закрыть пять групп реального evidence:

1. **Final Stepik HUMAN VISUAL / device pass**: COMPUTER smoke, PHONE smoke, PED-01 на обоих устройствах, PED-06 обе ветки, PED-07 learner-facing UI, author-only/recovery/independence/F1 sequencing.
2. **Current SERVICE PASS**: базовый текстовый маршрут, upload безопасного материала, B7 live image generation, B8 real edit existing image, сохранение/скачивание там, где это требуется, PRIMARY/BACKUP с реальными текущими account conditions.
3. **Operational privacy/data setup**: session aliases, раздельное хранение contact mapping и pilot evidence, конкретные retention/delete rules для контактных данных и recordings, если recordings вообще будут, consent до сбора evidence.
4. **Moderator rehearsal**: N/P/T/C/S, stuck protocol, contamination, recovery, safety stop, F1 boundaries.
5. **Recruitment**: только после закрытия предыдущих групп выбрать 2 eligible screened novice для Wave 0.

## 8. Что считать следующим правильным действием

Следующий шаг проекта — **не новый Stepik write**.

Нужно пройти текущий private staging как владелец/QA на COMPUTER и PHONE по существующему `stepik-staging-checklist.md`, параллельно выполнить свежий `service-preflight-checklist.md`.

Owner QA не заменяет screened novice Human Pilot, но закрывает обязательные HUMAN VISUAL / device / service readiness gates и может выявить дефекты до того, как их увидят участники.

Если в этом проходе найден learner-facing дефект:

1. зафиксировать finding;
2. исправить canonical source через обычный GitHub workflow;
3. выполнить обязательные audits;
4. merge;
5. выполнить новый Stepik release только для образовавшегося PENDING;
6. повторить затронутый HUMAN VISUAL/service gate.

## 9. Verdict

**NOT READY / BLOCKED FOR FIRST HUMAN SESSION.**

Причина больше не в production automation и не в необъяснённом Stepik state.

Текущие blockers являются реальными pre-human gates: device/HUMAN VISUAL, current service actions, operational privacy setup, moderator rehearsal и затем recruitment.

Human Pilot остаётся **NOT STARTED**, Human Validation — **NOT PERFORMED**.
