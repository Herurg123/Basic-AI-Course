# Защита live-синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Источник содержания:** только текущий HEAD `main`

Этот документ фиксирует инфраструктурные условия, которые должны выполняться до любого обращения production workflow к реальному Stepik API. Он не меняет learner-facing содержание курса и не разблокирует массовую запись.

## 1. Current-main guard

Любой GitHub Actions job актуального production tooling, который собирается обратиться к реальному Stepik API, обязан непосредственно перед live-фазой выполнить `scripts/stepik_uploader/live_guard.py`.

Guard работает fail-closed и разрешает live-фазу только если одновременно:

- `GITHUB_REF == refs/heads/main`;
- `GITHUB_SHA` является полным Git SHA;
- GitHub API успешно возвращает текущий `refs/heads/main`;
- SHA текущего remote HEAD `main` точно совпадает с `GITHUB_SHA` данного run.

Если workflow был запущен с feature branch, если `main` успел получить новый commit, если GitHub API недоступен или ответ нельзя однозначно проверить, live-фаза останавливается до обращения к Stepik.

Проверка выполняется после ожидания live mutex. Поэтому run, который долго ждал другой live job, не получает права работать со старым checkout только потому, что на старте он был актуальным.

Guard не является механизмом отмены уже начатого Stepik write. После прохождения guard live-операция выполняется как единая защищённая фаза; автоматическое прерывание write из-за нового commit в середине операции запрещено, потому что это повышает риск частично записанного состояния. Следующий deployment снова обязан пройти current-main guard и обычные baseline/drift checks.

## 2. Единый live mutex текущего production course

Все production jobs, обращающиеся к реальному Stepik course `299189`, используют один фиксированный job-level concurrency contract:

```text
stepik-live-course-299189
```

Имя mutex намеренно не строится из пользовательского `course_id`. Иначе строки вроде `299189` и `0299189` могли бы попасть в разные concurrency groups, хотя после числового разбора указывали бы на один и тот же Stepik course.

`cancel-in-progress` всегда `false`: новый read-only или write run не имеет права отменять уже начатую live-фазу.

Один и тот же mutex используют как минимум:

- live job workflow `Stepik Uploader`;
- live job workflow `Stepik Bulk Status`;
- будущие workflows этого же production course, если они читают или пишут live Stepik.

Read-only inspect не выполняется параллельно с write. Два read-only live run тоже сериализуются. Это намеренно: preflight snapshot должен описывать одно устойчивое состояние курса, а не объект, который другой workflow меняет во время чтения.

Если в проекте когда-либо появится второй production Stepik course, для него сначала вводится отдельный явно проверенный fixed mutex и target-validation contract. Пользовательский input не должен сам определять пространство блокировок.

## 3. Что не сериализуется

Offline CI не использует live mutex:

- unit tests;
- structural dry-run без Stepik API;
- PR-проверки;
- локальный impact-detector после merge.

В `Stepik Bulk Status` unit tests вынесены в отдельный offline job. Только последующий live job получает production Stepik credentials и общий mutex.

## 4. Порядок live job

Безопасный порядок:

1. offline tests;
2. job получает общий live mutex;
3. checkout и подготовка runtime;
4. при необходимости читается GitHub deployment baseline;
5. выполняется current-main guard через GitHub API;
6. только после PASS разрешается Stepik API;
7. далее действуют golden/baseline/drift/idempotency/read-back guards конкретного режима.

Current-main guard не заменяет golden profile, deployment baseline, asset hash gate, `confirm_write`, read-back или запрет `DELETE`. Он добавляет отдельное условие: live Stepik нельзя читать или менять от имени уже устаревшего канонического commit.

## 5. Blocker contract

Типовые причины STOP:

- `live-source-not-main` — run запущен не из `refs/heads/main`;
- `live-source-stale-main` — remote HEAD `main` уже отличается от `GITHUB_SHA` run;
- `remote-main-check-failed` — GitHub API не позволил доказать актуальность `main`;
- отсутствует или некорректен `GITHUB_SHA` / `GITHUB_REPOSITORY` / GitHub token.

При blocker Stepik API не вызывается. Guard сохраняет machine-readable `live-source-guard.json` в artifact-каталог конкретного live workflow.

## 6. Граница гарантии без repository-level controls

Текущая защита действует в актуальных версиях production workflows и блокирует случайный dispatch актуального workflow с feature branch или устаревшего SHA.

Она не может задним числом переписать историческую feature branch, в которой сохранена старая версия workflow до появления `live_guard.py`. Абсолютно запретить запуск таких исторических workflow можно только repository-level механизмами вроде branch/ruleset/environment/secret scope. Владелец проекта явно исключил этот класс изменений до отдельного распоряжения.

Поэтому до такого распоряжения действует операционное правило: live Stepik dispatch выполняется только из текущего `main`; исторические ветки не используются как production launcher. Это известное ограничение, а не разрешение ослаблять guard в актуальном tooling.

## 7. Ограничения этого этапа

Эта защита не решает и не должна решать:

- general content compiler;
- golden migration M00-L02;
- machine-readable PENDING backlog;
- dependency-aware impact;
- deployment history/recovery;
- branch protection, repository rulesets, GitHub Environment или организацию secrets.

Последний пункт сознательно исключён владельцем до отдельного явного распоряжения.
