# PR #65 — adversarial audit: live golden integrity vs canonical divergence

**Дата:** 2026-09-15  
**PR:** #65 `Stepik: разделить live golden integrity и canonical divergence`  
**Base:** `16822dc1be03247f292a4eca3cbd3c98e1701120`  
**Audited head before review artifact:** `a7ccad82aa7f380985476a301288bd0771fb6028`  
**Trigger:** production read-only `sync-reconcile` run `34927791555`

## 1. Задача критика

Искать причины не принимать вариант A, в особенности сценарии, где устранение глобального blocker для `M02-L01` могло бы:

- ослабить фактическую защиту `M00-L01/M00-L02`;
- разрешить write/adoption/rebaseline golden без owner decision;
- замаскировать реальную live-мутацию golden как допустимый canonical drift;
- превратить notice в разрешающий сигнал;
- ухудшить fail-closed identity/position checks;
- изменить learner-facing курс или выполнить Stepik write.

## 2. Проверенные production evidence

Run `34927791555` был owner-dispatch `sync-reconcile` на `main` SHA `16822dc1be03247f292a4eca3cbd3c98e1701120`, `confirm_write=false`.

Сохранённый `course-snapshot.json` подтверждает:

- `M00-L01`: lesson `2591708`, title `M00-L01 — Начните безопасный рабочий диалог`, 6 live steps, section/unit position `1/1`;
- `M00-L02`: lesson `2591710`, title `M00-L02 — Подготовьте и передайте безопасный учебный материал`, 7 live steps, section/unit position `1/2`;
- `M02-L01`: lesson `2591717`, 6 live steps, section/unit position `3/1`.

Тот же run подтвердил canonical structural manifest:

- `M00-L01`: 6 canonical steps, `golden_read_only=true`;
- `M00-L02`: 8 canonical steps, `golden_read_only=true`;
- `M02-L01`: 6 canonical steps, non-golden.

Исходный run остановился до recorder из-за canonical-vs-observation mismatch `M00-L02: ожидалось 7, получено 8`. Stepik writes = 0.

## 3. Adversarial checks

### A. Реальная live-мутация golden всё ещё блокируется

PASS.

`validate_golden_profile()` больше не сравнивает canonical step count с observation fixture, но продолжает сравнивать сам fresh live Stepik с fixture по:

- course ID;
- section/unit/lesson IDs;
- section/unit positions;
- lesson language/visibility;
- exact observed live title;
- block sequence;
- live step count;
- learner-visible HTML hashes;
- free-answer source.

Дополнительно exact live title был добавлен в fixture из production read-only snapshot run `34927791555`. Это усиливает live-integrity проверку относительно состояния до PR.

### B. Canonical drift не может разрешить golden write

PASS.

Planner по-прежнему выдаёт `READ_ONLY_GOLDEN` для `M00-L01/M00-L02`. Новая classification имеет `automatic_write_allowed=false`. Ownership matrix требует owner approval и запрещает normal golden target write/adoption. Текущий exploitation writer вообще фиксирован на pilot `M02-L01`.

### C. Notice не участвует в write-authority

PASS.

`PlanResult.notices` попадает в machine-readable report, но verdict формируется только из blockers. Никакой writer/recovery route не читает notice как разрешение. Notice существует только для сохранения видимости расхождения, которое перестало быть глобальным blocker.

### D. Live mismatch не может быть ошибочно принят за canonical divergence

PASS.

Canonical divergence вычисляется planner-слоем, но затем live profile validation выполняется отдельно. Любой profile blocker возвращает `golden_status != confirmed` / blocker и останавливает live route. Следовательно, совпадение/расхождение канона не заменяет проверку фактического live golden.

### E. Identity/position fail-closed сохранён

PASS с residual note.

Golden planner допускает stable canonical-ID prefix как identity-candidate, чтобы изменение canonical title не делало старый READ_ONLY title глобальным blocker. При этом:

- candidate обязан быть единственным;
- section/unit position обязаны совпасть с каноном;
- затем golden profile отдельно проверяет фиксированные section/unit/lesson IDs и exact observed title.

Duplicate prefix, wrong position, missing fixed profile lesson или другой live lesson ID не проходят совокупные guards.

**Residual, non-blocking:** первичный planner mapping по-прежнему зависит от наличия stable `M00-L0x — ` prefix либо exact current title. Для текущего production course это подтверждено snapshot. Универсализация identity на profile-driven mapping может быть отдельным будущим refactor; она не нужна для Issue #64 и расширила бы scope текущего safety fix.

### F. Regression/CI

PASS.

GitHub Actions run `34930792255` на PR head `a7ccad82aa7f380985476a301288bd0771fb6028`:

- conclusion: `success`;
- 141/141 unit tests: `OK`;
- structural canonical dry-run: success;
- PR impact/live jobs: skipped;
- Stepik writes: 0.

Новые regression tests доказывают минимум:

- canonical golden title/step-count change не является live-integrity blocker;
- реальная live title mutation остаётся blocker;
- canonical divergence создаёт `GOLDEN_OWNER_REQUIRED`, а не global blocker;
- `automatic_write_allowed=false`;
- ownership class остаётся owner-only/no-rebaseline/no-retry.

## 4. Scope check

PASS.

Изменены только Stepik automation contracts, fixture, tooling и tests. Learner-facing `04_course/Mxx/**` и `05_assets/**` не менялись. Canonical IDs, F1, DELETE prohibition, bulk-write closure и pilot target не изменены.

## 5. Findings

- OPEN CRITICAL: **0**
- OPEN HIGH: **0**
- OWNER DECISION REQUIRED BEFORE MERGE: **0**
- NON-BLOCKING RESIDUALS: **1** — planner golden identity остаётся prefix/position based перед более строгой profile verification; current production evidence достаточна для Issue #64.

## 6. Verdict

**APPROVE FOR MERGE.**

Вариант A реализован как target-scoped separation:

- live golden integrity остаётся strict/fail-closed;
- canonical golden divergence остаётся видимой как `GOLDEN_OWNER_REQUIRED`;
- unrelated non-golden read-only/guarded sync больше не блокируется только из-за законного pending canonical change golden lesson;
- никакого нового golden write authority не появилось.

После merge обязательный production acceptance: новый owner-dispatch `sync-reconcile`, `course_id=299189`, `confirm_write=false`. Только его fresh Stepik read-back может подтвердить, что deadlock Issue #64 устранён в production execution path.
