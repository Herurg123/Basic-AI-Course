# Owner checklist: private Stepik release

Перед write:

1. Курс `299189` private/unpublished.
2. Запускать только `Stepik Private Course Release` из current `main`.
3. `course_id = 299189`.
4. Сначала допустим read-only run с `confirm_write=false`; для записи `confirm_write=true`.
5. Не rerun старый failed workflow как замену fresh dispatch после изменения `main`.

После run:

- workflow должен завершиться SUCCESS;
- final machine state должен иметь zero PENDING lessons и zero course-page pending;
- все 21 canonical lessons должны иметь baselines;
- не должно быть unresolved drift/read-back/history blockers;
- changed assets должны иметь подтверждённые bindings.

Успешный технический sync означает готовность private Stepik staging, а не автоматический public launch курса. Реальные педагогические/устройственные gates ведутся отдельно.
