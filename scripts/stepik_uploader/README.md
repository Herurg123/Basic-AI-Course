# Stepik uploader: безопасная первая фаза

Этот каталог содержит автоматизацию переноса утверждённого курса «ИИ с нуля» в существующий черновой курс Stepik. Источник истины для содержания остаётся в GitHub `main`; uploader не проектирует уроки заново.

## Текущий статус

Первая фаза намеренно поддерживает только безопасные режимы:

- `inspect` — READ-ONLY чтение реального курса и двух вручную собранных golden lessons;
- `dry-run` — компиляция структурного manifest и diff-план без записи.

Режимы `skeleton`, `assets-test`, `content-test-one`, `upload-remaining` и `verify` зарезервированы контрактом, но до анализа golden sample завершаются как `BLOCKED`. Это сделано специально: Stepik `block.name`, фактическое разбиение learner-facing текста и профиль ссылок нельзя надёжно угадать до чтения уже собранных M00-L01/M00-L02.

Два golden lessons являются READ-ONLY. Автоматизация не удаляет их, не перезаписывает и не исправляет «для единообразия».

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

Структурный manifest компилируется из `04_course/Mxx/Mxx-Lyy/lesson.md`, `stepik-plan.md` и названий модулей в `04_course/README.md`. Для текущего канона валидируются 9 модулей, 21 Lesson ID и платформенный предел не более 16 логических шагов на урок.

## Live inspect

Для live inspect нужен обычный числовой `course_id`, а OAuth-секреты должны находиться только в environment или GitHub Actions Secrets:

```text
STEPIC_CLIENT_ID
STEPIC_CLIENT_SECRET
```

Локальный пример:

```bash
cp scripts/stepik_uploader/.env.example .env
# заполнить .env локально и экспортировать переменные окружения своим способом
python scripts/stepik_uploader/stepik_uploader.py inspect --course-id 123456 --repo-root .
```

`.env` уже исключён из Git. Не передавайте `client_secret`, access token, пароль или cookies в чат, issue, PR, Actions input или лог.

`inspect` читает цепочку `course → sections → units → lessons → steps/step-sources`, сохраняет нормализованный snapshot и пытается однозначно распознать M00-L01/M00-L02 по каноническим заголовкам и позициям. Любая неоднозначность становится blocker.

## Идемпотентность и сетевые ошибки

- `DELETE` не используется.
- Golden lessons никогда не входят в write-set.
- Существующий объект не обновляется по одному совпавшему признаку.
- GET может повторяться только для временных `429/5xx`.
- POST/PUT автоматически не повторяются: повтор POST после сетевой неопределённости способен создать дубль.
- После включения write-фазы каждая запись должна получать отдельный read-back до следующей операции.

## Stepik Files

По официальной справке Stepik файлы курса/урока загружаются через интерфейс настроек, а learner получает файл по ссылке, вставленной автором в шаг. Стабильный официальный upload/list endpoint для этих файлов в текущей документации не подтверждён.

Поэтому базовый v1 fallback — `manual-stepik-files`:

1. automation создаёт только подтверждённую структуру;
2. владелец загружает нужные assets через Stepik UI;
3. владелец копирует обычные ссылки;
4. ссылки попадают в URL-map;
5. content phase блокируется, пока нужный Asset ID не разрешён в URL.

Если позже эмпирически и по документации будет подтверждён устойчивый API-маршрут, его можно добавить отдельным PR без изменения канонического learner-facing содержания.

## Особые педагогические блокировки

Компилятор сохраняет `author_only`, `independence_sensitive` и `f1_sensitive`. Author-only строки исключаются из потенциального learner write-set. Для M03-L02, M04-L02, M05-L02, M06-L04, M07-L01 и M07-L02 автоматическое склеивание temporal boundaries недопустимо. `M07-L02` требует отдельного F1 integrity pass до массовой публикации.

API `201 Created` или точный read-back подтверждают только техническую запись. Они не доказывают педагогическую самостоятельность ученика и не делают WAVE 0 READY.
