# PR #63 — adversarial audit: Stepik deployment history / recovery / reconcile

**Дата:** 2026-09-15  
**PR:** #63 `Stepik: deployment history, partial-write recovery and reconcile`  
**Ветка:** `production/stepik-history-recovery`  
**Scope:** infrastructure only; learner-facing content не меняется; real Stepik writes в рамках разработки = `0`.

## 1. Проверяемые инварианты

Audit проверял не happy path, а возможность ошибочной повторной записи или ошибочного изменения machine state после частичного сбоя.

Обязательные инварианты:

- canonical learner-facing source остаётся current `main`;
- golden `M00-L01/M00-L02` остаются READ_ONLY;
- bulk write и DELETE остаются закрыты;
- HTTP success без read-back не является deployment proof;
- write intent не равен факту начала внешнего write;
- dispatch с неизвестным outcome не может blind-retry;
- partial continuation разрешена только из полностью доказанного prefix;
- final state-only recovery не может переписать посторонний current baseline;
- current Issue state не является event history;
- operational history не становится вторым content source;
- повреждённая или противоречивая history не принимается за доказательство.

## 2. Первый adversarial pass — найденные проблемы

### A. WRITE_INTENT преждевременно означал external write started

**Риск:** crash после durable intent, но до HTTP request, становился неотличим от реально начатого write.

**Исправление:** введён отдельный `WRITE_DISPATCH_STARTED`. `WRITE_INTENT` имеет `external_write_started=false`; только durable dispatch marker переводит event в потенциально внешний write.

### B. Retry/continuation provenance был недостаточно явным

**Риск:** повторный workflow run мог продолжать event без machine-readable связи с origin run.

**Исправление:** records содержат `recorded_by_workflow`; переходы из другого run содержат `event_relationship=RETRY_OR_CONTINUATION_OF_EVENT` с origin run ID. Run-specific recovery/reconcile records имеют attempt-specific IDs.

### C. sync-reconcile не оставлял durable machine-readable evidence

**Риск:** reconcile decision существовал только как transient report и не участвовал в audit trail.

**Исправление:** каждый reconcile run append-ит `RECONCILE_CLASSIFIED`. Reconcile-only record без `EVENT_STARTED` не считается незавершённым deployment event.

### D. Stale baseline evidence мог опираться на недостаточную историю

**Риск:** старое committed состояние, случайно совпавшее с current live, могло выглядеть как доказательство stale Issue baseline.

**Исправление:** stale-baseline evidence использует только последний однозначно доказуемый `MACHINE_STATE_COMMITTED`; equal latest timestamps с разными fingerprints дают conflict/STOP.

### E. Intent-only retry конфликтовал с immutable timestamp payload

**Риск:** semantic-identical retry пытался создать тот же record ID с новым timestamp и блокировал сам себя.

**Исправление:** `WRITE_INTENT` переиспользуется semantic-idempotently только при полном совпадении operation/method/target/fingerprints. Любое отличие = STOP.

### F. MACHINE_STATE_COMMITTED мог быть отмечен без exact final-state validation

**Риск:** успешный Issue PATCH технически мог закрепить baseline, отличный от `FINAL_READBACK_CONFIRMED`.

**Исправление:** status и baseline-after обязаны точно совпасть с final read-back до append `MACHINE_STATE_COMMITTED`.

### G. Recovery мог перезаписать unrelated current baseline

**Риск:** compare-before-PATCH защищает от race после чтения, но не доказывает, что уже прочитанный baseline допустим для конкретного event.

**Исправление:** incomplete event допускает current baseline только `baseline-before` или уже доказанный `final`. Третье значение = `MACHINE_STATE_DIVERGED_DURING_EVENT` / owner STOP.

## 3. Второй adversarial pass — найденные проблемы

### H. Critical: confirmed prefix + unresolved later dispatch разрешал duplicate write

Сценарий:

1. operation 1 получила `WRITE_COMPLETED` + `OP_READBACK_CONFIRMED`;
2. operation 2 получила `WRITE_DISPATCH_STARTED`;
3. process умер до result/read-back operation 2;
4. fresh live всё ещё совпадает с confirmed intermediate после operation 1.

Старый classifier мог увидеть last confirmed intermediate и разрешить `AUTO_CONTINUE_FROM_CONFIRMED_PREFIX`, повторив operation 2 при неизвестном server-side outcome.

**Исправление:** continuation разрешена только если все уже начатые dispatch полностью подтверждены `WRITE_COMPLETED` + per-operation read-back и нет более позднего unresolved dispatch. Любой `writes_started - confirmed_operations > 0` = STOP. Отдельные regression tests покрывают crash after dispatch, completed-without-readback и known failure after prefix.

### I. Known failure после confirmed prefix мог ошибочно попасть в partial continuation

**Риск:** `WRITE_FAILED_KNOWN` следующей operation не должен превращаться в автоматический новый dispatch под тем же operation ID.

**Исправление:** known-failure branch классифицируется раньше partial continuation. Новый внешний retry требует explicit owner-directed attempt identity.

### J. Arbitrary exception после dispatch ошибочно считался FAILED_KNOWN

**Риск:** локальная/programming ошибка могла быть записана как доказательство того, что Stepik точно ничего не применил.

**Исправление:** только доказанный `StepikAPIError` known-failure path получает `WRITE_FAILED_KNOWN`; любой непредусмотренный exception после durable dispatch считается `WRITE_AMBIGUOUS`.

### K. Operational history доверялась без полного integrity gate

**Риск:** вручную повреждённые или внутренне противоречивые records могли использоваться recovery как evidence; branch protection/rulesets в текущем scope отсутствуют.

**Исправление:** перед recovery/reconcile валидируются stable event ID, directory/identity match, единая logical identity records, schema/record IDs, cardinality ключевых phases, intent→dispatch→result→read-back chain, APPLIED/NOOP consistency и exact final/committed relationship. Нарушение = STOP.

## 4. Mandatory failure scenarios после исправлений

Покрыты automated tests:

- successful APPLIED logical event;
- NOOP event без external writes;
- failure до первого Stepik write;
- intent сохранён, dispatch не начинался;
- ambiguous API/network/5xx result;
- known 4xx failure;
- arbitrary exception after dispatch;
- failed operation read-back;
- final read-back missing;
- state PATCH/history handshake failure;
- multi-step crash между operations;
- confirmed prefix + unresolved later dispatch;
- completed later write без read-back;
- duplicate logical retry / semantic intent reuse;
- new main during recovery;
- human/manual change after partial automation write;
- stale machine baseline from latest committed history only;
- conflicting latest committed history;
- unrelated current baseline during incomplete event;
- reconcile-only durable evidence;
- tampered logical identity / result-without-dispatch / conflicting results;
- golden/structural fail-closed.

## 5. CI evidence

Финальный code+contract HEAD перед добавлением этого review-файла: `bb322a75696ad3ba192974e59623e904a8897406`.

GitHub Actions:

- workflow: `Stepik Uploader`;
- run ID: `34926355087`;
- job: `Тесты и structural dry-run`;
- job ID: `104245144591`;
- result: `success`;
- unit tests: `137/137 OK`;
- structural dry-run step: `success`;
- PR impact job: skipped as expected;
- live job: skipped as expected;
- real Stepik writes during audit/development: `0`.

Предыдущие green checkpoints также использовались во время исправлений, но merge decision опирается на указанный финальный code+contract run.

## 6. Residual risks / не-blocking

### Application-level immutability, не repository-level protection

History branch защищена от rewrite/contradiction кодом и integrity gate. Branch protection/rulesets/GitHub Environment намеренно не менялись, поскольку это исключено из scope. Пользователь с достаточными repository permissions теоретически способен сфальсифицировать полностью согласованный набор records. Это trust-boundary репозитория, а не открытый recovery bug текущего PR.

### Current-main guard имеет неизбежное TOCTOU окно

Workflow проверяет fresh `main` перед live phase, а event навсегда привязан к source SHA; новый main блокирует закрытие/continuation старого event. Без блокировки merge или внешней транзакционной координации невозможно атомарно связать GitHub ref с Stepik HTTP write. Текущий контракт fail-closed сохраняет provenance и не позволяет stale event закрыть новый pending. Более строгая per-dispatch remote-main recheck может быть отдельным hardening stage, но не устраняет атомарное окно полностью.

### History root scalability

Текущий discovery перечисляет event directories через GitHub Contents API. При очень большой многолетней history потребуется sharding/index/tree-based discovery. Для текущего курса/этапа это эксплуатационный scalability backlog, не correctness blocker.

### GitHub Actions Node warning

CI показывает deprecation warning для Node 20 actions, которые GitHub runner принудительно выполняет на Node 24. Checks зелёные; это dependency-maintenance backlog, не blocker этого PR.

## 7. Final verdict

**OPEN CRITICAL: 0**  
**OPEN HIGH: 0**  
**OWNER DECISION REQUIRED BEFORE MERGE: 0**

PR можно merge после двух последних механических проверок:

1. current `main` не ушёл вперёд относительно проверенной base без повторной оценки diff;
2. PR mergeable, а delta после финального green code+contract HEAD состоит только из этого review artifact.

Learner-facing content, canonical IDs, F1, golden lessons, bulk/DELETE policy этим PR не изменяются.
