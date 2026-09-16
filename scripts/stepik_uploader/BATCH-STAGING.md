# Guarded batch staging для private Stepik

## Назначение

`Stepik Staging Batch Build` устраняет необходимость вручную запускать один и тот же production workflow для каждого ordinary PENDING lesson.

Batch-route **не заменяет** проверенный `staging_build_runtime.py`. Он оркестрирует тот же one-lesson runtime последовательно, сохраняя его live guards, read-back, deployment history и machine-state commit.

## Scope

Workflow автоматически строит scope из current machine state Issue #54, durable deployment history и canonical manifest текущего `main`.

В initial batch допускаются только lessons, которые одновременно:

- присутствуют в canonical manifest;
- имеют `status=PENDING` в Issue #54;
- не являются `READ_ONLY_GOLDEN`;
- не имеют существующего deployment baseline, то есть подходят для initial staging route.

Кроме них planner включает **recovery targets**: ordinary lessons текущего `source_main_sha`, для которых durable history содержит незавершённый deployment event. Это нужно, чтобы повторный batch автоматически завершал доказуемый state/history commit gap даже тогда, когда Issue #54 уже успел получить baseline и убрать lesson из PENDING.

`M00-L01` и `M00-L02` никогда не входят в ordinary batch. Pending `course_page` также не входит: для него нужен отдельный route.

Для уже закрытого lesson исторический incomplete event от старого source SHA не расширяет новый batch scope. Если такой lesson снова становится actual PENDING target, строгий one-lesson preflight сам проверяет всю его incomplete history и останавливает write при stale/ambiguous event. Для нетаргетного lesson batch-recovery рассматривает только incomplete events **текущего** `source_main_sha`.

Если PENDING lesson отсутствует в manifest, initial PENDING конфликтует с существующим baseline, current-source recovery history неоднозначна или её scope нельзя доказать по machine state, planner возвращает blocker и batch не начинает write.

## Один owner dispatch, два автоматических этапа

При `confirm_write=true` один ручной dispatch включает:

1. **All-target preflight.** Каждый initial/recovery target проходит текущий live guard и commit-gap recovery check; initial targets дополнительно проходят `staging_build_runtime.py` без write. До завершения preflight всех targets Stepik content не изменяется.
2. **Sequential write/recovery.** Только если весь preflight завершился успешно и batch scope не изменился, те же targets обрабатываются по одному в canonical order. Для recovery target с доказанным final read-back новый Stepik write не выполняется.

Перед write scope Issue #54 и durable history перечитываются. `source_main_sha` и точный ordered target list обязаны совпасть с initial scope.

## Commit после каждого lesson

После каждого успешного lesson write/recovery batch немедленно:

- проверяет наличие `sync-state.next.json`, journal и lesson event;
- race-check сравнивает Issue #54 с state, прочитанным непосредственно перед lesson;
- PATCH-ит Issue #54;
- фиксирует asset events и lesson event как `MACHINE_STATE_COMMITTED` в durable deployment history;
- добавляет append-only journal comment в Issue #54.

Поэтому уже подтверждённый lesson не зависит от успешности всех последующих targets. При падении batch повторный запуск строит scope заново: committed targets пропускаются, а доказуемые current-source commit gaps включаются в recovery scope. Неоднозначное состояние actual target останавливает batch, а не маскируется.

## Fail-closed правила

Batch сохраняет production invariants one-lesson route:

- только `course_id=299189`;
- только current `main` SHA;
- тот же concurrency lock `stepik-live-course-299189`, поэтому batch и one-lesson workflow не могут писать параллельно;
- private course/private target lesson;
- golden profile должен оставаться confirmed;
- initial write без recovery разрешён только из exact pristine skeleton;
- unknown live content не усыновляется;
- blind retry POST/PUT запрещён;
- physical visual assets проходят deterministic materialization, binding verification и read-back;
- любой blocker, drift, ambiguity или read-back failure останавливает batch до следующего target.

## Финальный machine gate

После успешной записи workflow заново читает Issue #54 и durable history и требует, чтобы ordinary batch planner вернул `target_count=0`.

Это означает отсутствие remaining ordinary initial-staging PENDING lessons и current-source incomplete ordinary deployment events. Это **не** закрывает автоматически:

- `M00-L02` golden canonical/live divergence;
- `course_page`;
- HUMAN VISUAL PASS;
- PED-01 real desktop/phone route;
- PED-03 current live generation/edit;
- PED-06 publication visual check;
- PED-07 final learner-facing UI regression;
- moderator rehearsal, consent/data-minimization и Human Pilot.

## Запуск

После merge workflow запускается вручную из `main`:

- `course_id`: `299189`
- `confirm_write`: `true`

Отдельный batch preflight с `confirm_write=false` остаётся доступен для диагностики, но для production write не обязателен: `confirm_write=true` всегда сначала выполняет полный all-target read-only preflight и только затем открывает последовательную запись/recovery.
