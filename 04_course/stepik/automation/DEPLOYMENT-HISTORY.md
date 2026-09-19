# Immutable deployment history

Deployment history хранит доказательства внешних Stepik operations отдельно от current state Issue #54.

## Logical lesson event

Каждый lesson deployment/recovery связан с:

- canonical object ID;
- course ID;
- source Git SHA;
- desired fingerprint;
- stable event identity;
- state before;
- Stepik object IDs.

## Последовательность

`EVENT_STARTED → WRITE_INTENT → WRITE_DISPATCH_STARTED → WRITE_COMPLETED/WRITE_FAILED_KNOWN/WRITE_AMBIGUOUS → OP_READBACK_CONFIRMED → FINAL_READBACK_CONFIRMED → MACHINE_STATE_COMMITTED`.

Не каждый event обязан содержать write: доказанный NOOP или state-only recovery может завершиться без Stepik mutation.

## Правила

- immutable records не переписываются;
- новый workflow run может продолжить тот же stable event, если semantic identity совпадает;
- conflicting identity/history = STOP;
- machine baseline считается committed только после Issue PATCH;
- old event с source SHA, который больше не current main, не может закрыть новый pending.

Historical event kinds прежних migration-маршрутов могут читаться для обратной совместимости истории, но не создают special runtime class и не являются production write routes.
