# Learner-facing hygiene для Stepik

## Назначение

Этот production-контур устраняет внутренние ID проекта из интерфейса, который видит ученик, не меняя стабильную внутреннюю идентичность объектов в GitHub и machine state.

Внутренние идентификаторы вида:

- `M04-L01`;
- `M04-L01-A01`;
- `M04-L01-E01`;
- `M04-L01-C01`;

остаются допустимыми в canonical paths, production metadata, HTML comments, deployment history и Issue `#54`, но не должны требоваться ученику и не должны отображаться в learner-facing тексте Stepik.

`ready_for_bulk_write=false` независимо от прохождения этого контура.

## Human-facing title contract

Канонический заголовок урока для ученика равен H1 из `lesson.md` без добавления canonical ID.

Пример:

- внутренний ID: `M04-L01`;
- canonical human title: `Получите ответ по безопасному исходнику`;
- старый Stepik title: `M04-L01 — Получите ответ по безопасному исходнику`;
- целевой Stepik title: `Получите ответ по безопасному исходнику`.

Для автоматической миграции принимаются только два состояния:

1. точный canonical human title;
2. точный legacy title `canonical_id — canonical human title`.

Любой другой title считается manual/unknown drift и блокирует автоматическую запись. Совпадение только по фрагменту ID недостаточно.

## Learner body contract

All-course regression проверяет:

- видимый Markdown всех canonical `lesson.md`;
- видимый HTML итогового verified rendering;
- все 21 canonical lesson title.

Проверяются все 148 learner-facing steps. Hidden HTML comments и link destinations могут сохранять production IDs, потому что это служебный слой. Видимые link labels и обычный learner text проверяются.

Inline Markdown assets в verified rendering получают смысловой H1 без production ID. Исходное имя/путь asset при этом не переименовывается.

## Два класса title migration

### 1. Title-only metadata

Для sections и lessons без подтверждённого content baseline разрешён только `PUT title` при точном legacy match.

Контур использует:

`WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → read-back → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED`.

Network failure или HTTP 5xx после dispatch классифицируются как ambiguous. Blind retry запрещён.

`CREATE` и `DELETE` не используются.

Title-only metadata не имеет отдельного baseline в Issue `#54`. Поэтому если `FINAL_READBACK_CONFIRMED` уже доказан, но run упал до `MACHINE_STATE_COMMITTED`, entrypoint может дописать только history commit без повторного Stepik write. Это разрешено и после продвижения `main`, потому что подтверждается уже существующий immutable event, а не выполняется новая миграция.

Partial/ambiguous history без final read-back автоматически не усыновляется.

### 2. Tracked lessons с content baseline

`M02-L01` и `M04-L01` уже имеют подтверждённые deployment baselines. Их нельзя переименовывать отдельным title-only PUT, потому что title входит в lesson fingerprint.

Для них используется content-aware learner hygiene event:

1. live lesson ID должен совпасть с Issue `#54` baseline;
2. до первого write live fingerprint должен совпадать с baseline;
3. durable baseline lesson snapshot фиксируется до dispatch;
4. title update и изменённые learner steps планируются как один последовательный event;
5. после каждой операции выполняется full-lesson read-back;
6. final desired fingerprint должен совпасть с фактическим Stepik;
7. новый baseline формируется только после final read-back;
8. Issue `#54` меняется с race guard;
9. `MACHINE_STATE_COMMITTED` добавляется только после подтверждённого machine-state boundary.

Если run упал после final read-back и успешного Issue PATCH, следующий run может завершить только history commit без нового Stepik write. Если live соответствует лишь промежуточному prefix, продолжение допускается только когда тот же prefix доказан per-operation history.

## Asset contract во время hygiene

Learner hygiene не является asset-materialization route.

Для tracked lesson, где verified rendering требует физический Stepik asset, должен существовать уже подтверждённый asset baseline. Runtime повторно проверяет:

- source path;
- canonical SHA-256;
- Stepik lesson ID;
- attachment ID;
- filename;
- size;
- URL path;
- фактически скачанные bytes.

При несовпадении write блокируется. Новые attachment POST в learner-hygiene route не выполняются.

## Golden protection

`M00-L01` и `M00-L02` остаются `READ_ONLY_GOLDEN`.

Если их live title содержит legacy ID prefix, состояние классифицируется как:

`GOLDEN_TITLE_OWNER_REQUIRED`.

Обычный learner-hygiene writer не имеет права менять эти два lesson title. Это намеренная защита, а не незакрытый технический дефект PR.

Section title, содержащий `M00`, не является golden lesson content и может быть очищен обычным exact-match title route, если live golden lesson integrity при этом полностью подтверждена.

## Owner workflow

Live migration выполняется только workflow:

`.github/workflows/stepik-learner-hygiene.yml`

Условия:

- только manual `workflow_dispatch`;
- фиксированный `course_id=299189`;
- `confirm_write=true`;
- общий mutex `stepik-live-course-299189`;
- `cancel-in-progress=false`;
- current-main guard до runtime;
- Issue `#54` читается до write;
- tracked machine-state update проходит race compare;
- history commit выполняется после machine-state boundary;
- технические artifacts сохраняются;
- Human Visual Validation после write остаётся обязательной.

PR-trigger этого workflow запускает только offline tests. Stepik credentials в PR job не передаются, live job пропускается.

## Fail-closed состояния

Автоматический hygiene прекращается при любом из следующих состояний:

- arbitrary/manual title drift;
- duplicate/ambiguous section или lesson position;
- golden live integrity drift;
- tracked live fingerprint не совпадает с baseline или доказанным recovery prefix;
- несколько incomplete events одного объекта;
- dispatch без доказанного COMPLETED + read-back;
- ambiguous write;
- известный write failure;
- повреждённый durable history;
- stale/mismatching asset baseline;
- unresolved verified rendering;
- current workflow запущен не с актуального `main`.

Во всех этих случаях blind retry запрещён.

## Acceptance этого контура

До merge кода требуется:

- 0 открытых CRITICAL;
- 0 открытых HIGH;
- all-course learner-ID regression PASS;
- все 148 learner-facing rendered steps без видимых internal IDs;
- workflow safety tests PASS;
- recovery/adversarial tests PASS;
- Stepik writes из PR = `0`.

После merge и owner-dispatched live hygiene требуется повторная Human Visual Validation `M04-L01`. Только после неё можно изменить его Human status с `FAIL / RETEST REQUIRED` на PASS.

Этот контур не разрешает массовый upload остальных уроков и не заменяет remaining production gates.
