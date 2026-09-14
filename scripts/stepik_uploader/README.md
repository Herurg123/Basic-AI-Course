# Stepik uploader: безопасная автоматизация

Этот каталог содержит автоматизацию переноса утверждённого курса «ИИ с нуля» в существующий черновой курс Stepik. Источник истины для содержания остаётся в GitHub `main`; uploader (загрузчик курса) не проектирует уроки заново.

## Текущий статус

Поддерживаются безопасные режимы:

- `inspect` — READ-ONLY (только чтение) реального курса и двух вручную собранных golden lessons (эталонных уроков);
- `dry-run` — пробный запуск без записи: компиляция структурного manifest (машиночитаемого манифеста сборки) и diff-плана (плана различий).

Live inspect курса `299189` подтвердил M00-L01/M00-L02 как READ-ONLY golden sample. Наблюдаемая платформенная конфигурация сохранена в `04_course/stepik/automation/golden-profile.v1.json`: количество и порядок шагов, `block.name`, free-answer configuration и SHA-256 learner-visible HTML каждого golden step. Следующий live inspect снимает фазовый `needs-golden-profile` только если реальный Stepik по-прежнему совпадает с этим профилем.

Режимы `skeleton`, `assets-test`, `content-test-one`, `upload-remaining` и `verify` пока остаются fail-closed. После golden checkpoint причина блокировки уже не «неизвестна модель Stepik», а отсутствие утверждённого content compiler и отдельного теста одной не-golden lesson. Два эталонных урока по-прежнему нельзя удалять, перестраивать или перезаписывать.

## Что показал golden sample

- M00-L01: 6 Stepik steps, sequence `text, text, text, text, free-answer, text`.
- M00-L02: 7 Stepik steps, sequence `text, text, text, text, text, free-answer, text`.
- Free-answer использует `is_attachments_enabled=false`, `is_html_enabled=true`, `manual_scoring=false`.
- Markdown helper assets в golden фактически встроены в learner-facing text.
- DOCX/PNG M00-L02 отдаются по подтверждённым Stepik lesson-file URLs.
- В обоих golden lessons количество строк Stepik-плана совпадает с количеством реальных Stepik steps 1:1.

`golden-profile.v1.json` — derived platform-observation fixture, а не второй источник содержания курса. Если golden lesson изменится вручную или API начнёт возвращать другую структуру/HTML, inspect должен остановиться, а не «приспособиться» молча.

## Локальная проверка без Stepik

Из корня репозитория:

```bash
python -m pip install -r scripts/stepik_uploader/requirements.txt
python -m unittest discover -s tests/stepik_uploader -v
python scripts/stepik_uploader/stepik_uploader.py dry-run --repo-root .
```

Offline `dry-run` (локальный пробный запуск без обращения к Stepik) обязан сделать ноль API writes (операций записи через API). Он создаёт в `artifacts/stepik-uploader/`:

- `build-manifest.structural.json`;
- `dry-run-plan.json`;
- `run-report.json`.

Структурный manifest компилируется из `04_course/Mxx/Mxx-Lyy/lesson.md`, `stepik-plan.md` и названий модулей в `04_course/README.md`. Для текущего канона валидируются 9 модулей, 21 Lesson ID и платформенный предел не более 16 логических шагов на урок.

## Live inspect

Для live inspect нужен обычный числовой `course_id`, а OAuth-секреты должны находиться только в environment (переменных окружения) или GitHub Actions Secrets:

```text
STEPIC_CLIENT_ID
STEPIC_CLIENT_SECRET
```

Рабочий черновой курс проекта имеет `course_id=299189`; GitHub Actions уже подставляет его по умолчанию. `.env` исключён из Git. Не передавайте `client_secret`, access token (токен доступа), пароль или cookies в чат, issue, PR, Actions input или лог.

`inspect` читает цепочку `course → sections → units → lessons → steps/step-sources`, сохраняет нормализованный snapshot (снимок состояния), распознаёт M00-L01/M00-L02 и проверяет их против сохранённого golden profile. Любая неоднозначность становится blocker (блокирующей ошибкой).

Существующие skeleton lessons определяются по точному каноническому title либо по стабильному `Mxx-Lyy` в title вместе с точной section/unit position. Если canonical ID или позиция неоднозначны, uploader останавливается. Устаревший текст title при однозначном stable ID не считается отсутствующим уроком и никогда не ведёт к планированию дубля.

## Идемпотентность и сетевые ошибки

- `DELETE` не используется.
- Эталонные уроки никогда не входят в write-set (набор объектов для записи).
- Существующий объект не обновляется по одному совпавшему признаку.
- GET может повторяться только для временных `429/5xx`.
- POST/PUT автоматически не повторяются: повтор POST после сетевой неопределённости способен создать дубль.
- После включения write-фазы (фазы записи) каждая запись должна получать отдельный read-back (контрольное чтение обратно) до следующей операции.

## Stepik Files

По официальной справке Stepik файлы курса/урока загружаются через интерфейс настроек, а learner (ученик) получает файл по ссылке, вставленной автором в шаг. Стабильный официальный upload/list endpoint (API-точка загрузки/получения списка) для этих файлов в текущей документации не подтверждён.

Поэтому базовый fallback (резервный маршрут) v1 — `manual-stepik-files`:

1. automation (автоматизация) определяет точный список нужных binary assets;
2. владелец загружает их через Stepik UI;
3. владелец копирует обычные ссылки;
4. ссылки попадают в URL-map (карту URL);
5. content phase (этап публикации содержания) блокируется, пока нужный Asset ID не разрешён в URL.

Markdown helper assets могут быть встроены в текст, если это подтверждено production route; URL для них не выдумывается.

## Особые педагогические блокировки

Компилятор сохраняет `author_only`, `independence_sensitive` и `f1_sensitive`. Строки `author_only` (только для автора) исключаются из потенциального learner write-set. Для M03-L02, M04-L02, M05-L02, M06-L04, M07-L01 и M07-L02 автоматическое склеивание temporal boundaries (временных границ между самостоятельной попыткой и последующей подсказкой/проверкой) недопустимо. `M07-L02` требует отдельного F1 integrity pass (проверки сохранности финальной самостоятельной задачи) до массовой публикации.

API `201 Created` или точный read-back подтверждают только техническую запись. Они не доказывают педагогическую самостоятельность ученика и не делают WAVE 0 READY.
