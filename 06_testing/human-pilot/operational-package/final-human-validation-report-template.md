# Final Human Validation Report — Template

## 1. Verdict

Choose exactly one:

- `PASS / HUMAN PILOT VALIDATED`
- `FAIL / BLOCKED`
- `PARTIAL`
- `IN PROGRESS`

**Human validation may be called performed only when real human sessions described in this report actually occurred.**

Report date:  
Accepted production/staging version:  
Operational package version:  
Prepared by:  
Reviewed by:

## 2. Scope completed

| Stage | Required | Actual | Status |
|---|---|---|---|
| Wave 0 | 2 real screened novices, protocol shakedown |  |  |
| Wave 1 | 6 fresh screened novices, full M00→M08 |  |  |
| Fix/retest cycle | all CRITICAL/BLOCKING addressed |  |  |
| Wave 2 | ≥4 fresh novices, accepted version / permitted scope |  |  |
| Stepik staging observation | required for full PASS |  |  |

If participants stopped, show started/completed/not-reached counts. Do not erase stopped participants from the record.

## 3. Architecture §17.2 gate checklist

### Condition 1 — Wave 1
- 6 fresh screened novices completed planned full-course evidence: `YES / NO`
- Evidence:

### Condition 2 — Wave 2
- minimum 4 fresh screened novices on accepted version/permitted retest scope: `YES / NO`
- Evidence:

### Condition 3 — unresolved CRITICAL
- count open:
- PASS condition met: `YES / NO`

### Condition 4 — unresolved BLOCKING
- count open:
- PASS condition met: `YES / NO`

### Condition 5 — pilot-critical repeated clean evidence
For each area, list at least 3 clean successful observations from different fresh participants on accepted version:

| Area | Participant IDs | Count | PASS condition met |
|---|---|---:|---|
| M00 |  |  |  |
| M03-L02 |  |  |  |
| M04-L02→L03 |  |  |  |
| M05-L02 |  |  |  |
| M06-L04 |  |  |  |
| M07-L02 F1 |  |  |  |

### Condition 6 — clean F1
- clean F1 PASS IDs on accepted version:
- count:
- at least 3 fresh participants: `YES / NO`

### Condition 7 — all confirmation F1 non-pass classified
| Participant ID | F1 verdict | Root cause | Course-caused? | Issue ID/status |
|---|---|---|---|---|

Any unresolved course/progression/protocol-caused F1 non-pass blocks PASS.

### Condition 8 — privacy-before-transfer integrity
- unresolved B3 false-pass/safety breach: `NO / YES`
- evidence/issues:

### Condition 9 — no substitute evidence
Confirm accepted evidence never counted:

- regeneration as B8 edit: `CONFIRMED / VIOLATION`
- self-check/second model as B10 basis: `CONFIRMED / VIOLATION`
- chat-only output as B12/F1 application: `CONFIRMED / VIOLATION`

### Condition 10 — Stepik UX
- private/target staging actually observed: `YES / NO`
- if NO, maximum verdict = `PARTIAL`.

### Condition 11 — timing
- full learner time captured, including active/wait/break/retry/F1 separation: `YES / NO`

### Condition 12 — gate boundary
- report explicitly distinguishes human pilot from closed beta/public release: `YES / NO`

## 4. Participant accounting

| Wave | Screened | Eligible | Started | Completed planned route | Stopped/withdrew | Reached F1 |
|---|---:|---:|---:|---:|---:|---:|
| W0 |  |  |  |  |  |  |
| W1 |  |  |  |  |  |  |
| W2 |  |  |  |  |  |  |
| Retest |  |  |  |  |  |  |

## 5. Timing results

Report individual values and descriptive summaries, not a made-up population promise.

- full-course active time individual values:
- median:
- min/max:
- elapsed time composition:
- module-level notable outliers:
- F1 time values:
- time to first meaningful action:
- first perceived practical value pattern:

State clearly how these compare with production estimate and whether product messaging needs a separate owner decision.

## 6. Independent-check outcomes

Attach/derive from `check-evidence-sheet.csv` and summarize:

| Check ID | Dimension | Attempted | PASS | FAIL | Contaminated | Not reached | Ambiguous |
|---|---|---:|---:|---:|---:|---:|---:|

No percentage is presented as general population efficacy.

## 7. Intervention analysis

- N count:
- P count:
- T count:
- C count:
- S count:
- lessons with repeated T-help:
- lessons/checks with C contamination:
- moderator calibration/adjudication issues:

Explain whether support actually faded toward M06/M07.

## 8. Key human findings

### Comprehension

### Technical / Stepik UX

### Privacy-before-transfer

### Image generation vs edit

### Verification / limits of trust

### Actual application

### F1 independence

### Service failover

### Device differences

## 9. Findings closure

| Severity | Open | Fixed-pending-retest | Closed | Accepted-nonblocking |
|---|---:|---:|---:|---:|
| CRITICAL |  |  |  |  |
| BLOCKING |  |  |  |  |
| POLISH/OBSERVATION |  |  |  |  |

List every open issue ID. If any CRITICAL/BLOCKING is open, final verdict cannot be PASS.

## 10. Retest integrity

- fixes confirmed on fresh participants where required: `YES / NO`
- same-user recovery used only diagnostically where applicable: `YES / NO`
- accepted version identified consistently across clean evidence: `YES / NO`
- older-version evidence mistakenly used as accepted-version confirmation: `NO / YES`

## 11. Final conclusion

### If PASS

Use wording:

> Human Pilot на реальных screened novice users завершён по Human Pilot Architecture v1.0. На принятой версии обязательный minimum evidence закрыт, нерешённых CRITICAL/BLOCKING findings нет, минимум три fresh participant дали clean F1 PASS с фактическим применением. Статус: `PASS / HUMAN PILOT VALIDATED`.

Then state explicitly:

> Это разрешает переход к подготовке closed beta. Это **не** означает, что closed beta проведена или что public release разрешён.

### If FAIL/BLOCKED

State blocking issue IDs, required fix/retest scope and do not soften verdict into «почти готово».

### If PARTIAL

State exactly which architecture conditions remain unfulfilled. Do not use `human-validated` wording.

## 12. Next gate

Only after `PASS / HUMAN PILOT VALIDATED`:

- prepare closed-beta protocol/criteria;
- run closed beta according to Manifest;
- include retention/transfer task after a predefined pause;
- perform later final dynamic Stepik/service checks before public release.
