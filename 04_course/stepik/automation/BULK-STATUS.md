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
- learner-ID hygiene regression для canonical Markdown и итогового visible HTML всех 148 steps;
- human-facing canonical title contract;
- owner-only guarded learner-hygiene implementation;
- owner-only controlled first-upload implementation для `M04-L01`;
- transactional attachment materialization contract для `M04-L01-A01.txt`;
- separate asset + lesson deployment history;
- state/history recovery без blind retry.

**Machine acceptance первого upload `M04-L01`: PASS.** Run `34969028781` успешно материализовал TXT attachment, записал 6 learner steps и подтвердил machine-state/history boundary.

**Human Visual Validation после machine PASS: FAIL / RETEST REQUIRED.** Функциональные элементы работали, но learner-facing UI показывал внутренние IDs. Ремедиация описана в [`LEARNER-HYGIENE.md`](LEARNER-HYGIENE.md), а фактологический record обновлён в [`M04-L01-LIVE-ACCEPTANCE-2026-09-15.md`](M04-L01-LIVE-ACCEPTANCE-2026-09-15.md).

При этом:

- `ready_for_bulk_write=false`;
- массовый upload остаётся запрещён;
- повторная Human Visual Validation обязательна после live learner-hygiene migration.

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

После успешной materialization `M04-L01-A01.txt` machine state содержит verified binding. Для следующих write routes остаются 4 non-golden visual sources:

- `05_assets/M03/M03-L02/M03-L02-A03-alice.png`;
- `05_assets/M03/M03-L02/M03-L02-A03.png`;
- `05_assets/M04/M04-L02/M04-L02-A02.svg`;
- `05_assets/M05/M05-L01/M05-L01-A02.svg`.

Learner-hygiene route не материализует новые assets. Для tracked `M04-L01` он повторно проверяет существующий attachment ID, filename, size, URL path и downloaded bytes против canonical SHA-256.

## Verified rendering и learner-ID hygiene

Rendering layer отделён от source compiler и writer.

Контракт:

- local Markdown link не заменяется содержимым прямо внутри предложения;
- инструкция остаётся learner-facing;
- linked Markdown материал добавляется отдельным блоком в тот же Stepik step;
- nested Markdown раскрывается рекурсивно;
- inline H1 материалов очищается от production ID только в learner-visible представлении;
- external/confirmed URLs сохраняются ссылками;
- physical file/image без verified runtime binding даёт `MaterializationRequired`;
- итоговый HTML всех 148 learner steps не содержит repo-relative learner links;
- итоговый visible HTML всех 148 learner steps не содержит internal Lesson/Asset/Exercise/Check IDs;
- author-only material не попадает в learner output.

Canonical ID, asset filename/path, HTML comments и machine metadata не переименовываются и остаются production identity.

## Human-facing title state в bulk-status

Canonical expected title равен human-facing H1 из `lesson.md` без `Mxx-Lxx —`.

Bulk-status различает:

- `HUMAN_EXACT`: live title уже равен canonical human title;
- `LEGACY_PREFIX_EXACT`: live title точно равен `canonical_id — canonical human title`;
- любое другое состояние: blocker как arbitrary/manual title drift.

Точный legacy title не трактуется как отсутствующий lesson и не разрешает duplicate creation.

Для tracked `M02-L01`/`M04-L01`, если live всё ещё совпадает с подтверждённым legacy baseline, status становится `LEARNER_HYGIENE_REQUIRED`, а не ложным `DRIFT_BLOCKED`.

Для `M00-L01/M00-L02` legacy title становится `GOLDEN_TITLE_OWNER_REQUIRED`; обычный writer их не меняет.

## Controlled first upload `M04-L01`

Owner-only run `34969028781` подтвердил маршрут первого upload:

1. current-main guard и общий live mutex;
2. private course/lesson, exact title/language/position;
3. source compilation `M04-L01`;
4. exact publication route TXT;
5. attachment capability preflight;
6. durable WAL до POST/PUT;
7. один attachment POST без retry;
8. attachment list + ID/name/size + download SHA-256 read-back;
9. финальный rendering с фактическим Stepik URL;
10. update исходного placeholder + create remaining five steps;
11. read-back после каждого lesson write;
12. final lesson fingerprint = rendered desired;
13. race-checked Issue state PATCH;
14. `MACHINE_STATE_COMMITTED` после PATCH.

Фактические IDs первого upload:

- Stepik lesson: `2591721`;
- attachment: `239272`;
- steps: `11291289, 11308577, 11308578, 11308579, 11308580, 11308581`;
- asset SHA-256: `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`.

`DELETE` не выполнялся.

Этот исторический one-off route не является обычным update route после learner-hygiene migration.

## Learner-hygiene gate

Owner-only workflow `.github/workflows/stepik-learner-hygiene.yml`:

- фиксирован на course `299189`;
- требует `confirm_write=true`;
- использует общий mutex `stepik-live-course-299189`;
- выполняет current-main guard до runtime;
- section и lesson без content baseline переименовывает только при exact legacy match;
- tracked `M02-L01/M04-L01` обновляет content-aware, потому что title входит в lesson fingerprint;
- arbitrary/manual drift блокирует;
- CREATE/DELETE не использует;
- ambiguous write не ретраит;
- final tracked baseline фиксирует в Issue `#54` только после read-back и race check;
- history commit gap восстанавливает без повторного Stepik write;
- golden lesson titles не меняет автоматически.

## Machine state

Issue `#54` использует schema v3 и хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — post-baseline learner-facing changes.

Сейчас подтверждены baselines `M02-L01` и `M04-L01`, а также verified asset binding `05_assets/M04/M04-L01/M04-L01-A01.txt`.

После merge learner-facing изменений dependency-aware impact обновит PENDING в Issue `#54`; сам push в `main` Stepik не меняет.

## Golden и существующие tracked lessons

- `M00-L01/M00-L02` остаются `READ_ONLY_GOLDEN`;
- canonical golden divergence не даёт права записи в golden;
- legacy golden title cleanup требует отдельного owner-approved решения;
- `M02-L01` остаётся tracked exploitation pilot с baseline/drift guard;
- `M04-L01` имеет confirmed initial-upload baseline;
- existing non-golden content без baseline не усыновляется автоматически;
- arbitrary title drift не переписывается автоматически.

Target-scoped notice `M00-L02` сохраняется: current canonical содержит 8 steps, confirmed live golden — 7.

## Что всё ещё требуется перед `upload-remaining`

До массового write остаются отдельные gates:

1. merge learner-hygiene remediation и owner-dispatched live migration;
2. повторная Human Visual Validation `M04-L01`;
3. transactional materialization/read-back для PNG assets;
4. deterministic SVG→PNG conversion + visual/read-back verification;
5. обобщение initial-upload orchestration с hard-coded `M04-L01` на разрешённый set remaining lessons;
6. общий post-baseline drift guard для всех загруженных lessons;
7. integrity pass для independence/F1-sensitive lessons;
8. private all-course staging verification;
9. Human Pilot readiness по `06_testing`.

До их закрытия `ready_for_bulk_write=false` независимо от успешности pilot upload или learner-hygiene migration.
