# Recovery Readiness — Human Pilot

**Назначение:** не позволять модератору придумывать содержательную «повторную проверку» после того, как увидена ошибка участника.

Перед Wave 0 проверить доступность author-only recovery там, где production его уже предусматривает. Learner не видит этот индекс.

## Реестр

| Primary check | Contamination / nonproof case | Approved recovery source | Pilot rule |
|---|---|---|---|
| `M03-L02-C01` B1/B2/B5/B6 | content hint; ранний C01 реально повлиял; B1 temporal evidence отсутствует | `04_course/M03/M03-L02/author-notes.md` §6, `R1` | исходный A01 не повторять для level 3; использовать R1 без раскрытия скрытого условия/критериев |
| `M04-L02-C01` B3 | подсказано, что скрывать/передавать; post-hoc privacy explanation | `04_course/M04/M04-L02/author-notes.md` §4–7, `R1` | новая ситуация; реальное safe action **до transfer**; repeated contamination не «чинить» ослаблением B3 |
| `M05-L02-C02` B8 | content hint; Part 2 подсказал edit; иное contamination | `04_course/M05/M05-L02/author-notes.md` §5, `R-B8-PRIMARY` / `R-B8-BACKUP` | B7 не повторять, если он уже clean; B8 требует новый safe existing source + real edit |
| `M06-L04-C01` B9/B10/B11/C1 + A1/A2 context | content hint по claim/method/source/number/status/next step | `04_course/M06/M06-L04/author-notes.md` §6, `R1/R2/R3` | выдавать только нужный alternate, не весь набор; learner-facing инструкция нейтральна; B10 всё равно требует real opened basis |
| `M06-L04-C02` B12 | подсказан способ применения или отсутствует actual application | production `author-notes.md` §7 задаёт evidence rule, но не фиксирует универсальный готовый alternate | не придумывать «применение за ученика»; нужна новая безопасная ситуация/артефакт с самостоятельно выбранным применением; если чистый эквивалент нельзя подготовить заранее, открыть pilot finding и не выдавать PASS |
| `M06-L04-C03` C2/C3 | содержательная подсказка переноса/основания или объяснение стало post-hoc заменой действия | production `author-notes.md` §8 задаёт контракт, но не отдельный универсальный named recovery | не повторять раскрытую ситуацию косметически; подготовить содержательно другую equivalent область через production fix/review до зачётного re-check, иначе `NOT PROVEN` |
| `M07-L02-C01` F1 | любой substantive hint по задаче/плану/источнику/edit/application | Human Pilot Architecture + M07-L02 lesson card | текущая F1 = `PRACTICE / CONTAMINATED`; после practice участник сам выбирает **другую новую реальную посильную задачу**; модератор её не предлагает |

## Общие проверки перед выдачей recovery

- [ ] primary attempt уже зафиксирована как non-pass/contaminated/not-proven;
- [ ] recovery не раскрывалась участнику заранее;
- [ ] новая ситуация отличается содержательно, а не именами/числами;
- [ ] модератор не добавил объяснение, которое сообщает проверяемый метод;
- [ ] temporal evidence начинается заново до post-action rubric;
- [ ] Check ID/competency остаются теми же, если production именно так определяет recovery;
- [ ] recovery evidence записывается отдельной attempt строкой;
- [ ] техническая невозможность не превращается в содержательную ошибку ученика;
- [ ] повторное contamination не получает PASS.

## Если recovery заранее не определён

Модератор **не импровизирует зачётную ситуацию на месте** после наблюдения ошибки. Действия:

1. закрыть текущую попытку честным статусом;
2. записать finding;
3. при необходимости провести practice без зачёта;
4. подготовить новый содержательно эквивалентный recovery в правильном production/author-only слое;
5. провести branch → PR → critic → merge, если recovery меняет канонические материалы;
6. затем выполнить clean re-check по правилам архитектуры.

F1 является особым случаем: его recovery уже определён как новая собственная реальная задача участника, а не авторский готовый кейс.
