# Observer Form — Human Pilot Session

> Один экземпляр на Participant ID × session. Не записывать ненужное личное содержимое.

## A. Session metadata

- Participant ID: `P___`
- Wave: `W0 / W1 / W2 / RETEST`
- Session #: 
- Date:
- Moderator:
- Observer (если отдельный):
- Device: `PHONE / COMPUTER / OTHER`
- Browser:
- PRIMARY/BACKUP route:
- Production/staging version:
- Operational package version:
- Recording consent: `NONE / SCREEN / AUDIO / BOTH`

## B. Entry state

- Start Lesson ID:
- Resume point:
- Service preflight date/status:
- Participant reports outside help/material exposure since previous session? `NO / YES / UNKNOWN`
- If yes/unknown: кратко, может ли это загрязнить конкретную future independent attempt?

## C. Event log

| Time | Lesson/Check | Observed action | Participant words only if needed | Stuck? | Intervention N/P/T/C/S | Evidence pointer | Issue ID |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

### Запись наблюдения

Писать поведение, а не интерпретацию:

- хорошо: «открыл источник X, сопоставил число 17 с ответом, сказал “здесь не совпадает”»;
- плохо: «хорошо проверил факт».

Не копировать секретный/личный материал, если достаточно описания действия.

## D. Stuck events

На каждый meaningful stuck:

- Lesson/Check ID:
- Что участник пытался сделать:
- Наблюдаемая причина до вмешательства:
- Просил ли помощь сам:
- Нейтральный вопрос использован? `NO / YES`:
- Итоговая классификация: `CONTENT / TECHNICAL / STEPIK / SERVICE / DEVICE / SAFETY / UNKNOWN`
- Intervention ID из intervention log:
- После вмешательства evidence contamination? `NO / YES / N/A`
- Issue ID:

## E. Independent-attempt snapshot

На каждую independent attempt в сессии:

- Check ID:
- Competency/dimension:
- Attempt #: 
- Начало до раскрытия rubric/hint подтверждено? `YES / NO / UNKNOWN`
- Content intervention: `NONE / C / S-with-content / OTHER`
- Technical help count:
- Result: `PASS / FAIL / PRACTICE-CONTAMINATED / NOT COMPLETED / AMBIGUOUS`
- Evidence pointer:
- Recovery needed? `NO / YES`
- Recovery scenario ID, если заранее предусмотрен:

Не использовать post-hoc рассказ как замену отсутствующего temporal evidence.

## F. Privacy / verification / application flags

Отметить только применимое:

- B3 safe decision/action observed **before transfer**: `YES / NO / N/A / AMBIGUOUS`
- B7 live generation observed: `YES / NO / N/A`
- B8 existing-source real edit observed: `YES / NO / N/A`
- B10 real basis actually opened/compared: `YES / NO / N/A / AMBIGUOUS`
- B12 actual application observed: `YES / NO / N/A / AMBIGUOUS`
- Safety stop occurred: `YES / NO`

## G. Session close

- End Lesson ID / resume point:
- Session end time:
- Active learner minutes:
- Technical/service wait minutes:
- Break minutes:
- Moderator/admin minutes:
- Recovery/retry minutes:
- F1 minutes (if any):
- New issue IDs:
- Any evidence requiring second review because ambiguous/critical/F1? 
- Any accidental sensitive data captured? `NO / YES` → if YES, stop normal handling and remediate per data rules.

## H. Participant comments after scored work

Only after relevant independent attempts are closed:

- «Где было особенно непонятно?»
- «Где технически было трудно продолжить?»
- «Что показалось лишним или повторяющимся?»
- «Где вы впервые получили результат, который реально был полезен?»

Комментарии участника являются usability evidence, но не переписывают уже наблюдавшийся PASS/FAIL самостоятельного действия.
