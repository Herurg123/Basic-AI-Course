# Рабочий журнал rewrite learner-facing материалов

**Дата старта:** 2026-09-17  
**Базовый `main` SHA:** `becc164a6701d2ce6dd91a49842994ecb0d454df`  
**Snapshot:** `snapshot/pre-human-language-rewrite-2026-09-17`  
**Рабочая ветка:** `rewrite/human-language-2026-09-17`

## Зафиксированное расхождение правил

В `project-instructions-v1.4.md` положительный критический аудит обычно ведёт к немедленному merge PR. Текущее задание владельца прямо требует не выполнять merge до двух независимых аудитов, ручного чтения DOCX и финального решения владельца.

Для этой задачи применяется более строгий обратимый gate текущего задания: изменения остаются в feature-ветке и PR, `main` и Stepik не изменяются. Расхождение должно быть вынесено владельцу как `OWNER DECISION REQUIRED` и не скрываться.

## Regression contract

Обязательно сохранить результаты Astra `PED-01…PED-07`:

- PED-01 — помощь с файлами до первого реального файлового действия и различение этапов работы с файлом;
- PED-02 — recovery-ситуация M03 остаётся новой;
- PED-03 — подготовка до первой генерации и первого редактирования изображения;
- PED-04 — не раскрывать точный ответ перед независимой проверкой;
- PED-05 — объяснять смысл сохранения до требования сохранить;
- PED-06 — интерфейсные ветки понятны без второго аккаунта;
- PED-07 — внутренние ID и production terminology не возвращаются в learner-facing слой.

## Статус на 17 сентября 2026

- [x] Зафиксирован SHA исходного `main`.
- [x] Создан snapshot.
- [x] Создана feature-ветка.
- [x] Завершено чтение канона и предыдущих аудитных материалов.
- [x] Сформирована карта learner-facing файлов.
- [x] Rewrite M00–M08 завершён.
- [x] Rewrite learner-facing assets завершён.
- [x] Rewrite промостраницы завершён.
- [x] Авторский self-check завершён.
- [x] Draft PR #97 открыт.
- [x] PR/offline CI на learner-content SHA `09d13a1a…` — success по всем шести workflow.
- [x] Regression PED-01…PED-07 повторно проверен на новой редакции; source-level blockers не найдены.
- [x] Аудит глазами абсолютного новичка завершён — source-level PASS.
- [x] Методический adversarial audit завершён — source-level PASS.
- [x] DOCX review-копия сформирована.
- [x] DOCX отрендерен в 54 страницы и все 54 страницы просмотрены визуально — PASS.
- [ ] Real-device PED-01 acceptance на телефоне и компьютере.
- [ ] Live-account PED-03 acceptance для актуальной бесплатной генерации/редактирования.
- [ ] Публикационный route/visual check PED-06 в фактически собранном маршруте.
- [ ] Human Pilot на абсолютных новичках.
- [ ] Merge PR #97.

## OWNER DECISION REQUIRED

Source-редакция, regression-проверки, независимые model-аудиты, PR/offline CI и review-DOCX готовы для решения владельца. Однако это **не** закрывает реальные device/live-account gates и Human Pilot.

До явного решения владельца:

- PR #97 остаётся draft;
- `main` не изменять;
- Stepik writes не выполнять;
- не выдавать source/model PASS за подтверждение понятности живыми новичками.

Отдельный отчёт по DOCX: `90_reviews/human-language-rewrite-2026-09-17/docx-visual-qa.md`.
