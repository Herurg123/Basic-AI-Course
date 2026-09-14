# Политика эксплуатационной синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Журнал:** GitHub issue `#54`  
**Источник содержания:** только актуальный `main`

## Зачем нужен отдельный sync-контур

После первой загрузки курс продолжит меняться: будут исправляться опечатки, формулировки, ссылки, примеры и иногда структура уроков. Простая схема «при каждом merge сразу отправить изменения в Stepik» небезопасна по двум причинам:

1. она бесконечно дёргает внешний API даже при правках, не влияющих на learner-facing Stepik content;
2. она может молча перезаписать ручную правку в Stepik, сделанную после предыдущего deployment.

Поэтому `main` и Stepik синхронизируются не по push-триггеру, а через явный двухфазный контур: **локально отметить потенциальный impact → вручную проверить/применить live sync**.

## 1. Что происходит при изменении курса в `main`

После push/merge в `main` workflow **не обращается к Stepik API**.

Локальный impact-detector анализирует только Git diff и отмечает уроки-кандидаты, если изменились:

- `04_course/Mxx/Mxx-Lyy/lesson.md`;
- `04_course/Mxx/Mxx-Lyy/stepik-plan.md`;
- learner-facing assets в `05_assets/Mxx/Mxx-Lyy/`;
- отдельно отмечается изменение `04_course/stepik/course-page.md`.

`lesson-card.md`, `author-notes.md` и изменения tooling сами по себе не считаются learner-facing Stepik update.

Если есть потенциальный impact, в issue `#54` появляется запись `PENDING` с `source_main_sha`, Lesson ID и затронутыми путями. Это **не означает**, что Stepik уже обновлён.

## 2. Почему Stepik не синхронизируется автоматически после merge

Live Stepik вызывается только вручную через `workflow_dispatch`.

Это защищает от:

- частых внешних запросов при серии мелких коммитов;
- записи промежуточного состояния между несколькими связанными PR;
- случайного overwrite после ручной правки в Stepik;
- повторных writes при idempotent/no-op состоянии.

Обычный merge может породить только локальную `PENDING` запись. OAuth secrets в этом job не используются.

## 3. Deployment baseline

Для каждого автоматически управляемого урока после успешной записи хранится подтверждённый baseline:

- canonical Lesson ID;
- Stepik lesson ID;
- `source_main_sha`;
- точное время подтверждённого read-back;
- стабильный fingerprint learner-visible состояния;
- Stepik step IDs;
- Git paths, из которых был собран урок.

Текущий machine-readable baseline хранится внутри body issue `#54` между markers `STEPIK_SYNC_STATE_V1_BEGIN/END`. История реальных применений сохраняется отдельными комментариями `APPLIED`.

Issue не является источником содержания курса: это только эксплуатационный deployment state. Содержание по-прежнему берётся исключительно из `main`.

## 4. Fingerprint

Fingerprint строится не из Stepik object ID и не из сырой HTML-строки.

В него входят:

- title урока;
- `language`;
- `is_public`;
- позиции шагов;
- `block.name`;
- `block.source`;
- нормализованное HTML-содержимое шага.

При HTML-нормализации игнорируются служебные атрибуты ссылок, которые Stepik может добавить при сохранении (`target`, `rel`). Поэтому штатная платформенная нормализация не вызывает ложный drift.

## 5. Три состояния перед обновлением

Перед любым update сравниваются три версии:

1. **baseline** — что было подтверждённо записано в прошлый раз;
2. **live** — что сейчас реально находится в Stepik;
3. **desired** — что компилируется из текущего `main`.

Безопасная запись возможна только в одном случае:

`live == baseline` и `desired != baseline`.

Это означает: GitHub изменился, а Stepik с прошлого подтверждённого deployment никто не трогал.

Если `live != baseline`, состояние классифицируется как `DRIFT_BLOCKED`. Автоматическая запись запрещена, даже если live случайно совпадает с новым desired: сначала нужно разобраться, кто и почему изменил Stepik вне журнала.

Если `live == baseline == desired`, результат `IN_SYNC`, write-запросов нет.

## 6. Какие изменения можно обновлять автоматически

Первая версия exploitation-sync разрешает только **in-place content update** уже существующих шагов при неизменной структуре урока:

- то же количество steps;
- те же позиции;
- тот же lesson;
- курс и урок остаются draft/non-public;
- язык остаётся `ru`;
- lesson не относится к запрещённой чувствительной зоне текущего pilot scope;
- live fingerprint совпадает с baseline.

Тогда изменяются только те step positions, у которых desired content реально отличается. После каждого `PUT` выполняется немедленный read-back. Автоматического retry write-запроса нет.

## 7. Что пока блокируется

Автоматически не выполняются:

- удаление шагов;
- уменьшение количества шагов;
- перестановка шагов;
- изменение lesson title/других metadata;
- overwrite при live drift;
- изменение golden `M00-L01` / `M00-L02`;
- массовый update independence/F1-sensitive lessons без отдельного integrity pass.

Такие случаи получают `STRUCTURAL_UPDATE_BLOCKED`, `METADATA_UPDATE_BLOCKED` или другой явный blocker. Это не потеря изменения: `PENDING` остаётся в журнале, пока не появится отдельно проверенный migration route.

## 8. Режимы workflow

### `sync-status`

Read-only. Читает Stepik, baseline и текущий канон, затем сообщает:

- `IN_SYNC`;
- `UPDATE_REQUIRED`;
- `DRIFT_BLOCKED`;
- `STRUCTURAL_UPDATE_BLOCKED`;
- `METADATA_UPDATE_BLOCKED`;
- `BASELINE_MISSING_BLOCKED` / `BASELINE_BOOTSTRAP_REQUIRED`.

Ничего в Stepik не пишет.

### `sync-changed`

Write-mode. Требует `confirm_write=true`.

Перед записью повторяет все проверки `sync-status`. При `UPDATE_REQUIRED` обновляет только реально отличающиеся steps, делает read-back и только после этого обновляет baseline в issue `#54` и добавляет `APPLIED` comment.

Если запись в Stepik прошла, а обновление GitHub journal по какой-то причине не удалось, workflow считается failed. Следующий run увидит расхождение live/baseline и заблокируется. То есть отказ журнала приводит к STOP, а не к молчаливому продолжению.

## 9. Текущий scope до открытия bulk upload

На текущем checkpoint общий content compiler ещё не включён для всех 21 урока. Поэтому `sync-status`/`sync-changed` технически ограничены уже проверенным `M02-L01` как pilot exploitation-route.

Это сделано намеренно: сначала доказывается корректность механизма обновления и drift protection на одном уже загруженном уроке. Перед разблокировкой `upload-remaining` тот же контракт должен быть применён к общему compiler для всех learner-facing lessons.

`upload-remaining` не должен быть открыт, пока массовый compiler не умеет одновременно:

- создавать baseline после первого verified upload каждого урока;
- вычислять desired/live fingerprints;
- обновлять только changed steps;
- блокировать live drift;
- формировать `PENDING/APPLIED` audit trail.

## 10. Эксплуатационный результат

В нормальном режиме после запуска курса процесс выглядит так:

`PR/merge в main → PENDING в #54 без Stepik API → накопление нескольких правок → ручной sync-status → sync-changed при чистом baseline → read-back → APPLIED + новый baseline`.

Это отделяет разработку курса от публикации, не создаёт постоянный polling Stepik и оставляет проверяемую историю того, **что требовало обновления и когда оно действительно было применено**.
