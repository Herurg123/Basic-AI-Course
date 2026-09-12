# Human Pilot Wave Summary — Template

## 1. Идентификация

- Wave: `W0 / W1 / W2 / RETEST`
- Dates:
- Production/staging version(s):
- Operational package version:
- Report author:
- Status: `COMPLETE / PARTIAL / BLOCKED`

## 2. Sample accounting

| Metric | Count |
|---|---:|
| screened |  |
| eligible |  |
| started |  |
| completed full planned route |  |
| stopped/withdrew |  |
| not reached F1 |  |
| PHONE-primary |  |
| COMPUTER-primary |  |
| PRIMARY route |  |
| BACKUP route |  |

Не удалять stopped/withdrawn из `started`. Указать причины безопасными кодами/категориями.

## 3. Independent outcomes

Таблица по каждому Check ID / competency dimension:

| Check ID | Dimension | Participants attempted | PASS | FAIL | PRACTICE/CONTAMINATED | NOT REACHED | AMBIGUOUS |
|---|---|---:|---:|---:|---:|---:|---:|
|  |  |  |  |  |  |  |  |

Показывать counts с явными знаменателями. Не превращать маленькую выборку в популяционную «эффективность курса».

## 4. Pilot-critical checkpoints

Для каждой области:

- M00 technical entry/safety;
- M03-L02 B1/B2/B5/B6;
- M04-L02 → M04-L03 B3/B4;
- M05-L02 B7/B8;
- M06-L04 A1/A2/B9–B12/C1–C3;
- M07-L02 F1.

Зафиксировать:

| Area | Clean successful participant IDs | Count | Accepted-version evidence sufficient? | Open issue IDs |
|---|---|---:|---|---|
|  |  |  |  |  |

## 5. Interventions

| Type | Count | Main Lesson/Check IDs | Interpretation |
|---|---:|---|---|
| N |  |  |  |
| P |  |  |  |
| T |  |  |  |
| C |  |  |  |
| S |  |  |  |

Отдельно перечислить повторяющиеся technical-help точки и все content contamination events.

## 6. Timing

### Full learner route

Для участников, завершивших запланированный полный маршрут:

- individual active-learning times:
- minimum:
- median:
- maximum:
- technical/service wait distribution:
- break distribution:
- recovery/retry time:
- F1 time:

Не смешивать breaks/admin/technical wait с active learner time. При сообщении total elapsed показать состав.

### First meaningful action/value

- время до первого осмысленного действия по участникам:
- где участники впервые сообщили/показали практическую ценность:
- повторяющийся pattern:

## 7. Special invariants

### B3 privacy-before-transfer
- clean PASS IDs:
- FAIL/contaminated IDs:
- safety stop IDs:
- issues:

### B7/B8
- live generation observed IDs:
- real edit observed IDs:
- regeneration mistaken for edit? `NO / YES` + issue IDs:

### B10
- real basis opened/compared IDs:
- self-check/second-model false evidence incidents:
- issues:

### B12
- actual application IDs:
- chat-only/nonapplication incidents:
- issues:

### F1
- clean F1 PASS IDs:
- non-pass IDs + root-cause class:
- contaminated IDs:
- second-review/adjudication outcomes:
- course-caused F1 non-pass remains open? `NO / YES`:

## 8. Stepik/service/device findings

- staging UX blockers:
- advisory sequencing/early-hint incidents:
- PRIMARY→BACKUP switches and reason:
- PHONE-specific barriers:
- COMPUTER-specific barriers:
- service outages separated from course defects:

## 9. Findings by severity

### CRITICAL
| Issue ID | Summary | Status | Required action/retest |
|---|---|---|---|

### BLOCKING
| Issue ID | Summary | Status | Required action/retest |
|---|---|---|---|

### POLISH / OBSERVATION
| Issue ID | Summary | Status/decision |
|---|---|---|

## 10. Wave verdict

Choose one:

- `PROCEED`
- `PROCEED AFTER LISTED NONBLOCKING CLEANUP`
- `FIX + RETEST BEFORE NEXT WAVE`
- `BLOCKED — ARCHITECTURE/OWNER DECISION REQUIRED`

Reason:

### For Wave 0 only
Protocol/forms frozen for Wave 1? `YES / NO`

### For Wave 1 only
List fixes required before Wave 2:

### For Wave 2 only
Does this wave satisfy its part of Human Pilot Architecture §17.2? `YES / NO / PARTIAL` with explicit missing evidence.

## 11. Boundary statement

Even a successful wave is not by itself `PASS / HUMAN PILOT VALIDATED` unless the final report confirms **all** architecture gate conditions. Human pilot is not closed beta and not public release.
