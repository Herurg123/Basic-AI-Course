# Stepik Private Course Release

## Назначение

`Stepik Private Course Release` — owner-scoped orchestration для завершения private staging курса `299189` одним ручным `workflow_dispatch`.

Он не заменяет обычный `Stepik Staging Build` и `Stepik Staging Batch Build`. Обычные маршруты сохраняют прежние границы: golden-уроки не записываются ordinary writer, course page остаётся отдельным объектом. Новый workflow лишь последовательно вызывает уже проверенные ordinary механизмы и два явно одобренных special route.

## Зафиксированные owner decisions

1. `M00-L02`: актуальный canonical GitHub из 8 learner-facing Stepik rows является целевым состоянием. Подтверждённый 7-step live golden должен быть мигрирован в 8-step live.
2. `course-page`: `04_course/stepik/course-page.md` имеет статус `OWNER-APPROVED COPY / production metadata` и является источником целевых текстов карточки курса.

Оба решения зафиксированы в операционном Issue #54. Само решение не является доказательством live write.

## Порядок одного запуска

Workflow всегда работает fail-closed и выполняет этапы в следующем порядке:

1. проверяет `course_id=299189`, current `main`, private course и machine state;
2. выполняет read-only preflight course page;
3. выполняет read-only preflight special migration `M00-L02`;
4. выполняет read-only preflight всех ordinary `PENDING` lessons;
5. только если все preflight прошли, при `confirm_write=true` последовательно пишет ordinary lessons;
6. синхронизирует course page или write-free закрывает уже доказанный commit-gap;
7. **последней** выполняет owner-approved migration `M00-L02` 7→8;
8. проверяет, что lesson backlog и `pending.course_page` пусты, а M00-L02 имеет confirmed 8-step machine baseline;
9. сохраняет полный evidence artifact на 90 дней.

`M00-L02` идёт последним намеренно: старый 7-step golden fixture продолжает защищать live structure на всём ordinary batch. Только после завершения остальных writes выполняется явно одобренное изменение golden content.

## Course page safety

Course-page route:

- разрешён только для private Russian course `299189`;
- требует `is_paid=false`;
- переносит только canonical content fields: title, summary, acquired skills, about/target/requirements/course format, workload и beginner difficulty;
- `acquired_skills` передаётся Stepik как список строк;
- не меняет sections, owner, authors, instructors, tags/categories, language, publication state или paid state;
- после PUT перечитывает course object и требует exact canonical read-back плюс неизменность preserved metadata;
- Issue #54 закрывает `pending.course_page` только после final read-back;
- ambiguous write не ретраится автоматически.

Commit-gap recovery по course page не выполняет Stepik write. В read-only preflight он только доказывает recoverability; durable history дописывается лишь при `confirm_write=true`.

## M00-L02 golden migration safety

Special route фиксирован на `course_id=299189` и `M00-L02`.

До первого write он требует, чтобы live lesson точно совпадал с старым подтверждённым 7-step golden fixture. Затем допускаются только:

- PUT существующих positions 1–7, если canonical compiled step отличается;
- один POST нового position 8.

DELETE, произвольный reorder, запись другого golden lesson и blind retry отсутствуют. После каждого внешнего write требуется operation read-back. Частичный retry допустим только из последнего durable confirmed intermediate fingerprint.

После final read-back route:

- записывает normal machine baseline M00-L02 с 8 step IDs;
- закрывает M00-L02 PENDING;
- создаёт `golden-profile.next.json` из фактического final live;
- валидирует новый fixture против всего live golden profile;
- **не коммитит fixture в `main` из workflow**.

После успешного owner run `golden-profile.next.json` должен быть принят отдельным обычным PR через branch → CI → critic → merge. Для этого дополнительный Stepik write или owner dispatch не нужен.

## Recovery semantics

Повтор того же workflow после частичного сбоя является штатным recovery route:

- уже закрытые ordinary lessons не входят в новый batch scope;
- ordinary commit-gap восстанавливается существующим `staging_commit_gap_recovery.py`;
- уже закрытый course page пропускается;
- доказанный course-page commit-gap закрывается без повторного PUT;
- M00-L02 продолжает только из durable confirmed intermediate state или final history;
- ambiguous / unknown dispatch state всегда останавливает workflow и требует отдельного разбора.

## Что этот workflow НЕ доказывает

Успешный run даёт SOURCE PASS → MACHINE PASS для собранного private Stepik staging. Он не означает автоматически:

- HUMAN VISUAL PASS;
- SERVICE PASS;
- HUMAN VALIDATION PASS;
- старт Human Pilot;
- разрешение публичной публикации курса.

После machine-сборки выполняются отдельные visual/service/readiness gates по действующему governance.
