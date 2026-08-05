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
| Sender action observability | `13bedf8f` | Typed, provider-aware `typing_on`/`typing_off`/`mark_seen` outcomes with redacted logging and live-visual regression coverage |

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
foundation is deployed through `17f5b672` with 5 availability tests and a
277-test combined gate, but proposal/readiness/checkout wiring, reservation
lifecycle and disposable MariaDB proof remain open in `IMP-084/086/088`.
