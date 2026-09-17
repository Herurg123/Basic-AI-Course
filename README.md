# Basic AI Course

Базовый бесплатный курс по практической ИИ-грамотности для пользователей нулевого уровня.

## Правило репозитория

`main` содержит только утверждённое состояние проекта и является единственным каноническим источником проектных документов. Содержательные изменения готовятся в отдельных ветках и попадают в `main` через Pull Request после обязательного критического аудита.

После открытия Pull Request рабочий чат или агент сам запускает отдельный критический проход, не ожидая дополнительной команды владельца проекта. Если критик не находит критических проблем, PR сливается в `main` сразу. Если обнаружена критическая проблема или требуется проектное решение владельца, merge останавливается и вопрос выносится на обсуждение.

Для текстовых проектных документов каноническим рабочим форматом является Git-дружественный текстовый исходник, как правило Markdown (`.md`). DOCX и PDF создаются как производные версии для передачи людям, согласования и публикации/переноса в Stepik. Параллельное независимое редактирование `.md` и `.docx` не используется.

Общие источники ChatGPT Project не являются зеркалом GitHub. В них сохраняется bootstrap-копия актуальной проектной инструкции и могут находиться осознанные внешние исходные материалы, которые не дублируют Git-tracked документы. Манифест, архитектура, матрицы, стандарты, шаблоны и производственные файлы читаются из актуального `main`.

Перед работой ИИ-агенты и специализированные чаты должны ознакомиться с bootstrap-инструкцией, затем с актуальной инструкцией проекта в `main`, `AGENTS.md`, действующим манифестом и относящимися к задаче утверждёнными документами непосредственно в `main`.

Все GitHub Actions workflow обязаны завершаться русскоязычной Summary, где без открытия внутренних логов видно: что планировалось, что выполнено, что не выполнено, общий результат и краткая причина ошибки. Для этого используется общий reusable workflow `_russian-run-summary.yml`, а соблюдение правила автоматически проверяется `project-governance.yml`.

## Автоматическая гигиена веток

В репозитории используется GitHub Actions workflow [`.github/workflows/repository-janitor.yml`](.github/workflows/repository-janitor.yml). Он запускается раз в сутки и может удалять только доказанно безопасные рабочие ветки. Принцип автоматики: при любой неопределённости ветка сохраняется.

Workflow жёстко разрешён только для репозитория `Herurg123/Basic-AI-Course` и только при запуске из `refs/heads/main`. Если default branch перестанет быть `main`, уборка аварийно останавливается без удалений.

Автоудаление разрешено только для веток с явно перечисленными рабочими префиксами. Текущий allowlist: `architecture/`, `audit/`, `bootstrap/`, `governance/`, `housekeeping/`, `production/`, `setup/`, `testing/`. `main`, default branch, protected-ветки, ветки из `KEEP_BRANCHES`, неизвестные пространства имён, ветки с открытыми PR и ветки, используемые как base открытого PR, не удаляются.

Ветка со смёрженным в `main` PR может стать кандидатом только если её текущий SHA точно совпадает с head SHA этого смёрженного PR, после merge не было новых коммитов и прошёл установленный карантин. Ветка без подходящего merged PR может стать кандидатом только если сравнение с `main` показывает `ahead_by = 0` и прошёл отдельный более длинный карантин. Непосредственно перед реальным удалением workflow повторно проверяет текущий SHA, protection и открытые PR, чтобы не удалить ветку, состояние которой изменилось во время запуска.

Первые **7 запусков** `Repository Janitor` всегда работают в режиме `DRY-RUN`: удаление физически не выполняется. После защитного периода действует дополнительный circuit breaker: за один запуск может быть удалено не более **5 веток**. Для экстренной остановки реальных удалений можно установить Repository variable `REPOSITORY_JANITOR_FORCE_DRY_RUN=true`; тогда janitor продолжит аудит и русскоязычную сводку, но ничего не удалит.

В сводке GitHub Actions по-русски показываются найденные ветки, кандидаты, удалённые и сохранённые ветки, а также причины каждого решения. Изменение критериев janitor, разрешённых префиксов, `KEEP_BRANCHES`, карантинов, лимита удалений или числа dry-run запусков выполняется только через обычный branch → Pull Request → критический аудит → merge workflow.

## Структура

- `00_governance/` — нормативные документы и проектные правила.
  - `manifest/` — действующий манифест и его версии.
  - `project-instructions/` — общая инструкция проекта.
  - `decision-log/` — журнал существенных проектных решений.
- `01_architecture/` — утверждённая архитектура курса и производные документы.
  - `competency-map/` — карта компетенций.
  - `course-architecture/` — общая архитектура курса.
  - `service-matrix/` — матрица сервисов.
  - `lesson-standard/` — стандарт сценария урока и копируемый шаблон.
  - `coverage-matrix/` — полная матрица покрытия.
  - `next-levels/` — граница следующих уровней обучения.
- `02_research/` — исследования, конкуренты, аудит источников и сервисов.
- `03_sources/` — исходные авторские материалы.
- `04_course/` — уроки и модули курса.
- `05_assets/` — изображения, схемы и прочие материалы.
- `06_testing/` — пилот, бета и результаты тестирования.
- `90_reviews/` — критические аудиты и заключения по Pull Request.
- `releases/` — зафиксированные версии курса и производные публикационные экспорты.

## Текущее состояние

**Педагогический аудит Astra 14.09.2026:** [отчёт по всем 21 уроку](90_reviews/pedagogy-zero-level-2026-09-14/audit-report.md) выявил PED-01…PED-07. Source-level исправления приняты через PR #59; independent critic обнаружил и помог устранить CRIT-C-01 до merge. [Issue #50](https://github.com/Herurg123/Basic-AI-Course/issues/50) сохраняется как контекст аудита и реальных regression/readiness gates, а не как признак отсутствия source-исправлений. Source PASS не закрывает автоматически PED-01 real device route, PED-03 live generation/edit, PED-06 publication visual check, PED-07 итоговый live learner UI и Human Pilot.

В `main` утверждены:

- структура репозитория и workflow;
- [манифест курса v1.3](00_governance/manifest/manifest-v1.3.md), который точечно обновляет полный базовый текст v1.2;
- [инструкция проекта v1.5](00_governance/project-instructions/project-instructions-v1.5.md);
- [карта компетенций v1.2](01_architecture/competency-map/competency-map-v1.2.md), которая точечно обновляет полный базовый текст v1.1 и приводит возрастную границу к D-2026-09-11-AGE;
- [матрица сервисов v1.1](01_architecture/service-matrix/service-matrix-v1.1.md), которая точечно обновляет полный базовый текст v1.0;
- [общая архитектура курса v1.1](01_architecture/course-architecture/course-architecture-v1.1.md), которая сохраняет 9 модулей и 21 Lesson ID и снимает age functional testing из внутренних gates;
- [стандарт сценария урока v1.2](01_architecture/lesson-standard/lesson-standard-v1.2.md), который точечно дополняет базовую [v1.1](01_architecture/lesson-standard/lesson-standard-v1.1.md) правилом «зачем до нового осмысленного действия», и `lesson-template.md`;
- [полная Матрица покрытия v1.0](01_architecture/coverage-matrix/coverage-matrix-v1.0.md): все 19 компетенций, упражнения, проверки, доказательства, сервисы, риски и Asset ID; нижележащие возрастные формулировки читаются с учётом Манифеста v1.3 и Архитектуры v1.1;
- [Карта следующих уровней v1.0](01_architecture/next-levels/next-levels-v1.0.md): граница завершенной бесплатной базы и дальнейшего усложнения; будущие продукты пока являются гипотезами;
- [решение по завершению F1](00_governance/decision-log/2026-09-10-f1-completion.md);
- [решение D-2026-09-11-AGE](00_governance/decision-log/2026-09-11-age-platform-boundary.md): возраст является внешним условием ИИ-платформы, а не внутренним gate курса; «понятно подростку» означает уровень сложности, а не гарантию доступа;
- [решение D-2026-09-11-PILOT-DEFER](00_governance/decision-log/2026-09-11-pilot-defer.md): human pilot M00–M01 остаётся обязательным до beta / публичного выпуска, но его отсутствие больше не блокирует production M02–M08; synthetic/model-based проверки не считаются human validation;
- [решение D-2026-09-12-STEPIK-FLOW](00_governance/decision-log/2026-09-12-stepik-advisory-sequencing.md): ограничения навигации Stepik не подменяются фиктивным hard gate; learner получает понятную рекомендацию и recovery-route;
- [решение D-2026-09-13-LEARNER-UX](00_governance/decision-log/2026-09-13-learner-ux-evidence.md): learner-facing слой использует простой язык и прямые ссылки, independent evidence строится на естественном следе работы без скрытой формы, а recovery физически доступен ученику;
- [решение D-2026-09-13-RATIONALE-BEFORE-ACTION](00_governance/decision-log/2026-09-13-rationale-before-action.md): перед новым смысловым действием новичок получает краткое объяснение, зачем действие нужно, без раскрытия решения самостоятельной задачи;
- [проектные карточки 21 урока v1.0](04_course/README.md), их [сводный аудит](04_course/lesson-cards-v1.0-summary.md) и [возрастной addendum](04_course/lesson-cards-v1.0-age-policy-addendum.md);
- [Service Acceptance 2026-09-11](06_testing/service-acceptance/service-acceptance-2026-09-11.md): **PASS WITH EXPLICIT NONBLOCKING OBSERVATIONS**. PRIMARY Алиса, BACKUP GigaChat, B10 и X01–X10 подтверждены без обязательной оплаты. Историческая строка `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED` после D-2026-09-11-AGE не является текущим блокером проекта; для Human Pilot всё равно нужен свежий current service preflight;
- [production M00–M01](04_course/vertical-slice-m00-m01-production-summary.md): пять ученических уроков, пять Stepik-планов и 11 Asset ID;
- [production M02–M03](04_course/vertical-slice-m02-m03-production-summary.md): четыре ученических урока, четыре Stepik-плана и шесть Asset ID;
- [production M04–M05](04_course/vertical-slice-m04-m05-production-summary.md): пять ученических уроков, пять Stepik-планов и десять Asset ID; M05-L02 сохраняет обязательные живые B7/B8;
- [production M06](04_course/vertical-slice-m06-production-summary.md): четыре ученических урока, четыре Stepik-плана и восемь Asset ID; M06-L04 закрывает самостоятельные A1/A2/B9–B12/C1–C3 с post-action rubric и re-check при содержательном загрязнении попытки;
- [production M07–M08](04_course/vertical-slice-m07-m08-production-summary.md): три ученических урока, три Stepik-плана и шесть ранее зарезервированных Asset ID; независимый adversarial-аудит PR #29 завершён с verdict `APPROVED WITH POLISH`, CRITICAL = 0, NONCRITICAL BLOCKING = 0;
- [UX fix batch для абсолютного новичка](04_course/ux-novice-fix-summary-2026-09-13.md): прямые ссылки, понятный learner-facing язык, четыре статуса проверки, DOCX fallback, learner-facing recovery и бесплатный Stepik evidence-route без платной загрузки файлов;
- model-based synthetic pre-pilot отчёты для M00–M08, которые не являются human validation;
- [FULL CUMULATIVE AUDIT M00–M08](90_reviews/full-cumulative-audit-m00-m08-2026-09-12.md) на `main` @ `de0c7cbd9b9ec60440a378675482de0af134c47e`: **PASS / CLEAN**, CRITICAL = 0, NONCRITICAL BLOCKING = 0, POLISH = 3. Предыдущий `CUM-01` закрыт после fix PR #31;
- [Human Pilot Architecture v1.1](06_testing/human-pilot/human-pilot-architecture-v1.1.md) как текущий point update к полному [v1.0](06_testing/human-pilot/human-pilot-architecture-v1.0.md): актуальные нормативные ссылки, неизменённые F1/independence/contamination/evidence/PASS/FAIL и PED-01…PED-07 regression/readiness contract;
- [Operational Human Pilot Package](06_testing/human-pilot/operational-package/README.md): screener, consent/data handling, private Stepik staging и service preflight checklists, moderator/observer/F1 forms, recovery/evidence aggregation rules, machine-readable logs, issue/retest tracking и report templates; PR #35 прошёл adversarial critic, два найденных operational gap были исправлены до финального `APPROVED`.

Stepik `course_id=299189` остаётся private. Production recovery learner-hygiene/section-order и golden-title migration имеют подтверждённые machine/Human Visual PASS на своих scopes. Но это **не** all-course equivalence proof: current Issue #54 содержит 18 PENDING lessons и pending course-page относительно более нового canonical source; кроме того, остаются physical materialization и real device/service/publication gates.

**Current Wave 0 readiness:** [`06_testing/human-pilot/readiness/wave0-readiness-2026-09-16.md`](06_testing/human-pilot/readiness/wave0-readiness-2026-09-16.md) = `NOT READY / BLOCKED FOR FIRST HUMAN SESSION`. Исторический readiness record 12.09.2026 не переписан.

Human Pilot Architecture и operational package утверждены, но сам human pilot ещё не проведён. Human validation остаётся `NOT PERFORMED`.

Следующий production gate — **сборка и доказательство актуального private Stepik staging**, привязанного к точному `main` SHA. После этого до Wave 0 всё равно должны быть фактически закрыты PED-01 desktop/phone, PED-03 current service generation/edit, PED-06/PED-07 publication/UI checks, consent/data-minimization, moderator rehearsal, current service preflight и наличие двух eligible participants.

После readiness последовательность такая: Wave 0 → Wave 1 → подтверждённые fixes → Wave 2 / retest → итоговый human-validation verdict. Только после human validation возможен переход к closed beta; public release и финальные динамические Stepik/service checks остаются последующими gates.
