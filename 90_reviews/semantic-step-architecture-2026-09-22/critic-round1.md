# Independent architectural critic — round 1

Дата: 22 сентября 2026 года. PR #117.  
Проверенный head: `c54562a2b2d45308354544c38f151ef4a5749ef1`.

## Verdict

**REQUEST_CHANGES**

Learner-facing слой не изменён, scope Шага 2 соблюдён. Архитектура в целом согласована с Semantic Step Contract и принятым Step 1, но три обязательных решения ещё оставлены production-исполнителю. Это противоречит требованию Шага 2 не оставлять скрытых архитектурных выборов.

## CR2-01 — opt-in и title contract недостаточно детерминированы

Архитектура говорит, что точное машинное представление `authored-semantic-v1` исполнитель может выбрать в существующем parser style, а title допускает authored heading / production title / lesson-title fallback.

Проблема:
- production SOL должен сам выбрать формат канонической директивы;
- fallback на lesson title сохраняет тот самый риск misleading role первого шага;
- «явный production title» не имеет канонического поля.

Требование:
1. зафиксировать точный non-visible синтаксис lesson opt-in;
2. зафиксировать, откуда authored mode берёт title;
3. если title отсутствует — compile должен fail, а не угадывать;
4. не добавлять второй параллельный canonical source.

## CR2-02 — semantic role не имеет канонического production representation

Типы 10 ролей описаны нормативно, но пакет не определяет, где будущий compiled lesson хранит роль каждого шага. Если оставить текущий свободный `Тип шага`, regression tests либо снова будут угадывать роль, либо роль останется только в документах аудита.

Требование:
- определить одно non-visible поле в `stepik-plan.md` для semantic type;
- значения только enum Semantic Step Contract;
- compiler/tests могут использовать type для validation, но не для генерации learner sentences;
- migration batch обязан заполнить type для каждого opt-in row;
- никаких новых обязательных visible sections из type.

## CR2-03 — финальный dual audit массового learner change сформулирован слабее project gate

B1–B6 имеют scoped ZERO-LEVEL/PEDAGOGUE audits. B7 говорит об интеграционном проходе, но не требует однозначно два **полных независимых прохода 148/148 final HTML**.

После миграции universal frame итоговый learner result фактически изменится почти по всему курсу. Project instruction для массового rewrite требует полный проход обеими ролями.

Требование:
- B7: full ZERO-LEVEL 148/148 + full PEDAGOGUE 148/148 на окончательном compiled HTML;
- отдельно ordinary critic;
- результаты сохранить раздельно;
- batch audits не заменяют final whole-course dual gate;
- B7 merge запрещён до трёх PASS.

## Проверено без замечаний

- 118 findings / 19 families отображены в mapping;
- 22-task backlog арифметически согласован;
- 8 batches имеют зависимости и scope;
- no Stepik write на Шаге 2;
- архитектурный PR не меняет learner-facing файлы;
- F1 SEM-117/118 сохранены;
- M07-L01/M07-L02/M08 roles сохранены;
- B8/B10/B12 calibrations сохранены;
- damaged PNG и service-failure evidence limits сформулированы честно;
- opt-in migration как стратегия blast-radius лучше одномоментного глобального switch.

После исправления CR2-01…03 нужен round 2.
