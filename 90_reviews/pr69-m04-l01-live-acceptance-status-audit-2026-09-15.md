# Adversarial audit PR #69 — live acceptance status `M04-L01`

**Дата:** 15 сентября 2026  
**PR:** #69 `Stepik: зафиксировать live acceptance M04-L01`  
**Scope:** status/documentation-only фиксация фактически завершённого owner live acceptance  
**Кодовый/learner-facing write scope:** отсутствует

## Verdict

- OPEN CRITICAL: **0**
- OPEN HIGH: **0**
- OWNER DECISION REQUIRED BEFORE MERGE: **0**
- VERDICT: **PASS / MERGE ALLOWED**

## Проверенные источники факта

Live owner-dispatch:

- GitHub Actions run `34969028781`;
- mode `first-upload-m04-l01`;
- `confirm_write=true`;
- course `299189`;
- source `main@de98e60b845b51eda4c551cdc55c0c7139c35a55`;
- workflow/job result: `SUCCESS`.

Immutable deployment history:

- asset event `evt-e9a1d3f142cc3ff8d239b2e2d1cf898d`;
- lesson event `evt-8e53b979b6277bf8c749a572d77d913e`;
- asset final read-back: `APPLIED`;
- lesson final read-back: `APPLIED`;
- asset `MACHINE_STATE_COMMITTED`: commit `8bc298466dc26a13f4ad5472961a3e6062205f30`;
- lesson `MACHINE_STATE_COMMITTED`: commit `df30979d8150373f7a5b8ba488a2596d49356a20`.

Issue `#54`:

- machine-state schema v3;
- confirmed baseline `M04-L01`;
- verified asset binding `05_assets/M04/M04-L01/M04-L01-A01.txt`;
- existing `M02-L01` baseline preserved;
- existing independent PENDING backlog preserved.

## Факты, сверенные в документации PR

### Asset

Точно совпадают с immutable history / Issue state:

- Stepik attachment ID: `239272`;
- Stepik lesson ID: `2591721`;
- file: `M04-L01-A01.txt`;
- size: `1952` bytes;
- URL: `https://stepik.org/media/attachments/lesson/2591721/M04-L01-A01.txt`;
- canonical/download SHA-256: `sha256:21675505c4b0c766541671daa260ccc1f020ff5d7034b3df45526d2923770ba0`.

### Lesson

Точно совпадают с final read-back / machine state:

- Stepik lesson ID: `2591721`;
- step IDs: `11291289, 11308577, 11308578, 11308579, 11308580, 11308581`;
- source SHA: `de98e60b845b51eda4c551cdc55c0c7139c35a55`;
- final fingerprint: `sha256:e1633c610ca4e2b03d3b797b93baf2dc97d3e47c43f9fd4f34d809864697e538`;
- block shape: `text,text,text,text,free-answer,text`;
- all six lesson writes have per-operation read-back;
- final lesson read-back confirmed;
- `readback_failures=[]`.

### Safety / scope

Подтверждено, что PR не размывает safety boundaries:

- `ready_for_bulk_write=false` остаётся явным;
- успешный machine acceptance не назван Human Validation;
- отдельная human visual validation `M04-L01` оставлена невыполненной;
- golden `M00-L01/M00-L02` остаются read-only;
- `M00-L02` target-scoped `GOLDEN_OWNER_REQUIRED` (canonical 8 vs live golden 7) сохранён;
- `DELETE` не приписан и не разрешён;
- общий bulk upload не объявлен выполненным;
- оставшиеся PNG/SVG/general orchestration/integrity/stale-title/staging/Human Pilot gates сохранены.

## Adversarial вопросы

### Не перепутан ли API read-back с визуальной проверкой человеком?

Нет. Новый acceptance record прямо говорит, что machine PASS не является Human Validation и отдельно требует визуальную проверку интерфейса Stepik и learner attachment.

### Не усыновлён ли unknown live state постфактум?

Нет. Документация опирается на owner-dispatched event, WAL, per-operation read-back, final read-back, Issue state и immutable `MACHINE_STATE_COMMITTED`, а не на простое `live == desired`.

### Не открыт ли bulk route одним успешным пилотом?

Нет. `ready_for_bulk_write=false` зафиксирован в обоих статусных документах и acceptance record; remaining gates перечислены явно.

### Не заявлено ли, что все physical assets уже materialized?

Нет. Документация переводит только подтверждённый `M04-L01-A01.txt` в verified binding и оставляет четыре non-golden visual physical sources для следующих gates.

### Не изменён ли learner-facing content?

Нет. До audit-файла PR меняет только:

- `04_course/stepik/automation/BULK-STATUS.md`;
- `04_course/stepik/automation/README.md`;
- новый `04_course/stepik/automation/M04-L01-LIVE-ACCEPTANCE-2026-09-15.md`.

Уроки, планы уроков и learner assets не изменялись.

## CI

PR run `34969996627`:

- `Тесты и structural dry-run`: SUCCESS;
- owner live job: SKIPPED;
- merge-impact job: SKIPPED на PR, как ожидается.

Stepik writes из PR #69: **0**.

## Residual nonblocking items

1. Human visual validation `M04-L01` всё ещё должна быть выполнена владельцем отдельно; machine read-back этого не заменяет.
2. Node.js deprecation warnings GitHub Actions остаются инфраструктурным maintenance item и не влияют на смысл PR.
3. Успешный TXT attachment route не является доказательством PNG/SVG image routes; они остаются отдельными gates.

## Итог

PR #69 корректно синхронизирует каноническую production-документацию с доказанным live состоянием, не повышая уровень готовности сверх фактически подтверждённого. Блокирующих замечаний нет.
