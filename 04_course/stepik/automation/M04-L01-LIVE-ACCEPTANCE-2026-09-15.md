# Live acceptance `M04-L01` — 15 сентября 2026

**Machine status:** PASS  
**Human Visual Validation:** FAIL / RETEST REQUIRED  
**Stepik course:** `299189`  
**Canonical source первого upload:** `main@de98e60b845b51eda4c551cdc55c0c7139c35a55`  
**GitHub Actions run первого upload:** `34969028781`  
**Mode:** `first-upload-m04-l01`

## Итог machine acceptance

Owner-dispatched controlled first upload завершён успешно. Это первый подтверждённый production acceptance общего verified-rendering + physical-asset + initial-upload контура на non-golden lesson.

Подтверждено:

- current-main guard: PASS;
- golden live integrity: confirmed;
- target lesson: `M04-L01`, Stepik lesson ID `2591721`;
- TXT asset `05_assets/M04/M04-L01/M04-L01-A01.txt` материализован через Stepik attachment API;
- attachment ID: `239272`;
- attachment URL: `https://stepik.org/media/attachments/lesson/2591721/M04-L01-A01.txt`;
- canonical/download SHA-256: `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`;
- asset event: `evt-e9a1d3f142cc3ff8d239b2e2d1cf898d`, status `APPLIED`;
- lesson event: `evt-8e53b979b6277bf8c749a572d77d913e`, status `APPLIED`;
- rendered learner steps: `6`;
- Stepik step IDs: `11291289, 11308577, 11308578, 11308579, 11308580, 11308581`;
- lesson final fingerprint: `sha256:e1633c610ca4e2b03d3b797b93baf2dc97d3e47c43f9fd4f34d809864697e538`;
- per-operation read-back: подтверждён для всех шести lesson writes;
- final lesson read-back: confirmed;
- `readback_failures=[]`;
- Issue `#54` успешно переведён на machine-state schema v3;
- asset baseline и lesson baseline записаны в Issue `#54`;
- оба deployment events получили `MACHINE_STATE_COMMITTED` после успешного race-checked Issue PATCH.

## Фактические write operations первого upload

1. существующий placeholder step `11291289` обновлён как learner step position 1;
2. созданы steps `11308577` … `11308581` для positions 2 … 6;
3. `DELETE` не выполнялся;
4. golden lessons не изменялись;
5. массовый upload не запускался.

Verified rendering contract для `M04-L01` сохраняет shape:

`text → text → text → text → free-answer → text`.

`free-answer` использует только подтверждённый golden source contract:

```json
{
  "is_attachments_enabled": false,
  "is_html_enabled": true,
  "manual_scoring": false
}
```

Author-only `M04-L01-A02` не входит в learner rendering.

## Human Visual Validation после machine PASS

После первого upload владелец открыл урок в learner-facing интерфейсе Stepik и предоставил визуальную проверку. Функциональная часть работала, но был выявлен production UX regression.

Подтверждено как работающие элементы:

- TXT attachment открывается/скачивается;
- внешние ссылки на Алису AI и GigaChat кликабельны;
- `free-answer` отображается;
- основной learner content доступен.

Выявленный дефект:

- заголовок урока показывал внутренний canonical ID, например `M04-L01 — …`;
- learner body показывал Asset/lesson ID, например `M04-L01-A01` и cross-lesson ссылки вида `M04-L03`;
- sidebar показывал `Mxx-Lxx` в названиях уроков.

Это противоречит принятому learner UX contract: внутренние canonical/Asset/Exercise/Check/production ID не должны быть нужны или видны абсолютному новичку.

Поэтому machine acceptance остаётся **PASS**, но Human Visual Validation имеет статус **FAIL / RETEST REQUIRED**. Этот документ не должен трактоваться как Human PASS.

Дефект зафиксирован в Issue `#70`. Исправление разрабатывается в PR `#71` и включает all-course learner-ID regression, human-facing title contract и guarded title/content migration без `DELETE` и duplicate creation.

## Что machine PASS доказывает

Доказан end-to-end machine route:

`canonical main → source compiler → asset resolution → attachment materialization → verified rendering → WAL write → per-operation read-back → final fingerprint → Issue machine state → immutable MACHINE_STATE_COMMITTED history`.

Attachment URL не угадывался и появился только после фактического Stepik response/read-back. Реальные bytes были скачаны обратно и сверены с canonical SHA-256 до фиксации baseline.

## Что ещё требуется после исправления learner hygiene

Перед признанием `M04-L01` полностью прошедшим live acceptance требуется повторная Human Visual Validation уже после guarded learner-hygiene migration. Нужно визуально подтвердить как минимум:

- в sidebar и заголовке урока нет `M04-L01`;
- в learner body нет внутренних lesson/Asset/Exercise/Check ID;
- смысловые подписи материалов понятны без знания структуры репозитория;
- TXT attachment по-прежнему открывается;
- внешние ссылки по-прежнему кликабельны;
- `free-answer` по-прежнему отображается корректно;
- порядок и смысл шести шагов не искажены.

После этого отдельно всё ещё требуются общие production gates:

- transactional materialization/read-back для PNG assets;
- deterministic SVG→PNG route и visual verification;
- обобщённый initial-upload orchestration для remaining lessons;
- integrity pass independence/F1-sensitive lessons;
- финальная private all-course staging verification;
- Human Pilot по правилам `06_testing`.

`ready_for_bulk_write=false`.

## Известный независимый notice

`M00-L02` продолжает иметь target-scoped `GOLDEN_OWNER_REQUIRED`: current canonical содержит 8 steps, confirmed live golden — 7. Этот notice не связан с `M04-L01` acceptance и не разрешает автоматическую запись в golden.

Кроме того, learner-hygiene migration не меняет заголовки `M00-L01` и `M00-L02` обычным writer route: оба golden lesson остаются `READ_ONLY_GOLDEN`, а удаление ID из их live titles требует отдельного owner-approved решения.
