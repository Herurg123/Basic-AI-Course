# Stepik uploader: безопасная автоматизация

Этот каталог содержит автоматизацию переноса утверждённого курса «ИИ с нуля» в существующий private/staging курс Stepik. Источник истины для содержания остаётся в GitHub `main`; uploader не проектирует уроки заново.

## Текущий подтверждённый статус

Рабочий курс: `course_id=299189`.

Подтверждены следующие контуры:

- `inspect` — READ-ONLY снимок реального курса и проверка двух golden lessons;
- `dry-run` — offline structural manifest и план без Stepik writes;
- `content-test-one` — исторический ограниченный first-write route для `M02-L01`; реальный write, read-back, визуальная проверка и повторный no-op успешно выполнены;
- `staging-build-one` — guarded initial-staging route для одного ordinary PENDING lesson: current-main/private/golden/PENDING guards, WAL/read-back, durable history, machine-state commit и visual materialization; production-путь доказан на нескольких ordinary lessons;
- `staging-batch` — guarded one-dispatch orchestration поверх `staging-build-one`: сначала read-only preflight всего ordinary PENDING scope, затем при едином явном `confirm_write=true` последовательная запись и отдельный state/history commit каждого lesson; повторный запуск подхватывает доказуемые current-source commit gaps;
- `sync-status` — drift-guarded read-only сравнение `desired ↔ live ↔ baseline`;
- `sync-changed` — drift-guarded exploitation update при неизменной структуре, но текущая реализация **жёстко ограничена `M02-L01`**;
- отдельный workflow `Stepik Bulk Status` — READ-ONLY full-course preflight всех 21 уроков и asset inventory.

Не считать существующий `sync-changed` общим bulk-sync. Не считать старые режимы `skeleton`, `assets-test`, `upload-remaining` и `verify` подтверждёнными production write routes: массовый initial staging разрешается только через guarded `Stepik Staging Batch Build`, который переиспользует проверенный one-lesson runtime и останавливается fail-closed при первом blocker/drift/ambiguity.

`M00-L01` и `M00-L02` остаются `READ_ONLY_GOLDEN` для ordinary staging. Текущая canonical-vs-live divergence `M00-L02` и pending `course_page` не входят в batch и требуют отдельных проверяемых reconciliation routes.

После педагогического PR #59 Issue #54 хранит machine backlog относительно текущего канона. Успешный batch должен закрыть ordinary initial-staging PENDING scope, но сам по себе не является all-course human/readiness verdict.

## Guarded ordinary staging

`staging-build-one` является базовым production-контрактом ordinary initial staging. Для конкретного lesson он требует:

- current `main` SHA;
- private course и private target lesson;
- exact canonical title/language/position;
- confirmed golden profile без structural blockers;
- текущий `PENDING` и отсутствие initial deployment baseline, либо доказуемый commit-gap recovery;
- exact pristine skeleton для нового upload без recovery history;
- verified materialization/binding физических learner-facing visual assets, если они нужны;
- последовательные PUT/POST без blind write retry;
- GET read-back каждой операции и финальный read-back;
- PATCH machine state только после подтверждённого live state;
- durable `MACHINE_STATE_COMMITTED` после machine-state commit.

`Stepik Staging Batch Build` не создаёт второй writer. Он строит ordered scope из canonical manifest + Issue #54, исключает golden/course-page, прогоняет **все** targets в read-only режиме и только после успешного all-target preflight открывает последовательные one-lesson writes. Перед write повторно проверяются current `main` и exact batch scope. После каждого lesson state/history фиксируются независимо, поэтому уже подтверждённый lesson не зависит от судьбы следующего.

Если batch падает, повторный запуск заново читает Issue #54 и durable history: committed targets не повторяются, доказуемые current-source commit gaps входят в recovery scope, а stale/ambiguous history блокирует дальнейшие writes. Детальный контракт: [`BATCH-STAGING.md`](BATCH-STAGING.md).

## Подтверждённый pilot M02-L01

`M02-L01` был выбран как обычный не-golden lesson, не отмеченный independence/F1-sensitive.

Первый live write:

- использовал существующий skeleton;
- выполнил последовательные PUT/POST без автоматических write retries;
- после каждой записи выполнил GET read-back;
- после завершения перечитал курс;
- сохранил те же Stepik lesson/step IDs в подтверждённом состоянии;
- прошёл визуальную проверку владельцем.

Повторный запуск дал `NOOP_ALREADY_MATCHES`, `created=0`, `updated=0`.

После этого deployment baseline M02-L01 был bootstrap-записан в Issue #54. Отдельный `sync-status` подтвердил, что на той версии канона `desired == live == baseline`.

Этот checkpoint доказал технический контракт pilot route; последующий guarded staging расширил его через отдельные fail-closed production guards, а batch только оркестрирует уже проверенный one-lesson runtime.

## Exploitation sync contract

После появления baseline обычный content update разрешён только если одновременно:

```text
live == baseline
and
desired != baseline
```

Если:

```text
live != baseline
```

результат обязан быть `DRIFT_BLOCKED`.

Существующий Stepik content не перезаписывается автоматически без подтверждённого baseline. Изменение количества/порядка steps или lesson metadata блокируется отдельным статусом и требует отдельного migration route.

Baseline меняется только после успешного write + read-back. Merge в `main` сам по себе не вызывает live Stepik write.

## Full-course read-only preflight

`Stepik Bulk Status` читает все 21 урок и строит для каждого состояние относительно канона/live/baseline там, где compiler уже доступен.

Он проверяет минимум:

- 9 modules / 21 lessons;
- stable canonical IDs и positions;
- golden protection;
- существующие skeleton placeholders;
- stale titles без создания дублей;
- sensitive/F1 flags;
- asset inventory и SHA-256 физических файлов;
- отсутствие missing source files;
- наличие baseline для уже управляемого content.

Этот режим делает `stepik_writes=0` и никогда сам не открывает bulk write.

## Golden profile

`04_course/stepik/automation/golden-profile.v1.json` фиксирует подтверждённое наблюдение платформенной конвенции:

- M00-L01: 6 Stepik steps, sequence `text, text, text, text, free-answer, text`;
- M00-L02: 7 Stepik steps, sequence `text, text, text, text, text, free-answer, text`;
- free-answer source: `is_attachments_enabled=false`, `is_html_enabled=true`, `manual_scoring=false`;
- Stepik IDs/positions;
- SHA-256 learner-visible HTML golden steps;
- подтверждённые file URLs golden M00-L02.

Golden profile является derived platform-observation fixture, а не вторым источником содержания. Не обновлять его просто потому, что fingerprint не совпал. Любой golden update требует отдельного проверяемого route.

## Локальная проверка без Stepik

Из корня репозитория:

```bash
python -m pip install -r scripts/stepik_uploader/requirements.txt
python -m unittest discover -s tests/stepik_uploader -v
python scripts/stepik_uploader/stepik_uploader.py dry-run --repo-root .
```

Offline `dry-run` обязан сделать ноль API writes. Structural manifest сам по себе не разрешает запись: `write_enabled=false`, а write gates проверяются live перед конкретной операцией.

## GitHub Actions и секреты

OAuth credentials находятся только в GitHub Actions Secrets под именами:

```text
STEPIC_CLIENT_ID
STEPIC_CLIENT_SECRET
```

Не передавать `client_secret`, access token, пароль, cookies или OAuth tokens через чат, issue, PR, workflow input или лог.

Для read-only режимов `confirm_write` остаётся выключенным. Любой разрешённый write-route обязан требовать отдельное явное подтверждение. В batch одно `confirm_write=true` подтверждает exact ordinary scope одного запуска; оно не распространяется на golden/course-page и не отключает all-target preflight или per-lesson guards.

## Идемпотентность и сетевые ошибки

- `DELETE` не используется.
- Golden lessons по умолчанию не входят в обычный write-set.
- GET может повторяться только для временных `429/5xx`.
- POST/PUT автоматически не повторяются.
- Каждая запись получает отдельный read-back до следующей операции.
- Повтор уже совпадающего состояния должен быть no-op/recovery без нового blind write.
- После неопределённого write response сначала читается live state; повторный write вслепую запрещён.
- Batch прекращает переход к следующему target при первом недоказуемом состоянии.

## Stepik Files и assets

Physical assets публикуются только через явно утверждённые и проверяемые routes. Для learner-facing visual assets ordinary staging поддерживает transactional Stepik attachment materialization с отдельными source/materialized hashes, byte/read-back и machine provenance. Это не является разрешением на произвольный generic file upload для любых типов файлов.

Для physical assets действует fail-closed подход:

1. inventory фиксирует Asset ID, source Git path и SHA-256;
2. automation определяет, должен asset быть встроен, показан отдельно или опубликован как файл/attachment;
3. если нужен внешний/Stepik URL, content write блокируется до фактически подтверждённого URL/version;
4. URL никогда не конструируется по догадке;
5. изменение Git hash physical asset считается новым deployment requirement даже при прежней строке URL;
6. untracked same-name attachment автоматически не усыновляется.

Если требуемый route не подтверждён для конкретного asset type, automation останавливается fail-closed и выдаёт точный handoff вместо догадки.

## Особые педагогические блокировки

Compiler обязан сохранять `author_only`, `independence_sensitive` и `f1_sensitive`.

К sensitive lessons относятся как минимум:

- M03-L02;
- M04-L02;
- M05-L02;
- M06-L04;
- M07-L01;
- M07-L02.

Автоматическое склеивание temporal boundaries недопустимо. M07-L02 требует отдельного F1 integrity pass.

Structural dry-run текущего канона показывает 9 modules / 21 lessons / 150 logical steps и `unresolved_assets=[]`, но это только offline source check. Guarded batch перед write выполняет свежий live preflight каждого target и current-main/golden guards.

API success и точный read-back подтверждают техническую запись. Они не заменяют PHONE/COMPUTER staging check, live-service acceptance, HUMAN VISUAL или Human Pilot и не делают `WAVE 0 READY`.
