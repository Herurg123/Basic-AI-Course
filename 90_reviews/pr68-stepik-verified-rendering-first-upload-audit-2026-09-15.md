# Adversarial audit PR #68 — verified rendering и controlled first upload

**Дата:** 15 сентября 2026 года  
**PR:** #68 `Stepik: verified rendering и controlled first upload`  
**Проверенный code head:** `0560314d0c9de225f8605dbca7c29d9659ffb5b9`  
**Base:** `main` = `427840525d4a36dfe17f3365486d55828e0115ea`  
**Роль проверки:** критик; цель — найти причины не принимать изменение, а не подтвердить авторский вывод.

## Итоговый вердикт

- **OPEN CRITICAL:** 0
- **OPEN HIGH:** 0
- **OWNER DECISION REQUIRED BEFORE MERGE:** 0
- **Вердикт:** **ОДОБРЕНО К MERGE**

Live acceptance `M04-L01` намеренно не относится к merge этого engineering PR. После merge он остаётся отдельным owner-dispatched production acceptance; общий bulk write остаётся закрытым.

## Проверенный scope

Аудит проверял:

1. source-preserving verified rendering 21 canonical lessons / 148 learner-facing steps;
2. отсутствие repo-relative learner links в render-ready HTML;
3. inline Markdown adaptation и nested dependency expansion;
4. materialization gate для физических файлов;
5. Stepik attachment capability preflight и multipart upload;
6. no-blind-retry classification для POST/PUT;
7. download/read-back фактических attachment bytes;
8. отдельные logical deployment events для asset и lesson;
9. sync state schema v3 с отдельным `assets` baseline;
10. Issue #54 compare-before-PATCH race guard;
11. `MACHINE_STATE_COMMITTED` только после успешного machine-state PATCH;
12. initial-upload recovery при partial/complete states;
13. owner-only workflow gates, current-main guard и общий live mutex;
14. сохранение golden READ_ONLY, запрета DELETE и `ready_for_bulk_write=false`.

## Закрытые HIGH findings

### HIGH-01 — unresolved dispatch мог допустить blind continuation partial first-upload

**Найдено:** первоначальный first-upload runtime разрешал partial continuation, когда fresh live совпадал с последним подтверждённым intermediate fingerprint. Этого недостаточно, если после него уже существовал более поздний `WRITE_DISPATCH_STARTED` без доказанного `WRITE_COMPLETED + OP_READBACK_CONFIRMED` либо `WRITE_FAILED_KNOWN`.

**Риск:** повторный POST/PUT после уже dispatch-нутого write; duplicate Stepik operation или конфликтующая immutable history.

**Исправление:** `initial_upload_writer` теперь сам, независимо от caller boolean, требует:

- все ранее dispatch-нутые operation IDs полностью совпадают с `WRITE_COMPLETED` и `OP_READBACK_CONFIRMED` IDs;
- event не содержит `WRITE_AMBIGUOUS`, `WRITE_FAILED_KNOWN` или `READBACK_FAILED`;
- число подтверждённых writes совпадает с live matching prefix;
- live partial fingerprint присутствует в подтверждённом per-operation read-back history.

**Regression evidence:**

- `test_dispatch_gap_blocks_partial_resume_without_new_write`;
- `test_known_failed_dispatch_blocks_partial_resume_without_new_write`;
- существующий recovery dispatch-gap suite также остаётся зелёным.

**Статус:** CLOSED.

### HIGH-02 — complete live после подтверждённых writes мог быть ошибочно классифицирован как NOOP

**Найдено:** если все step writes уже были подтверждены, но workflow падал до `FINAL_READBACK_CONFIRMED`, повторный run видел complete live content. Без provenance-aware recovery это могло завершиться как `NOOP_CONFIRMED`, несмотря на фактически выполненные writes.

**Риск:** противоречие deployment history и неправильная семантика baseline.

**Исправление:** complete recovery разрешён только при полностью подтверждённом write history; final status остаётся `APPLIED`, если event содержит dispatch evidence. Повторных Stepik writes нет.

**Regression evidence:**

- `test_proven_complete_recovery_adds_final_applied_without_new_write`;
- `test_runtime_resume_flag_can_finish_proven_complete_event_without_new_write`.

**Статус:** CLOSED.

### HIGH-03 — untracked complete live мог быть автоматически усыновлён как baseline

**Найдено:** complete live content, случайно совпадающий с rendered desired, не является доказательством, что его создал текущий deployment event.

**Риск:** automatic adoption неизвестного/manual live state и потеря provenance.

**Исправление:** complete matching state без полного proven deployment write history останавливается fail-closed. Первый upload не создаёт baseline только потому, что `live == desired`.

**Regression evidence:** `test_complete_matching_live_without_proven_history_is_blocked`.

**Статус:** CLOSED.

### HIGH-04 — runtime complete-recovery gate не совпадал с writer API

**Найдено:** runtime выводил единый `allow_partial_resume` из последнего подтверждённого fingerprint, а writer для уже complete live state первоначально ожидал отдельный `allow_complete_recovery`. После падения непосредственно перед final read-back это безопасно блокировало recovery, но оставляло production event незавершённым без штатного пути завершения.

**Исправление:** единый runtime resume signal может открыть как partial, так и complete recovery, но writer всё равно независимо требует полный набор dispatch/completed/read-back evidence и точное число подтверждённых writes.

**Regression evidence:** `test_runtime_resume_flag_can_finish_proven_complete_event_without_new_write`.

**Статус:** CLOSED.

## Rendering и педагогическая целостность

- `lesson.md` остаётся источником learner-facing текста; renderer не пересказывает контент из краткого Stepik-plan.
- Markdown learner material не вставляется слепо внутрь предложения. Исходная инструкция остаётся на месте, а материал добавляется отдельным блоком в том же Stepik step.
- Nested Markdown dependency раскрывается рекурсивно.
- Physical asset без verified binding не получает выдуманный URL, а даёт `MaterializationRequired`.
- M04-L01 author-only ключ не попадает в learner rendering.
- `free-answer` source берётся из confirmed golden profile.
- All-course regression доказывает 21/21 lessons и 148/148 learner steps при synthetic verified bindings.

Открытых педагогических HIGH/CRITICAL дефектов в diff не найдено.

## Attachment materialization и provenance

Проверено:

- capability preflight требует фактический `POST`, `multipart/form-data`, writable `lesson` и required writable `file upload`;
- source file hash сверяется до POST;
- same-name existing attachment не усыновляется автоматически даже при совпадающих bytes без machine/history provenance;
- несколько same-name объектов = STOP;
- POST выполняется один раз; write retry отсутствует;
- network/5xx/неоднозначный success = ambiguous outcome;
- created attachment подтверждается по ID, lesson, name, size и фактическому download SHA-256;
- URL принимается только с HTTPS Stepik host;
- asset baseline записывается отдельно от lesson baseline.

Owner-approved working assumption D-2026-09-15-STEPIK-ATTACHMENTS остаётся условным: если live API перестаёт подтверждать capability или upload/read-back, route fail-closed останавливается.

## State / history / race

- schema v1/v2 безопасно нормализуется в v3 с пустым `assets`; существующий lesson baseline не теряется;
- asset source path не может выйти за пределы repo-relative namespace;
- Issue #54 обновляется только после re-read + exact compare с ранее прочитанным state;
- asset и lesson `MACHINE_STATE_COMMITTED` записываются только после успешного PATCH Issue #54;
- asset materialization и lesson initial upload используют разные logical events, потому что точный lesson desired fingerprint появляется только после verified attachment URL;
- final asset history без machine-state commit может быть восстановлен без повторного POST;
- partial lesson recovery допускает только remaining suffix из доказанного prefix;
- complete proven recovery завершает event как APPLIED без повторного Stepik write.

## Workflow safety

- live route существует только как explicit `workflow_dispatch` mode `first-upload-m04-l01`;
- требуется `confirm_write=true`;
- current-main guard обязателен до runtime;
- live mutex фиксирован: `stepik-live-course-299189`;
- PR/push CI не запускает owner live job;
- target hard-coded как M04-L01 внутри runtime;
- неправильный course ID fail-closed на publication policy / live guards;
- target должен быть private, `ru`, иметь точный title/position и не быть golden/independence/F1-sensitive;
- новый attachment POST разрешён только пока lesson остаётся исходным one-step skeleton placeholder;
- DELETE не реализован;
- общий bulk write не разблокирован.

## CI evidence

Последний проверенный code head: `0560314d0c9de225f8605dbca7c29d9659ffb5b9`.

GitHub Actions run: `34966368959`.

Результат:

- unit tests: **200/200 OK**;
- structural dry-run: success;
- owner live job: skipped;
- impact-after-merge job: skipped на PR, как ожидается;
- Stepik writes в PR: **0**.

## Остаточные риски, не блокирующие merge

1. **Live acceptance ещё не выполнен.** Первый настоящий `M04-L01-A01.txt` POST и lesson upload должны выполняться только после merge из `main` через owner dispatch. До этого engineering route считается реализованным, но не production-accepted.
2. **Stepik public docs vs фактический API.** Документация Stepik связывает файловое хранилище с платными курсами, тогда как конкретный бесплатный course 299189 фактически объявляет attachment POST capability. Это уже осознанное owner-approved working assumption; capability preflight перед write делает расхождение fail-closed.
3. **Ambiguous attachment POST.** Автоматическое повторение запрещено. Для такого случая потребуется отдельный reconcile/owner route. Это сознательно безопаснее duplicate upload.
4. **Capability-preflight STOP после `EVENT_STARTED`.** До внешнего POST может остаться безопасный incomplete event, требующий reconcile. Это операционное неудобство, но Stepik state при этом не меняется.
5. **PNG/SVG materialization ещё не live-accepted.** Один успешный TXT pilot не разблокирует image/SVG routes и общий bulk upload.

## Merge gate

На проверенном code head:

- CRITICAL = 0;
- HIGH = 0;
- обязательного owner decision до merge нет;
- live Stepik acceptance должен остаться отдельным post-merge owner action;
- `ready_for_bulk_write=false` сохраняется.

**PR #68 одобрен к merge.**
