# Защита live-синхронизации GitHub → Stepik

**Статус:** production automation contract  
**Курс Stepik:** `299189`  
**Источник содержания:** только текущий HEAD `main`

Этот документ фиксирует инфраструктурные условия до обращения production workflow к реальному Stepik API. Он не меняет learner-facing содержание курса и не разблокирует общий bulk write.

## 1. Current-main guard

Любой актуальный production job, который собирается обратиться к реальному Stepik API, непосредственно перед live-фазой выполняет `scripts/stepik_uploader/live_guard.py`.

Guard разрешает live-фазу только если одновременно:

- `GITHUB_REF == refs/heads/main`;
- `GITHUB_SHA` является полным Git SHA;
- GitHub API успешно возвращает текущий `refs/heads/main`;
- remote HEAD `main` точно совпадает с `GITHUB_SHA` данного run.

Feature branch, устаревший SHA, недоступный GitHub API или неоднозначный ответ = STOP до Stepik API.

## 2. Единый mutex курса

Все актуальные live jobs курса `299189` используют один GitHub Actions concurrency group:

```yaml
concurrency:
  group: stepik-live-course-299189
  cancel-in-progress: false
```

Mutex фиксирован по реальному course ID и не строится из пользовательского `inputs.course_id`.

Это сериализует актуальные live workflows, включая Stepik Uploader и Stepik Bulk Status, и не позволяет двум штатным live job одновременно менять/проверять один курс.

## 3. Offline CI не держит live mutex

Unit tests, structural dry-run и обычный PR CI выполняются отдельно от live mutex и без Stepik credentials.

Mutex применяется только к job, который действительно может перейти к live Stepik API. Человеческая привычка запирать вообще всё одним замком обычно заканчивается тем, что никто уже не помнит, зачем замок был нужен; здесь этого не делаем.

## 4. Machine-readable deployment state

Issue `#54` содержит единый machine-readable sync state согласно `SYNC-POLICY.md`:

- confirmed lesson baselines;
- `pending.lessons`;
- отдельный `pending.course_page`.

Live sync читает state до Stepik-фазы и после успешного verified result повторно читает Issue перед PATCH.

Если machine state изменился между этими чтениями, PATCH запрещён. Run останавливается, чтобы не затереть более новое pending/baseline состояние.

## 5. Pending closure после live check

Pending конкретного lesson object закрывается только после `result.verified == true` и одного из результатов:

- `APPLIED`;
- `NOOP_CONFIRMED`.

APPLIED обновляет baseline только после read-back. NOOP_CONFIRMED не отправляет фиктивную запись и закрывает pending только потому, что live Stepik, current canonical content и baseline подтверждённо совпали.

Другие pending lessons и `pending.course_page` таким sync не затрагиваются.

## 6. Никакого автоматического retry write

После неуспешной или неоднозначной live операции автоматический write retry запрещён.

Следующий запуск сначала заново проверяет:

- current main;
- deployment baseline;
- live Stepik fingerprint;
- structural/golden guards.

Причина проста: повторять внешний write после неизвестного partial result без reconcile означает превращать журнал deployment в художественную литературу.

## 7. Read-back обязателен

Успешный HTTP status сам по себе не считается подтверждением применения.

После разрешённой записи automation читает live объект снова и сравнивает его с ожидаемым результатом. Baseline и закрытие pending разрешены только после успешного read-back.

## 8. DELETE и структурные изменения

Автоматический `DELETE` запрещён.

Не подтверждённые этим контуром изменения количества steps, reorder и lesson metadata блокируются. Текущий эксплуатационный write route остаётся узким и idempotent.

## 9. Golden и bulk ограничения

- M00-L01/M00-L02 остаются golden `READ_ONLY`;
- M02-L01 остаётся pilot lesson с подтверждённым deployment baseline;
- общий bulk write закрыт;
- `Stepik Bulk Status` является read-only preflight и не превращается в bulk writer от одного успешного статуса.

## 10. Push в main не выполняет Stepik write

После merge/push в main dependency-aware impact job:

- не использует Stepik credentials;
- не обращается к Stepik API;
- строит before/after dependency graph;
- обновляет machine-readable PENDING в Issue `#54` с compare-before-patch race guard.

Неизвестная learner-facing dependency = STOP и красный job, а не молчаливое отсутствие pending.

## 11. Что current-main guard и mutex не решают

Они не являются полным механизмом recovery после внешней partial write.

Если Stepik write уже состоялся, а последующий state PATCH не смог завершиться из-за race/сбоя, требуется отдельный reconcile. Полноценные partial-write recovery, deployment history, baseline reconcile и ownership matrix относятся к следующему этапу инфраструктуры.

Также этот контракт не изменяет branch protection/rulesets/GitHub Environment/secrets. Такие организационные меры вводятся только по отдельному распоряжению владельца.

## 12. Fail-closed при конфликте

Если любой guard, baseline comparison, dependency mapping, read-back или state race нельзя однозначно подтвердить, automation останавливается.

Ни актуальный Stepik content, ни Issue `#54` не перезаписываются «по наиболее вероятному варианту».
