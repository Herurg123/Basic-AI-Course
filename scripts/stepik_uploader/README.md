# Stepik uploader: безопасная автоматизация

Этот каталог содержит автоматизацию переноса утверждённого курса «ИИ с нуля» в существующий черновой курс Stepik. Источник истины для содержания остаётся в GitHub `main`; uploader (загрузчик курса) не проектирует уроки заново.

## Текущий статус

Поддерживаются три рабочих режима:

- `inspect` — READ-ONLY (только чтение) реального курса и проверка двух вручную собранных golden lessons (эталонных уроков);
- `dry-run` — пробный запуск без записи: структурный manifest и diff-план;
- `content-test-one` — **единственный разрешённый write-test этой фазы**, жёстко ограниченный существующим черновым уроком `M02-L01` и требующий явного `--confirm-write` / флага `confirm_write` в GitHub Actions.

Массовые режимы `skeleton`, `assets-test`, `upload-remaining` и `verify` пока остаются fail-closed. Два golden lesson M00-L01/M00-L02 по-прежнему READ-ONLY и никогда не входят в write-set.

Live inspect курса `299189` подтвердил golden profile и все 21 существующий lesson. Платформенная конфигурация сохранена в `04_course/stepik/automation/golden-profile.v1.json`: количество и порядок шагов, `block.name`, free-answer configuration и SHA-256 learner-visible HTML каждого golden step.

## Почему первым write-test выбран M02-L01

`M02-L01` — обычный не-golden lesson, не отмеченный как independence-sensitive или F1-sensitive. В Stepik он уже существует как skeleton с единственной стандартной заглушкой `Урок сгенерирован роботом ;)`.

Его единственный Markdown asset `M02-L01-A01.md` содержит две учебные ситуации. Для test pass они встраиваются в learner-facing Stepik text по подтверждённой golden-конвенции для Markdown helper assets. Поэтому первый write-test не требует ручной загрузки binary files и не вводит новый внешний storage URL.

Compiler допускает только текущую подтверждённую H2-структуру M02-L01. Изменение заголовков/shape production lesson или asset превращается в blocker, а не в молчаливую догадку.

Ожидаемая Stepik sequence для M02-L01:

`text, text, text, text, free-answer, text`

Free-answer configuration берётся из сохранённого golden profile, а не задаётся «по памяти».

## Safety rails write-test

`content-test-one` разрешён только если одновременно выполнены все условия:

- `course_id=299189` проходит golden profile validation;
- курс остаётся непубличным черновиком;
- live plan не имеет blockers;
- target — только `M02-L01` на точной module/unit position и с точным canonical title;
- текущее состояние target lesson — либо исходная стандартная заглушка, либо уже записанный uploader-ом точный prefix/full content;
- пользователь явно включил `confirm_write`;
- `DELETE` отсутствует.

На исходном skeleton первый placeholder step обновляется через один `PUT`, затем недостающие steps создаются последовательными `POST`. Каждый write немедленно проверяется отдельным GET read-back. POST/PUT автоматически не повторяются при сетевой ошибке.

После успешной записи весь курс читается ещё раз, а target lesson проверяется на полный совпадающий sequence/content fingerprint. Повторный запуск того же `content-test-one` должен дать `NOOP_ALREADY_MATCHES` и создать **0** новых steps.

Если выполнение оборвалось после части writes, следующий запуск сначала читает фактическое состояние. Совпадающий prefix можно безопасно продолжить; любое несовпадение останавливает процесс. Автоматического destructive cleanup нет.

## Что показал golden sample

- M00-L01: 6 Stepik steps, sequence `text, text, text, text, free-answer, text`.
- M00-L02: 7 Stepik steps, sequence `text, text, text, text, text, free-answer, text`.
- Free-answer использует `is_attachments_enabled=false`, `is_html_enabled=true`, `manual_scoring=false`.
- Markdown helper assets в golden фактически встроены в learner-facing text.
- DOCX/PNG M00-L02 отдаются по подтверждённым Stepik lesson-file URLs.
- В обоих golden lessons количество строк Stepik-плана совпадает с количеством реальных Stepik steps 1:1.

`golden-profile.v1.json` — derived platform-observation fixture, а не второй источник содержания курса. Если golden lesson изменится вручную или API начнёт возвращать другую структуру/HTML, inspect должен остановиться.

## Локальная проверка без Stepik

Из корня репозитория:

```bash
python -m pip install -r scripts/stepik_uploader/requirements.txt
python -m unittest discover -s tests/stepik_uploader -v
python scripts/stepik_uploader/stepik_uploader.py dry-run --repo-root .
```

Offline `dry-run` обязан сделать ноль API writes. Он создаёт в `artifacts/stepik-uploader/`:

- `build-manifest.structural.json`;
- `dry-run-plan.json`;
- `run-report.json`.

Структурный manifest — phase-neutral canonical projection. Он сам по себе никогда не разрешает write: `write_enabled=false`, а реальные write gates проверяются live перед конкретной операцией.

## Live inspect и GitHub Actions

Для live режима OAuth-секреты должны находиться только в environment или GitHub Actions Secrets:

```text
STEPIC_CLIENT_ID
STEPIC_CLIENT_SECRET
```

Рабочий черновой курс проекта имеет `course_id=299189`; GitHub Actions подставляет его по умолчанию. `.env` исключён из Git. Не передавайте `client_secret`, access token, пароль или cookies в чат, issue, PR, Actions input или лог.

Для `inspect` и `dry-run` флаг `confirm_write` должен оставаться выключенным. Для `content-test-one` его нужно включить явно. Без него CLI завершится `BLOCKED` до обращения к write API.

## Идемпотентность и сетевые ошибки

- `DELETE` не используется.
- Эталонные уроки никогда не входят в write-set.
- Существующий объект не обновляется по одному совпавшему признаку.
- GET может повторяться только для временных `429/5xx`.
- POST/PUT автоматически не повторяются: повтор POST после сетевой неопределённости способен создать дубль.
- Каждая запись получает отдельный read-back до следующей операции.
- Повторный successful content-test должен быть no-op.

## Stepik Files

По официальной справке Stepik файлы курса/урока загружаются через интерфейс настроек, а learner получает файл по ссылке, вставленной автором в шаг. Стабильный официальный upload/list endpoint для lesson/course files в текущей документации не подтверждён.

Поэтому базовый fallback v1 для binary assets — `manual-stepik-files`:

1. automation определяет точный список нужных binary assets;
2. владелец загружает их через Stepik UI;
3. владелец копирует обычные ссылки;
4. ссылки попадают в URL-map;
5. content phase блокируется, пока нужный Asset ID не разрешён в URL.

Markdown helper assets могут быть встроены в текст только там, где это не ломает педагогическое действие и подтверждено production route. URL никогда не конструируется по догадке.

## Особые педагогические блокировки

Compiler сохраняет `author_only`, `independence_sensitive` и `f1_sensitive`. Для M03-L02, M04-L02, M05-L02, M06-L04, M07-L01 и M07-L02 автоматическое склеивание temporal boundaries недопустимо. `M07-L02` требует отдельного F1 integrity pass до массовой публикации.

API success и точный read-back подтверждают только техническую запись. Они не доказывают педагогическую самостоятельность ученика и не делают WAVE 0 READY.
