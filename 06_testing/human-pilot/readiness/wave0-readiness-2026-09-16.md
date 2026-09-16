# Wave 0 readiness — 16.09.2026

**Дата baseline:** 16 сентября 2026 года  
**Проверенный canonical source SHA:** `f16a20100e1933548d84c3706423764bb1e3d416` (`main` на начало reconciliation)  
**Stepik course:** `299189`  
**Итоговый verdict:** **NOT READY / BLOCKED FOR FIRST HUMAN SESSION**  
**Human Pilot:** **NOT STARTED**  
**Human validation:** **NOT PERFORMED**

Этот record не заменяет и не переписывает исторический [`wave0-readiness-2026-09-12.md`](wave0-readiness-2026-09-12.md). Документ от 12.09.2026 остаётся доказательством состояния на свою дату.

## 1. Правило статусов

В этом baseline статусы относятся только к реально доказанному слою:

- `SOURCE PASS` — канонические исходники соответствуют требованию;
- `MACHINE PASS` — автоматизированный read-back/verification доказал конкретное machine-состояние;
- `HUMAN VISUAL PASS` — человек проверил фактически видимый learner-facing интерфейс;
- `SERVICE PASS` — действие реально выполнено в актуальном сервисе на проверяемом маршруте;
- `HUMAN VALIDATION PASS` — действие выполнено реальным screened novice с допустимой самостоятельностью.

Эти статусы не взаимозаменяемы. `workflow=success` не означает автоматически `WAVE 0 READY`.

## 2. Снимок production Stepik, на котором основан verdict

### Что доказано

- Курс `299189` доказан как private/ru в production evidence и текущем `golden-profile.v1.json`.
- Section-position incident #74 восстановлен production run `35015060946`: итоговые section positions `1..9`, затронуты только `section.position`, content invariant подтверждён.
- Learner-hygiene partial-write incident #80 восстановлен без blind retry; M02-L01 получил confirmed baseline production run `35078545526`.
- M04-L01 learner-hygiene write production run `35079859897` завершён с final fingerprint `sha256:56aca7da0220b8dfba35f299a80f7324bca885f8ac70636e8f987167dde915c4`, read-back и machine-state commit.
- Owner Human Visual Validation после remediation подтвердил восстановленный порядок, human-facing M04/M07/M08 surfaces, attachment/link/free-answer и отсутствие проверенных internal ID.
- Golden title migration production run `35086056899` изменила только два заголовка M00-L01/M00-L02; post-write fixture принят PR #83. Owner final HVA подтвердил оба human-facing title без canonical prefixes.

### Что НЕ доказано

Current machine state Issue #54 не является all-course equivalence proof. На момент baseline он содержит confirmed lesson baselines только для `M02-L01` и `M04-L01`, а также **18 PENDING lessons** относительно более нового canonical source:

`M00-L02`, `M00-L03`, `M01-L01`, `M01-L02`, `M02-L02`, `M03-L01`, `M03-L02`, `M04-L02`, `M04-L03`, `M05-L01`, `M05-L02`, `M06-L01`, `M06-L02`, `M06-L03`, `M06-L04`, `M07-L01`, `M07-L02`, `M08-L01`.

Отдельно в machine state остаётся PENDING для `04_course/stepik/course-page.md`.

Golden profile подтверждает post-migration title state M00-L01/M00-L02, но не усыновляет более новый canonical content. Для `M00-L02` отдельно известна canonical-vs-golden divergence: current canonical план содержит 8 steps, confirmed live golden profile — 7.

Следовательно, private Stepik, который сейчас существует, **не доказанно эквивалентен актуальному `main`**. Это достаточный blocker само по себе.

## 3. Readiness gates

| # | Gate | Статус на 16.09.2026 | Evidence | Blocker первой human session | Что осталось сделать |
|---:|---|---|---|:---:|---|
| 1 | Canonical course architecture | **SOURCE PASS** | `main@f16a201...`; PI v1.4; Manifest v1.3+v1.2; CA v1.1+v1.0; CM v1.2+v1.1; Coverage v1.0; SM v1.1+v1.0; LS v1.2+v1.1 | нет | При сборке staging не менять архитектуру; привязать staging к точному source SHA. |
| 2 | Astra PED-01…PED-07 remediation | **SOURCE PASS / REAL GATES OPEN** | PR #59; critic `90_reviews/pedagogy-zero-level-2026-09-14/pr59-critic-review.md`; current source regression M00/M03/M05/M06 | **да** | Закрыть PED-01 device, PED-03 service, PED-06 publication и PED-07 final live UI gates; сохранить PED-02/04/05 без регрессии. |
| 3 | Independent critic после Astra fixes | **SOURCE PASS** | PR #59 independent critic: CRIT-C-01 найден, исправлен commit `14b006cec1e630e7a706cd35534f228f6067a88d`, повторный source review APPROVE | нет | Не выдавать source approval за live/human acceptance. |
| 4 | Current private Stepik state | **PARTIAL MACHINE/HUMAN PASS / NOT STAGING-READY** | course `299189`; recovery/hygiene/golden runs `35015060946`, `35078545526`, `35079859897`, `35086056899`; owner HVA; current golden profile | **да** | Собрать и доказать private staging на выбранном current `main` SHA, не только отдельные migrated objects. |
| 5 | Canonical GitHub ↔ live Stepik equivalence | **BLOCKED / NOT PROVEN** | Issue #54 schema v3: 18 pending lessons + pending course-page; only M02/M04 confirmed tracked baselines; golden scope отдельный | **да** | На ШАГЕ 2 построить актуальную private сборку и дать all-course source↔live proof; PENDING должен быть объяснён/закрыт относительно staging SHA. |
| 6 | Learner-facing ID hygiene | **SOURCE PASS + LIMITED HUMAN VISUAL PASS / FULL LIVE NOT PROVEN** | all-course offline regression: 148 visible rendered steps без internal IDs; HVA проверила migrated M04/M07/M08 и golden titles | **да** | После полной сборки проверить итоговый learner-facing UI всего предъявляемого staging; source clean не достаточно. |
| 7 | Section/module ordering integrity | **MACHINE PASS + HUMAN VISUAL PASS** на текущем live snapshot | recovery run `35015060946`: positions 1..9; owner HVA после `35079859897` | нет сейчас | После любых Step 2 structural/title/content writes повторить machine snapshot и визуальный regression порядка. |
| 8 | Physical assets/materialization | **BLOCKED / INCOMPLETE** | M04 TXT binding подтверждён; current bulk-status фиксирует ещё 4 non-golden visual sources, требующих physical materialization/read-back: два M03 PNG и два SVG-derived visual assets | **да** | Материализовать/привязать physical assets в private staging, проверить bytes/rendering/visibility; SVG → deterministic PNG с visual verification. |
| 9 | PED-01 desktop route | **NOT TESTED** | source памятка существует; PR #59 critic явно оставил real-device gate pending | **да** | На реальном компьютере пройти obtain → find → attach/use → save → re-find без содержательной помощи; сохранить evidence. |
| 10 | PED-01 phone route | **NOT TESTED** | source памятка существует; PR #59 critic явно оставил real-device gate pending | **да** | На реальном телефоне пройти тот же полный маршрут; сохранить evidence. |
| 11 | PED-03 live image generation/edit | **BLOCKED / CURRENT SERVICE PASS ABSENT** | M05-L02 source требует live generation и real edit; SM/документация не является функциональным acceptance; critic PR #59 оставил live gate pending | **да** | Выполнить свежий service preflight на бесплатных PRIMARY/BACKUP: live generation + actual edit existing image, с датой и evidence. |
| 12 | PED-06 publication visual check | **BLOCKED / NOT PUBLISHED-PROVEN** | два source PNG существуют и branching в M03-L02 корректен; `M03-L02` сейчас PENDING; physical publication обоих assets не доказана | **да** | В итоговой Stepik-сборке проверить обе ветки: другой интерфейс, видимость/кликабельность, правильный asset, без второго аккаунта. |
| 13 | Author-only / recovery visibility | **SOURCE/OFFLINE PASS / FULL LIVE NOT PROVEN** | source compiler фильтрует author-only; current M03 recovery source material distinct; Stepik advisory sequencing contract существует | **да** | В полном staging проверить отсутствие author-only leakage, физическую доступность recovery, расположение check/recovery и отсутствие ранней содержательной подсказки. |
| 14 | Consent/data-minimization operational setup | **DOCUMENTED / NOT OPERATIONALLY INSTANTIATED** | approved participant info/consent, data-handling, privacy/safety-stop documents | **да** | До первой сессии подготовить session aliases/storage, разделение identity↔session evidence, consent-before-collection и deletion/retention operation. |
| 15 | Moderator rehearsal | **NOT PERFORMED** | runbook/moderator guide существуют; фактического rehearsal evidence нет | **да** | Провести rehearsal без участника: тайминг, допустимые/запрещённые вмешательства, contamination logging, stop protocol, recovery transitions. |
| 16 | Current service preflight | **BLOCKED / STALE FOR PILOT** | Service Acceptance 11.09.2026 — историческое evidence; PED-03 требует актуального live-account acceptance; сервисный слой динамический | **да** | Непосредственно перед Wave 0 перепроверить access/registration/free limits/files/search/image generation/edit для PRIMARY/BACKUP и зафиксировать SERVICE PASS/FAIL. |
| 17 | Two eligible Wave 0 participants | **NOT AVAILABLE / NOT RECRUITED IN THIS STEP** | recruitment screener существует; рекрутинг на ШАГЕ 1 запрещён | **да** | После закрытия технических/операционных gates отобрать двух eligible novice participants по screener без запуска сессий раньше readiness PASS. |

## 4. PED regression matrix для readiness

| PED | Текущий source verdict | Реальный gate перед Wave 0 | Readiness verdict |
|---|---|---|---|
| PED-01 | PASS source | desktop + phone full file/note route | **BLOCKED** |
| PED-02 | PASS source; current shared-printer recovery сохраняет отличия | regression при финальной сборке | **PASS source / recheck on staging** |
| PED-03 | PASS source | current free live generation + actual edit | **BLOCKED** |
| PED-04 | PASS source после CRIT-C-01; current M06-L04 не перечисляет категории до E01 | проверить final staging sequencing/no early cue | **PASS source / recheck on staging** |
| PED-05 | PASS source; причина trace дана до требования | проверить, что сборка не переставила/не раскрыла шаги | **PASS source / recheck on staging** |
| PED-06 | PASS source | both interface assets published/visible/correct branch/no second account | **BLOCKED** |
| PED-07 | PASS source/offline rendering | final visible Stepik UI whole staging | **BLOCKED** |

## 5. Реальные blockers до первой human session

Первая human session запрещена до закрытия следующего набора:

1. собрать private Stepik staging, доказанно соответствующий выбранному актуальному `main` SHA, и снять/объяснить текущий Issue #54 PENDING относительно этого staging;
2. материализовать все learner-facing physical assets, необходимые выбранной Wave 0 траектории, с read-back/visual proof;
3. пройти PED-01 на компьютере и телефоне;
4. выполнить current service preflight, включая PED-03 live generation и real edit на бесплатных PRIMARY/BACKUP;
5. выполнить PED-06 обеих publication branches и PED-07 all-staging visible UI regression;
6. проверить author-only leakage, recovery visibility, independent sequencing и CRIT-C-01 в фактическом staging;
7. операционно подготовить consent/data-minimization/storage;
8. провести moderator rehearsal;
9. только после предыдущих gates отобрать двух eligible Wave 0 participants.

## 6. Что не является blocker сейчас, но остаётся regression gate

- Порядок sections `1..9` на текущем live snapshot доказан и прошёл HVA; его нужно перепроверить после следующей сборки, но инцидент #74 не считается текущим открытым blocker.
- Golden title cleanup M00-L01/M00-L02 завершён production run `35086056899`, fixture принят PR #83, final HVA PASS; повторять миграцию не требуется. Но canonical content divergence M00-L02 остаётся частью общего equivalence blocker.
- M02 partial-write incident #80 восстановлен и не требует blind retry; это закрытая recovery-история, а не текущий blocker.

## 7. Запрещённые интерпретации этого baseline

Этот документ **не разрешает**:

- live Stepik write в рамках ШАГА 1;
- автоматический rebaseline неизвестного live state;
- Wave 0 или рекрутинг;
- статус `HUMAN VALIDATED`;
- подмену real gates модельной/документационной проверкой;
- вывод `WAVE 0 READY` из наличия tooling.

## 8. Handoff после ШАГА 1

Следующая задача — **ШАГ 2: «сборка и доказательство актуального private Stepik staging»**.

Его результатом должен стать конкретный private staging course `299189`, привязанный к точному принятому `main` SHA, с доказанной all-course/target-wave equivalence, materialized physical assets, корректным learner-facing UI, сохранёнными section positions, author-only/recovery boundaries и актуализированным machine state без необъяснённого PENDING относительно предъявляемой участнику версии.

До такого доказательства verdict остаётся **NOT READY / BLOCKED FOR FIRST HUMAN SESSION**.
