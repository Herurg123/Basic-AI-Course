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

Живые параметры среды будут заполняться только по фактическим наблюдениям владельца во время пошагового OWNER-OBSERVED прогона.

| Parameter | Observed |
|---|---|
| Date | 2026-09-11 |
| Local time | pending per test |
| Connection | NOT TESTED |
| Russian ordinary connection | NOT TESTED |
| VPN | NOT TESTED |
| Browser/device | NOT TESTED |
| Alice account | NOT TESTED |
| Alice Plus / boosts | NOT TESTED |
| GigaChat account | NOT TESTED |
| Paid entitlement | NOT TESTED |
| Tester | OWNER for live UI actions |

Географическая проходимость не будет объявлена PASS, пока обязательные действия не выполнены на обычном российском соединении без VPN.

## 4. Accounts and entitlement state

`NOT TESTED`. Требуется отдельно зафиксировать для каждого сервиса: fresh/free либо `FREE EXISTING ACCOUNT, NOT FRESH`, наличие Plus/Premium/boosts и отсутствие платной лицензии, меняющей обязательные функции.

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

Для GigaChat есть существенное расхождение: действующее пользовательское соглашение требует обязательной авторизации для использования Сервиса, а help-страница standalone-инструмента удаления фона заявляет, что регистрация не нужна. До живой проверки это фиксируется как `OFFICIAL SOURCE CONFLICT`; ни одна из сторон конфликта не превращается в LIVE/OWNER PASS автоматически.

## 6. Alice test matrix

| Test ID | Account | Action | Expected | Observed | Status | Evidence | Affected lessons | Notes |
|---|---|---|---|---|---|---|---|---|
| A01 | pending | открыть web и сделать простой текстовый запрос | чат доступен без обязательной оплаты | pending | NOT TESTED | — | M00-L01, M01-L01 | — |
| A02 | pending | проверить фактическую обязательность login для text/B4/B7/B8/download | различить optional vs required login | pending | NOT TESTED | — | M00-L01–L03, M05-L02 | — |
| A03 | pending | новый чат и повторный старт | новый диалог реально создается | pending | NOT TESTED | — | M00-L03 | — |
| A04 | pending | DOCX fixture upload + вопрос по содержимому | файл прочитан, ответ относится к нему | pending | NOT TESTED | — | M00-L02 | — |
| A05 | pending | PNG fixture upload + анализ | изображение распознано | pending | NOT TESTED | — | M00-L02 | — |
| A06 | pending | живая B7 | новая картинка реально сгенерирована бесплатно | pending | NOT TESTED | — | M05-L02 | — |
| A07 | pending | реальный edit существующего исходника | изменен именно исходник | pending | NOT TESTED | — | M05-L02 | — |
| A08 | pending | скачать B7/B8 | результат реально сохранен | pending | NOT TESTED | — | M00-L03, M05-L02 | — |
| A09 | pending | наблюдать лимиты/очередь/upsell | upsell не равен обязательной оплате | pending | NOT TESTED | — | M00, M05-L02 | — |
| A10 | pending | child/parent route | legal route confirmed; functional route only if lawful account available | pending | DOC-CONFIRMED / FUNCTION NOT TESTED | official terms | M00-L01, release risk | no fake minor account |

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

X01–X10: `NOT TESTED`. Включают прямую ссылку PRIMARY, новый чат, DOCX, PNG, внешний источник, поиск фрагмента, возврат, копирование, сохранение и предусмотренное переключение PRIMARY → BACKUP.

## 9. B10 technical route

Официальные и проектные документы подтверждают только контракт. Фактическая цепочка `утверждение → отдельное основание → конкретный фрагмент → возврат → сопоставление` должна быть OWNER-OBSERVED. Статус: `NOT TESTED`.

## 10. Age / parent route

- Алиса AI: `DOC-CONFIRMED` — несовершеннолетний может использовать сервис с ведома, согласия и под контролем законного представителя.
- GigaChat: `DOC-CONFIRMED` — формальный пользователь соглашения 18+; лицо младше 18 может пользоваться только с согласия и под контролем родителя/представителя, принявшего соглашение.
- Функциональная доступность B4/B7/B8 в реальном child/parent route: `NOT TESTED`; при отсутствии законного подходящего аккаунта будет `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED`.

## 11. Free limits and observed queues

Пока только `DOC-CONFIRMED`: у Алисы стандартные бесплатные лимиты и возможная временная деградация функций при нагрузке; у GigaChat договор позволяет Банку вводить лимиты без предварительного уведомления. Реальная очередь/лимит: `NOT TESTED`.

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

Пока живые evidence отсутствуют. Fixtures подготовлены отдельно как `ACCEPTANCE FIXTURE`, а не как course assets.

## 15. Deviations from Service Matrix

На старте содержательной девиации не установлено. Найденный конфликт standalone-auth GigaChat уже был отмечен в SM v1.0 и остается предметом живого G07.

## 16. Blocks / risks

1. Interactive browser недоступен агенту: живые UI-факты могут подтверждаться только OWNER-OBSERVED.
2. Географический PASS требует обычного российского соединения без VPN.
3. Child functional route может остаться BLOCKED при отсутствии законного подходящего аккаунта.
4. Алиса B4/B7/B8 может временно деградировать при высокой нагрузке; временный outage не равен архитектурному FAIL.

## 17. Gate verdict

`IN PROGRESS — НЕ PASS`.

## 18. Production implications

Финальные интерфейсные инструкции, скриншоты, видео и утвержденный производственный вертикальный срез M00–M01 пока не разрешены.

## 19. Retest conditions

- повторить временно недоступный PRIMARY позже;
- при outage проверить утвержденный BACKUP;
- не покупать Plus/Boost ради прохождения acceptance;
- при изменении сервисного контракта эскалировать до изменения SM/архитектуры.

## 20. Date / tester / evidence level

- Date: 2026-09-11
- Authoring agent: Service Acceptance Lead
- Live UI tester: OWNER
- Current highest live evidence: none yet
- Current documentary evidence: DOC-CONFIRMED
