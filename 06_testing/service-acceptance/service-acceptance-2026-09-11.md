# Service Acceptance — 2026-09-11

**Gate status:** `IN PROGRESS — candidate PASS WITH EXPLICIT NONBLOCKING OBSERVATIONS; adversarial audit/PR not yet complete`  
**Evidence mode available in this chat:** `OWNER-OBSERVED` for live UI actions; `DOC-CONFIRMED` for official-source facts. Interactive Computer Use is unavailable, therefore no UI action is labeled `LIVE-PASS`.

## 1. Purpose

Проверить наблюдаемыми данными, может ли обычный пользователь пройти обязательные технические действия курса по утвержденному бесплатному маршруту: PRIMARY = Алиса AI web; BACKUP = GigaChat web + внешний браузер; B10 = реальное внешнее основание; B8 PRIMARY = реальный edit загруженного исходника; B8 BACKUP = узкое изменение/замена фона.

## 2. Normative basis

На старте прогона непосредственно из `main` прочитаны: project instructions v1.3, `AGENTS.md`, root `README.md`, Manifest v1.2, Competency Map v1.1, Service Matrix v1.0, Course Architecture v1.0, Lesson Standard v1.1, coverage matrix/operations/assessment/assets-and-validation, lesson-cards summary, а также карточки `M00-L01`, `M00-L02`, `M00-L03`, `M01-L01`, `M01-L02`, `M05-L02`.

Содержательного конфликта, требующего перепроектирования до acceptance, не обнаружено.

## 3. Test environment

| Parameter | Observed |
|---|---|
| Date | 2026-09-11 |
| Local time | owner run approximately 12:01–14:xx +03:00; not every action separately timestamped |
| Connection | ordinary Russian connection |
| VPN | off |
| Browser/device | Firefox / computer |
| Alice | anonymous for A01–A05; existing account for A06–A08 |
| Alice entitlement | `FREE EXISTING ACCOUNT, NOT FRESH`; Plus/boosts offered as upsell, not required |
| GigaChat | anonymous for G01a–G07 functional checks; first-ever GigaChat login then completed via Sber ID/phone |
| GigaChat entitlement | fresh GigaChat service use; no paid entitlement required or observed |
| Tester | OWNER for live UI actions |

Географический маршрут выполнен на обычном российском соединении без VPN по сообщению владельца.

## 4. Accounts and entitlement state

**Alice.** Text, new-session workaround, DOCX and PNG worked anonymous. B7 generation required login. After normal login on an existing non-fresh account, B7, real B8 edit and download completed without payment. Screenshots showed Plus/boost purchase offers rather than an already-required paid plan; no paid action was used.

**GigaChat.** Anonymous web chat supported text, new chat, DOCX, PNG, B7 and B8/background edit + download. Separate login route was also tested: Sber ID, +7 phone entry, first-use agreement, then GigaChat opened. Owner reported this was the first GigaChat use on the account. No payment or subscription barrier appeared.

## 5. Official-source freshness check

Checked 2026-09-11 against current official sources.

| Source | Current fact supported | Evidence status |
|---|---|---|
| `https://yandex.ru/legal/alice_chat/ru/` | Alice web service; minor use with knowledge/consent/control of legal representative | DOC-CONFIRMED |
| `https://alice.yandex.ru/support/ru/assistant/chat-alice` | free basic chat; non-Plus degradation possible under high load | DOC-CONFIRMED |
| `https://alice.yandex.ru/support/ru/assistant/chat/files` | file sending/analysis supported; high-load caveat | DOC-CONFIRMED |
| `https://alice.yandex.ru/support/ru/assistant/chat/picture` | free web image generation without mandatory Plus | DOC-CONFIRMED |
| `https://alice.yandex.ru/support/ru/assistant/chat/edit-photos` | uploaded JPEG/PNG can be edited and downloaded | DOC-CONFIRMED |
| `https://yandex.ru/legal/alicebst/ru/` | standard free limits and optional paid boosts | DOC-CONFIRMED |
| `https://developers.sber.ru/docs/ru/policies/gigachat/agreement` | free personal beta; formal auth requirement; minor route via parent/representative; limits may change | DOC-CONFIRMED |
| `https://giga.chat/help/articles/how-to-start-work-with-gigachat` | Sber ID / phone login; Russian SIM route | DOC-CONFIRMED |
| `https://giga.chat/help/articles/faq` | in-Russia route; VPN should be off | DOC-CONFIRMED |
| `https://giga.chat/help/articles/work-with-docs` | DOCX/PDF/TXT supported | DOC-CONFIRMED |
| `https://giga.chat/help/articles/gigachat-load-picture` | image upload/analysis supported | DOC-CONFIRMED |
| `https://giga.chat/help/articles/how-to-generate-images` | image generation supported | DOC-CONFIRMED |
| `https://giga.chat/help/articles/background-remove` | standalone background tool free/browser/no registration claim | DOC-CONFIRMED / OFFICIAL SOURCE CONFLICT |

### Official source conflict

The GigaChat agreement states mandatory authorization, while current owner-observed web behavior allowed anonymous text, new chat, DOCX, PNG, image generation, background edit and download. The standalone background tool also opened without login. This remains `OFFICIAL SOURCE CONFLICT`: live functionality is recorded as observed; it does not rewrite the legal text.

## 6. Alice test matrix

| Test ID | Account | Action | Expected | Observed | Status | Evidence | Affected lessons | Notes |
|---|---|---|---|---|---|---|---|---|
| A01 | anonymous | open web + simple text | text answer without required payment | answer received | OWNER-OBSERVED-PASS | owner report | M00-L01, M01-L01 | Russia, VPN off |
| A02 | anonymous + free existing | actual login boundaries | distinguish optional/required login | text/DOCX/PNG anonymous; B7 required login; B7/B8 worked after normal login | OWNER-OBSERVED-PASS | owner report/screenshots | M00-L01–L03, M05-L02 | login is capability-specific |
| A03 | anonymous | start new dialog | new working dialog possible | built-in `Новый чат` asked login; opening `alice.yandex.ru` in a new tab produced a fresh dialog and answer | OWNER-OBSERVED-PASS WITH UI CAVEAT | owner report | M00-L03 | anonymous workaround is direct/new tab |
| A04 | anonymous | DOCX fixture upload + factual question | document read correctly | Beta after Alpha; 12 conditional days | OWNER-OBSERVED-PASS | owner report | M00-L02 | fixture `AF-DOC-2026-0911` |
| A05 | anonymous | PNG fixture analysis | image/code recognized | `AF-IMG-314`, square left, circle right; screenshot also showed `Войти` | OWNER-OBSERVED-PASS | owner report + screenshot | M00-L02 | anonymous state visible |
| A06 | `FREE EXISTING ACCOUNT, NOT FRESH` | B7 new image generation | real image generated free | first anonymous attempt requested login; after login image generated free | OWNER-OBSERVED-PASS | owner report | M05-L02 | no Plus/boost required |
| A07 | same | edit uploaded existing fixture | edit the source, not unrelated generation | light-blue background + green triangle; code/shapes/labels preserved | OWNER-OBSERVED-PASS | owner screenshot | M05-L02 | proves existing-source edit |
| A08 | same | save/download edited result | file saved without payment | downloaded free | OWNER-OBSERVED-PASS | owner report | M00-L03, M05-L02 | — |
| A09 | same | observe queue/limits/upsell | optional upsell must not become required payment | Plus/boost offers observed; required actions still completed free; no queue/limit encountered | OWNER-OBSERVED-PASS WITH OBSERVATION | owner screenshots/reports | M00, M05-L02 | limits remain dynamic |
| A10 | n/a | child/parent route | normative route + functional test if lawful account exists | normative route confirmed; no lawful child functional account tested | BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED | official terms + project manifest | M00-L01 / release risk | nonblocking only while course does not promise independent child route |

## 7. GigaChat test matrix

| Test ID | Account | Action | Expected | Observed | Status | Evidence | Affected lessons | Notes |
|---|---|---|---|---|---|---|---|---|
| G01 | anonymous + fresh GigaChat service use | access + login route | free route; login feasible by Russian phone/Sber ID | anonymous chat worked; +7/Sber ID login later succeeded; first-use agreement accepted; service opened | OWNER-OBSERVED-PASS | owner reports/screenshots | M00-L01 | no OTP/phone data stored in report |
| G02 | anonymous | new chat | new dialog works | new chat created and answered; old anonymous chat is discarded unless user logs in | OWNER-OBSERVED-PASS WITH UI CAVEAT | owner screenshots | M00-L03 | history-loss warning must be taught |
| G03 | anonymous | DOCX fixture | document read free | file consent dialog shown; Beta/12 days extracted correctly | OWNER-OBSERVED-PASS WITH CONSENT CAVEAT | owner screenshots | M00-L02 | consent says no personal/secret data |
| G04 | anonymous | PNG fixture | image analysis | `AF-IMG-314`, square left, circle right | OWNER-OBSERVED-PASS | owner screenshot | M00-L02 | — |
| G05 | anonymous | B7 generation | real image generated free | image generated free | OWNER-OBSERVED-PASS | owner report | M05-L02 | no login/payment |
| G06 | anonymous | BACKUP B8 background edit + download | edit existing source and save | background changed to light yellow, source code/shapes/labels preserved; file downloaded free | OWNER-OBSERVED-PASS | owner screenshot/report | M05-L02 | narrow B8 contract satisfied |
| G07 | anonymous | standalone auth discrepancy | observe actual auth requirement | catalog/background route opened and continued in browser without login | OWNER-OBSERVED-PASS / OFFICIAL SOURCE CONFLICT REMAINS | owner screenshots/report | M05-L02 | functional observation does not override agreement text |
| G08 | anonymous + logged-in verification | paid barrier after minimal set | no mandatory subscription | text/DOCX/PNG/B7/B8/download completed free; login also completed without payment | OWNER-OBSERVED-PASS | accumulated owner evidence | M00, M05-L02 | — |

## 8. Cross-cutting browser operations

| ID | Operation | Result |
|---|---|---|
| X01 | direct PRIMARY link | OWNER-OBSERVED-PASS |
| X02 | new chat/start | OWNER-OBSERVED-PASS WITH UI CAVEATS |
| X03 | upload file | OWNER-OBSERVED-PASS |
| X04 | upload image | OWNER-OBSERVED-PASS |
| X05 | open external source | OWNER-OBSERVED-PASS |
| X06 | find specific fragment | OWNER-OBSERVED-PASS |
| X07 | return to AI chat | OWNER-OBSERVED-PASS |
| X08 | copy usable text | OWNER-OBSERVED-PASS |
| X09 | save/download result | OWNER-OBSERVED-PASS |
| X10 | switch PRIMARY → BACKUP without artificial failure | OWNER-OBSERVED-PASS |

X10 evidence: Alice conclusion copied into GigaChat; GigaChat accepted it and continued the task.

## 9. B10 technical route

`OWNER-OBSERVED-PASS`.

Observed chain: opened official Alice terms in a separate browser tab → `Ctrl+F` found the minor-use fragment → copied one full source sentence → returned to Alice → asked whether the supplied sentence supports the claim → Alice explicitly matched the claim to the source sentence. This is a real `claim → source → fragment → return → compare` chain, not an AI-provided citation shortcut.

## 10. Age / parent route

- Alice: `DOC-CONFIRMED` minor use with knowledge, consent and control of legal representative.
- GigaChat: `DOC-CONFIRMED` formal adult user; under-18 use only with parent/representative consent/control under the current agreement.
- Functional child/parent execution: `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED`.

Release-risk assessment: **nonblocking for the current M00–M01 production vertical slice and adult/general route, provided no independent minor route is promised.** Manifest v1.2 says the course is understandable to roughly 12–14-year-olds but is not positioned as a children’s course, and that an independent route for an age group is promised only after the relevant conditions are checked. Before any publication claim that a minor can complete independently, a lawful child/parent functional test is required.

## 11. Free limits and observed queues

No queue or hard free-limit was hit during this run. Alice showed optional Plus/boost upsell, but required B7/B8/download still completed without purchase. Official sources still warn that high load and standard limits can temporarily affect functions; this remains a dynamic retest condition, not a present fail.

## 12. PRIMARY/BACKUP failover

`OWNER-OBSERVED-PASS` for the approved service pair. Both PRIMARY and BACKUP independently completed the required minimum. X10 additionally proved operational switching from Alice to GigaChat without fabricating a service outage.

## 13. Mapping to Lesson IDs

- `M00-L01`: A01/A02/A03/A10 + G01/G02/G08.
- `M00-L02`: A04/A05 + G03/G04.
- `M00-L03`: A03/A08/G02 + X01–X10.
- `M01-L01`: A01 + text/copy/apply continuity.
- `M01-L02`: B10 + X05–X08.
- `M05-L02`: A06/A07/A08/A09 + G05/G06/G07/G08.

## 14. Evidence index

Evidence level is `OWNER-OBSERVED`, not `LIVE-PASS`.

Key screenshots supplied by owner showed: Alice anonymous image analysis; Alice Plus/boost upsell; Alice real edit of `AF-IMG-314`; Giga anonymous chat/new-chat warning; Giga DOCX consent and correct answer; Giga PNG analysis; Giga background edit; Giga standalone background route; Sber ID login; first-use Giga agreement; B10 comparison; Alice→Giga X10 continuation.

Screenshots containing profile or login context are intentionally not committed as raw evidence. Report records the observations without storing PII, QR, phone, cookies, tokens or browser-profile data.

Fixtures used: `ACCEPTANCE_FIXTURE_document.docx`, `ACCEPTANCE_FIXTURE_image.png`. They are acceptance-only fixtures, not final course assets.

## 15. Deviations from Service Matrix

Observed behavior requires a documented service-matrix delta, not a silent rewrite:

1. Alice anonymous text/DOCX/PNG are available; B7 requires login; B8/download work after ordinary login. Built-in anonymous `Новый чат` asks login, but opening a new direct tab creates a fresh anonymous dialog.
2. GigaChat current web behavior is substantially more permissive than the agreement text: anonymous text, new chat, DOCX, PNG, B7, background edit and download all worked. The legal/auth conflict remains explicit.
3. Giga file upload shows a specific consent warning about personal data/secrets.
4. Giga anonymous new chat deletes the previous anonymous dialog/history.

These are dynamic operational findings. They do not change the approved architecture: PRIMARY remains Alice; BACKUP remains GigaChat; B8 backup remains narrow background edit.

## 16. Blocks / risks

- `BLOCKED — CHILD FUNCTIONAL TEST NOT PERFORMED`: nonblocking for current adult/general vertical slice, blocking for any claim of independent minor completion.
- `OFFICIAL SOURCE CONFLICT`: Giga agreement requires auth while observed web route allows anonymous use. Must remain visible in instructions/SM; do not state that the legal requirement disappeared.
- Free quotas/load can change; recheck before production screenshots/video and before publication.
- UI labels/placement are dynamic and should not be elevated into architecture.

## 17. Gate verdict

**Candidate verdict before audit: `PASS WITH EXPLICIT NONBLOCKING OBSERVATIONS`.**

Reason: all blocking PRIMARY, BACKUP, B10 and cross-cutting functional requirements were owner-observed on ordinary Russian connection without VPN, foreign card or required payment. The only unperformed functional route is child/parent execution, which the current project manifest does not permit us to promise independently until tested.

## 18. Production implications

If adversarial audit confirms this verdict, the project may proceed to the interface-dependent M00–M01 production vertical slice. Do not start full-course production, M02–M08, Stepik publication or broad asset production as a consequence of this gate alone.

Production instructions must include the observed caveats: Alice login boundary for B7, Alice anonymous new-chat workaround, Giga anonymous-history loss, Giga file-consent dialog, and optional-vs-required paid offers.

## 19. Retest conditions

Retest when: UI route materially changes; B4/B7/B8 becomes unavailable; payment becomes mandatory; Russian access changes; official terms materially change; before promising an independent minor route; before locking final screenshots/video for release.

Temporary outage must be recorded and BACKUP tested; do not purchase Plus/Boost merely to pass acceptance.

## 20. Date / tester / evidence level

- Date: 2026-09-11
- Authoring role: Service Acceptance Lead
- Live UI tester: OWNER
- Highest live evidence: `OWNER-OBSERVED-PASS`
- Documentary evidence: `DOC-CONFIRMED`
- Interactive-agent evidence: none
- Branch: `testing/service-acceptance-2026-09-11`
- Current state: awaiting adversarial audit, service-matrix delta decision and PR workflow
