# Service Acceptance — 2026-09-11

**Gate status:** `IN PROGRESS — НЕ PASS`  
**Evidence mode available in this chat:** `OWNER-OBSERVED` for live UI actions; `DOC-CONFIRMED` for official-source facts. Interactive Computer Use is unavailable, therefore no UI action is labeled `LIVE-PASS` unless separately observed by an interactive browser agent.

## 1. Purpose

Проверить наблюдаемыми данными, может ли обычный пользователь пройти обязательные технические действия курса по утвержденному бесплатному маршруту: PRIMARY = Алиса AI web; BACKUP = GigaChat + внешний браузер; B10 = реальное внешнее основание; B8 PRIMARY = реальный edit загруженного исходника; B8 BACKUP = узкое изменение/удаление фона.

До положительного завершения gate интерфейсно-зависимый производственный вертикальный срез M00–M01 не считается разрешенным.

## 2. Normative basis

На старте прогона непосредственно из `main` прочитаны:

1. `00_governance/project-instructions/project-instructions-v1.3.md`
2. `AGENTS.md`
3. `README.md`
4. `00_governance/manifest/manifest-v1.2.md`
5. `01_architecture/competency-map/competency-map-v1.1.md`
6. `01_architecture/service-matrix/service-matrix-v1.0.md`
7. `01_architecture/course-architecture/course-architecture-v1.0.md`
8. `01_architecture/lesson-standard/lesson-standard-v1.1.md`
9. `01_architecture/coverage-matrix/coverage-matrix-v1.0.md`
10. `01_architecture/coverage-matrix/coverage-operations-v1.0.md`
11. `01_architecture/coverage-matrix/coverage-assessment-v1.0.md`
12. `01_architecture/coverage-matrix/coverage-assets-and-validation-v1.0.md`
13. `04_course/lesson-cards-v1.0-summary.md`
14. `04_course/M00/M00-L01/lesson-card.md`
15. `04_course/M00/M00-L02/lesson-card.md`
16. `04_course/M00/M00-L03/lesson-card.md`
17. `04_course/M01/M01-L01/lesson-card.md`
18. `04_course/M01/M01-L02/lesson-card.md`
19. `04_course/M05/M05-L02/lesson-card.md`

Governance v1.3 имеет приоритет над историческими ссылками части архитектурных файлов на PI v1.2. Содержательного конфликта, требующего перепроектирования перед acceptance, на старте не обнаружено.

## 3. Test environment

| Parameter | Observed |
|---|---|
| Date | 2026-09-11 |
| Local time | same owner run; per-action timestamps not separately captured |
| Connection | ordinary Russian connection |
| Russian ordinary connection | OWNER-OBSERVED |
| VPN | off |
| Browser/device | Firefox / computer |
| Alice account | anonymous / not logged in for A01–A05 |
| Alice Plus / boosts | not applicable to anonymous A01–A05; no paid action used |
| GigaChat account | NOT TESTED |
| Paid entitlement | no paid entitlement used in observed Alice route |
| Tester | OWNER for live UI actions |

Географическая часть A01–A05 выполнена на обычном российском соединении без VPN по сообщению владельца.

## 4. Accounts and entitlement state

Для A01–A05 Алиса использовалась без авторизации. Это сильнее, чем проверка существующего бесплатного аккаунта для соответствующих функций, но не доказывает, что B7/B8/download также доступны анонимно. Если позднее потребуется login, состояние аккаунта будет зафиксировано отдельно как fresh/free либо `FREE EXISTING ACCOUNT, NOT FRESH`.

GigaChat: `NOT TESTED`.

## 5. Official-source freshness check

Проверено 2026-09-11 по официальным источникам.

| Source | Current fact supported | Evidence status |
|---|---|---|
| https://yandex.ru/legal/alice_chat/ru/ | Алиса AI доступна по `alice.yandex.ru`; несовершеннолетний может пользоваться с ведома, согласия и под контролем законного представителя | DOC-CONFIRMED |
| https://alice.yandex.ru/support/ru/assistant/chat-alice | Базовый чат бесплатен; при высокой нагрузке без Алиса Плюс могут временно быть недоступны генерация картинок и анализ файлов/изображений; текст остается доступен | DOC-CONFIRMED |
| https://alice.yandex.ru/support/ru/assistant/chat/files | Файлы можно отправлять бесплатно; анализ файлов/изображений может временно быть недоступен без Plus при высокой нагрузке | DOC-CONFIRMED |
| https://alice.yandex.ru/support/ru/assistant/chat/picture | B7 доступна на web и заявлена бесплатно без Алиса Плюс, с приоритетом Plus при нагрузке | DOC-CONFIRMED |
| https://alice.yandex.ru/support/ru/assistant/chat/edit-photos | На web заявлено редактирование реально загруженного JPEG/PNG: фон, объекты, стиль и другие изменения; результат можно скачать | DOC-CONFIRMED |
| https://yandex.ru/legal/alicebst/ru/ | Для бесплатных пользователей существуют стандартные лимиты; после исчерпания предлагаются платные бусты, но это не доказывает обязательность оплаты для минимального курса | DOC-CONFIRMED |
| https://developers.sber.ru/docs/ru/policies/gigachat/agreement | GigaChat consumer beta предоставляется без платы для личного некоммерческого использования; формальный пользователь 18+; лица младше 18 — с согласия и под контролем родителя/представителя; обязательна авторизация; Банк может вводить лимиты | DOC-CONFIRMED |
| https://giga.chat/help/articles/how-to-start-work-with-gigachat | Вход по телефону; для нового Сбер ID достаточно российской SIM, быть клиентом банка не обязательно | DOC-CONFIRMED |
| https://giga.chat/help/articles/faq | В РФ GigaChat заявлен как работающий без ограничений; VPN рекомендуют отключить; не-клиент банка может получить Сбер ID по российской SIM | DOC-CONFIRMED |
| https://giga.chat/help/articles/work-with-docs | Анализ DOCX/PDF/TXT официально поддерживается | DOC-CONFIRMED |
| https://giga.chat/help/articles/gigachat-load-picture | Загрузка и анализ изображений официально поддерживаются | DOC-CONFIRMED |
| https://giga.chat/help/articles/how-to-generate-images | Генерация изображений заявлена как бесплатная возможность | DOC-CONFIRMED |
| https://giga.chat/help/articles/background-remove | Standalone удаление/замена фона заявлено бесплатным, браузерным и без регистрации; результат можно скачать | DOC-CONFIRMED / OFFICIAL SOURCE CONFLICT |

### Official source conflict

Для GigaChat есть существенное расхождение: действующее пользовательское соглашение требует обязательной авторизации для использования Сервиса, а help-страница standalone-инструмента удаления фона заявляет, что регистрация не нужна. До живой проверки это фиксируется как `OFFICIAL SOURCE CONFLICT`.

## 6. Alice test matrix

| Test ID | Account | Action | Expected | Observed | Status | Evidence | Affected lessons | Notes |
|---|---|---|---|---|---|---|---|---|
| A01 | anonymous | открыть web и сделать простой текстовый запрос | чат доступен без обязательной оплаты | ответ получен без login | OWNER-OBSERVED-PASS | owner report | M00-L01, M01-L01 | Россия, VPN off, Firefox, computer |
| A02 | anonymous | проверить фактическую обязательность login | различить optional vs required login | text, DOCX и PNG работают anonymous; встроенная кнопка нового чата требует login | OWNER-OBSERVED-PASS / PARTIAL FOR OTHER FUNCTIONS | owner report + screenshot for A05 | M00-L01–L03, M05-L02 | B7/B8/download ещё не проверены |
| A03 | anonymous | новый чат и повторный старт | новый диалог реально создается | встроенный `Новый чат` запросил login; новая вкладка с `alice.yandex.ru` дала новый диалог и ответ | OWNER-OBSERVED-PASS WITH UI CAVEAT | owner report | M00-L03 | курс может использовать новую вкладку/прямую ссылку без обязательной регистрации |
| A04 | anonymous | DOCX fixture upload + вопрос по содержимому | файл прочитан, ответ относится к нему | верно извлечено: после Альфы Бета, 12 условных дней | OWNER-OBSERVED-PASS | owner report | M00-L02 | fixture `AF-DOC-2026-0911` |
| A05 | anonymous | PNG fixture upload + анализ | изображение распознано | верно распознаны `AF-IMG-314`, квадрат слева, круг справа; UI показал визуальные элементы | OWNER-OBSERVED-PASS | owner report + supplied screenshot | M00-L02 | screenshot visibly shows `Войти`, supporting anonymous state |
| A06 | pending | живая B7 | новая картинка реально сгенерирована бесплатно | pending | NOT TESTED | — | M05-L02 | — |
| A07 | pending | реальный edit существующего исходника | изменен именно исходник | pending | NOT TESTED | — | M05-L02 | — |
| A08 | pending | скачать B7/B8 | результат реально сохранен | pending | NOT TESTED | — | M00-L03, M05-L02 | — |
| A09 | pending | наблюдать лимиты/очередь/upsell | upsell не равен обязательной оплате | пока обязательной оплаты не возникало | IN PROGRESS | owner observations | M00, M05-L02 | финальный статус после B7/B8 |
| A10 | pending | child/parent route | legal route confirmed; functional route only if lawful account available | normative route confirmed only | DOC-CONFIRMED / FUNCTION NOT TESTED | official terms | M00-L01, release risk | no fake minor account |

## 7. GigaChat test matrix

| Test ID | Account | Action | Expected | Observed | Status | Evidence | Affected lessons | Notes |
|---|---|---|---|---|---|---|---|---|
| G01 | pending | регистрация/вход | российский номер / Сбер ID, без оплаты; не-клиент банка допустим | pending | NOT TESTED | — | M00-L01 | OTP only by owner |
| G02 | pending | новый чат | новый диалог реально создается | pending | NOT TESTED | — | M00-L03 | — |
| G03 | pending | DOCX fixture | файл читается без тарифного барьера | pending | NOT TESTED | — | M00-L02 | — |
| G04 | pending | PNG fixture | изображение анализируется | pending | NOT TESTED | — | M00-L02 | — |
| G05 | pending | B7 | реальная генерация и download | pending | NOT TESTED | — | M05-L02 | — |
| G06 | pending | BACKUP B8 | существующий исходник → удаление/замена фона → download | pending | NOT TESTED | — | M05-L02 | no broader claim |
| G07 | pending | standalone auth discrepancy | фактическое требование login | pending | NOT TESTED | — | M05-L02 | compare with source conflict |
| G08 | pending | платный барьер после минимального набора | обязательная подписка не появляется | pending | NOT TESTED | — | M00, M05-L02 | — |

## 8. Cross-cutting browser operations

Частично подтверждены: прямой PRIMARY web-route, повторный старт через новую вкладку, DOCX upload и PNG upload. X05–X10 и полный failover на BACKUP ещё `NOT TESTED`.

## 9. B10 technical route

Фактическая цепочка `утверждение → отдельное основание → конкретный фрагмент → возврат → сопоставление` должна быть OWNER-OBSERVED. Статус: `NOT TESTED`.

## 10. Age / parent route

- Алиса AI: `DOC-CONFIRMED` — несовершеннолетний может использовать сервис с ведома, согласия и под контролем законного представителя.
- GigaChat: `DOC-CONFIRMED` — формальный пользователь соглашения 18+; лицо младше 18 может пользоваться только с согласия и под контролем родителя/представителя, принявшего соглашение.
- Функциональная доступность B4/B7/B8 в реальном child/parent route: `NOT TESTED`; при отсутствии законного подходящего аккаунта будет `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED`.

## 11. Free limits and observed queues

A01–A05 прошли без платного барьера. Реальная очередь/лимит пока не наблюдались. Документально известны стандартные бесплатные лимиты Алисы и возможность временной деградации при нагрузке.

## 12. PRIMARY/BACKUP failover

`NOT TESTED`. PRIMARY и BACKUP должны быть проверены независимо; успешный PRIMARY не превращает сломанный BACKUP в overall PASS.

## 13. Mapping to Lesson IDs

- `M00-L01`: A01/A02/A10/G01/G08
- `M00-L02`: A04/A05/G03/G04
- `M00-L03`: A03/A08/G02 + X01–X10
- `M01-L01`: A01 + стабильный текстовый диалог + copy/apply
- `M01-L02`: B10 route + X05–X07
- `M05-L02`: A06/A07/A08/A09 + G05/G06/G07/G08

## 14. Evidence index

1. OWNER report A01: simple text response received anonymously.
2. OWNER report A03a: built-in new-chat action requested login.
3. OWNER report A03b: new browser tab opened a fresh anonymous dialogue and returned an answer.
4. OWNER report A04: DOCX fixture read correctly; control facts `Бета` and `12 условных дней` extracted.
5. OWNER-supplied screenshot A05: UI visibly not logged in (`Войти`), response correctly identifies `AF-IMG-314`, square and circle, and shows visual elements.

Fixtures are `ACCEPTANCE FIXTURE`, not course assets.

## 15. Deviations from Service Matrix

No architecture-breaking deviation found so far. New observed nuance: Alice anonymous route supports text, DOCX and PNG analysis, and a fresh dialogue can be started by reopening the service in a new tab even though the built-in new-chat action requests login. This is an implementation/UI route detail, not yet a Service Matrix contract change.

## 16. Blocks / risks

1. Interactive browser недоступен агенту: живые UI-факты подтверждаются OWNER-OBSERVED.
2. B7/B8/download for PRIMARY not yet tested.
3. BACKUP GigaChat not yet tested.
4. B10 not yet tested.
5. Child functional route may remain blocked if no lawful suitable account is available.
6. Alice B4/B7/B8 may temporarily degrade at high load; temporary outage is not automatically architecture FAIL.

## 17. Gate verdict

`IN PROGRESS — НЕ PASS`.

## 18. Production implications

Финальные интерфейсные инструкции, скриншоты, видео и утвержденный производственный вертикальный срез M00–M01 пока не разрешены.

## 19. Retest conditions

- repeat temporarily unavailable PRIMARY later;
- on outage test approved BACKUP;
- do not buy Plus/Boost for acceptance;
- if service contract changes, escalate to SM/architecture delta rather than silently adapting.

## 20. Date / tester / evidence level

- Date: 2026-09-11
- Authoring agent: Service Acceptance Lead
- Live UI tester: OWNER
- Current highest live evidence: OWNER-OBSERVED-PASS
- Current documentary evidence: DOC-CONFIRMED
