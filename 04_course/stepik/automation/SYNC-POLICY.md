# Stepik sync policy

## 1. Единый lesson contract

Все canonical lessons M00-L01…M08-L01 используют одну схему:

`canonical main → PENDING → preflight → guarded initial/refresh/recovery → final read-back → machine baseline → immutable history commit`.

Специальных защищённых lesson-классов нет.

## 2. Refresh

Если machine baseline существует:

- target определяется по baseline lesson ID и canonical position;
- fresh live до write обязан быть совместим с baseline;
- desired content компилируется из текущего `main`;
- поддерживаются только доказанные non-destructive изменения;
- после каждого внешнего write выполняется read-back;
- pending закрывается только после final confirmed state.

Manual/unknown drift не перезаписывается автоматически.

## 3. Initial

Если baseline отсутствует, normal overwrite существующего неизвестного урока запрещён. Initial route допускается только для доказанного безопасного skeleton/import state и обязан создать первый baseline после final read-back.

## 4. Recovery

Commit-gap/state-gap может быть восстановлен без повторного Stepik write, если immutable history уже доказывает final state и fresh live ему соответствует. Partial continuation допускается только для доказанного prefix.

## 5. Assets

Visual assets могут получать immutable versioned attachment при изменении bytes. Generic attachment reuse разрешён только при exact machine baseline + download hash verification. Неизвестный existing attachment не принимается автоматически.

## 6. Course page

Course page синхронизируется тем же private-release workflow через отдельный target-scoped guarded route и собственный deployment event.

## 7. Machine state

Issue #54 является current state, но не единственным доказательством. PATCH выполняется только после compare-before-PATCH и final read-back. Immutable history получает `MACHINE_STATE_COMMITTED` только после успешного state PATCH.

## 8. Запрещено

- blind retry после ambiguous dispatch;
- automatic adoption неизвестного live;
- silent rebaseline;
- destructive rollback;
- `DELETE`;
- изменение live из feature branch или stale main SHA.
