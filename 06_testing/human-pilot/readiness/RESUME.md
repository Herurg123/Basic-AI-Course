# Wave 0 Readiness Execution — RESUME

**Checkpoint date:** 2026-09-12  
**Canonical main checked:** `939eee4f33d7e75b15b4f5df2a34c09b4a148bd9`  
**Working branch:** `testing/wave0-readiness-execution`  
**Open PR:** none at checkpoint creation  
**Current stage:** `A — STEPIK STAGING`  
**Human validation:** `NOT PERFORMED`  
**Wave 0:** `NOT READY / OWNER ACTION REQUIRED`

## What is actually complete

- Fresh `main` verified; no commit newer than merge PR #37 was present at checkpoint start.
- Current project instructions, `AGENTS.md`, root `README.md`, Human Pilot README, Human Pilot Architecture, full Operational Human Pilot Package index/content, and current Wave 0 readiness record were checked from `main`.
- First unresolved readiness blocker confirmed: Stepik staging does not yet have evidence.
- No new pilot architecture, wave, form, sample size, competency framework, recovery framework, or production lesson was created.
- Current Stepik official documentation was checked for the implementation route before giving the owner staging instructions.

## Stepik platform note discovered during readiness work

Current Stepik Help Center documentation distinguishes:

1. legacy Enterprise private courses, which can use `Только приглашённые`; and
2. the current general course-testing route: a course must be published, have its opening date set in the future, and invited users receive the `Тестирующие` role so they can access content before official opening.

The Help Center also states that a draft course cannot add testers. Therefore the implementation route must be chosen from the capabilities actually visible in the owner's Stepik account; no project status may assume a legacy Enterprise private-course option exists.

Official references checked:

- https://help.stepik.org/article/54745
- https://help.stepik.org/article/54812
- https://help.stepik.org/article/54813

This note does **not** change Human Pilot Architecture. Any Stepik route is acceptable for readiness only after it satisfies the canonical staging checklist in practice, including no broad learner access to course content before the pilot, PHONE/COMPUTER smoke checks, author-only separation, sequencing and F1 integrity.

## Current blocker

`Private/closed Stepik staging assembled` = `NOT PERFORMED`.

Until real staging evidence is returned, these cannot be promoted to PASS:

- Stepik staging checklist;
- recovery execution readiness in staging;
- Wave 0 readiness.

## OWNER ACTION REQUIRED — Stepik staging

Use course content from canonical `main` at:

`939eee4f33d7e75b15b4f5df2a34c09b4a148bd9`

### 1. Create the staging course

In Stepik open `Преподавание` → create a new course. Build the learner-facing M00–M08 route from the accepted production files. Do not copy author-only rubrics, answers or recovery material into learner-visible steps.

### 2. Choose the access route actually available in the account

**Preferred if the account offers it:** publish as `Только приглашённые` / private course.

**If that option is unavailable:** use Stepik's documented testing route:

- publish the course;
- set the course opening date safely in the future, beyond the planned Wave 0 window;
- use `Права доступа` → `Тестирующие` for pilot accounts;
- use one-time tester invitation links where practical;
- confirm from a non-tester account/incognito state that learner content is not accessible before the opening date.

Do not put invitation tokens/secret links, passwords, cookies or account secrets into GitHub.

### 3. Build the complete production sequence

Before returning evidence, ensure the staging build contains M00–M08 and all 21 Lesson IDs in the accepted order, with learner-facing material matching production and with author-only/recovery material separated from the learner route.

### 4. Return evidence to the operating chat

Return only non-secret evidence:

- ordinary Stepik course URL or course ID (not an invitation-token URL);
- confirmation of the production SHA used: `939eee4f33d7e75b15b4f5df2a34c09b4a148bd9`;
- screenshot of `Настройки → Публикация` showing the selected access/opening-date state;
- screenshot of `Права доступа` showing that the testing/private role is configured, with emails, names and invitation tokens redacted;
- screenshot of the course syllabus showing the module/lesson structure;
- result of a non-tester access check before opening: what is visible and what is blocked;
- whether a separate tester account can open the learner route successfully.

After this evidence is received, the operating chat must run the canonical `stepik-staging-checklist.md` rather than infer `READY` from screenshots alone.

## Unresolved blockers after staging creation

- staging checklist PHONE smoke check;
- staging checklist COMPUTER smoke check;
- independent-attempt and F1 integrity in staging;
- consent/data-minimization operational setup;
- moderator rehearsal;
- recovery execution readiness in staging;
- time-sensitive service preflight;
- two eligible real Wave 0 participants screened, consented and scheduled.

## Next concrete step

Receive real Stepik staging evidence from the owner, verify it against `stepik-staging-checklist.md`, and record only observed results. Do not declare `WAVE 0 READY` or `HUMAN PILOT IN PROGRESS` before the remaining readiness evidence exists.
