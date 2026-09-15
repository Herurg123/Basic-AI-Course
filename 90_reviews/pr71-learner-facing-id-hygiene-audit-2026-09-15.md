# PR #71 — финальный adversarial audit learner-facing hygiene

**Дата:** 15 сентября 2026  
**PR:** #71 `Stepik: очистить learner-facing слой от внутренних ID`  
**Code/docs head до audit-only commit:** `8369ab0ca5044b9009c52f18e898089883b66e09`  
**Base:** `main@9fee02c2193574d238130de6c106b82a1222b513`

## Итоговый verdict

- OPEN CRITICAL: **0**
- OPEN HIGH: **0**
- OWNER DECISION REQUIRED BEFORE MERGE: **0**
- learner-facing hygiene code gate: **PASS**
- Stepik writes из PR: **0**
- `ready_for_bulk_write`: **false**
- post-merge live action: **owner-dispatched learner-hygiene workflow + Human Visual Validation RETEST**

PR допускается к merge после обычной проверки, что audit-only commit не изменил code/content contracts.

## Что проверялось

Adversarial review покрывал не только отсутствие строковых ID, но и эксплуатационные failure modes:

1. canonical learner Markdown всех 21 lessons;
2. verified rendering всех 148 learner-facing steps;
3. inline Markdown asset titles;
4. human-facing lesson title contract;
5. exact legacy-title detection;
6. arbitrary/manual title drift;
7. duplicate/create/delete risks;
8. golden read-only protection;
9. tracked `M02-L01/M04-L01` baseline compatibility;
10. Issue #54 race boundary;
11. immutable deployment history ordering;
12. partial recovery;
13. stale-main recovery;
14. ambiguous/known-failed writes;
15. asset-baseline reuse для `M04-L01-A01.txt`;
16. current-main guard и общий live mutex;
17. PR workflow isolation от live Stepik credentials/writes;
18. совместимость будущего `bulk-status`/`sync-runtime` с human titles;
19. документацию machine PASS vs Human FAIL/RETEST.

## Подтверждённый learner-facing результат

Fail-first all-course regression первоначально выявил **48 learner-visible internal-ID occurrences**.

После ремедиации:

- canonical visible Markdown не содержит `Mxx-Lxx`, Asset/Exercise/Check IDs;
- visible HTML verified rendering всех **148** learner-facing steps не содержит internal IDs;
- Markdown link destinations и hidden production comments могут сохранять canonical IDs;
- learner-visible link labels заменены на смысловые русские названия;
- inline Markdown H1 humanize-ится только в learner representation, исходные filenames/paths не переименовываются;
- canonical lesson H1 остаётся human-facing без ID-prefix.

Проверенные вручную diff-примеры сохраняют педагогический смысл: «учебный исходник», «подготовленная несовершенная версия», «учебная карточка», «техническая памятка», «две подготовленные визуальные версии», «короткая форма фиксации результата» и названия соседних уроков заменяют служебные ID без удаления самого действия или объяснения.

## Title migration contract

Автоматически разрешены только:

- уже корректный `HUMAN_EXACT`;
- точный `LEGACY_PREFIX_EXACT = canonical_id — canonical human title`.

Любое другое название считается manual/unknown drift и блокирует автоматическую запись.

Title-only route:

- только PUT существующего объекта;
- CREATE отсутствует;
- DELETE отсутствует;
- WAL до dispatch;
- no blind retry;
- read-back после write;
- final history proof обязателен.

Tracked `M02-L01/M04-L01` не переименовываются отдельным metadata PUT. Title входит в lesson fingerprint, поэтому title + изменённые learner steps проходят одним baseline-aware event.

## Golden protection

`M00-L01` и `M00-L02` остаются `READ_ONLY_GOLDEN`.

PR **не** ослабляет этот guard. Legacy title этих lessons классифицируется как `GOLDEN_TITLE_OWNER_REQUIRED`; автоматический write запрещён.

Это отдельное post-merge owner decision и не требуется для merge PR #71, потому что Issue #70 прямо исключает обычный writer route для golden lessons.

Известный независимый `M00-L02` canonical-vs-live divergence (8 canonical steps против 7 confirmed live golden) также остаётся target-scoped owner state и не усыновляется автоматически.

## HIGH findings, найденные и закрытые во время разработки/audit

### HIGH-1: active status/sync ожидал legacy ID-prefix после hygiene

**Риск:** после успешной очистки title `bulk-status`/pilot sync мог бы классифицировать нормальный human title как drift либо ожидать старый fingerprint.

**Исправление:** human H1 стал canonical expected title; exact legacy prefix является только migration state; arbitrary drift fail-closed. `sync_runtime.py` для tracked `M02-L01` также использует human title.

**Regression:** bulk-status тестирует human `IN_SYNC`, legacy `LEARNER_HYGIENE_REQUIRED` и arbitrary drift blocker.

### HIGH-2: tracked final read-back + Issue PATCH + history-commit gap мог застрять после продвижения main

**Риск:** Stepik уже применён и Issue #54 уже содержит подтверждённый baseline, но `MACHINE_STATE_COMMITTED` не успел записаться. После нового merge current-main guard запрещал старому event продолжение, а новый event не должен стартовать поверх incomplete history.

**Исправление:** `learner_hygiene_entrypoint.py` распознаёт только доказанный old-source boundary, где Issue baseline строго равен `FINAL_READBACK_CONFIRMED.actual_confirmed_state`, и создаёт commit-only artifacts. Workflow затем дописывает history без Stepik write и требует отдельный rerun перед новой миграцией.

**Regression:** old-source matching state, same-source normal recovery, mismatching Issue state not adopted.

### HIGH-3: title-only FINAL_READBACK_CONFIRMED мог навсегда остаться incomplete после нового main

**Риск:** title PUT и final read-back уже подтверждены, но history `MACHINE_STATE_COMMITTED` упал; live title уже human. После изменения main старый title event нельзя было безопасно завершить обычным retry.

**Исправление:** entrypoint до новых writes перечисляет canonical title object IDs и для `title-metadata` дописывает только `MACHINE_STATE_COMMITTED`, если immutable event уже имеет валидный `FINAL_READBACK_CONFIRMED`. Никакой Stepik write не выполняется. Partial/ambiguous events без final не усыновляются.

**Regression:** proven old-source final commits with `stepik_writes=0`; no-final event remains incomplete; multiple incomplete events fail closed.

## Recovery / history verdict

Tracked hygiene соблюдает:

`EVENT_STARTED → durable baseline snapshot → WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → read-back → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → Issue race boundary → MACHINE_STATE_COMMITTED`.

Разрешённый recovery:

- полностью доказанный prefix;
- final read-back без Issue update;
- Issue already updated + missing history commit;
- title-only final proof + missing history commit.

Запрещённый automatic recovery:

- ambiguous write;
- known failed write;
- dispatch gap;
- failed read-back;
- manual/unproven live drift;
- несколько incomplete events;
- stale asset binding;
- arbitrary title drift.

Blind retry отсутствует.

## Workflow safety

`.github/workflows/stepik-learner-hygiene.yml`:

- PR event запускает offline tests only;
- live job запускается только `workflow_dispatch`;
- `confirm_write` по умолчанию false;
- разрешён только fixed course `299189`;
- live job использует общий mutex `stepik-live-course-299189`;
- current-main guard выполняется раньше runtime;
- Issue #54 читается до runtime;
- tracked state PATCH выполняется только после compare guard;
- history commit идёт после machine-state boundary;
- `continue-on-error` нет;
- PR live job skipped.

## CI evidence

Final code/docs head `8369ab0ca5044b9009c52f18e898089883b66e09`:

- Stepik Uploader PR run `34992175225`: **SUCCESS**;
- Stepik Learner Hygiene PR run `34992175116`: **SUCCESS**;
- unit tests: **224 / 224 OK**;
- structural dry-run: **SUCCESS**;
- owner live jobs: **SKIPPED**;
- Stepik writes: **0**.

Node.js 20 deprecation warning остаётся maintenance notice: actions выполняются с forced Node 24 и CI green. На семантику PR не влияет.

## Документация и Human Validation

`M04-L01-LIVE-ACCEPTANCE-2026-09-15.md` больше не смешивает machine и human gates:

- machine acceptance первого upload: PASS;
- Human Visual Validation: **FAIL / RETEST REQUIRED** из-за internal-ID leakage;
- attachment, внешние ссылки и free-answer функционально работали;
- после live hygiene требуется повторная human проверка.

`LEARNER-HYGIENE.md`, automation `README.md` и `BULK-STATUS.md` описывают новый human-title contract, recovery boundary и оставшиеся gates.

## Residual risks / non-blocking

1. **Golden live titles остаются с legacy ID-prefix до отдельного owner-approved решения.** Это намеренное следствие READ_ONLY_GOLDEN. PR не выдаёт это за исправленное live состояние.
2. **Live golden body не переписывается этим PR.** All-course regression доказывает чистоту текущего canonical/verified rendering, а не изменение read-only golden fixture в Stepik. Любое изменение golden learner-visible content требует отдельного owner decision и нового golden evidence.
3. Исторические one-off `first-upload-m04-l01` / `content-test-one` маршруты всё ещё знают старый prefixed-title contract. После hygiene они fail closed на title mismatch и не являются обычным update route. Будущий general initial uploader должен использовать human-title contract.
4. `planner.py` сохраняет совместимость с human и legacy title для распознавания существующего skeleton. Реальный write hygiene строже: arbitrary drift автоматически не перезаписывается.
5. Human Visual Validation после live migration остаётся обязательной и не может быть заменена API/read-back тестами.

Ни один residual не разрешает bulk write.

## Merge gate

**PASS** при следующих фактах:

- CRITICAL = 0;
- HIGH = 0;
- owner decision required before merge = 0;
- CI green;
- Stepik writes from PR = 0;
- audit-only commit не меняет code/content contracts.

Следующее производственное действие после merge: дождаться post-merge CI/impact, затем owner-dispatch `.github/workflows/stepik-learner-hygiene.yml` с `confirm_write=true`, проверить machine result/Issue #54/history и выполнить Human Visual Validation RETEST `M04-L01`.
