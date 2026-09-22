# Production batches

## Общий порядок

Последовательность обязательна:

`B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7`.

Причина порядка: сначала безопасная opt-in инфраструктура, затем курс от входных навыков к independent/F1. Поздние уроки зависят от терминов, технических операций и support routes ранних модулей.

До B7 не выполнять Stepik write. Каждый content batch проверяет **offline final HTML**; private staging остаётся на предыдущей принятой версии до завершения всей миграции. Это предотвращает смешанный live-state, где часть курса уже authored-semantic, а часть ещё legacy.

## B0 — Infrastructure, no learner diff

**Scope:** INF-01, INF-02.

**Files:** production compiler/parser/tests only.

**Prerequisites:** Step 2 architecture merged.

**Forbidden:** opt-in любого урока; source/assets changes; Stepik write.

**Semantic acceptance:** learner output всех 21 уроков не меняется.

**Machine acceptance:**
- 21/21 legacy compile;
- normalized HTML equivalence current main;
- parser принимает только точный `<!-- learner-render-contract: authored-semantic-v1 -->`;
- authored lesson требует `Semantic type` у каждого row;
- authored span без H2/H3 fail'ится вместо title fallback;
- negative/positive authored-mode fixtures;
- author-only leakage test;
- inline-source single-copy tests.

**Audits:** normal critic. ZERO-LEVEL/PEDAGOGUE не требуются, только если доказан нулевой learner diff.

**Stepik impact expectation:** code path может быть классифицирован как global impact существующей системой, но external write не выполняется. Это сохраняется как известный pending operational effect до B7.

## B1 — M00: orientation and technical foundation

**Lessons:** M00-L01, M00-L02, M00-L03.

**Primary tasks:** ARCH-01/02/03/04/05/09/10/11, TECH-01.

**Key risks:** первый опыт абсолютного новичка, новый/чистый чат, PRIMARY/BACKUP, inline-vs-navigation, поля ответа.

**Prerequisites:** B0 PASS.

**Allowed files:** три `lesson.md`, три `stepik-plan.md`, только связанные learner assets/support if required.

**Forbidden:** изменение компетенций, обязательный backup всем, лишняя отчётность.

**Semantic acceptance:**
- первый внешний action имеет достаточную техническую опору;
- объяснение не притворяется практикой;
- check в Stepik не отправляет ученика отвечать ИИ;
- M00-L03 material route однозначен;
- все три урока opt-in authored mode.

**Machine acceptance:** compiled HTML diff ограничен M00; no synthetic frame; links/assets resolve; step count/IDs reconciled if boundaries change.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE на весь M00 route.

**Stepik:** no write.

## B2 — M01–M02: result evaluation, context and honest evidence

**Lessons:** M01-L01, M01-L02, M02-L01, M02-L02.

**Primary tasks:** ARCH-01/02/03/04/05/07/12, LOCAL-01, LOCAL-02.

**Key risks:** absence-of-evidence, inline scope, собственный выбор vs косметическая переформулировка, already-good result.

**Prerequisites:** B1, чтобы ранние операции/термины уже были стабильны.

**Forbidden:** принуждать к изменению хорошего результата; придумывать evidence; раскрывать готовый контекст.

**Semantic acceptance:**
- «нет относящихся сведений» допустим как результат проверки;
- M02 practice сохраняет собственный выбор ученика;
- inline cards не показывают будущую фазу;
- support доступна в момент нужды.

**Machine acceptance:** compiled HTML final order matches plan; no duplicated inline-source.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE по M01–M02 route.

**Stepik:** no write.

## B3 — M03–M04: independence, source checking and asset repair

**Lessons:** M03-L01, M03-L02, M04-L01, M04-L02, M04-L03.

**Primary tasks:** ARCH-01/02/03/04/05/06/08/09, ASSET-01, LOCAL-03.

**Key risks:** самостоятельный выбор метода/основания, recovery, damaged PNG, source verification.

**Prerequisites:** B2; для ASSET-01 доступен подлинный допустимый source image.

**Forbidden:** сгенерированный fake UI; вторая обязательная регистрация; готовый метод проверки в M04-L03 independent step.

**Semantic acceptance:**
- M04-L03 independent attempt не получает method/source/order;
- recovery после content hint использует новую содержательно иную попытку;
- M03-L02 asset repair не объявляется HUMAN VISUAL PASS;
- navigation возвращает к реальной операции.

**Machine acceptance:** PNG decodes; hashes/materialization plan consistent; final HTML contains correct image branch and no author-only material.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE; отдельный adversarial independence check M04-L03.

**Stepik:** no write.

## B4 — M05: image generation/edit and recovery

**Lessons:** M05-L01, M05-L02.

**Primary tasks:** ARCH-01/02/03/04/05/07/09/10/12, LOCAL-04.

**Key risks:** B7 vs B8, actual edit existing image, backup differences, recovery disclosure.

**Prerequisites:** B3.

**Forbidden:** считать regeneration реальным edit; выдавать фон/конкретную правку как правильное решение; заставлять менять уже пригодный результат без новой цели.

**Semantic acceptance:**
- B7 и B8 различимы;
- для B8 существует реальная потребность изменить existing image либо честная альтернативная ситуация;
- recovery сохраняет собственный выбор;
- limiting support появляется только в разрешённый момент.

**Machine acceptance:** source/material ordering, asset resolution, no early disclosure fixture.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE; отдельная проверка B8 invariant.

**Stepik:** no write. SERVICE PASS не закрывается.

## B5 — M06: grounds, verification and application

**Lessons:** M06-L01, M06-L02, M06-L03, M06-L04.

**Primary tasks:** ARCH-01/02/03/04/05/06/08/12.

**Key risks:** B9/B10/B11/B12, support timing, independent categories, recovery/application routing.

**Prerequisites:** B4.

**Forbidden:** подсказывать тип основания/статус до independent action; заменять реальное основание self-check ИИ; считать отказ применением.

**Semantic acceptance:**
- M06-L04 independent action идёт до post-action categories/check;
- непроверенное существенное не применяется как подтверждённое;
- безопасный отказ сохраняется как корректное решение, но B12 требует дальнейшего реального завершения;
- recovery не обязателен всем и возвращается к C01/application.

**Machine acceptance:** final route/order fixtures for M06-L04; inline scope M06-L03; known Stepik HTML normalization preserved.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE; adversarial independence check M06-L04.

**Stepik:** no write.

## B6 — M07–M08: rehearsal, F1 and reflection

**Lessons:** M07-L01, M07-L02, M08-L01.

**Primary tasks:** ARCH-01/02/03/04/05/06/08, F1-01.

**Key risks:** единственный F1, SEM-117/118, false PASS, early rubric leakage, превращение M08 во второй экзамен.

**Prerequisites:** B5. Все необходимые компетенции и recovery patterns уже стабильны.

**Forbidden:**
- готовая задача F1;
- готовый method/source/next step;
- полная rubric до E01;
- автоматический NOT PROVEN из-за отсутствия отдельного поля;
- обязательная вторая работа успешному ученику;
- новая генерация/доказательство в M08.

**Semantic acceptance:**
- M07-L01 остаётся rehearsal;
- M07-L02 остаётся единственным independent F1;
- фактическое применение обязательно;
- post-check покрывает SEM-117;
- SEM-118 даёт честный repeat только при реальной недоказанности/contamination;
- M08 только reflection/transfer.

**Machine acceptance:** F1 leakage fixtures; author-only A02 absent from pre-attempt learner HTML; A03 appears post-action; all transitions terminate before M08.

**Audits:** critic + ZERO-LEVEL + PEDAGOGUE + отдельный adversarial F1 review.

**Stepik:** no write.

## B7 — whole-course integration and legacy removal

**Scope:** DOC-01 + integration only.

**Prerequisites:** B1–B6 merged with all 21 lessons authored-semantic-v1 and PASS.

**Allowed files:** compiler/tests/docs plus corrections found by integration audit. Любая новая learner correction возвращается в соответствующий scoped audit.

**Actions:**
1. assert 21/21 authored mode и 100% final rows (N/N; baseline = 148) с валидным `Semantic type`;
2. remove legacy framing and dead heuristics;
3. update GENERAL-COMPILER/README;
4. whole-course compile;
5. compare lesson/step counts, IDs, links, assets, author-only isolation;
6. structural regression;
7. semantic zero-level reading of all changed final HTML with risk-weighted full check of independence areas;
8. pedagogue integration check;
9. only after merge, run existing guarded private Stepik release from current main.

**Forbidden:** manual Stepik editing; bypass existing release workflow; declare HUMAN VISUAL/SERVICE/Human Pilot closed.

**Machine acceptance:** 21/21 compile; no legacy path; no unresolved dependencies; known normalization tests pass; no internal IDs; no duplicate inline-source.

**Human/model acceptance:**
- ordinary independent critic: PASS;
- **full ZERO-LEVEL audit: 100% final learner HTML (N/N; baseline = 148), отдельный проход, PASS**;
- **full PEDAGOGUE audit: 100% final learner HTML (N/N; baseline = 148), отдельный проход, PASS**.

Scoped audits B1–B6 не заменяют эти два финальных whole-course прохода. Если semantic boundary repair меняет число шагов относительно baseline 148, сначала фиксируются новый N и полная reconciliation таблица старые→новые IDs/ссылки; затем оба аудита покрывают N/N. B7 merge запрещён, пока любой из трёх verdict не PASS.

**Stepik impact expectation:** all 21 lessons may be PENDING because shared compiler changed. After accepted B7 main, perform one guarded private release, reconcile read-back, then reopen required HUMAN VISUAL/device/service gates for the changed course.

## Batch failure rule

Если batch получает blocker, следующий batch не начинается, пока blocker не исправлен и соответствующий audit не повторён. Исключение только для чисто независимых ASSET/SERVICE external gates, если архитектурный source уже доказуемо корректен и проектные правила явно разрешают отложенный gate; такой gate нельзя ошибочно помечать PASS.
