# Live acceptance `M04-L01` — 15 сентября 2026

**Статус:** MACHINE ACCEPTANCE PASS  
**Stepik course:** `299189`  
**Canonical source:** `main@de98e60b845b51eda4c551cdc55c0c7139c35a55`  
**GitHub Actions run:** `34969028781`  
**Mode:** `first-upload-m04-l01`

## Итог

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

## Фактические write operations

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

## Что этот PASS доказывает

Доказан end-to-end machine route:

`canonical main → source compiler → asset resolution → attachment materialization → verified rendering → WAL write → per-operation read-back → final fingerprint → Issue machine state → immutable MACHINE_STATE_COMMITTED history`.

Attachment URL не угадывался и появился только после фактического Stepik response/read-back. Реальные bytes были скачаны обратно и сверены с canonical SHA-256 до фиксации baseline.

## Что этот PASS не доказывает

Этот результат **не является Human Validation** и сам по себе не означает готовность общего bulk write.

Отдельно всё ещё требуются:

- человеческая визуальная проверка отображения `M04-L01` в интерфейсе Stepik и открытия learner attachment;
- transactional materialization/read-back для PNG assets;
- deterministic SVG→PNG route и visual verification;
- обобщённый initial-upload orchestration для remaining lessons;
- integrity pass independence/F1-sensitive lessons;
- stale-title metadata route;
- финальная private all-course staging verification;
- Human Pilot по правилам `06_testing`.

`ready_for_bulk_write=false`.

## Известный независимый notice

`M00-L02` продолжает иметь target-scoped `GOLDEN_OWNER_REQUIRED`: current canonical содержит 8 steps, confirmed live golden — 7. Этот notice не связан с `M04-L01` acceptance и не разрешает автоматическую запись в golden.
