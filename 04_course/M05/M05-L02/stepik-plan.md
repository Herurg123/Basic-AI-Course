# Stepik plan — M05-L02

> Производственный план переноса. Не является публичным ученическим текстом. Действуют D-2026-09-12-STEPIK-FLOW, D-2026-09-13-LEARNER-UX и Semantic Step Contract v1.0.

<!-- learner-render-contract: authored-semantic-v1 -->

| № | Тип шага | Содержание | Материал / действие | Проверка | Semantic type |
|---:|---|---|---|---|---|
| 1 | safety + learner contract | Два live evidence: own generation B7 и real edit existing image B8; neutral material only; UI knowledge не проверяется; no payment | — | — | EXPLANATION |
| 2 | optional technical support | A03 inline один раз **до E01**: unrelated geometry example; generation → save → reselect same image → neutral test edit → save both. Familiar learner skips. GigaChat login only if actual action requests it | `M05-L02-A03.md`; сервисы only for mechanics | — | TECHNICAL_SUPPORT |
| 3 | order / navigation | Объяснить, зачем полностью закончить part1 и сохранить own prompt + generated image до раскрытия part2; no hard-gate claim | — | — | NAVIGATION |
| 4 | independent generation | A01-part1 inline; learner сам формулирует description/remaining requirements и реально generates image. PRIMARY Alice; conditional GigaChat at generation failure; save prompt+image | `M05-L02-A01-part1.md`; live service | `M05-L02-E01` | INDEPENDENT_PRACTICE |
| 5 | post-action C01 | Открыть generated image locally; в Stepik short text: purpose, own description, important requirements, what was actually created/saved. No image upload; A03/demo not evidence | local image + free-answer Stepik | `M05-L02-C01` | CHECK |
| 6 | reveal new purpose + own choice | A01-part2 inline only after part1. Start E02: compare existing image with new purpose and **record one own correction before technical help**. If no honest mismatch / early reveal influenced source / content hint chose correction → route to step10, no invented defect | `M05-L02-A01-part2.md` + own note | `M05-L02-E02` | INDEPENDENT_PRACTICE |
| 7 | conditional technical support after choice | Only after correction is recorded: link back to step2 for mechanics. Do not change correction to fit tool. Backup limitation is technical, not content key; unavailable chosen edit remains incomplete or uses recovery | [technical step 2](https://stepik.org/lesson/2591725/step/2) | — | TECHNICAL_SUPPORT |
| 8 | real edit existing image | Continue E02: use exact saved source, perform recorded correction, save source+edited result. New generation from scratch does not count; technical failure is not imaginary evidence | existing E01 source + live edit function | продолжение `M05-L02-E02` | INDEPENDENT_PRACTICE |
| 9 | post-action C02 | Open both actual versions locally; in Stepik short text: mismatch, correction chosen before help, observed change, why edited version fits better. No mandatory image upload | local source+edited image + free-answer Stepik | `M05-L02-C02` | CHECK |
| 10 | conditional recovery — source first | Only if contamination / no meaningful mismatch / technically unexecutable main attempt. Before future purpose is shown, learner independently generates and saves a new wide 16:9 book-exchange header source. No step11 purpose visible here | new safe live source authored in `lesson.md` | recovery for `M05-L02-C02` | RECOVERY |
| 11 | conditional recovery — purpose/edit | Reveal different use only after recovery source exists: small square schedule icon. Learner records own correction, then may use technical help, really edits same recovery source, saves both. После работы идти только вперёд; старый C02 не редактировать | recovery source + natural trace | recovery evidence через следующий self-review | RECOVERY |
| 12 | post-recovery reflection + consolidation | Если recovery использовалась, **после** неё локально разобрать mismatch, own correction before help, observed edit и fit to new purpose; successful learner этот фрагмент пропускает. Затем A02 inline optional local form и общий generation→edit итог | natural trace + `M05-L02-A02.md` | — | REFLECTION |

## Что именно показывает техническая проба

Learner-facing A03 опирается на официальные пользовательские инструкции, повторно проверенные **22.09.2026**:

- Алиса AI: генерация описана в пользовательской справке; редактирование выполняется через загрузку JPEG/PNG и описание изменения;
- GigaChat: генерация изображений документирована; загрузка изображений документирована; узкий резерв удаления/замены фона документирован как реальная операция.

Это **документационная перепроверка, не live-account acceptance**. Перед публикацией на свежих бесплатных аккаунтах отдельно подтверждается фактическая доступность хотя бы одной B7 и B8 по принятому маршруту.

## Evidence / completion

- A03 не является evidence B7/B8.
- B7 = own description + фактически generated live image.
- B8 = existing safe source + own correction recorded before content help + фактически edited version of that source + comparison.
- New generation from scratch ≠ B8.
- Images stay with learner; Stepik uses short free-answer after action.
- Already-suitable source does not justify invented defect: use staged recovery.
- Technical unavailability does not become PASS and does not require purchase.

## Recovery / independence

Recovery is split across steps 10–11 to preserve order:

1. generate and save new source **without knowing future reuse**;
2. only then reveal new use;
3. learner chooses correction;
4. technical help allowed only after own choice;
5. real edit;
6. move forward to a separate post-recovery self-review; the old C02 is never revisited.

The recovery source is a wide multi-object book-exchange header; the later use is a small square schedule icon. This makes a substantive adaptation necessary without naming a single correct edit: crop/recomposition/simplification/scale/background handling can be reasonable depending on actual source and available service.

If learner’s reasonable correction is unsupported by available services, do not label the choice wrong. No B8 PASS until a real edit exists.

## Service boundary

Current documentation confirms Alice editing uploaded JPEG/PNG and GigaChat’s narrow background route, but this batch does not claim a fresh-account live run. Backup capability must not leak “background” as the answer before learner records a correction.

**Quiz не заменяет:** live generation или real edit.
