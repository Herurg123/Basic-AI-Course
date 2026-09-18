# Stepik rewrite title refresh — worklog

Дата: 2026-09-18  
Курс Stepik: `299189`  
Base main: `090b6c489f7d4c1b64d11e63cf89e971ec491b94`  
Ветка: `fix/stepik-rewrite-title-refresh-2026-09-18`

## Инцидент

Fresh private-release run `35305734918` остановился на read-only preflight M00-L02.

Подтверждено:

- offline tests/dry-run — PASS;
- current-main/fixed-scope — PASS;
- initial machine scope — PASS;
- course-page preflight — PASS;
- первый blocker: `M00-L02: live metadata drift`;
- все mutating steps skipped;
- Stepik writes = `0`.

Evidence artifact показал:

- course private, ru;
- live M00-L02 lesson ID `2591710`;
- live title = `Подготовьте и передайте безопасный учебный материал`;
- accepted golden-profile title совпадает с live точно;
- current canonical title после human-language rewrite = `Передайте ИИ материал и попросите работать именно по нему`.

Это доказанная canonical title migration, а не manual drift.

Дополнительная проверка показала, что human-language rewrite изменил заголовки почти всех learner lessons, поэтому локальный special-case только для M00-L02 недостаточен.

## Исправление

Title update становится частью того же guarded lesson deployment event.

### Ordinary lessons

`assess_sync` разрешает title-only metadata difference как `UPDATE_REQUIRED` только после того, как current live fingerprint уже доказан как exact confirmed baseline. Изменение `language` или `is_public` остаётся `METADATA_UPDATE_BLOCKED`.

Writer:

1. создаёт WAL intent для lesson title PUT;
2. делает single non-retried PUT;
3. читает lesson обратно;
4. требует exact title + private + ru;
5. фиксирует operation read-back fingerprint;
6. только затем продолжает step PUTs;
7. финальный lesson read-back по-прежнему обязан быть transport-equivalent текущему canonical.

Ambiguous/failed title write не ретраится вслепую.

### Golden M00-L02 / M00-L01

Special routes сохраняют accepted fixture как pre-write proof:

- до первого write live обязан совпасть с accepted golden fixture;
- canonical title может отличаться от accepted live title;
- title PUT выполняется внутри того же immutable lesson event;
- partial recovery допускается только по history-proven intermediate fingerprint;
- step IDs/order и block contracts остаются неизменными;
- final proposed golden profile получает фактический final live title.

Global `golden_write_policy=READ_ONLY` не меняется; эти маршруты остаются explicit owner-approved exceptions.

## Неприкосновенные guards

- fixed course `299189`;
- private course / private ru lesson only;
- exact lesson ID/position;
- baseline or golden fixture proof before first write;
- no fuzzy title matching;
- no blind retry;
- no DELETE/reorder;
- final read-back required;
- public launch gates PED-01/PED-03/PED-06/Human Pilot не затрагиваются.

## Тесты

Добавлены/изменены проверки:

- proven title migration => UPDATE_REQUIRED;
- manual title drift => DRIFT_BLOCKED;
- private/ru refresh metadata guard;
- WAL order для title PUT;
- title read-back mismatch => failure;
- public/non-ru title write blocked before dispatch;
- writer performs title migration inside tracked content sync;
- final golden profile captures new live title.

CI/critic status заполняется после PR.
