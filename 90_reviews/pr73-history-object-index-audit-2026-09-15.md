# PR #73 — adversarial audit history object index

Дата: 2026-09-15

## Контекст инцидента

Owner-run `34999937820` выполнил доказанный префикс learner-facing title cleanup и затем остановился на чтении deployment history с `HTTP 403`.

Durable history показывает завершённый `MACHINE_STATE_COMMITTED` event для `title:lesson:M07-L01`, привязанный к run `34999937820`. Следующая title-only операция по исходному plan — `M07-L02`; новых history commits после завершения M07-L01 до BLOCKED нет. Повторный blind run до исправления history lookup запрещён.

## Root cause

Старый `find_object_events()` для каждого `object_id`:

1. перечитывал root всех deployment events;
2. вызывал `store.load()` для каждого event;
3. `store.load()` перечитывал directory и каждый JSON record;
4. только после этого отбрасывал events другого object.

При growing history это давало нагрузку порядка `objects × events × records` и привело к GitHub API throttling/403 во время long-running hygiene.

## Новый контракт

Для GitHub store:

- каждый object lookup получает свежий recursive Git tree snapshot history branch;
- tree должен быть полным; `truncated=true` => fail closed;
- на event выбирается один immutable anchor blob: `EVENT_STARTED`, если он есть, иначе детерминированно первый JSON record (это сохраняет reconcile-only events);
- anchor identity валидируется: schema, record/phase, stable event identity и соответствие directory event id;
- anchor identity кэшируется только по immutable Git blob SHA;
- новый event, появившийся в ходе текущего run, обнаруживается на следующем tree snapshot;
- полный `store.load(event_id)` выполняется только для anchors с нужным `object_id`;
- после full load identity повторно проверяется; mismatch GitHub index/full event => fail closed;
- MemoryHistoryStore сохраняет прежнюю семантику полного перебора с `continue` для чужих objects.

## Adversarial checks

### A1. Stale cache после новых writes

Проверено regression-тестом: после первого lookup в tree добавляется новый event с новым blob SHA. Следующий lookup видит event, загружает только новый anchor и не перечитывает старые anchors.

Verdict: PASS.

### A2. Index скрывает чужой incomplete event

Index строится не по desired/current event id, а по всем event directories текущего tree snapshot. Поэтому event от старого source/semantics остаётся кандидатом того же `object_id` и будет полностью загружен обычным recovery-кодом.

Verdict: PASS.

### A3. Reconcile-only event без EVENT_STARTED исчезает

Нет: если `EVENT_STARTED` отсутствует, выбирается детерминированно первый JSON record event. `find_incomplete_object_events()` по-прежнему отдельно требует наличие EVENT_STARTED, а `find_object_events()` сохраняет reconcile-only observations.

Verdict: PASS.

### A4. Повреждённый anchor позволяет пропустить event

Нет: malformed blob, неверная schema, отсутствие identity, stable-event mismatch, directory mismatch или truncated tree дают `DeploymentHistoryError` до writer.

Verdict: PASS.

### A5. Оптимизация изменила MemoryHistoryStore recovery semantics

Первый CI выявил регрессию: full Memory store scan ошибочно трактовал нерелевантный event как index mismatch. Исправлено: строгий mismatch применяется только к GitHub indexed route; Memory store сохраняет прежний filter behavior. Старые entrypoint recovery tests снова зелёные.

Verdict: PASS after fix.

### A6. Production Git Trees endpoint предположен без проверки

Read-only проверка реальной branch `stepik-deployment-history-v1` выполнена: recursive Git tree API доступен, содержит history events/records и не показал truncation. Реальный completed event M07-L01 прочитан через contents/blob evidence.

Verdict: PASS.

## CI

- `Stepik Learner Hygiene` PR workflow после fix: SUCCESS.
- `Stepik Uploader` PR workflow после fix: SUCCESS.
- Owner/live jobs на PR: SKIPPED.
- Stepik writes из PR: 0.

## Residual risks

1. History branch продолжит расти. Если recursive tree когда-либо станет `truncated`, route намеренно остановится и потребуется отдельная индексная архитектура, а не silent partial scan.
2. GitHub может применить secondary throttling и к нормальному числу append commits. Текущий fix устраняет доказанный N×full-scan источник нагрузки, но не объявляет GitHub API безлимитным.
3. Run `34999937820` был частично применён: уже подтверждённые title-only writes сохраняются и должны быть распознаны как `already_clean`; откат не требуется и не выполняется.

## Verdict

- OPEN CRITICAL: 0
- OPEN HIGH: 0
- OWNER DECISION REQUIRED BEFORE MERGE: 0
- SAFE TO MERGE: YES
- LIVE RETRY BEFORE MERGE: NO
- BULK WRITE READY: NO
