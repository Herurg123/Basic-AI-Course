# M07–M08 vertical slice — production summary

**Ветка:** `production/m07-m08-batch-v1`  
**Дата:** 12 сентября 2026 года  
**Base SHA:** `ed02eb0bbde6f5b95edec40fc9c04977c378d113`  
**Production status:** `READY FOR INDEPENDENT AUDIT`  
**Human validation:** `NOT PERFORMED`.

## 1. Scope

Произведены только `M07-L01`, `M07-L02`, `M08-L01`.

M00–M06, архитектура, competency placement, PRIMARY/BACKUP, 9 модулей, 21 Lesson ID и существующие Exercise/Check/Asset ID не перепроектировались.

## 2. Produced files

### M07-L01
- `lesson.md`;
- `stepik-plan.md`;
- `author-notes.md`;
- `M07-L01-A01.md`;
- `M07-L01-A02.md`.

### M07-L02
- `lesson.md`;
- `stepik-plan.md`;
- `author-notes.md`;
- `M07-L02-A01.md`;
- `M07-L02-A02.md`;
- `M07-L02-A03.md`.

### M08-L01
- `lesson.md`;
- `stepik-plan.md`;
- `M08-L01-A01.md`.

### Cross-cutting
- `06_testing/synthetic-prepilot-m07-m08/synthetic-prepilot-2026-09-12.md`;
- этот production summary;
- минимальные navigation/status updates.

## 3. Competency contract

- `M07-L01`: F1 INTRO + PRACTICE, уровень 2.
- `M07-L02`: F1 INDEPENDENT, уровень 3, единственный финальный independent F1.
- `M08-L01`: только C2/C3 REUSE + B12 reflection/REUSE; новых competency levels нет.

## 4. F1 safeguards

- no step-by-step scaffold;
- own new real task;
- actual B12 application mandatory;
- content hint contaminates independence;
- contaminated attempt requires another own new real task;
- temporal evidence cannot be created post-action;
- high-stakes excluded;
- optional skills are not forced;
- correct refusal is safe but does not close F1;
- self-check/second model does not replace real basis.

## 5. Lesson Gate

| Lesson | Result | Concrete evidence |
|---|---|---|
| M07-L01 | `PASS` | A01 is one safe integrated task; A02 has no order; E02 reveals only changed condition; C01 requires actual educational application and explanation; lesson says rehearsal, not final |
| M07-L02 | `PASS` | A01 gives task classes only; learner chooses own task; lesson permits technical help only; A03 is post-action/nonprocedural; A02 requires temporal evidence, completion and B12; author notes define contamination recovery and critical false-PASS |
| M08-L01 | `PASS` | lesson starts after completed F1, explicitly states base complete; only REUSE; A01 defines complexity boundary by task, not brand; no service/purchase/course promise |

## 6. Course-level regression check

- M03 independence/temporal evidence preserved: post-action explanation cannot retroactively create choices.
- M04 privacy preserved: decision and safe preparation happen before transmission.
- M05 image boundary preserved: B7/B8 are not forced into F1.
- M06 verification preserved: real basis required where significant; AI self-check/second model is not evidence.
- M06 application preserved and strengthened in F1: actual completion + actual B12 mandatory.

Result: `PASS`.

## 7. Author self-red-team

### M07-L01
- hidden algorithm in A02: not found;
- all skills artificially forced: not found;
- E02 next step leaked: not found;
- F1 falsely closed: explicitly prevented;
- result allowed to remain in chat: prevented by C01;
- template-following sufficient: no.

### M07-L02
- ready-made task: no;
- options menu that becomes solution: no;
- rubric/evidence form as workflow: no;
- content hint leaves level 3 intact: no, contamination rule explicit;
- retroactive temporal evidence: rejected;
- unfinished task passes: rejected;
- «would apply» passes: rejected;
- refusal alone passes: rejected;
- significant unchecked fact passes: critical fail;
- file/search/image forced: no;
- high-stakes accepted: no;
- new competency: no.

### M08
- second exam: no;
- new competency: no;
- purchase/registration dependency: no;
- next level by service/brand: no;
- base artificially devalued: no;
- «base practice is enough» disallowed: no, explicitly valid.

Author red-team result: `PASS — NO PRODUCTION BLOCKER FOUND`.

## 8. Synthetic pre-pilot

Completed: `SIMULATED / MODEL-BASED — NOT HUMAN PILOT`.

Result: `MODEL-BASED PASS — READY FOR INDEPENDENT AUDIT, NOT HUMAN-VALIDATED`.

Human validation remains `NOT PERFORMED`.

## 9. Dependencies / future gates

- current dynamic service/publishing layer remains governed by Service Matrix / Service Acceptance;
- Stepik uses advisory sequencing, not fictional hard gates;
- human pilot remains mandatory before beta/public release;
- independent audit of this batch is a separate next gate;
- cumulative audit M00–M08 is not part of this production batch.

## 10. Architecture confirmation

- new Lesson IDs: `0`;
- new Exercise IDs: `0`;
- new Check IDs: `0`;
- new Asset IDs: `0`;
- competency placement changed: `no`;
- M00–M06 redesigned: `no`;
- PRIMARY/BACKUP changed: `no`;
- M08 became a second exam: `no`;
- next level became an upsell: `no`.

## 11. Pilot-critical

Future human pilot must especially test:
- M07-L01 A02: enough support without becoming recipe;
- understanding that not every skill is mandatory;
- ability to choose manageable own task for M07-L02;
- interpretation of «finished» and actual application;
- breadth of safe task choice;
- real F1 duration and retry frequency;
- M08 base/next-level boundary and absence of sales perception.

## 12. Production conclusion

Production batch itself is complete and internally passes Lesson Gate, regression check, author self-red-team and synthetic model-based pre-pilot.

It is **not yet independently audited, not human-validated, not published to Stepik and not a cumulative M00–M08 audit**.
