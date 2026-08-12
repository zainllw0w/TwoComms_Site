# 08_COMPLETION_LOG — что действительно завершено

Правило: запись появляется только после code in `main`, fresh tests и production
proof. Branch-only work is listed in `12_SOURCE_RECONCILIATION.md`, not here.

| Срез | Main commit(s) | Результат |
|---|---|---|
| W0–W3 | `0a251273`, `b11f71a4`, `0b3e14a6`, `3d7f8a46` | diagnostics, safety, contour, buyer truth |
| W4/W4C | `c696ee9e`, `305a4748`, `3191e08c` | assisted checkout, model-led dialogue, catalog parity |
| W4D / IMP-073 | `e4e410bf` | outgoing registry/echo, DB fallback при сбое cache, media behavior; F-CORE-007/015 |
| W6 | `34d1e165` | arbiter, FSM, funnel branches, product-switch journal |
| W7 | `bca7e4e2`, `1380db8e` | admin workspace, pagination, UI evidence |
| IMP-080 | `8ccac4f9`, `0d6cc6a2` | variant-aware price read model and production proof |
| IMP-051/053/055/056 | `2a89d860`, `cd070cba`, `efc0ee10`, `c00c8c5a` | backstop, policy, fulfillment, durable claims |
| IMP-057 | `d0098d0b`, `65bbde3e` | objection lifecycle and documentation |
| Current reliability slice | `6b86e103` | delivery marker rollback, tagged-send boundary, Gemini pooled cooldown |
| IMP-099 | `66acb900`, `2f1efa4b` | Cyrillic sizes, TTN deadline/stage advance, transcript-bound media, fast-return payer |
| IMP-058 | `274c2c61`, `79882368`, `92d46c5a` | Durable event-time funnel analytics, classified drop-offs, 17 event types, MySQL backfill/scan proof |
| IMP-089 | `280c07e8` | Bounded superseded-invoice lifecycle, polling recovery, terminal markers, legacy materialization, MySQL migration `0134` and daemon/check-only proof |
| IMP-077 / F-OPS-009 | `31f8151f`, `221cf37d` | Flow throttle/dedupe/admin links plus terminal summary, lifecycle-key separation, Ukrainian lifecycle copy and a single actionable failed-paylink alert |
| F-PAY-015 / daemon reconcile | `280d8f03`, `93ae8684` | Superseded review audit links are non-owning; repeated backfill preserves separate terminal episodes; MySQL reconcile and daemon recovery verified |
| F-CAT-007 / prompt parity | `e44d1440`, `0ad694bc` | Prompt sizes bind to exact variant+fit; authoritative empty size contract no longer falls back to product-wide sizes; product 110 = variant 81, thermo green, 1450 грн, oversize XS/M |
| IMP-102 / F-FUP-013 / IMPR-FUP-014 | `0d4d38c0`, `0e9e9ba5`, `4cb86743`, `414e639e` | Durable follow-up delivery FSM, receipt-first recovery without resend, guarded finalization race and audited ambiguous manager resolution |
| IMP-103 / IMPR-FUP-015 | `4dfff3a2`, `35d3bd93` | Materialized event-driven continuation, immutable event payload/time, absolute policy timeline, pre-send invoice/restock recheck, audited continuation API; migration `0143` |
| IMP-104 / F-CAT-008/009/010 / IMPR-CAT-007 | `1f5dcb70`, `7fdbe613`, `1f8cead2`, `434428ad` | Configuration-specific price authority from speech through hosted checkout; generic/no-variant option propagation, fail-closed ambiguity/unavailability guards and durable escalation when holding delivery fails; 255 focused tests |
| Sender action observability | `13bedf8f`, `d3e2c51b`, `0d471ebe`, `c0f9fd1f` | Typed provider-aware `typing_on`/`typing_off`/`mark_seen` outcomes, bounded perceptible typing, typing-off-before-send ordering and permission-transition claim cleanup; focused live-visual/reply-priority evidence 63/63 |
| Live visual refinement | `d7f10477`, `8a2f9ee1`, `233297b3`, `6e05c6b2`, `e262c0c4` | Four UI code slices plus one documentation shortlist are represented in current `main`; current-main browser evidence 135/135. The historical refinement branch is superseded and must not be cherry-picked wholesale |
| Cancelled fallback terminalization | `d84ca10d` | An unarmed outage-recovery intent is terminalized whenever permission, lease or typing/send boundary cancels the customer send; no dangling fallback intent survives a definite no-send path |
| IMP-086 reservation lifecycle foundation | `90fdd0ec` | Warehouse/catalog reservation lifecycle, paid commit without physical decrement, fulfillment/write-off/reversal links and late-payment `OVERBOOKED_REVIEW`; migration `0144` applied in production. Later manager notification, deterministic lock ordering and stale-callback/revision safety are recorded in deployed `1849441d` below |
| IMP-085/086 parser and reservation hardening | `1849441d` | Bounded commerce-turn facts and trusted URL pinning are integrated before Gemini; migration `0145` adds deterministic allocation locking, revision-safe reservation replacement, late-payment manager hand-off and stale warehouse callback protection. Full `management warehouse` gate: 2877 OK; production SHA/migration/daemon verified |
| IMP-098 / F-PAY-010 subtask | `7440bb98` | Human/operator authority is mandatory for prepayment amount evidence; model/customer origin, customer counteroffer, receipt and multi-amount text fail closed before deal/invoice creation. 41 focused tests and rollback proof on production MariaDB; IMP-098 remains open for its other orphan findings |
| IMP-086 / F-CAT-011 subtask | `a7857ada` | Paid warehouse commitments protect capacity independently of checkout TTL; manual/unrelated negative adjustments preserve active and paid reservations, while exact-order fulfillment consumes only its own paid rows. Focused 92/92, full 2897 OK; IMP-086 remains PARTIAL for MariaDB concurrency proof and manager-review UI |
| IMP-094 / F-TEST-004 subtask | `dd93f9f3` | Reduced-motion coverage verifies refresh selectors semantically rather than by adjacency. Inbox/UI 188/188 and repeated full 2897 OK; IMP-094 remains OPEN for the disposable MariaDB gate |
| F-CORE-003 lease/reclaim invariant | `18ddc636` | Lease duration is normalized to strictly outlive stale-processing reclaim; strict timeout boundary and claim ownership regressions prevent a second automation sender from entering the former overlap window |
| F-CAT-011 late-payment race extension | `b23dfeed` | Provider-confirmed payment time distinguishes a delayed callback from a late payment; reallocated capacity becomes one idempotent `OVERBOOKED_REVIEW`/manager task rather than a second stock promise |
| IMP-105 / F-STATE-011 | `fbe33a68` | Current paid/shipped presentation and paid filter are episode-scoped; historical order/payment remains visible only as buyer history. Direct presentation 18 tests; current buyer/UI gate 159 tests; production current checkpoint `fbe33a68` |
| Implement2 W1.6 / F-AI-010/011 / F-CTX-003 | `05d2cef4`, `ec6febcc`, `0c536e0a`, `796028ba`, `130cd920` | Typed immutable Gemini JSON controls, fail-closed legacy compatibility, application-owned authority/evidence gates, obfuscated-token sanitization and removal of duplicate saved payment protocol. Migration `0152`; 240/240 local gate and production parser/prompt/health proof |
| Implement2 W1.7 / IMP-060 | `214ae4b9` reachable through `b9bab236`, plus W1.7 follow-up | Historical/imported URLs are metadata-only, live webhook bytes use owned storage with claim/reuse, media phase/error is persisted before provider analysis, and historical payment vision cannot revive stale local media. Fresh focused gate `162/162`; production MariaDB migration `0153` and metadata-only reconciliation. No post-migration live analysis exists, so `F-AI-018` remains open under `IMP-044` |

The current canonical status is the checkbox list in `07_IMPLEMENTATION_PLAN.md`.
`IMP-081` is intentionally absent from the completed table: its deployed
semantic/inventory foundation is useful and verified, but the task remains
PARTIAL until runtime/admin consumers and a disposable MariaDB gate exist.

`IMP-082/083` are also intentionally absent from the completed table. Their
typed price-aware graph/ranker foundation is deployed through `7b5d5cc7`,
`1c4d6d48`, while `e44d1440`/`0ad694bc` add verified prompt price/size parity.
The tasks remain PARTIAL because durable runtime commerce-session integration,
stale binding, relaxed alternatives and full topology remain open.

`IMP-084` is likewise absent from the completed table. Its exact availability
foundation and proposal reservation wiring are deployed through `90fdd0ec` with
availability and reservation tests, but readiness/alternative consumers and a
disposable MariaDB proof remain open in `IMP-084/086/088`.

`IMP-085` and `IMP-086` remain partial rather than complete: parser facts and
reservation hardening are deployed through `a7857ada`, but durable commerce
session/candidate anchoring, readiness/alternative consumers, manager review UI
and a disposable concurrent MariaDB gate remain before their residual checkboxes
can close.
