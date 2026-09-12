# Wave 0 Readiness Record — Human Pilot

**Дата:** 12 сентября 2026 года  
**Основание:** `main` после PR #36, merge commit `4950b2af453136468cae3f2f93134a85cb37dde0`  
**Human Pilot Architecture:** APPROVED  
**Operational Human Pilot Package:** APPROVED  
**Human validation:** `NOT PERFORMED`  
**Wave 0 readiness verdict:** `NOT READY / OWNER ACTION REQUIRED`

---

## 1. Назначение

Этот record фиксирует фактическую готовность к **первой human session**, а не готовность документов.

Утверждённая архитектура и operational package сами по себе не делают Wave 0 готовой. До первого участника нужно подтвердить реальную Stepik-среду, работу модератора, организационную privacy/data схему, recovery readiness и текущую работоспособность сервисного маршрута.

`NOT READY` здесь не означает дефект курса. Это означает, что обязательные внешние/человеческие readiness-действия ещё не выполнены или не имеют evidence.

---

## 2. Readiness matrix

| Readiness item | Status | Evidence / current state | Blocking Wave 0? |
|---|---|---|---|
| Human Pilot Architecture v1.0 | `PASS` | утверждена PR #33 | нет |
| Operational Human Pilot Package | `PASS` | утверждён PR #35 после adversarial critic и fixes | нет |
| Canonical status synchronization | `PASS` | PR #36 merged; human validation по-прежнему `NOT PERFORMED` | нет |
| Private Stepik staging assembled | `NOT PERFORMED` | staging course/build не предоставлен и не проверен | **да** |
| Stepik staging checklist | `NOT PERFORMED` | PHONE/COMPUTER smoke check, author-only visibility, sequencing и F1 integrity не проверены в реальной staging-среде | **да** |
| Consent/data-minimization operational setup | `PARTIAL` | утверждены template и data rules; не зафиксированы фактическое внешнее место хранения contact mapping/consent, ответственный и конкретные retention rules для contact/raw recording data | **да** |
| Moderator rehearsal N/P/T/C/S | `NOT PERFORMED` | human moderator ещё не прошёл rehearsal | **да** |
| Recovery documentation | `PASS — DOCUMENTED` | `recovery-readiness.md` связывает checks с существующими author-only recovery и запрещает on-the-fly зачётный сценарий | нет |
| Recovery execution readiness in staging | `NOT PERFORMED` | не проверено, что recovery действительно скрыты от learner и доступны moderator в нужный момент в staging | **да** |
| Current service preflight | `NOT PERFORMED` | time-sensitive functional preflight PRIMARY/BACKUP/B4/B7/B8/B10/save не выполнялся перед human session | **да** |
| Wave 0 participants | `NOT STARTED` | нужны 2 real screened novice users; модели/авторы/регулярные AI-users не подходят | **да для запуска сессии** |

---

## 3. OWNER ACTION REQUIRED — private Stepik staging

Владелец проекта должен собрать **private/staging** версию курса в Stepik по принятой production-версии.

Нужно сохранить для проверки:

- staging course/build identifier или ссылку, достаточную для доступа проверяющего;
- GitHub production commit SHA, из которого собрана staging-версия;
- подтверждение, что это private/staging, а не public release.

Не передавать в GitHub access tokens, пароли, cookies или иные секреты.

После появления staging нужно пройти канонический checklist:

`06_testing/human-pilot/operational-package/stepik-staging-checklist.md`

Wave 0 остаётся blocked, пока итог checklist не `READY`.

---

## 4. OWNER ACTION REQUIRED — moderator

Нужно назначить реального human moderator/observer и провести rehearsal по:

`06_testing/human-pilot/operational-package/moderator-guide.md`

Минимум нужно подтвердить, что moderator без подсказки различает:

- `P` neutral protocol;
- `T` technical/interface help;
- `C` substantive content help;
- `S` safety stop;
- последствия contamination для level-3/F1.

Moderator, который системно путает `T` и `C` или задаёт ведущие вопросы, не готов к Wave 0.

---

## 5. OWNER ACTION REQUIRED — consent/data handling

Template и правила уже утверждены, но до participant recruitment нужно определить фактическую организационную схему вне GitHub:

- кто хранит Candidate/Participant contact mapping;
- где она хранится;
- кто имеет доступ;
- срок удаления contact data;
- если используется optional screen/audio recording: отдельное хранилище, доступ и срок удаления;
- способ фиксировать consent без помещения имени/подписи в GitHub pilot-data.

После этого можно отметить operational data setup `PASS` без раскрытия самих персональных данных в репозитории.

---

## 6. OWNER ACTION REQUIRED — Wave 0 participants

Для Wave 0 требуются **2 реальных screened novice users**.

Использовать:

`06_testing/human-pilot/operational-package/recruitment-screener.md`

Не засчитываются как human validation:

- модели/агенты;
- авторы/редакторы курса;
- участники production/model audits;
- люди с регулярным/профессиональным AI workflow;
- люди, заранее увидевшие author-only rubric/recovery/F1 material.

Контактные данные кандидатов не помещаются в GitHub.

---

## 7. Service preflight

Service preflight принципиально time-sensitive. Его следует выполнить **не заранее “для галочки”, а непосредственно перед первой Wave 0 session**, а после заметного перерыва или изменения интерфейса повторить затронутые проверки.

Использовать:

`06_testing/human-pilot/operational-package/service-preflight-checklist.md`

Проверяются минимум PRIMARY/BACKUP и реальные функции B4 upload, B7 generation, B8 edit, B10 external-source route и сохранение/скачивание, если требуется сценарием.

Публичное описание сервиса или модельный пересказ его функций не являются functional preflight evidence.

---

## 8. Что можно считать закрытым уже сейчас

Без дополнительных human/external действий закрыты только документальные gates:

- production M00–M08 — `PASS / CLEAN`;
- Human Pilot Architecture — `APPROVED`;
- Operational Human Pilot Package — `APPROVED`;
- recovery map/rules — `DOCUMENTED`;
- status synchronization — `PASS`.

Нельзя повышать статус до `WAVE 0 READY`, `HUMAN PILOT IN PROGRESS` или `HUMAN VALIDATED` только на основании этих документов.

---

## 9. Условие смены статуса на WAVE 0 READY

`WAVE 0 READY` разрешено поставить только когда одновременно:

1. private Stepik staging существует и `stepik-staging-checklist.md` = `READY`;
2. operational consent/data setup определён и проверен;
3. moderator rehearsal = `PASS`;
4. recovery execution readiness в staging = `PASS`;
5. current service preflight = `PASS` или допустимый `PASS-WITH-ROUTE-SWITCH`;
6. минимум 2 eligible Wave 0 participants рекрутированы/запланированы без раскрытия персональных данных в GitHub.

До этого текущий verdict сохраняется:

`NOT READY / OWNER ACTION REQUIRED`.

Human validation при любом readiness-статусе до первой реальной сессии остаётся:

`NOT PERFORMED`.
