# Stepik section position recovery — 2026-09-15

Статус: **production blocker / guarded one-off recovery**.

Связанный incident: GitHub issue #74. Целевой курс: Stepik `course_id=299189`.

## Что произошло

Owner-dispatched learner hygiene run `34999937820` выполнял title-only `PUT /api/sections/{id}` с payload, содержащим только `title`. После этого у sections M01–M07 поле `position` стало `1`; M00 осталось `1`, M08 осталось `9`. Run `35007565631` на текущем `main` обнаружил структуру fail-closed и не выполнил новых Stepik writes.

До повреждения run `34999937820` зафиксировал однозначную структуру:

| Module | Section ID | Position | Unit IDs |
|---|---:|---:|---|
| M00 | 755023 | 1 | 2631074, 2631076, 2631077 |
| M01 | 755025 | 2 | 2631081, 2631082 |
| M02 | 755027 | 3 | 2631083, 2631084 |
| M03 | 755028 | 4 | 2631085, 2631086 |
| M04 | 755029 | 5 | 2631087, 2631088, 2631089 |
| M05 | 755030 | 6 | 2631090, 2631091 |
| M06 | 755031 | 7 | 2631092, 2631093, 2631094, 2631095 |
| M07 | 755032 | 8 | 2631097, 2631098 |
| M08 | 755033 | 9 | 2631100 |

Machine-readable копия evidence находится в `section-position-recovery-2026-09-15.v1.json`.

## Исправленный write-contract

Section write больше не имеет права отправлять короткий `PUT` только с изменяемым полем.

`section_write.py` перед каждым section PUT:

1. читает raw section через GET;
2. читает `OPTIONS /api/sections/{id}`;
3. требует, чтобы `PUT` был явно разрешён и `actions.PUT` содержал контракт writable-полей;
4. копирует в payload **каждое** поле, объявленное Stepik writable, из live GET;
5. изменяет только явно переданный override (`title` или `position`);
6. блокируется, если хотя бы одно writable-поле нельзя доказуемо сохранить;
7. после PUT читает raw section повторно и требует точного совпадения всех отправленных writable-полей;
8. дополнительно проверяет неизменность `course` и `units`, если они присутствуют в GET.

Для title hygiene section write дополнительно требует, чтобы live `position` до записи совпадала с canonical position, и подтверждает ту же position после записи.

## Recovery route

Recovery реализован отдельным workflow: `Stepik Section Position Recovery`.

Он не использует обычный learner hygiene route и не меняет title, lesson, unit или step content.

Перед любым write route требует:

- fixed `course_id=299189`;
- private Russian course;
- точный набор девяти section ID из incident baseline;
- точный набор unit ID для каждого section;
- exact live title, зафиксированный после incident;
- canonical target position из текущего manifest;
- для M01–M07 live position только `1` (incident state) или уже восстановленная target position;
- M00 position `1` и M08 position `9` как неизменяемые sentinels;
- успешный OPTIONS-derived full-preserving PUT contract для **всех** ещё не восстановленных sections до первого write.

Writes выполняются в порядке M07 → M01. После каждого отдельного PUT:

- raw read-back подтверждает target position и все preserved fields;
- WAL содержит WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED;
- полный course snapshot перечитывается;
- exact map section positions должен отличаться только уже подтверждёнными recovery operations;
- устойчивый fingerprint title/unit/lesson/step content обязан оставаться неизменным.

Любой ambiguous write, 5xx/network outcome, missing read-back, неожиданный drift, изменённый unit ID или content fingerprint = STOP без blind retry.

## Owner execution sequence после merge

Сначала выполнить workflow **Stepik Section Position Recovery** из `main` с:

- `course_id = 299189`
- `confirm_write = false`

Ожидаемый результат: `verdict=READY`, `stepik_writes=0`, семь planned operations M07…M01 и подтверждённые section PUT contracts.

Только после проверки этого artifact выполнить тот же workflow повторно с:

- `course_id = 299189`
- `confirm_write = true`

Успех recovery означает:

- `verdict=PASS`;
- positions по section IDs точно `1..9`;
- content invariant до/после совпадает;
- writes были только `section.position`;
- journal автоматически добавлен в issues #74 и #54;
- `human_visual_validation=RETEST_REQUIRED`.

После этого можно возвращаться к обычному `Stepik Learner Hygiene` для оставшегося M08 title cleanup и tracked M02/M04, а затем выполнить Human Visual Validation.

До успешного recovery обычный learner hygiene нельзя использовать как способ «самопочинки»: его structural planner обязан оставаться fail-closed на повреждённых positions.
