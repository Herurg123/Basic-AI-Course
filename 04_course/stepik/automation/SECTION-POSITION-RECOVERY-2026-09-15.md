# Stepik section position recovery — 2026-09-15

Статус: **production blocker / guarded one-off recovery**.

Связанный incident: GitHub issue #74. Целевой курс: Stepik `course_id=299189`.

## Что произошло

Owner-dispatched learner hygiene run `34999937820` выполнял title-only `PUT /api/sections/{id}` с payload, содержащим только `title`. После этого у sections M01–M07 поле `position` стало `1`; M00 осталось `1`, M08 осталось `9`. Run `35007565631` на текущем тогда `main` обнаружил структуру fail-closed и не выполнил новых Stepik writes.

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

## Дополнительное production evidence: detail OPTIONS непригоден

После merge PR #76 owner-dispatched read-only recovery run `35013088945` был запущен из `main` SHA `cc4fb41e6b834a4e724ab09fd981c7db5e0e4359` с `confirm_write=false`.

Он подтвердил правильный recovery plan: ровно семь операций M07 → M01, M00/M08 как sentinels, `stepik_writes=0`. Но preflight был безопасно остановлен на `OPTIONS /api/sections/755032` с HTTP 500. Повторный запуск failed job с теми же read-only параметрами дал тот же HTTP 500 и снова `stepik_writes=0`.

Следовательно, detail `OPTIONS` нельзя использовать как production safety oracle для section PUT.

## Исправленный write-contract

Section write больше не имеет права отправлять короткий `PUT` только с изменяемым полем и больше не зависит от detail `OPTIONS`.

`section_write.py` перед каждым section PUT:

1. читает **raw section object** через GET;
2. требует наличие и корректный тип structural identity fields: `id`, `course`, `units`, `position`, `title`;
3. разрешает только явный override `title` или `position`;
4. делает deep copy **всего raw GET object**;
5. меняет в копии только один явно переданный authored field;
6. отправляет полный raw-derived object как `PUT /api/sections/{id}`;
7. после PUT повторно читает raw section;
8. требует точного результата для override и точного сохранения всех остальных полей, кроме узкого набора server/viewer-managed полей (`actions`, `progress`, `slug`, `update_date` и других явно перечисленных derived fields).

Это read-modify-write контракт: опасность omission reset устраняется тем, что ни одно поле исходного raw объекта не опускается из payload. Если Stepik отвергнет полный payload, write считается известной ошибкой и recovery останавливается. Любой 5xx/network outcome после dispatch считается ambiguous и blind retry запрещён.

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
- успешный raw-GET full-object read-modify-write contract для **всех** ещё не восстановленных sections до первого write.

Writes выполняются в порядке M07 → M01. После каждого отдельного PUT:

- raw read-back подтверждает target position и сохранность authored fields;
- WAL содержит WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED;
- полный course snapshot перечитывается;
- exact map section positions должен отличаться только уже подтверждёнными recovery operations;
- устойчивый fingerprint title/unit/lesson/step content обязан оставаться неизменным.

Любой ambiguous write, 5xx/network outcome, missing read-back, неожиданный drift, изменённый unit ID или content fingerprint = STOP без blind retry.

## Owner execution sequence после merge исправления

Сначала выполнить workflow **Stepik Section Position Recovery** из нового `main` с:

- `course_id = 299189`
- `confirm_write = false`

Ожидаемый результат: `verdict=READY`, `stepik_writes=0`, семь planned operations M07…M01 и семь raw-GET-derived section PUT contracts. Artifact должен показывать `contract_source=raw-get-full-object-read-modify-write`, `options_required=false` и полный `payload_fields` каждого section.

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
