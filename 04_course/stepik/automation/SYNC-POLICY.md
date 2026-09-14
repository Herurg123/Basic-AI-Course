# Политика эксплуатационной синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Current machine state:** GitHub Issue `#54`  
**Immutable deployment history:** derived branch `stepik-deployment-history-v1`  
**Источник learner-facing содержания:** только актуальный `main`

## 1. Базовый принцип

Merge в `main` не выполняет Stepik write автоматически. Он только определяет learner-facing impact и обновляет machine-readable PENDING в Issue `#54`.

Live sync запускается отдельным owner dispatch. Перед записью automation сверяет current `main`, live Stepik, confirmed baseline и незавершённую deployment history. Неоднозначность означает `STOP`.

Issue `#54` и deployment-history branch являются только эксплуатационным состоянием и не используются как источник содержания курса.

## 2. Закрытые области

- `M00-L01` и `M00-L02` остаются golden `READ_ONLY`;
- общий bulk write закрыт;
- `DELETE` запрещён;
- structural step changes, reorder и неподтверждённые metadata update не применяются обычным route;
- Stepik course page пока не имеет write route;
- automatic adoption/rebaseline неизвестного live state запрещён.

## 3. Три слоя состояния

Система разделяет:

1. **Current machine state** в Issue `#54`: confirmed lesson baselines и активный PENDING.
2. **Immutable deployment/recovery history**: append-only JSON evidence records в `stepik-deployment-history-v1`.
3. **Human-readable comments Issue #54**: журнал результатов, blockers и owner decisions.

Current state отвечает на вопрос «что подтверждено сейчас». History отвечает на вопрос «что реально происходило и что можно доказать после сбоя». Comments помогают человеку, но не заменяют machine evidence.

Schema history: [`DEPLOYMENT-HISTORY.md`](DEPLOYMENT-HISTORY.md). Recovery/reconcile: [`RECOVERY-RECONCILE.md`](RECOVERY-RECONCILE.md).

## 4. Current machine state schema v2

В body Issue `#54` находится один JSON block между markers `STEPIK_SYNC_STATE_V1_BEGIN/END`. Marker name сохранено для migration compatibility; внутренняя `schema_version=2`.

State содержит `course_id`, `updated_at`, `lessons`, `pending.lessons` и отдельный `pending.course_page`.

На один canonical Lesson ID существует один active pending object. Повторный merge сохраняет `first_pending_*`, обновляет `latest_pending_*` и объединяет `source_paths/reason_codes`.

## 5. Закрытие pending

Lesson pending закрывается только после доказанного confirmed state:

- `APPLIED`; или
- `NOOP_CONFIRMED`.

Для нового deployment это требует durable `FINAL_READBACK_CONFIRMED`, после чего next state проходит обычный compare-before-PATCH guard Issue `#54`.

`APPLIED` означает, что в рамках логического event был внешний Stepik write. Это остаётся `APPLIED`, если recovery-run лишь завершил final read-back после ранее подтверждённых step-writes.

`NOOP_CONFIRMED` означает, что логический event не выполнял Stepik write и fresh live уже совпадал с confirmed baseline/canonical state.

Dry-run, status, reconcile-only classification, HTTP success без read-back и partial state pending не закрывают.

## 6. Dependency-aware impact

Impact detector использует `git diff --name-status -M` и before/after dependency graph из repo-relative Markdown links canonical `lesson.md` и `stepik-plan.md`.

Учитываются added, modified, renamed и deleted files. Direct learner content, lesson assets и course page классифицируются отдельно. Shared learner-facing dependency связывается с реальными consumers через graph, а не через второй ручной список.

`author-notes.md`, review-only материалы, tooling/scripts/tests/workflows и `04_course/stepik/automation/**` сами по себе learner PENDING не создают.

Unknown или ambiguous learner dependency = `STOP` без PATCH Issue.

## 7. Baseline и drift

Confirmed lesson baseline хранит canonical Lesson ID, Stepik lesson ID, applied source SHA/time, fingerprint, step IDs и source Git paths.

Normal write разрешён, когда fresh live точно совпадает с baseline, а desired canonical state отличается поддерживаемым способом.

`live != baseline` сначала проходит history-backed reconcile:

- доказанный automation residue может быть recovery case;
- доказанный final automation write с отсутствующим state PATCH может быть state-only recovery;
- committed history, подтверждающая fresh live при отличающемся Issue baseline, классифицируется как `STALE_MACHINE_BASELINE` и требует owner decision;
- unknown/manual origin остаётся `STOP_OWNER_DECISION`.

Совпадение `live == canonical` само по себе не доказывает происхождение и не разрешает auto-rebaseline.

## 8. Deployment history и write-ahead

До каждого внешнего Stepik write durable history обязана получить `WRITE_INTENT`. Intent означает только сохранённое намерение и имеет `external_write_started=false`.

Непосредственно перед HTTP write durable-записывается `WRITE_DISPATCH_STARTED` с `external_write_started=true`. Если intent уже существует с теми же semantic fields и dispatch не начинался, retry переиспользует этот immutable intent; конфликт semantic fields = `STOP`.

History связывает event с canonical object/kind, source SHA, workflow/run identity, state before, desired state, Stepik IDs, per-operation intent/dispatch/result/read-back, final read-back, failure/recovery reason и machine-state commit.

Timeout, network failure, HTTP 5xx или иной неизвестный server-side outcome после dispatch = `WRITE_AMBIGUOUS`; blind retry запрещён.

Доказанный `WRITE_FAILED_KNOWN` допускает обычный guarded retry только когда все dispatch операции завершились known failure, нет ambiguous/read-back evidence и fresh live всё ещё точно совпадает с baseline. Любое live divergence = owner decision.

## 9. Recovery и reconcile

`sync-reconcile` является read-only по отношению к Stepik: читает live state и history, классифицирует ситуацию и не выполняет Stepik write. При этом его `RECONCILE_CLASSIFIED` durable-записывается в operational history с workflow identity текущего run.

Reconcile-only record без `EVENT_STARTED` не считается незавершённым deployment event.

Auto action допустим только когда происхождение доказуемо:

- final read-back доказан, state PATCH отсутствует, fresh live совпадает: state-only recovery, Stepik writes `0`;
- partial prefix подтверждён per-operation read-back, fresh live совпадает с last confirmed intermediate fingerprint: continuation только remaining operations;
- intent сохранён, но dispatch не начинался и baseline/live/source не изменились: normal guarded route;
- все dispatch операции доказанно `FAILED_KNOWN`, live всё ещё baseline: normal guarded route;
- baseline/live совпадают: обычный guarded sync либо no-op.

Owner decision обязателен при manual/unknown drift, ambiguous result, failed read-back без доказательства, stale machine baseline, structural/metadata divergence, golden lesson, conflicting events, missing baseline с неизвестным origin и adoption/rebaseline.

Новый `main` не меняет target уже начатого event. `event.source_sha != current main` блокирует старый recovery и не позволяет ему закрыть новый pending, даже если live совпадает с intermediate fingerprint старого event.

## 10. Race protection

Current machine state PATCH выполняется только по схеме:

`read expected → compute next → re-read current → compare → PATCH only if unchanged`.

После live deployment `MACHINE_STATE_COMMITTED` добавляется в immutable history только после успешного Issue PATCH и только если status/baseline-after PATCH-нутого state точно совпадают с `FINAL_READBACK_CONFIRMED`.

Если final Stepik read-back уже durable-зафиксирован, а PATCH не состоялся, следующий recovery может восстановить state без повторного Stepik write только при достаточном evidence.

## 11. Live safety

Сохраняются:

- fresh current-main guard;
- единый mutex `stepik-live-course-299189`;
- отсутствие blind automatic write retry;
- durable intent → dispatch write-ahead history;
- per-operation и final read-back;
- fail-closed unknown state/dependency;
- запрет destructive recovery и `DELETE`.

Подробности: [`LIVE-SAFETY.md`](LIVE-SAFETY.md).

## 12. Human-readable journal

Comments Issue `#54` остаются append-only human log для PENDING, APPLIED, NOOP, RECOVERED_STATE, blockers и owner decisions.

Comment не является единственным доказательством deployment и не используется вместо machine state/history.

## 13. Ownership matrix

Эксплуатационная ownership matrix находится в [`ownership-matrix.v1.json`](ownership-matrix.v1.json) и проверяется automated completeness test.

Она определяет source of truth, detection/initiation/execution ownership, approval, retry/partial/reconcile/rebaseline policy, mandatory STOP, evidence, state mutation и history event для обязательных классов событий.

Матрица не является вторым content manifest.

## 14. Что этот этап не разблокирует

History/recovery/reconcile не разблокируют общий bulk write, course-page write, golden write, `DELETE` или автоматическое принятие неизвестного live state как baseline.
