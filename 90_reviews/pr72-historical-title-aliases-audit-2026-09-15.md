# Adversarial audit PR #72 — exact historical title aliases

**Дата:** 2026-09-15  
**PR:** #72  
**Scope:** только две доказанные historical title aliases для learner-hygiene preflight

## Контекст

Owner-dispatched run `34998566701` на `main@d3c11c9ca9da9b0ed17b888f2d7f5330f450a421` завершился `BLOCKED` до первого Stepik write. Причина: два live lesson title не совпали ни с current canonical title, ни с exact legacy-prefix current canonical title:

- `M06-L02 — Проверьте исходные числа и расчет`;
- `M07-L01 — Соберите освоенные действия в одну работу`.

Canonical titles в текущем `main`:

- `M06-L02`: `Проверьте исходные числа и расчёт`;
- `M07-L01`: `Соберите знакомые действия в одну работу`.

Артефакт failed run содержит только `course-snapshot.before.json`, `live-source-guard.json`, `run-report.json`, предыдущие Issue state/body и `title-hygiene-plan.json`. `sync-state.next.json`, after-snapshot и tracked events отсутствуют. Runtime проверяет `title_plan.blockers` до любого title/content writer. Поэтому факт run: **Stepik writes = 0**.

## Изменение

В `title_hygiene.py` добавлен allowlist `HISTORICAL_TITLE_ALIASES`, привязанный к точному `(kind, canonical_id)`:

- `("lesson", "M06-L02")` → только точная строка `M06-L02 — Проверьте исходные числа и расчет`;
- `("lesson", "M07-L01")` → только точная строка `M07-L01 — Соберите освоенные действия в одну работу`.

Текущий exact legacy-prefix, построенный из current canonical title, остаётся разрешённым как раньше.

## Adversarial checks

### 1. Fuzzy adoption отсутствует

PASS. Нет нормализации регистра, `ё/е`, punctuation, edit-distance, prefix-only или substring matching. Сравнение остаётся exact-string membership.

### 2. Alias нельзя использовать для другого урока

PASS. Allowlist ключуется одновременно по `kind` и `canonical_id`. Regression test меняет `M06-L02` на `M06-L99` и ожидает blocker.

### 3. Похожие, но неизвестные stale/manual titles не усыновляются

PASS. Regression test проверяет почти похожие строки (`расчеты`, `...в одну задачу`) и получает blockers без operations.

### 4. Identity Stepik объекта не определяется по title

PASS. Как и до PR, identity строится по canonical module/lesson position и exact Stepik object id из snapshot. Alias влияет только на допустимость title transition после identity resolution.

### 5. Writer по-прежнему защищён от TOCTOU

PASS. `TitleOperation.live_title` сохраняет фактическую historical строку из planning. Перед PUT writer заново читает live title и блокируется, если он изменился после planning.

### 6. WAL/read-back/no-blind-retry не ослаблены

PASS. PR не меняет `execute_title_only_operation`; write path, `WRITE_INTENT`, `WRITE_DISPATCH_STARTED`, ambiguous handling и read-back остаются прежними.

### 7. Golden protection не ослаблена

PASS. `M00-L01/M00-L02` остаются `GOLDEN_TITLE_OWNER_REQUIRED`; historical allowlist не содержит golden targets.

### 8. Bulk readiness не открывается

PASS. Изменение не затрагивает bulk gate и не устанавливает `ready_for_bulk_write=true`.

## CI evidence

PR head до этого audit-файла: `91bb55c41d6c5861946945e674c008e22cb4d679`.

- `Stepik Learner Hygiene` run `34999528128`: SUCCESS; live owner job SKIPPED.
- `Stepik Uploader` run `34999528078`: SUCCESS; owner live job SKIPPED.
- Unit suite: **227 tests / OK**.
- Structural dry-run: SUCCESS.
- Stepik writes from PR CI: **0**.

## Findings

- OPEN CRITICAL: **0**
- OPEN HIGH: **0**
- OWNER DECISION REQUIRED BEFORE MERGE: **0**

## Verdict

**APPROVE FOR MERGE.**

После merge требуется новый owner-dispatched `Stepik Learner Hygiene` run на актуальном `main`, `course_id=299189`, `confirm_write=true`. Предыдущий failed run не следует rerun-ить как старую attempt: новый dispatch должен пройти current-main guard против нового merge SHA.
