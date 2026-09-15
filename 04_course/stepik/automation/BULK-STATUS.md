# Read-only preflight всего курса перед массовым Stepik upload

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Workflow:** `Stepik Bulk Status`  
**Источник содержания:** актуальный `main`

## Назначение

`bulk-status` остаётся read-only gate перед будущим `upload-remaining`. Он читает фактический курс Stepik, machine state из Issue `#54`, canonical manifest, source-compiled learner steps, learner dependency graph и asset publication policy.

Этот режим **никогда не пишет в Stepik** и не изменяет Issue `#54`.

## Текущий статус gates

Закрыты на уровне engineering/offline verification:

- structural manifest всех 21 lessons;
- general source compiler;
- author-only filtering;
- asset route resolution 49/49 dependency occurrences;
- verified rendering всех 21 lessons / 148 learner-facing steps при наличии verified physical bindings;
- context-aware inline Markdown adaptation;
- owner-only controlled first-upload implementation для `M04-L01`;
- transactional attachment materialization contract для `M04-L01-A01.txt`;
- separate asset + lesson deployment history;
- state/history recovery без blind retry.

**Не выполнен:** реальный live acceptance `first-upload-m04-l01` на current `main`.

Поэтому:

- `ready_for_bulk_write=false`;
- массовый upload остаётся запрещён;
- инженерная готовность pilot route не считается фактической materialization или Human Validation.

## General source compiler

Текущий all-course contract:

- 21 canonical lessons;
- 150 structural plan rows;
- 2 author-only rows исключаются;
- 148 learner-facing source-compiled rows;
- learner-facing `lesson.md` сохраняется в исходном порядке;
- `free_answer_source` берётся только из confirmed golden profile;
- compiler сам не разрешает write.

## Asset publication resolution

Текущий topology contract:

- 48 direct repo-relative links;
- 49 dependency occurrences с nested dependency;
- 43 уникальных source-файла;
- topology fingerprint `sha256:ecbb9f9b8426c5bd4bba9f07816ab0e647022c13c0f38b4c29d9debd6096c20d`;
- unresolved routes: 0;
- 5 unique physical files требуют materialization перед финальным rendering соответствующих steps.

Publication modes:

- `.md` → `inline-source`;
- non-golden `.png` → `stepik-image-upload`;
- `.svg` → deterministic rasterization в PNG → Stepik image upload;
- существующие golden M00-L02 DOCX/PNG → exact `confirmed-url`;
- `M04-L01-A01.txt` → `stepik-attachment-upload`.

`stepik-attachment-upload` основан на D-2026-09-15-STEPIK-ATTACHMENTS. API discovery подтвердил для course `299189`: существующие lesson attachments, `POST /api/attachments`, `multipart/form-data`, required writable `file` типа `file upload` и writable `lesson`.

Capability проверяется повторно перед реальным POST. Изменение API/permission/plan = fail-closed STOP.

## Verified rendering

Rendering layer отделён от source compiler и от writer.

Контракт:

- local Markdown link не заменяется содержимым прямо внутри предложения;
- инструкция остаётся learner-facing;
- linked Markdown материал добавляется отдельным блоком в тот же Stepik step;
- nested Markdown раскрывается рекурсивно;
- external/confirmed URLs сохраняются ссылками;
- physical file/image без verified runtime binding даёт `MaterializationRequired`;
- после verified bindings итоговый HTML всех 148 learner steps не содержит repo-relative learner links;
- author-only material не попадает в learner output.

Без runtime bindings физической materialization сейчас требуют:

- `05_assets/M03/M03-L02/M03-L02-A03-alice.png`;
- `05_assets/M03/M03-L02/M03-L02-A03.png`;
- `05_assets/M04/M04-L01/M04-L01-A01.txt`;
- `05_assets/M04/M04-L02/M04-L02-A02.svg`;
- `05_assets/M05/M05-L01/M05-L01-A02.svg`.

## Controlled first upload `M04-L01`

Pilot выбран так, чтобы одной live acceptance проверить обычный rendering, настоящий TXT attachment и `free-answer` Check.

Owner-only mode `first-upload-m04-l01`:

1. требует `confirm_write=true`;
2. проходит current-main guard и общий live mutex;
3. подтверждает private course/lesson, exact title/language/position;
4. source-compiles `M04-L01`;
5. проверяет точный publication route TXT;
6. повторяет attachment capability preflight;
7. до POST создаёт durable WAL history;
8. attachment POST не ретраится;
9. подтверждает attachment через list + ID/name/size + download SHA-256;
10. строит финальный rendering только с фактическим verified URL;
11. создаёт/обновляет только steps существующего skeleton lesson;
12. после каждого PUT/POST выполняет read-back;
13. final lesson fingerprint должен совпасть с rendered desired;
14. asset и lesson получают отдельные final history events;
15. Issue state обновляется race-checked только после полного read-back;
16. history получает `MACHINE_STATE_COMMITTED` только после Issue PATCH.

Если state PATCH или history commit обрывается после verified live write, повторный run может завершить только доказанную state/history часть без повторных Stepik writes.

`DELETE` отсутствует.

## Machine state

После первого успешного first-upload Issue `#54` перейдёт на schema v3. Старые schema v1/v2 при чтении нормализуются без потери lesson baseline.

Schema v3 разделяет:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — post-baseline learner-facing changes.

Это позволяет повторно использовать attachment URL только после проверки live attachment и canonical bytes, а не по памяти предыдущего workflow.

## Golden и существующие tracked lessons

- `M00-L01/M00-L02` остаются `READ_ONLY_GOLDEN`;
- canonical golden divergence не даёт права записи в golden;
- `M02-L01` остаётся отдельным tracked exploitation pilot с baseline/drift guard;
- existing non-golden content без baseline не усыновляется автоматически;
- stale title не означает отсутствующий lesson и не разрешает duplicate creation.

## Что всё ещё требуется перед `upload-remaining`

После успешного live acceptance `M04-L01` остаются отдельные gates:

1. transactional materialization/read-back для PNG assets;
2. deterministic SVG→PNG conversion + visual/read-back verification;
3. обобщение initial-upload orchestration с hard-coded `M04-L01` на разрешённый set remaining lessons;
4. общий post-baseline drift guard для всех загруженных lessons;
5. integrity pass для independence/F1-sensitive lessons;
6. explicit stale-title metadata route без duplicate creation;
7. private all-course staging verification;
8. Human Pilot readiness по `06_testing`.

До их закрытия `ready_for_bulk_write=false` независимо от успешности одного pilot upload.
