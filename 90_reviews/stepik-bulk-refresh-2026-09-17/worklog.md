# Stepik existing-course bulk refresh — worklog

Дата: 2026-09-17  
Курс Stepik: `299189`  
Base `main`: `e18cb7d570d42a73d29d20f23c3608e0fe95efb9`  
Ветка: `fix/stepik-existing-course-refresh-2026-09-17`

## Исходный инцидент

Owner запустил `Stepik Private Course Release`, run `35264730769`, после того как курс был временно снят с публикации. Запуск остановился на `Зафиксировать initial machine scope` до любого Stepik write.

Фактическая причина: `staging_batch_plan.py` был маршрутом только для initial staging. После learner-facing rewrite 19 ordinary lessons уже имели confirmed machine baseline, поэтому planner классифицировал их как несовместимые с initial upload и выставил `write_allowed=false`. `M00-L01` и `M00-L02` были отдельно исключены как golden, course page оставалась PENDING.

Подтверждено по workflow log:

- source SHA: `e18cb7d570d42a73d29d20f23c3608e0fe95efb9`;
- `CONFIRM_WRITE=true`;
- `target_count=0`;
- `write_allowed=false`;
- все mutating steps были skipped;
- Stepik writes: `0`.

Инцидент отдельно зафиксирован в durable Stepik sync issue #54. Course `299189` должен оставаться private до успешного полного refresh + read-back.

## Цель исправления

Добавить отдельный fail-closed путь обновления уже существующего private курса без ослабления initial-upload, golden и drift guards.

Не допускается превращать initial uploader в blind overwrite. Existing baseline используется как доказательство допустимого pre-write live state, а не как препятствие.

## Архитектура

### Ordinary lessons

Planner делит PENDING ordinary lessons на:

- `initial_target_ids`: baseline отсутствует, используется прежний initial staging route;
- `refresh_target_ids`: baseline существует, используется новый `staging_refresh_runtime.py`;
- `recovery_target_ids`: current-source immutable history доказывает commit gap закрытого объекта.

Refresh route требует одновременно:

- fixed course `299189`;
- private course и private ru target lesson;
- exact lesson identity/title/position;
- PENDING target;
- confirmed machine baseline;
- live fingerprint, совпадающий с доказанным baseline или подтверждённым WAL prefix;
- отсутствие metadata/structural divergence;
- exact learner step count/positions;
- current main SHA;
- final read-back после каждого PUT и финальный transport-equivalence check.

Разрешены только PUT существующих changed steps. CREATE/DELETE/reorder через ordinary refresh запрещены.

### Physical visual refresh

Rewrite изменил canonical SVG `05_assets/M05/M05-L01/M05-L01-A02.svg`.

Существующий materializer специально запрещает overwrite/delete same-name attachment. Новый refresh сохраняет это правило. Если canonical visual bytes изменились после confirmed baseline:

1. старый attachment сначала проверяется по ID/URL/bytes против machine baseline;
2. новый visual материализуется под детерминированным immutable versioned filename, suffix = первые 12 hex текущего source SHA256;
3. новый attachment загружается отдельным WAL event;
4. bytes read-back подтверждаются;
5. rendered lesson HTML получает verified URL нового attachment;
6. старый attachment не удаляется и не перезаписывается.

Это сохраняет доказуемый rollback/audit trail и исключает unsafe in-place replacement.

### Golden M00-L02

`M00-L02` уже имеет 8-step baseline и остаётся READ_ONLY_GOLDEN для ordinary routes. Existing explicit `golden_content_migration.py` сам маршрутизирует accepted 8-step fixture в guarded 8→8 content refresh при PENDING.

Инварианты: те же 8 IDs/positions, без create/delete/reorder, без block name/source change, content-only PUT + immutable history + final read-back + `golden-profile.next.json`.

### Golden M00-L01

`M00-L01` PENDING, но исторически не имел machine deployment baseline. Добавлен узкий owner-approved one-time route `golden_content_refresh_m00_l01_6to6.py`.

Инварианты:

- exact accepted 6-step target fixture до первого write;
- exact lesson metadata;
- те же 6 step IDs/positions;
- no create/delete/reorder;
- no block name/source changes;
- no attachment writes;
- only changed existing step text/HTML PUT;
- WAL + per-operation read-back + final transport-equivalence;
- после final read-back создаётся первый machine baseline M00-L01 и закрывается PENDING;
- global golden policy остаётся `READ_ONLY`;
- предлагаемый final golden profile строится по финальному live обоих golden lessons и должен идти отдельным evidence/fixture review.

Golden write order в complete release: `M00-L02` затем `M00-L01`. Это сохраняет accepted old fixture во время ordinary refresh и M00-L02 preconditions; M00-L01 final evidence после этого обновляет оба golden rows по final live.

### Durable history commit hardening

`history_cli.py` теперь перед commit machine-state boundary читает immutable event history и считает `identity.object_id/kind/source_sha` авторитетными. Вспомогательный event JSON нормализуется по immutable identity перед выбором baseline. Это исключает возможность закоммитить baseline другого lesson/asset из-за ошибочно подписанного helper artifact.

## Workflow orchestration

`Stepik Private Course Release` теперь:

1. выполняет offline tests/dry-run;
2. фиксирует current main + initial machine scope;
3. выполняет read-only preflight course page, M00-L02, M00-L01 и всех ordinary targets;
4. перед write повторно проверяет current main и неизменность initial/refresh/recovery scope;
5. последовательно применяет ordinary targets, каждый раз читая актуальный Issue #54 state, делая read-back, затем PATCH machine state, затем `MACHINE_STATE_COMMITTED`;
6. синхронизирует course page;
7. обновляет M00-L02;
8. обновляет M00-L01 последним;
9. требует zero PENDING lessons/course page и confirmed 6/8-step golden baselines;
10. сохраняет full evidence artifact.

Повтор старого failed run запрещён как способ деплоя. После merge нужен свежий manual dispatch от current `main`.

## Тесты

Добавлены/изменены unit/static tests для:

- initial vs refresh target planning;
- golden exclusion;
- unknown PENDING blocker;
- versioned visual materialization;
- drift blocking в ordinary refresh;
- changed/unchanged visual planning;
- M00-L01 6→6 shape/type/source invariants;
- immutable history identity normalization;
- complete-release ordering и zero-backlog final gate.

Статус CI/critic заполняется после открытия PR. До PASS всех проверок merge и live Stepik write запрещены.

## Неприкосновенные внешние gates

Это исправление касается только безопасной доставки уже одобренного canonical content в Stepik. Оно не закрывает и не переопределяет реальные launch gates курса:

- PED-01 real-device phone + computer;
- PED-03 live-account free image generation/editing route;
- PED-06 final assembled route/visual check;
- Human Pilot на реальных абсолютных новичках.

Даже успешный Stepik refresh не является автоматическим доказательством public-launch readiness.
