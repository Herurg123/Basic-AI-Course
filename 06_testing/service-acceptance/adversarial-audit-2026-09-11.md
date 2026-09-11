# Adversarial audit — Service Acceptance — 2026-09-11

**Type:** separate pre-PR adversarial pass  
**Role:** critic, not author confirmation  
**Context:** no separate critic agent/model is technically exposed in this session, so Project Instruction v1.3 fallback is used: a separate adversarial pass with explicit checklist and without relying on the author conclusion.

## Verdict

**ОДОБРЕНО для подготовки PR**, with explicit nonblocking observations listed below.

## Mandatory 16-point challenge

| # | Attack hypothesis | Finding | Result |
|---:|---|---|---|
| 1 | DOC-CONFIRMED was presented as LIVE-PASS | Report explicitly separates `DOC-CONFIRMED` from `OWNER-OBSERVED`; no UI fact is labeled LIVE-PASS | PASS |
| 2 | A paid account was used while described as free | Alice is labeled `FREE EXISTING ACCOUNT, NOT FRESH`; Giga functional checks worked anonymous and first Giga login was observed; no paid action used | PASS WITH EVIDENCE LIMITATION |
| 3 | Plus/Premium/boost was accidentally active | Alice upsell screens offered Plus/boost purchase; required B7/B8/download completed without purchase. Giga required no paid entitlement | PASS |
| 4 | VPN/foreign infrastructure hid geo barrier | Owner explicitly reported ordinary Russian connection, VPN off, Firefox/computer. Evidence level remains OWNER-OBSERVED | PASS |
| 5 | B7 was only a demo/marketing page | Owner actually prompted both services and reported real image generation; no marketing-only substitution | PASS |
| 6 | B8 was new generation instead of edit | Alice result preserved unique fixture code/shapes/labels while applying requested changes; Giga preserved source fixture while changing background | PASS |
| 7 | BACKUP was only declared, not working | Giga text, new chat, DOCX, PNG, B7, B8/background edit, download and login were all owner-observed | PASS |
| 8 | First success hid a later paywall | Full minimum chain continued through B7/B8/download in both routes without required payment | PASS |
| 9 | Child route was invented | Functional child route is explicitly `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED`; only official parent/legal route is DOC-CONFIRMED | PASS |
| 10 | Screenshots leak personal data | Raw screenshots containing profile/login/QR context are not committed. Report keeps only non-sensitive observations | PASS |
| 11 | B10 was replaced by an AI-provided link | Owner opened the official Alice terms in a separate tab, used `Ctrl+F`, copied the fragment, returned to chat and compared | PASS |
| 12 | Critical capability was accepted from marketing only | All blocking PRIMARY/BACKUP capabilities were functionally owner-observed; docs are supplementary | PASS |
| 13 | Temporary outage was misclassified as permanent FAIL | No temporary outage occurred in the tested mandatory flow | PASS / N.A. |
| 14 | Permanent defect was dismissed as temporary outage | No mandatory permanent defect was observed; UI/auth caveats are documented, not hidden | PASS / N.A. |
| 15 | Acceptance silently changed architecture | PRIMARY remains Alice, BACKUP remains GigaChat, B10 remains external-browser source, B8 BACKUP remains narrow background edit | PASS |
| 16 | Report allows M00–M01 while a critical dynamic dependency remains BLOCKED | The only blocked functional item is child/parent execution. Manifest v1.2 says the course is not positioned as a children’s course and an independent age-group route is promised only after conditions are checked. Therefore it is nonblocking for the current general/adult M00–M01 production slice, but blocks any claim of independent minor completion/public release until lawfully tested | PASS WITH NONBLOCKING OBSERVATION |

## Additional architecture check

- No mandatory action requires VPN, foreign card or paid subscription.
- Alice satisfies PRIMARY PASS: text, fresh working dialog route, DOCX, PNG, B7, real edit of uploaded source, download.
- GigaChat satisfies BACKUP PASS: text, login, DOCX, PNG, B7, narrow B8/background edit, free route.
- B10 route is observed end to end.
- X01–X10 are observed end to end.
- Giga anonymous behavior is more permissive than the current agreement wording. It is **`OBSERVED CAPABILITY — OUTSIDE CURRENT CONTRACT`** plus `OFFICIAL SOURCE CONFLICT`; it is not a reason to rewrite legal terms or the normative BACKUP route.

## Service Matrix decision

**No Service Matrix v1.1 is required for this acceptance.** The approved functional contract is confirmed: the same PRIMARY/BACKUP roles and required functions remain valid.

The normative Giga BACKUP remains the tested **authorized** route through Sber ID/phone. Anonymous Giga functionality is recorded only as **`OBSERVED CAPABILITY — OUTSIDE CURRENT CONTRACT`** because it is broader than the current contract and conflicts with the agreement wording.

A future SM revision is required only if a required route changes materially, for example if B4/B7/B8, paid access, geo access, age/legal route, or PRIMARY/BACKUP assignment changes.

## Nonblocking observations that must remain explicit

1. Alice built-in `Новый чат` requested login in anonymous mode; reopening the direct web route in a new tab created a fresh working dialog.
2. Alice B7 required ordinary login, but no Plus/boost/payment.
3. Giga anonymous text/file/image/B7/B8 behavior is `OBSERVED CAPABILITY — OUTSIDE CURRENT CONTRACT`; production BACKUP should use the verified login route.
4. Giga anonymous new chat discards the previous anonymous dialog/history unless the user logs in.
5. Giga file upload shows an explicit personal-data/secret-content consent warning.
6. Giga agreement says auth is mandatory while current web behavior allowed anonymous use; do not state that the legal requirement disappeared.
7. Child functional route is not tested and cannot be advertised as an independent minor route.
8. Free quotas/load remain dynamic and require retest before final screenshots/video/publication.
