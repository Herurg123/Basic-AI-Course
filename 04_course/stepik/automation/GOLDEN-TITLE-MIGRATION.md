# Owner-approved migration заголовков golden lessons

**Scope:** только `M00-L01` и `M00-L02` в private Stepik course `299189`.

## Зачем существует отдельный route

`M00-L01` и `M00-L02` являются `READ_ONLY_GOLDEN`. Обычный learner-hygiene writer намеренно не имеет права менять их. После общей очистки learner-facing ID в Stepik у этих двух уроков остались legacy prefixes:

- `M00-L01 — Начните безопасный рабочий диалог`;
- `M00-L02 — Подготовьте и передайте безопасный учебный материал`.

Learner UX contract требует human-facing titles без внутренних canonical IDs. Поэтому для этой единственной metadata migration используется отдельный owner-approved route.

## Что разрешено

Только два exact title transitions:

1. lesson `2591708`:
   `M00-L01 — Начните безопасный рабочий диалог` → `Начните безопасный рабочий диалог`;
2. lesson `2591710`:
   `M00-L02 — Подготовьте и передайте безопасный учебный материал` → `Подготовьте и передайте безопасный учебный материал`.

Target human title берётся из текущего canonical manifest. Observation fixture обязан содержать exact legacy predecessor. Любой другой live title = STOP.

Запрещены:

- POST/CREATE;
- DELETE;
- section/unit/position writes;
- step/body writes;
- изменение visibility/language;
- изменение golden lesson IDs или step sequence;
- автоматический rebaseline observation fixture.

## Preflight

Workflow `.github/workflows/stepik-golden-title-migration.yml` запускается вручную с `confirm_write=false`.

Preflight:

- проходит current-main guard;
- читает live course `299189`;
- проверяет private/ru state;
- строит targets только для `M00-L01/M00-L02`;
- проверяет fixed lesson IDs из `golden-profile.v1.json`;
- проверяет полный golden integrity;
- проверяет durable history на конфликтующие/incomplete events;
- выполняет `0` Stepik writes;
- выдаёт точное число planned title PUT.

## Write mode

Owner вручную запускает тот же workflow с `confirm_write=true`. Это и есть owner approval для конкретного explicit golden route.

Для каждого target:

1. live title обязан быть exact legacy, либо exact target с доказанным immutable history этого же event;
2. до dispatch создаётся durable `WRITE_INTENT`;
3. затем `WRITE_DISPATCH_STARTED`;
4. используется существующий production-proven lesson title-only PUT contract;
5. immediate lesson read-back обязан подтвердить exact target;
6. затем выполняется **полный course snapshot**;
7. migration-aware golden validation проверяет IDs, section/unit positions, lesson language/visibility, block sequence, step count, learner-visible HTML hashes и free-answer source;
8. только доказанный target state допускает переход к следующему lesson.

Ambiguous result, known failure, failed read-back, unknown title drift, foreign incomplete event или любой non-title golden drift = STOP. Blind retry запрещён.

## Recovery

Новый human title сам по себе не считается доказательством успешной migration.

Если live title уже target, route принимает его только когда exact immutable event history текущей migration доказывает per-operation read-back/final state. Target title без такой provenance считается manual/unknown drift и блокируется.

Это позволяет безопасно продолжить сценарий, где первый golden title уже подтверждён, а run остановился до второго, не превращая совпавший вручную title в автоматически принятый baseline.

## Observation fixture после write

`golden-profile.v1.json` остаётся observation fixture, а не desired-state файл. Workflow **не переписывает его автоматически**.

После полного live PASS workflow сохраняет artifact `golden-profile.next.json`, построенный из исходного fixture с двумя доказанными новыми observed titles и metadata текущего run/source SHA.

До принятия отдельного PR, обновляющего observation fixture по фактическому post-write snapshot, обычные live routes ожидаемо должны fail-closed на старом golden title. Это преднамеренная safety boundary.

Обновление fixture после успешного live run является отдельным reviewable change и не означает adoption неизвестного drift.

## Acceptance

До live write:

- PR CI PASS;
- отдельный adversarial review: 0 open CRITICAL / HIGH;
- owner preflight `confirm_write=false`: READY, `stepik_writes=0`, ровно ожидаемые targets.

После live write:

- exact two target titles подтверждены;
- фактических writes не больше двух;
- полный post-write golden integrity PASS;
- immutable history непротиворечива;
- отдельный PR обновил observation fixture по доказанному post-write state;
- Human Visual Validation подтверждает отсутствие `M00-L01/M00-L02` в learner-facing названиях.

Этот route не разрешает никаких других golden changes и не открывает общий bulk write.
