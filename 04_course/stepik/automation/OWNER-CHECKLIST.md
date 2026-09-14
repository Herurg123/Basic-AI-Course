# Owner checklist: текущий безопасный маршрут автоматизации Stepik

Этот список предназначен владельцу курса. Automation-чат выполняет техническую подготовку самостоятельно и запрашивает только действие, которое действительно нельзя выполнить доступным подключением.

## Канонический источник

- Источник истины по содержанию курса: свежий `main` GitHub.
- Рабочий Stepik staging: `course_id=299189`.
- Issue #54 — deployment journal/baseline, но не источник содержания.
- Перед любым live-действием нужно заново получить HEAD `main`; SHA из старого отчёта или этого документа не считается актуальным автоматически.

## Подтверждённые live checkpoints

На 14 сентября 2026 года подтверждено:

- в Stepik уже существуют 9 разделов и 21 урок;
- M00-L01 и M00-L02 защищены как `READ_ONLY_GOLDEN`;
- M02-L01 прошёл первый реальный API write, полный read-back, визуальную проверку владельцем и повторный запуск без лишних записей (`NOOP_ALREADY_MATCHES`);
- для M02-L01 в Issue #54 записан deployment baseline с Stepik lesson/step IDs и fingerprint;
- отдельный `sync-status` подтвердил работу тройного сравнения `desired ↔ live ↔ baseline` на пилотном уроке;
- отдельный `Stepik Bulk Status` ранее подтвердил сопоставление всех 21 уроков и отсутствие hard blockers на той версии канона;
- после педагогического PR #59 текущий `main` изменился, а Issue #54 содержит новую `PENDING` запись. Это **не означает**, что Stepik уже обновлён.

Поэтому старый full-course `bulk-status` нельзя считать актуальным preflight для нового `main`.

## Что реально умеет automation сейчас

Подтверждены следующие контуры:

- `dry-run` — offline structural проверка без Stepik API;
- `inspect` — read-only снимок реального курса;
- `content-test-one` — ограниченный первый write только для M02-L01; этап уже пройден и не является маршрутом массовой загрузки;
- `sync-status` / `sync-changed` — drift-guarded exploitation sync, но **пока только для M02-L01**;
- `Stepik Bulk Status` — read-only full-course preflight всех 21 уроков, asset inventory и sensitive/stale-title gates.

Не подтверждены и поэтому остаются закрыты:

- general compiler всех learner-facing уроков;
- безопасный first-upload writer для остальных skeleton lessons;
- общий exploitation sync для всех уроков;
- отдельный structural/title migration route;
- asset hash/version deployment gate для всех learner-facing файлов;
- отдельный verified golden-update route;
- синхронизация learner-facing course page;
- bulk write остальных уроков.

## Следующий обязательный live gate после изменения `main`

До разработки/открытия нового bulk write нужно на **свежем `main`** повторить read-only проверки:

1. `Stepik Uploader → inspect`;
2. `Stepik Bulk Status`;
3. сверить реальный private/staging state, все 21 mapping, golden profile, M02-L01 baseline/drift, stale titles, sensitive flags и asset inventory.

Эти проверки не должны менять Stepik.

Если live состояние неоднозначно, golden изменён, появился необъяснённый drift или mapping перестал быть однозначным, дальнейший write = `STOP` до разбора причины.

## OAuth и секреты

GitHub Actions использует secrets с именами:

- `STEPIC_CLIENT_ID`;
- `STEPIC_CLIENT_SECRET`.

Никогда не присылать в ChatGPT, issue, PR или лог:

- client secret;
- access token;
- пароль;
- cookies;
- OAuth tokens.

## Идемпотентность и write safety

Для любого подтверждаемого write-route сохраняются правила:

- никаких `DELETE`;
- POST/PUT автоматически не повторять после неопределённого ответа;
- после каждой записи сразу выполнять read-back;
- повторный запуск уже совпадающего состояния должен быть no-op;
- baseline менять только после фактически подтверждённого read-back;
- если `live != baseline`, автоматический overwrite запрещён (`DRIFT_BLOCKED`).

## Stepik Files / learner-facing assets

Нельзя конструировать URL файлов по догадке. Для каждого learner-facing physical asset перед публикацией должны быть известны его Git path, SHA-256, фактически deployed URL/version и результат проверки доступности.

Если надёжный upload API для требуемого типа хранения не подтверждён, используется установленный ручной fallback. Automation сначала выдаёт владельцу точные Lesson ID / Asset ID / Git path / имя файла / действие, и только после ручной операции проверяет полученный результат.

## Что владелец не должен делать вручную без отдельного handoff

Не нужно:

- создавать новые modules/lessons;
- исправлять skeleton-заголовки вручную;
- копировать learner-facing содержание в остальные уроки;
- массово загружать assets заранее;
- менять golden lessons;
- удалять placeholder steps;
- запускать `sync-changed` с ожиданием, что он синхронизирует весь курс;
- публиковать курс наружу.

Полный технический Stepik PASS ещё не равен `WAVE 0 READY`: после сборки остаются staging checks на PHONE/COMPUTER, live-service gates и Human Pilot.
