# Adversarial audit PR #62 — Stepik pending backlog + dependency-aware impact

**Дата:** 14 сентября 2026 года  
**Роль:** отдельный критический проход после авторской реализации  
**Scope:** только инфраструктурный этап 2 GitHub → Stepik  
**Stepik writes:** не выполнялись

## Проверочный вопрос

Можно ли принять PR, если считать ошибкой не только падение теста, но и любой сценарий, где learner-facing Git change способен исчезнуть из deployment backlog, чужой pending способен закрыться, Issue #54 способен быть затёрт гонкой или automation способен незаметно расширить write surface?

## Pass 1

### AUD-01 — нормативные документы отставали от реализации

**Severity:** blocking до исправления.

После реализации код переводил PENDING из comment-only истории в machine-readable state и добавлял dependency-aware impact, но текущие `SYNC-POLICY.md` / `LIVE-SAFETY.md` продолжали описывать прежний контур и часть новой функциональности как отсутствующую.

Это создавало два конкурирующих operational contract: код и каноническую документацию.

**Исправление:**

- `SYNC-POLICY.md` обновлён до schema v2, current pending lifecycle, dependency graph, rename/delete semantics и compare-before-patch race guard;
- `LIVE-SAFETY.md` обновлён до current-main + mutex + machine pending closure + residual partial-write limitation.

## Pass 2 после исправления

### 1. Machine-readable PENDING

PASS.

Проверено:

- первый pending создаёт один object на Lesson ID;
- повторный merge того же урока сохраняет `first_pending_*`, обновляет `latest_pending_*` и объединяет paths/reasons;
- разные уроки не смешиваются;
- course page живёт отдельно;
- baseline reference является snapshot последнего подтверждённого lesson baseline либо `null`, если baseline отсутствует;
- schema v1 читается и нормализуется в v2 без потери существующего M02-L01 baseline.

### 2. Закрытие pending

PASS в пределах текущего pilot write surface.

- допустимы только `APPLIED` и `NOOP_CONFIRMED`;
- runtime закрывает M02-L01 pending только при `result.verified == true`;
- APPLIED сначала формирует подтверждённый baseline record;
- NOOP не создаёт фиктивный Stepik write;
- другие lesson pending и course-page pending не закрываются.

### 3. Race protection Issue #54

PASS.

Для impact update и live sync используется схема read expected state → re-read current state → normalized equality check → PATCH only if unchanged. Любое изменение machine state между чтениями останавливает PATCH.

Оставшийся микроскопический TOCTOU-интервал между compare и REST PATCH не маскируется как атомарный CAS; это ограничение текущего GitHub Issues API route, а не молча проигнорированная гарантия.

### 4. Dependency-aware impact

PASS.

Проверено:

- direct `lesson.md` / `stepik-plan.md`;
- lesson assets;
- repo-local Markdown dependency links из canonical lesson/plan;
- shared learner-facing Markdown;
- переиспользованный asset другого lesson;
- added / modified / renamed / deleted;
- rename использует old mapping из before graph и new mapping из after graph;
- delete использует before graph;
- stale reference после delete блокирует;
- unknown shared learner-facing dependency блокирует;
- `author-notes.md`, tooling, tests/workflows/reviews сами по себе pending не создают;
- course page остаётся отдельным object.

### 5. Write-surface regression

PASS.

PR не:

- меняет learner-facing содержание;
- выполняет Stepik write;
- добавляет DELETE;
- разблокирует bulk write;
- снимает golden READ_ONLY с M00-L01/M00-L02;
- меняет branch protection/rulesets/GitHub Environment/secrets.

### 6. CI contract

PASS на первом CI до документационного исправления: unit tests + structural dry-run зелёные. После документационного исправления требуется повторный CI на финальном head.

## Остаточные ограничения, не являющиеся blocker этого этапа

1. Полноценная recovery-модель после сценария «Stepik write verified, но последующий Issue PATCH остановился/упал» ещё не реализована. Это прямо относится к следующему этапу partial-write recovery + baseline reconcile.
2. Course page имеет отдельный PENDING, но пока не имеет собственного confirmed deployment baseline/write route. `confirmed_baseline_ref=null` является явным состоянием, а не догадкой.
3. Общий bulk write остаётся закрыт.
4. Если race guard останавливает impact PATCH, GitHub Actions run становится красным и требует reconcile; automation намеренно не пытается слить конкурирующие state updates эвристикой.

## Вердикт

**ОДОБРЕНО после повторного зелёного CI на финальном head.**

Critical findings после Pass 2: **0**.
