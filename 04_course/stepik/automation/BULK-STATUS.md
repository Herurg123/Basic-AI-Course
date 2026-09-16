# Read-only preflight всего курса перед массовым Stepik upload

**Статус:** production automation contract  
**Дата актуализации статуса:** 16 сентября 2026 года  
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
- state/history recovery без blind retry;
- guarded section-position recovery implementation;
- owner-approved exact golden-title migration implementation.

Закрыты отдельные production incidents/gates:

- **M04-L01 initial machine acceptance:** run `34969028781`;
- **section positions:** recovery run `35015060946` вернул exact positions `1..9` без lesson/unit/step content drift;
- **M02 partial-write recovery:** run `35078545526` завершил recovery без повторного PUT уже принятого step;
- **M04 learner hygiene:** run `35079859897` — PASS, final fingerprint `sha256:56aca7da0220b8dfba35f299a80f7324bca885f8ac70636e8f987167dde915c4`;
- **Human Visual Validation remediation:** owner подтвердил M04/M07/M08 learner surfaces, order, attachment/links/free-answer и отсутствие проверенных learner IDs;
- **golden title cleanup:** production run `35086056899` изменил ровно два title M00-L01/M00-L02; PR #83 принял post-write fixture; final owner HVA — PASS.

Исторический `FAIL / RETEST REQUIRED` после первого M04 upload не является текущим HVA verdict: remediation и retest завершены. Он сохраняется только в датированном historical acceptance record.

При этом:

- `ready_for_bulk_write=false`;
- массовый upload остаётся запрещён;
- перечисленные PASS охватывают ограниченные production surfaces, а не all-course canonical equivalence.

Current Issue #54 содержит confirmed baselines только для `M02-L01` и `M04-L01`, verified binding для `M04-L01-A01.txt`, **18 PENDING lessons** и отдельный pending course-page. Поэтому current private course не считается доказанно эквивалентным актуальному `main`.

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
- unresolved source routes: 0.

Publication modes:

- `.md` → `inline-source`;
- non-golden `.png` → `stepik-image-upload`;
- `.svg` → deterministic rasterization в PNG → Stepik image upload;
- существующие golden M00-L02 DOCX/PNG → exact `confirmed-url`;
- `M04-L01-A01.txt` → `stepik-attachment-upload`.

После успешной materialization `M04-L01-A01.txt` machine state содержит verified binding. Для следующих write routes остаются 4 non-golden visual sources, которым ещё нужен physical materialization/read-back:

- `05_assets/M03/M03-L02/M03-L02-A03-alice.png`;
- `05_assets/M03/M03-L02/M03-L02-A03.png`;
- `05_assets/M04/M04-L02/M04-L02-A02.svg`;
- `05_assets/M05/M05-L01/M05-L01-A02.svg`.

Для PED-06 два M03 PNG являются не просто source dependencies: Human Pilot readiness требует доказать, что оба реально опубликованы/видимы и показываются в правильной learner branch без второго аккаунта.

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

All-course offline learner-ID PASS не доказывает, что current live Stepik уже содержит эту версию. После актуальной private staging-сборки требуется итоговый HUMAN VISUAL PASS learner-facing UI.

## Human-facing title state в bulk-status

Canonical expected title равен human-facing H1 из `lesson.md` без `Mxx-Lxx —`.

Bulk-status различает:

- `HUMAN_EXACT`: live title уже равен canonical human title;
- `LEGACY_PREFIX_EXACT`: live title точно равен `canonical_id — canonical human title`;
- любое другое состояние: blocker как arbitrary/manual title drift.

Точный legacy title не трактуется как отсутствующий lesson и не разрешает duplicate creation.

Для tracked `M02-L01`/`M04-L01`, если live совпадает с подтверждённым legacy baseline, status становится `LEARNER_HYGIENE_REQUIRED`, а не ложным `DRIFT_BLOCKED`.

Для read-only golden normal writer сохраняет запрет записи. Исторический `GOLDEN_TITLE_OWNER_REQUIRED` для M00-L01/M00-L02 уже закрыт отдельной owner-approved migration `35086056899`; live titles и strict observation fixture теперь human-facing. Это не разрешает automatic golden rebaseline/content write.

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
- mutating mode требует `confirm_write=true`;
- read-only preflight строит inspectable plan при `confirm_write=false`;
- использует общий mutex `stepik-live-course-299189`;
- выполняет current-main guard до runtime;
- section и lesson без content baseline переименовывает только при exact legacy match;
- tracked `M02-L01/M04-L01` обновляет content-aware, потому что title входит в lesson fingerprint;
- arbitrary/manual drift блокирует;
- CREATE/DELETE не использует;
- ambiguous write не ретраит;
- final tracked baseline фиксирует в Issue `#54` только после read-back и race check;
- history/partial-write gaps восстанавливает без blind retry;
- golden lesson titles обычным route не меняет.

Известная remediation-цепочка M02/M04/non-golden title hygiene завершена production writes и HVA. Наличие этого route не закрывает PENDING для остальных lessons.

## Machine state

Issue `#54` использует schema v3 и хранит отдельно:

- `lessons` — confirmed lesson baselines;
- `assets` — verified physical asset bindings;
- `pending` — post-baseline learner-facing changes.

На baseline 16.09.2026 подтверждены baselines `M02-L01` и `M04-L01`, а также verified asset binding `05_assets/M04/M04-L01/M04-L01-A01.txt`.

PENDING lessons: `M00-L02`, `M00-L03`, `M01-L01`, `M01-L02`, `M02-L02`, `M03-L01`, `M03-L02`, `M04-L02`, `M04-L03`, `M05-L01`, `M05-L02`, `M06-L01`, `M06-L02`, `M06-L03`, `M06-L04`, `M07-L01`, `M07-L02`, `M08-L01` — всего 18. Отдельно pending: `04_course/stepik/course-page.md`.

Push в `main` сам Stepik не меняет. PENDING не является автоматическим rebaseline и остаётся blocking evidence для claim об актуальной all-course equivalence.

## Golden и существующие tracked lessons

- `M00-L01/M00-L02` остаются `READ_ONLY_GOLDEN` для ordinary writer;
- canonical golden divergence не даёт права content write/rebaseline;
- exact legacy title cleanup уже выполнен отдельным owner-approved route и прошёл HVA;
- `M02-L01` остаётся tracked exploitation lesson с baseline/drift guard;
- `M04-L01` имеет confirmed post-hygiene baseline;
- existing non-golden content без baseline не усыновляется автоматически;
- arbitrary title drift не переписывается автоматически.

Target-scoped content notice `M00-L02` сохраняется: current canonical содержит 8 steps, confirmed live golden — 7.

## Что всё ещё требуется перед `upload-remaining`

До массового write и до доказанного актуального private staging остаются отдельные gates:

1. transactional materialization/read-back для remaining PNG assets;
2. deterministic SVG→PNG conversion + visual/read-back verification;
3. обобщение initial-upload orchestration с hard-coded `M04-L01` на разрешённый set remaining lessons;
4. общий post-baseline drift guard для всех загруженных lessons;
5. безопасное reconciliation 18 lesson PENDING + course-page относительно выбранного current `main` SHA без automatic adoption;
6. integrity pass independence/F1/Astra PED-01…PED-07 на фактическом staging;
7. private all-course staging equivalence verification;
8. Human Visual checks publication/learner-facing surfaces, включая PED-06/PED-07;
9. Human Pilot readiness по `06_testing/human-pilot/`, включая device/service/consent/moderator/participant gates.

Learner-hygiene remediation, section recovery и golden title migration больше не перечисляются как невыполненные текущие gates: они завершены и остаются regression evidence.

До закрытия перечисленного `ready_for_bulk_write=false` независимо от успешности отдельных production runs.
