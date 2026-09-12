# FULL CUMULATIVE COURSE AUDIT M00–M08 — 2026-09-12

**Репозиторий:** `Herurg123/Basic-AI-Course`  
**Аудируемая ветка:** `main`  
**Аудируемый HEAD:** `de0c7cbd9b9ec60440a378675482de0af134c47e`  
**Причина повторного запуска:** merge PR #31 с исправлением `CUM-01` для M04-L02.  
**Роль:** independent cumulative auditor, не production-author.  
**Human validation:** `NOT PERFORMED`.

## 1. Итоговый verdict

**FULL CUMULATIVE M00–M08: PASS / CLEAN.**

- **CRITICAL:** 0
- **NONCRITICAL BLOCKING:** 0
- **POLISH:** 3

Предыдущий blocking finding `CUM-01` закрыт. После его исправления заново прочитаны нормативные документы, архитектурные контракты, assessment/coverage, production summaries, synthetic pre-pilot, service acceptance и все 21 урока в learner order с `lesson-card.md`, `lesson.md`, `stepik-plan.md`, author-only материалами и релевантными assets.

Новых blocking-регрессий не обнаружено.

Следующий обязательный gate: **HUMAN PILOT / HUMAN VALIDATION** до beta / публичного выпуска.

## 2. Scope и read order

Повторный аудит выполнен по новому `main`, а не только по diff PR #31.

Проверены:

1. `AGENTS.md` и Project Instructions v1.3;
2. Manifest v1.2 + v1.3;
3. Course Architecture v1.0 + v1.1;
4. Competency Map v1.1 + v1.2;
5. Service Matrix v1.0 + v1.1;
6. Lesson Standard v1.1 и lesson template;
7. Coverage Matrix, lesson coverage, assessment, operations, assets/validation;
8. Next Levels v1.0;
9. decision logs F1 / AGE / PILOT-DEFER / STEPIK-FLOW;
10. root/course/testing README;
11. Service Acceptance;
12. production summaries M00–M08;
13. synthetic pre-pilot M00–M08;
14. все 21 урока M00→M08 и релевантные learner/author assets.

Перед записью результата повторно проверено, что `main` не изменился во время аудита и остаётся на `de0c7cbd...`.

## 3. Course-level contract

Cumulative production соответствует базовому обещанию курса: выпускник не обязан «знать всё об ИИ», но должен уметь самостоятельно и безопасно решить простую новую реальную задачу с ИИ, использовать свой материал при необходимости, оценить результат, доработать при реальной проблеме, проверить существенное по реальному основанию когда это нужно, фактически применить результат и перенести подход на новую ситуацию/сервис.

Ключевые invariants сохранены:

- independence = без substantive/content hint;
- technical/interface help допустима;
- evidence = наблюдаемое действие, не намерение и не quiz;
- temporal evidence для independent возникает до раскрытия способной подсказать рубрики;
- contaminated recovery использует действительно новую ситуацию;
- B3 privacy решается до передачи;
- B8 = реальный edit существующего исходника, не regeneration;
- B10 = реальное основание, не второй ИИ;
- B12 = фактическое применение;
- F1 = собственная новая реальная задача, actual completion + actual application;
- M08 = reflection/reuse после F1, не второй экзамен;
- Stepik sequencing честно advisory, без фиктивного hard gate;
- возраст остаётся внешней политикой платформы, не внутренним course gate.

## 4. Результат по модулям

| Module | Verdict | Cumulative conclusion |
|---|---|---|
| M00 | **PASS** | раннее действие, safety до ввода/upload, B0 только level 2, без скрытых цифровых prerequisites |
| M01 | **PASS** | оценка результата, конкретная доработка, реальное малое применение, поддержанная ранняя проверка основания |
| M02 | **PASS** | задача/критерий/существенный контекст без prompt-template и overprompt-догмы |
| M03 | **PASS** | самостоятельный текстовый цикл level 3; temporal evidence и honest contamination recovery защищены |
| M04 | **PASS** | свой материал + privacy-before-transfer; `CUM-01` закрыт новым B3 recovery R1 |
| M05 | **PASS** | B7 требует live generation; B8 требует real edit; contamination recovery защищён |
| M06 | **PASS** | полный B10: реальный источник, входы+расчёт, отсутствие достаточного основания; actual application |
| M07 | **PASS** | rehearsal не закрывает F1; финальный F1 собственный, adaptive, independent, completion/application обязательны |
| M08 | **PASS** | база уже завершена после F1; только перенос/reflection, без second exam/upsell |

## 5. Компетенции и границы зачёта

В cumulative контексте placement всех 19 competency ID согласован с архитектурой.

- `A1`, `A2`: самостоятельная оценка существенного и выбор основания защищены в M06-L04/F1.
- `B0`: целевой уровень 2, не маскируется под содержательную самостоятельность.
- `B1`, `B2`, `B5`, `B6`: independent evidence в M03-L02, без pre-attempt workflow; temporal trace обязателен.
- `B3`: **PASS после fix PR #31**; pre-transfer action + hidden materially-new recovery.
- `B4`: own neutral material в M04-L03, готовый asset курса не заменяет свой материал.
- `B7`: live image generation.
- `B8`: real edit existing source; regeneration не засчитывается.
- `B9`, `B10`, `B11`: полный независимый контур M06-L04 с реальным основанием и безопасным stop/switch.
- `B12`: реальное применение, особенно M06-L04 и F1.
- `C1`: выбор следующего действия не выдаётся готовой таблицей решений на независимых попытках.
- `C2`: transfer по типу задачи/интерфейса без обязательной повторной регистрации второго сервиса.
- `C3`: объяснение связано с реально выполненными решениями.
- `F1`: только `M07-L02-C01`; собственная новая простая/безопасная задача, actual completion + actual application.

## 6. Закрытие CUM-01

Предыдущий blocker был в M04-L02: learner-facing contract правильно говорил, что content hint загрязняет B3 level-3 attempt и требует новую ситуацию, но production не содержал заранее подготовленного recovery.

После PR #31:

- content hint явно переводит исходную попытку в `PRACTICE / CONTAMINATED`;
- post-hoc «я и так это знал» не восстанавливает independence;
- technical/interface help отделена от content hint;
- добавлен hidden author-only `R1` под тем же `M04-L02-C01`;
- `R1` существенно отличается от A02: внутренний групповой чат → публичное объявление, смешанные сведения и другая структура;
- learner сам принимает privacy-решение до передачи;
- нужен реальный safe version / safe retelling / refusal, а не список намерений;
- evidence фиксируется до author-key/rubric;
- чистый R1 PASS подтверждает B3 и сохраняет валидный prerequisite M04-L03;
- повторно загрязнённый R1 не получает independent PASS.

**CUM-01: CLOSED / PASS.**

## 7. False-PASS adversarial matrix

Повторно атакованы ключевые пути ложного зачёта.

| False-PASS path | Result |
|---|---|
| принять первый уверенный ответ без оценки | **BLOCKED** |
| пройти level 3 копированием готового prompt/template | **BLOCKED** |
| дать правильные слова только post-action | **BLOCKED / NOT PROVEN** |
| восстановить отсутствующий pre-rubric trace задним числом | **BLOCKED / NOT PROVEN** |
| механически написать «проверка не требовалась» при существенном утверждении | **BLOCKED** |
| загрузить материал до privacy-решения | **BLOCKED** |
| использовать согласие второй модели как B10 evidence | **BLOCKED** |
| заменить edit новой генерацией | **BLOCKED** |
| оставить результат только в чате | **BLOCKED** для B12/F1 |
| не выполнить actual application | **BLOCKED** |
| сохранить independent PASS после content hint | **BLOCKED; attempt → PRACTICE** |
| повторить contaminated task с косметической заменой имён/чисел | **BLOCKED** |
| получить готовый F1 exam case | **BLOCKED; его нет** |
| пройти F1 на high-stakes реальной задаче | **BLOCKED по admissibility** |
| превратить M08 в второй экзамен | **BLOCKED архитектурой и learner text** |

## 8. False-FAIL protection

Курс не вводит лишние требования ради красивой рубрики.

- хороший первый результат не обязан искусственно дорабатываться;
- file/search/image/calculator/second service не требуются, если не нужны задаче;
- если существенного проверяемого утверждения нет, B10 не навязывается искусственно;
- safe refusal является корректным действием, хотя F1 всё равно требует позже завершить допустимую задачу;
- простая реальная F1-задача может пройти, если она не пустая, действительно завершена и применена, а все применимые измерения доказаны;
- после курса допустимый итог — просто продолжать практиковать базу на новых задачах.

## 9. Progression / fading support

Cumulative progression остаётся постепенной:

`M00 действия и safety → M01 оценка/доработка → M02 постановка/контекст → M03 самостоятельный текстовый цикл → M04 свой материал/privacy → M05 visual create/edit → M06 verification/stop/apply → M07 integration/F1 → M08 reuse/reflection`.

Поддержка уменьшается перед level-3 checks. Ни M06-L04, ни F1 не содержат скрытого универсального workflow. F1 rubric остаётся outcome/evidence-based и adaptive к выбранной задаче.

Prompt dogma / обязательной формулы «идеального промпта» не обнаружено.

## 10. Service / portability / free path

Current Service Acceptance сохраняет пригодный базовый маршрут обязательных функций B4/B7/B8/B10.

Базовый course path не требует:

- обязательной платной подписки;
- VPN;
- зарубежной карты;
- обязательного premium-сервиса;
- обязательной второй модели как evidence.

PRIMARY/BACKUP не дублируют содержание уроков. B10 опирается на реальное внешнее основание/исходник/расчёт, а не на бренд модели.

Dynamic service/UI слой должен быть повторно проверен перед публикацией, как и предусмотрено governance.

## 11. Asset / ID integrity

Cumulative structure остаётся:

- 9 модулей;
- 21 Lesson ID;
- 19 competency ID;
- 41 канонический Asset ID.

Staged views, master/source/derivative files и hidden recovery scenarios не создают ложных новых Asset ID.

Fix M04-L02 не создал новый Exercise/Check/Asset ID.

### Ограничение текущего аудита по binary visual QA

Репозиторий на audited HEAD содержит неизменённые бинарные production derivatives, включая M00-L02 DOCX/PNG и M03-L02 PNG. Их blob SHA и физическое наличие подтверждены; production summaries фиксируют предыдущий render/visual check.

Текущий GitHub connector не даёт свежего pixel-level render бинарников внутри этого audit pass. Поэтому этот проход не заявляет новое независимое визуальное открытие каждого binary asset. Это ограничение инструмента, а не обнаруженный дефект курса; blobs не менялись относительно ранее принятого состояния.

## 12. Workload / cognitive load

Суммарная карточечная гипотеза 21 урока остаётся **271–470 минут**, то есть примерно **4 ч 31 мин – 7 ч 50 мин**, без перерывов и повторных попыток.

Это **не human-validated duration**.

Особенно pilot-critical участок: `M06-L04 → M07-L01 → M07-L02`.

## 13. POLISH findings

### POLISH-01 — learner-facing internal labels / jargon

В нескольких learner-facing местах ещё видны внутренние или полуавторские обозначения: `B3`, `B8`, `C01`, `level 3`, `post-action`, `technical/interface` и подобные.

После fix M04-L02 learner-part R1 также показывает служебный ID `M04-L02-C01`.

Это не меняет действие и не создаёт false PASS, но для абсолютного новичка такие маркеры являются лишним шумом. Рекомендуется отдельный nonblocking cleanup перед публикацией.

### POLISH-02 — synthetic probe «слишком простая задача»

В synthetic M07–M08 профиль с названием «выбрал слишком простую задачу» фактически атакует отсутствие наблюдаемого completion/application. Это полезный probe, но label шире фактически проверяемого риска.

Не вводить из этого новый несуществующий стандарт «задача должна быть достаточно сложной». F1 оценивает реальность, самостоятельность, completion/application и применимые компетенции, а не демонстративную сложность.

### POLISH-03 — историческая M04–M05 production summary

`04_course/vertical-slice-m04-m05-production-summary.md` отражает состояние исходного production batch и указывает для M04-L02 `author-notes: не нужен`. После более позднего CUM-01 fix `M04-L02/author-notes.md` существует и является частью current production.

Документ явно является исторической author summary старой ветки и не используется как current operational source, поэтому это не blocker. Для снижения архивной неоднозначности можно позднее добавить краткую superseded-note вместо переписывания истории задним числом.

## 14. Human pilot — следующий обязательный gate

**Human validation status: NOT PERFORMED.**

Clean cumulative audit не заменяет живой pilot.

Human pilot должен особенно проверить:

1. фактическое время прохождения и retry rate;
2. усталость на M06-L04 → M07;
3. понятность первых 30 минут для абсолютного новичка;
4. различение technical help и content hint;
5. мешают ли внутренние ID/jargon;
6. file/upload/save действия на desktop/mobile;
7. перенос privacy-before-transfer на собственные реальные данные;
8. способность выбрать F1-задачу, не слишком большую и не пустую;
9. понимание ситуации, когда verification действительно не требуется;
10. live B7/B8 UI/service limitations;
11. поведение при раннем просмотре следующих Stepik steps;
12. completion/attrition и фактическое ощущение завершённости базы перед M08.

## 15. Final gate decision

**CUMULATIVE PRODUCTION GATE M00–M08: PASSED.**

Курс можно переводить на следующий этап **HUMAN PILOT / HUMAN VALIDATION**.

Нельзя пока утверждать:

- что курс human-validated;
- что заявленное время подтверждено людьми;
- что beta/public release разрешён;
- что реальные новички стабильно проходят F1 без дополнительных production fixes.

После human pilot любые выявленные blocking-проблемы должны возвращаться в обычный fix → review → regression cycle.
