# Восстановление порядка sections после title-only PUT

**Статус:** guarded production recovery contract  
**Курс:** Stepik `299189`  
**Блокирующая проблема:** Issue `#74`  
**Bulk write:** закрыт, `ready_for_bulk_write=false`

## 1. Что произошло

Owner-dispatched learner-hygiene run `34999937820` выполнил подтверждённый префикс title-only `PUT` для sections M00…M07 и части lessons. Фактический следующий snapshot показал, что у sections M01…M07 поле `position` стало `1`; M00 осталось `1`, M08 осталось `9`.

Root cause: старый section title route отправлял в `PUT /api/sections/{id}` только `title`. Для Stepik `PUT` нельзя считать частичным update: production evidence и внешний API client подтверждают replacement-like semantics. Поэтому section update теперь строится только как schema-guarded read-modify-write `PUT`; `PATCH` не используется без отдельного доказательства реального API contract.

Старые title-events M00…M07 не переписываются. Их `MACHINE_STATE_COMMITTED` подтверждает только тот state, который был записан тогда; section `position` в нём отсутствует и structural correctness из этих records не выводится.

## 2. Exact recovery mapping

| Module | Stepik section | Повреждённое состояние | Цель |
| --- | ---: | ---: | ---: |
| M00 | 755023 | 1 | 1 |
| M01 | 755025 | 1 | 2 |
| M02 | 755027 | 1 | 3 |
| M03 | 755028 | 1 | 4 |
| M04 | 755029 | 1 | 5 |
| M05 | 755030 | 1 | 6 |
| M06 | 755031 | 1 | 7 |
| M07 | 755032 | 1 | 8 |
| M08 | 755033 | 9 | 9 |

M00 и M08 — read-only structural anchors этого recovery. Записи планируются только для M01…M07.

## 3. Frozen unit topology

Recovery не изменяет lesson/unit content и не создаёт/удаляет объекты. До первой записи и после всех записей должен совпасть exact unit→position→lesson layout:

- M00: `2631074/1/2591708`, `2631076/2/2591710`, `2631077/3/2591711`;
- M01: `2631081/1/2591715`, `2631082/2/2591716`;
- M02: `2631083/1/2591717`, `2631084/2/2591718`;
- M03: `2631085/1/2591719`, `2631086/2/2591720`;
- M04: `2631087/1/2591721`, `2631088/2/2591722`, `2631089/3/2591723`;
- M05: `2631090/1/2591724`, `2631091/2/2591725`;
- M06: `2631092/1/2591726`, `2631093/2/2591727`, `2631094/3/2591728`, `2631095/4/2591729`;
- M07: `2631097/1/2591731`, `2631098/2/2591732`;
- M08: `2631100/1/2591734`.

Любой неизвестный section ID, title drift, произвольная position, изменение unit ID/position/lesson binding или другой course ID = `STOP` до dispatch.

## 4. Section update contract после исправления

Перед любым section `PUT` automation обязана:

1. прочитать raw live section;
2. выполнить `OPTIONS /api/sections/{id}`;
3. доказать `PUT` в `Allow` и наличие `actions.PUT` schema;
4. собрать replacement payload из всех текущих writable fields, объявленных schema;
5. наложить только разрешённое изменение (`title` либо `position`);
6. отдельно доказать сохранение `title`, `position` и `course`;
7. завершить весь schema/read-modify-write preflight до `WRITE_DISPATCH_STARTED`;
8. после dispatch не выполнять blind retry при network/5xx/неоднозначном результате.

Для learner-hygiene section title route `position` входит в durable `state_before`/`baseline_after` как отдельный structural invariant и проверяется до и после write. Исторический title fingerprint сохраняется title-only, чтобы не менять identity уже существующих append-only events.

## 5. Read-only preflight

Workflow `.github/workflows/stepik-section-position-recovery.yml` запускается вручную с fixed `course_id=299189`.

При `confirm_write=false` route:

- проверяет current-main guard;
- читает live course;
- проверяет exact section IDs, titles, positions и frozen unit topology;
- читает отдельную recovery history;
- выполняет `GET`/`OPTIONS` replacement preflight для реально повреждённых sections;
- формирует artifacts;
- выполняет **0 Stepik writes**.

Это штатный способ получить свежий live snapshot перед разрешением recovery write.

## 6. Guarded write и WAL

При `confirm_write=true` для каждого реально повреждённого M01…M07 используется отдельный history object `section-position:Mxx`, kind `section-position-recovery`.

Нормальная операция:

`EVENT_STARTED → WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED → OP_READBACK_CONFIRMED`

После каждого `PUT` немедленно проверяются section ID, course, title, target position и unit topology.

`FINAL_READBACK_CONFIRMED` намеренно **не** ставится сразу после отдельного section write. Сначала automation делает fresh all-course snapshot и доказывает одновременно:

- exact section IDs;
- позиции M00…M08 строго `1..9`;
- ожидаемые titles;
- неизменную unit topology.

Только после общего structural PASS каждый незакрытый recovery event получает:

`FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED`.

Так поздний section write не может незаметно испортить ранее «подтверждённый» соседний position.

## 7. Crash recovery

Допустимое автоматическое продолжение:

- event создан, но dispatch не начался, live всё ещё exact malformed state: write может продолжиться;
- `WRITE_COMPLETED + OP_READBACK_CONFIRMED` есть, live уже exact target, но global final не успел: повторный write запрещён, route ждёт/выполняет global final;
- global final есть, `MACHINE_STATE_COMMITTED` не успел: дописывается только commit boundary без Stepik write;
- committed event + exact target live: `ALREADY_RECOVERED`.

Fail-closed случаи:

- ambiguous dispatch;
- known failed dispatch после dispatch boundary;
- failed immediate read-back;
- target position без durable recovery evidence;
- malformed position после подтверждённого dispatch;
- другой source/semantics у incomplete recovery event;
- любой неизвестный live structural state.

Blind retry отсутствует.

## 8. Что recovery не делает

Route не:

- меняет lesson title/body/steps;
- меняет unit position или lesson binding;
- создаёт sections/units/lessons;
- удаляет объекты;
- обновляет Issue `#54`;
- снимает `READ_ONLY_GOLDEN` с M00-L01/M00-L02;
- запускает learner-hygiene автоматически;
- открывает bulk write.

## 9. Gate после recovery

Learner-hygiene остаётся заблокированным до machine PASS section recovery. После PASS требуется fresh snapshot с positions `1..9` и неизменной unit topology.

Только затем можно отдельно запускать learner-hygiene. Ожидаемое продолжение:

- ранее очищенные 23 title классифицируются `already_clean`;
- M00-L01/M00-L02 остаются owner-only golden;
- non-golden остаток: M07-L02, M08 section, M08-L01;
- tracked M02-L01/M04-L01 идут только content-aware route с baseline/WAL/read-back;
- Issue `#54` меняется только после подтверждённой state boundary.

После полного machine PASS владелец повторяет Human Visual Validation: sidebar, M04-L01 body, attachment download, Алиса/GigaChat links, free answer, отсутствие author-only key и правильный порядок модулей.
