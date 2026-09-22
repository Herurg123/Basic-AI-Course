# B7 whole-course integration reconciliation

Дата: 22.09.2026.

Этот файл фиксирует только structural reconciliation между исходным 148-step platform baseline Step 1 и финальным authored-semantic каноном после B1–B6. Он не является HUMAN VISUAL, SERVICE или Human Pilot verdict.

## Финальный объём

- modules: **9**
- lessons: **21**
- structural plan rows: **150**
- author-only rows: **2**
- learner-facing Stepik steps: **148**
- authored-semantic-v1: **21/21**

Итоговый learner count **не изменился** относительно Step-1 baseline: N = 148.

## Platform block/source reconciliation

При сравнении всех 148 финальных rendered steps с Step-1 baseline найден ровно один намеренный block-type delta:

- `M08-L01 S02`: `free-answer → text`.

Причина: после semantic repair M08 является reflection-only после уже завершённого F1. На S02 learner только называет будущую задачу для последующей рамки переноса; отдельный Stepik submission там не нужен. Единственный итоговый learner response M08 остаётся `M08-L01-C01` на S05. Возврат S02 в `free-answer` создал бы лишнее обязательное действие и снова смешал бы reflection с check.

Других block-type deltas B7 не допускает.

У той же S02 закономерно меняется Stepik source object: старый `free-answer` profile (`is_attachments_enabled=false`, `is_html_enabled=true`, `manual_scoring=false`) → пустой `{}` для text block. Это не отдельная смысловая правка, а вторая половина того же reconciled block-type change.

Других Stepik source-object deltas B7 не допускает.

## Physical asset deployment boundary

Source integration обнаруживает ровно один ожидаемый pending physical materialization:

- `05_assets/M03/M03-L02/M03-L02-A03-alice.png`.

Причина: B3 детерминированно восстановил канонический PNG из декодируемых пикселей аутентичной повреждённой производной, поэтому старый live binding относится к прежнему source hash.

Это **не source blocker** B7 и не повод подделывать binding. Новый physical materialization + read-back выполняются только после accepted B7 merge через существующий guarded private release.

До этого момента не заявляются:
- HUMAN VISUAL PASS восстановленного кадра;
- Stepik materialization/read-back PASS для нового hash;
- SERVICE PASS;
- Human Pilot PASS.

## Compiler state

Production compiler после B7:
- требует exact `authored-semantic-v1`;
- не имеет legacy learner-frame fallback;
- не генерирует универсальные `Зачем / Где и с чем / Готово / Что дальше`;
- определяет `free-answer` детерминированно: `CHECK`, либо `COMPOSITE` с explicit Check ID;
- остальные semantic roles рендерит как `text`.

B7 regression обязан падать при любом новом block/source delta, втором pending physical materialization или возврате legacy frame.
