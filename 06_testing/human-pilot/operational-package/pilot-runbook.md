# Human Pilot Runbook

## 1. Gate order

1. Operational package approved + merged.
2. Private Stepik staging assembled and checklist = `READY`.
3. Moderator rehearsal passed.
4. Consent/data handling ready.
5. Service preflight passed.
6. Wave 0: 2 real screened novices.
7. Triage findings; fix/retest if needed.
8. Wave 1: 6 fresh screened novices, full M00→M08 route.
9. Fix confirmed defects through normal GitHub workflow.
10. Wave 2: minimum 4 fresh screened novices on accepted version or architecture-permitted scoped confirmation.
11. Final human-validation report + verdict.
12. Only after Human Pilot PASS: prepare closed beta.

No skipped step creates retrospective evidence.

## 2. Participant lifecycle

### Recruitment

- assign Candidate ID;
- complete screener;
- if eligible, assign Participant ID only after enrollment;
- keep contact mapping outside GitHub pilot evidence;
- do not show future checks/rubrics.

### Before Session 1

- participant information/consent;
- optional recording consent separately;
- record baseline device/browser/route;
- remind participant not to use secrets/confidential/high-stakes material;
- do **not** teach course content during onboarding.

### During sessions

- use observer form per session;
- timing log runs across learner work, waits, breaks, retries and F1 separately;
- every intervention goes to intervention log;
- independent checks go to evidence sheet;
- findings go to issue log as they occur, not reconstructed from memory later.

### After final session

- confirm completion/not reached status for every required independent check;
- collect brief non-leading overall usability comments only after scored work;
- do not change a failed check because participant gives a convincing retrospective explanation;
- retain dropout/stop in denominators and reasons.

## 3. Session structure

Full course is not forced into one sitting. Default planning is 3–4 sessions per full-course participant.

For each session:

1. start timestamp;
2. confirm correct Participant ID and staging version;
3. service preflight status still valid; if meaningful change occurred, re-run affected preflight;
4. resume learner route without content recap that reveals answers;
5. mark active learning / technical wait / break / admin / recovery separately;
6. do not split an independent attempt across a break unless participant itself needs to stop; if split occurs, log it as context;
7. end timestamp and next neutral resume point.

## 4. Wave 0 — protocol shakedown

### Sample

2 real screened novices. They count as people, but Wave 0 does not close validation because forms/protocol can still change afterward.

### Primary questions

- can moderator use N/P/T/C/S consistently?
- can observer capture temporal evidence without prompting content?
- does Stepik staging expose author-only information?
- are logs usable without collecting sensitive content?
- is timing practical?
- can F1 be observed without moderator assembly?

### Exit from Wave 0

Before Wave 1:

- all CRITICAL/BLOCKING findings affecting protocol/staging/course are fixed or explicitly block progression;
- forms are frozen for Wave 1 version;
- any changed operational package is re-reviewed through GitHub workflow;
- course fixes are merged through their own normal workflow and relevant service/staging checks repeated.

## 5. Wave 1 — discovery

### Sample

6 **new** screened novices, full M00→M08 route.

Device environment includes at minimum:

- 2 primarily PHONE;
- 2 primarily COMPUTER.

### Rule for incomplete participants

A participant who starts and stops remains in `started` and has `NOT REACHED` downstream outcomes. Do not erase them from the wave.

If fewer than 6 participants complete enough of the route to provide the required evidence, recruit additional fresh participants. Replacements increase `started`; they do not replace the historical row of the person who stopped.

### During discovery

Prefer observation over rescue. Repeated content need is a finding, not an instruction to coach harder.

After Wave 1, classify findings and decide fixes according to the approved severity model.

## 6. Fix cycle

For every CRITICAL/BLOCKING:

1. create issue ID;
2. establish observed vs expected behavior;
3. classify root cause;
4. identify correct canonical layer for fix;
5. implement via branch → PR → critic → merge;
6. update Stepik staging if learner-facing content changed;
7. run service preflight if route changed;
8. set finding `FIXED-PENDING-RETEST`;
9. perform required fresh-user retest;
10. close only after evidence confirms the fix.

Do not patch a learner-facing problem only in moderator instructions.

## 7. Wave 2 — confirmation

### Sample

Minimum 4 fresh screened novices who did not participate in Wave 0/1 and were not exposed to previous answers/fixes.

### Default

Full-course route on accepted version.

### Scoped confirmation only when architecture allows

If fixes are strictly local and do not touch progression, prerequisites, independence, safety, evidence, service route or F1, unaffected modules may be omitted for some confirmation participants. Still re-run:

- affected check with necessary preceding context;
- all affected downstream dependencies;
- M06-L04 → M07-L01 → M07-L02 when independence/F1 implications exist;
- F1 confirmation required by architecture.

### Human Pilot PASS minimum

No report can declare PASS unless architecture §17.2 is met, including:

- no unresolved CRITICAL/BLOCKING;
- required pilot-critical repeated clean observations;
- minimum 3 clean F1 PASS on accepted version from fresh participants;
- every Wave 2 F1 non-pass has root-cause classification and no unresolved course-caused failure;
- Stepik UX actually observed;
- complete timing collected.

## 8. Version control during human sessions

Every participant/session records:

- production/staging version identifier;
- operational-package version;
- service route/preflight date.

Do not silently switch learner-facing version mid-independent attempt. If emergency fix is required, stop the affected attempt and document which version produced which evidence.

Evidence from an older version may remain diagnostically useful but cannot automatically satisfy clean confirmation for the accepted fixed version.

## 9. Daily closeout

After each pilot day:

- ensure all sessions have timestamps;
- reconcile intervention log with observer notes;
- verify no sensitive raw content was accidentally committed/staged;
- assign issue IDs to unresolved findings;
- mark ambiguous evidence rather than force PASS/FAIL;
- note any service/interface change requiring next-session preflight.

## 10. No-notification rule

Human pilot is not an unattended automated test. Do not claim a future Wave result until real sessions have occurred and evidence has been recorded. Models may help classify anonymized findings afterward, never substitute for participants.
