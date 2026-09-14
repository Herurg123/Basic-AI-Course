# Политика эксплуатационной синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Журнал deployment state:** GitHub Issue `#54`  
**Источник содержания:** только актуальный `main`

## 1. Базовый принцип

После merge в `main` workflow не выполняет Stepik write автоматически. Он только определяет потенциальный learner-facing impact и обновляет machine-readable deployment state в Issue `#54`.

Live sync запускается отдельно владельцем. Перед любой записью он обязан подтвердить, что live Stepik всё ещё совпадает с последним подтверждённым baseline. Drift = STOP.

Issue `#54` хранит только deployment state и append-only журнал операций. Он не является источником содержания курса.

## 2. Что остаётся закрытым

До отдельного решения владельца:

- M00-L01 и M00-L02 остаются golden `READ_ONLY`;
- общий bulk write закрыт;
- автоматический `DELETE` запрещён;
- структурные изменения steps, reorder и неподтверждённые metadata update не применяются автоматически;
- Stepik course page не записывается этим контуром;
- branch protection, rulesets, GitHub Environment и организация secrets не входят в этот контракт.

## 3. Machine-readable sync state

В body Issue `#54` находится единственный machine-readable JSON block между markers:

```text
<!-- STEPIK_SYNC_STATE_V1_BEGIN -->
...
<!-- STEPIK_SYNC_STATE_V1_END -->
```

Имя marker сохранено для миграционной совместимости. Актуальная внутренняя `schema_version` равна `2`.

State содержит:

- `course_id`;
- `updated_at`;
- `lessons` — последние подтверждённые deployment baselines;
- `pending.lessons` — текущий backlog уроков с Git changes, ещё не подтверждёнными в Stepik;
- `pending.course_page` — отдельный pending object для Stepik course page либо `null`.

Существующий schema v1 читается fail-closed и нормализуется в v2 с пустым pending. После следующего успешного PATCH сохраняется schema v2.

## 4. Формат lesson pending

Для каждого canonical Lesson ID хранится один текущий pending object:

```json
{
  "object_id": "M03-L02",
  "kind": "lesson",
  "status": "PENDING",
  "reason_codes": ["direct-lesson-source", "shared-learner-dependency"],
  "source_paths": ["04_course/M03/M03-L02/lesson.md"],
  "first_pending_sha": "<40-char sha>",
  "latest_pending_sha": "<40-char sha>",
  "first_pending_at": "<UTC timestamp>",
  "latest_pending_at": "<UTC timestamp>",
  "confirmed_baseline_ref": null
}
```

Если у урока есть подтверждённый deployment baseline, `confirmed_baseline_ref` содержит ссылку `state_path=lessons.<Lesson ID>` и snapshot ключевых полей baseline: Stepik lesson ID, applied source SHA/time и fingerprint.

Если подтверждённого baseline нет, значение равно `null`; automation не выдумывает baseline.

Повторный merge того же уже pending-урока:

- не создаёт вторую логическую очередь;
- сохраняет `first_pending_sha` и `first_pending_at`;
- обновляет `latest_pending_sha` и `latest_pending_at`;
- объединяет `source_paths` и `reason_codes`.

## 5. Course page pending

`pending.course_page` имеет тот же жизненный цикл, но `kind=course_page` и `object_id=course-page`.

Course page не смешивается с lesson backlog и не закрывается lesson sync.

Пока для course page нет отдельного подтверждённого deployment baseline, `confirmed_baseline_ref` остаётся `null`.

## 6. Когда pending закрывается

Lesson pending удаляется из текущего backlog только после подтверждённого live read-back соответствующего объекта и результата:

- `APPLIED`; или
- `NOOP_CONFIRMED`.

Простой запуск workflow, dry-run, status-check, комментарий или отсутствие планируемой записи pending не закрывают.

Для текущего pilot sync M02-L01 `sync_runtime.py` формирует `sync-state.next.json` только после `result.verified == true`; APPLIED обновляет baseline и закрывает только M02-L01, NOOP_CONFIRMED закрывает только M02-L01 без фиктивной Stepik записи.

## 7. Dependency-aware impact

Impact-detector использует `git diff --name-status -M`, поэтому различает added, modified, renamed и deleted paths.

Для dependency mapping строятся два графа:

- before graph по предыдущему main SHA;
- after graph по новому main SHA.

Граф выводится из repo-relative Markdown links в канонических:

- `04_course/Mxx/Mxx-Lyy/lesson.md`;
- `04_course/Mxx/Mxx-Lyy/stepik-plan.md`.

Ручной второй список consumers не поддерживается.

### Прямые классы impact

Всегда учитываются:

- canonical `lesson.md`;
- canonical `stepik-plan.md`;
- `05_assets/Mxx/Mxx-Lyy/**` как lesson asset;
- `04_course/stepik/course-page.md` как отдельный course-page object.

### Shared learner-facing dependencies

Repo-local dependency link из canonical lesson/plan связывает изменённый target с реальными Lesson ID.

Это покрывает, в частности, общие learner-facing Markdown-файлы в `04_course/stepik/`, например `how-to-save-practice.md`, а также переиспользованные assets другого урока.

Для modified path используется объединение before/after mapping. Для rename учитываются old path из before graph и new path из after graph. Для delete используется before mapping; оставшаяся после delete ссылка на удалённый shared файл является blocker.

### Что не создаёт learner impact само по себе

- `author-notes.md`;
- review-only документы;
- tooling/scripts/tests/workflows;
- файлы `04_course/stepik/automation/**`.

Изменение этих файлов может запускать обычный CI, но не создаёт PENDING курса без фактической learner dependency.

## 8. Unknown dependency = STOP

Любой изменённый shared learner-facing Markdown-файл в `04_course/stepik/` вне `automation/**` и вне `course-page.md` обязан иметь однозначно выводимый canonical consumer mapping.

Если mapping отсутствует, impact job завершается с blocker `unknown-learner-facing-dependency` и не PATCH-ит Issue `#54`.

При rename новый shared path также обязан иметь mapping в after graph. При delete остаточная canonical ссылка на удалённый path блокирует job.

Это намеренный fail-closed режим: лучше красный deployment gate, чем пропущенное изменение learner-facing содержания.

## 9. Race protection Issue #54

Любой автоматический PATCH machine state выполняется только по схеме:

1. прочитать текущий body Issue `#54`;
2. извлечь и нормализовать expected machine state;
3. вычислить следующий state локально;
4. непосредственно перед PATCH снова прочитать Issue;
5. извлечь current machine state;
6. сравнить expected и current;
7. PATCH разрешён только при точном совпадении;
8. если state изменился, STOP без перезаписи.

Append-only комментарий добавляется только после успешного PATCH соответствующего state.

Тот же compare-before-patch используется после `sync-changed`, чтобы live run не затёр pending/baseline update другого процесса.

## 10. Baseline и drift

Подтверждённый lesson baseline хранит как минимум:

- canonical Lesson ID;
- Stepik lesson ID;
- applied source SHA;
- applied timestamp;
- applied fingerprint;
- подтверждённые Stepik step IDs;
- source Git paths, использованные компилятором.

Write разрешается только когда live fingerprint точно совпадает с последним baseline и desired content отличается разрешённым способом.

Если live Stepik отличается от baseline, automation не угадывает происхождение изменения и не перезаписывает его: `DRIFT_BLOCKED`.

## 11. Live safety

Все live jobs подчиняются `LIVE-SAFETY.md`:

- current-main guard;
- единый course mutex `stepik-live-course-299189`;
- отсутствие автоматического write retry;
- read-back после записи;
- fail-closed guards до Stepik API.

## 12. Журналирование

Machine-readable block показывает текущее состояние.

Комментарии Issue `#54` остаются append-only историей событий, например:

- baseline bootstrap;
- PENDING detection/update;
- read-only preflight;
- APPLIED;
- NOOP_CONFIRMED;
- blockers и owner decisions, если они нужны для эксплуатации.

Комментарий не заменяет machine state и не должен использоваться как единственный способ определить текущий pending backlog.

## 13. Следующий этап, который этим документом не реализуется

Отдельно остаются:

- полноценная deployment history как структурированный журнал;
- recovery после partial write или state-patch failure;
- baseline reconcile;
- ownership matrix для типов изменений и ручных решений.

Эти задачи не разблокируют общий bulk write автоматически и выполняются отдельным этапом.
