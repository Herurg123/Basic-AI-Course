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

**Live acceptance `M04-L01`: PASS.** Owner-dispatched run `34969028781` на `main@de98e60b845b51eda4c551cdc55c0c7139c35a55` успешно материализовал TXT attachment, записал 6 learner steps, подтвердил каждый write read-back, final lesson fingerprint, Issue schema v3 и `MACHINE_STATE_COMMITTED` для asset/lesson events. Подробности: [`M04-L01-LIVE-ACCEPTANCE-2026-09-15.md`](M04-L01-LIVE-ACCEPTANCE-2026-09-15.md).

При этом:

- `ready_for_bulk_write=false`;
- массовый upload остаётся запрещён;
- machine acceptance пилота не считается Human Validation.

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
- unresolved routes: 0.

Publication modes:

- `.md` → `inline-source`;
- non-golden `.png` → `stepik-image-upload`;
- `.svg` → deterministic rasterization в PNG → Stepik image upload;
- существующие golden M00-L02 DOCX/PNG → exact `confirmed-url`;
- `M04-L01-A01.txt` → `stepik-attachment-upload`.

До live pilot было 5 unique physical files, требующих materialization. После успешной materialization `M04-L01-A01.txt` machine state уже содержит verified binding для него. Для следующих write routes остаются 4 non-golden visual sources:

- `05_assets/M03/M03-L02/M03-L02-A03-alice.png`;
- `05_assets/M03/M03-L02/M03-L02-A03.png`;
- `05_assets/M04/M04-L02/M04-L02-A02.svg`;
- `05_assets/M05/M05-L01/M05-L01-A02.svg`.

`stepik-attachment-upload` основан на D-2026-09-15-STEPIK-ATTACHMENTS. Live acceptance подтвердил рабочий production route для TXT в бесплатном course `299189`: capability preflight прошёл, POST был выполнен без blind retry, actual attachment был прочитан обратно, bytes совпали с canonical SHA-256.

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

Для `M04-L01` этот contract теперь подтверждён не только offline, но и live final read-back: 6 steps, shape `text,text,text,text,free-answer,text`, lesson fingerprint `sha256:e1633c610ca4e2b03d3b797b93baf2dc97d3e47c43f9fd4f34d809864697e538`.

## Controlled first upload `M04-L01`

Pilot выбран так, чтобы одной live acceptance проверить обычный rendering, настоящий TXT attachment и `free-answer` Check.

Owner-only run `34969028781` подтвердил весь маршрут:

1. `confirm_write=true`;
2. current-main guard и общий live mutex;
3. private course/lesson, exact title/language/position;
4. source compilation `M04-L01`;
5. точный publication route TXT;
6. attachment capability preflight;
7. durable WAL до POST/PUT;
8. один attachment POST без retry;
9. attachment list + ID/name/size + download SHA-256 read-back;
10. финальный rendering с фактическим Stepik URL;
11. update исходного placeholder + create remaining five steps;
12. read-back после каждого lesson write;
13. final lesson fingerprint = rendered desired;
14. отдельные asset и lesson final history events;
15. race-checked Issue state PATCH;
16. `MACHINE_STATE_COMMITTED` для обоих events после PATCH.

Фактические IDs:

- Stepik lesson: `2591721`;
- attachment: `239272`;
- steps: `11291289, 11308577, 11308578, 11308579, 11308580, 11308581`;
- asset SHA-256: `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`.

`DELETE` не выполнялся.

## Machine state

Issue `#54` использует schema v3 и хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — post-baseline learner-facing changes.

После live acceptance в state есть:

- существующий baseline `M02-L01`;
- новый baseline `M04-L01`;
- verified asset binding `05_assets/M04/M04-L01/M04-L01-A01.txt`.

Это позволяет повторно использовать attachment URL только после проверки live attachment и canonical bytes, а не по памяти предыдущего workflow.

## Golden и существующие tracked lessons

- `M00-L01/M00-L02` остаются `READ_ONLY_GOLDEN`;
- canonical golden divergence не даёт права записи в golden;
- `M02-L01` остаётся отдельным tracked exploitation pilot с baseline/drift guard;
- `M04-L01` теперь имеет confirmed initial-upload baseline;
- existing non-golden content без baseline не усыновляется автоматически;
- stale title не означает отсутствующий lesson и не разрешает duplicate creation.

Target-scoped notice `M00-L02` сохраняется: current canonical содержит 8 steps, confirmed live golden — 7. Это не связано с `M04-L01` PASS и не блокирует независимые non-golden gates.

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

До их закрытия `ready_for_bulk_write=false` независимо от успешности pilot upload.
