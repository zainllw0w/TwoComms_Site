# 06_TEST_MATRIX — acceptance coverage

Статусы: `GREEN` — есть свежий автоматический evidence; `PARTIAL` — часть
контракта покрыта; `OPEN` — нужен отдельный implementation/live gate.

| ID | Сценарий | Статус | Evidence / остаток |
|---|---|---|---|
| T01 | Новый Instagram-вопрос | GREEN | IG intelligence/reply tests |
| T02 | UA/RU/EN и смена языка | GREEN | language/prompt tests |
| T03 | Реклама/ad context | PARTIAL | ad source absent: IMP-043 |
| T04 | Товар/размер/цвет/количество | PARTIAL | exact prompt parity GREEN; availability foundation GREEN, durable runtime session/reservation/checkout wiring remain IMP-082…088 |
| T05 | Payment link и expiry | GREEN | invoice TTL/payment tests |
| T06 | Успешная оплата | GREEN | payment truth/order tests |
| T07 | Duplicate payment webhook | GREEN | idempotency/payment tests |
| T08 | Pixel+CAPI | PARTIAL | related checkout contract; live evidence separate |
| T09 | Неуспешная оплата | GREEN | payment truth tests |
| T10 | Manager takeover | GREEN | ownership/takeover tests |
| T11 | Bot pause | GREEN | pause boundary tests |
| T12 | Follow-up payment link | GREEN | provider-evidenced delivery FSM plus materialized event continuation: 255 focused event/FSM/checkout/restock tests and production `434428ad` |
| T13 | Ответ до timer | GREEN | follow-up suppression tests |
| T14 | Явный отказ | GREEN | objection/follow-up tests |
| T15 | «Подумаю» | GREEN | policy tests |
| T16 | «Дорого» | GREEN | objection lifecycle tests |
| T17 | Discount eligibility | GREEN | policy/discount tests |
| T18 | TTN created | GREEN | shipment tests |
| T19 | Duplicate Nova Poshta event | GREEN | shipment idempotency tests |
| T20 | Получен / UGC | PARTIAL | delivery copy green; full UGC automation remains |
| T21 | Promo за отметку | PARTIAL | manual evidence gate, no auto promo |
| T22 | Exchange | GREEN | post-sale/exchange tests |
| T23 | Full refund | GREEN | reversal/FSM/payment tests |
| T24 | Complaint | GREEN | service suppression/escalation tests |
| T25 | Repeat order | GREEN | episode/repeat tests |
| T26 | Personal owner message | GREEN | classifier tests |
| T27 | Collaboration | GREEN | taxonomy tests |
| T28 | Reaction only | GREEN | reaction tests |
| T29 | Provider rate limit | GREEN | Meta/send backoff tests |
| T30 | All Gemini keys unavailable | GREEN | cooldown regression in `tests_ig_audit_fixes` |
| T31 | Worker restart | GREEN | durable claim/reclaim tests |
| T32 | UI order dropdown | GREEN | W7/order assignment tests |
| T33 | UI funnel branches | GREEN | W6/FSM/UI tests |
| T34 | UI follow-up timer | GREEN | W7/policy tests |
| T35 | Date filters/timezone | GREEN | W7 analytics tests |
| T36 | Dashboard raw-event reconciliation | GREEN | production MySQL: 197 events/96 drop-offs; API raw-event reconciliation, IMP-058 |
| T37 | Out-of-order webhook | GREEN | idempotent event keys + event-time ordering; IMP-058 regression tests |
| T38 | Multiple open orders | PARTIAL | model support; durable commerce session IMP-087 |
| T39 | Forwarded payment link | GREEN | paylink product/intent tests |
| T40 | Rollback drill | PARTIAL | superseded-invoice recovery IMP-089 is GREEN; full deterministic deploy/rollback gate remains IMP-094 |
| T41 | Full management suite | GREEN (SQLite) | 2675 tests passed, 3 skipped; MariaDB parity remains IMP-094 |
| T42 | Terminal Telegram outcome and lifecycle alert isolation | GREEN | 75 focused notification/lifecycle/send regressions: no retry for UNKNOWN/DEAD_LETTER, redacted bounded summary, distinct lifecycle keys and one failed-paylink alert; IMP-077 |
| T43 | Superseded payment review не объединяет коммерческие episodes | GREEN | 134 local commercial/payment tests; production MySQL reconcile x3 = zero remainder; client 59 separate terminal episodes, daemon running/alive on `93ae8684` |
| T44 | Verified sales semantics и inventory policy | PARTIAL | migrations `storefront.0088`/`fable5.0008`, InnoDB tables, 77 policies and append-only triggers verified; runtime/admin consumer + disposable MariaDB test gate remain IMP-081 |
| T45 | Typed price-aware graph и explainable candidates | PARTIAL | current full suite 2675; production 91=800/950, 110=1450, hard incompatible size rejected; durable runtime/stale binding remain IMP-082/083/087 |
| T46 | Variant-specific prompt price/size parity | GREEN | `e44d1440` + `0ad694bc`; product 110 prompt = variant 81, thermo green, 1450 грн, oversize XS/M; false XS/S/M/L/XL/XXL row absent; 188 focused + 2675 full suite |
| T47 | Exact warehouse/catalog availability | PARTIAL | `1849441d`; availability, proposal reservation, revision, stale-instance and stock-escalation tests are green locally; MariaDB lock/constraint proof and final production-like gate remain IMP-084/086/088 |
| T48 | Typing/send boundary and permission transition | GREEN | `c0f9fd1f` + `d84ca10d`; focused live-visual + reply-priority suite 63/63, including cancelled fallback recovery at typing/send boundary; production check/daemon passed |

**Fresh local gate for current checkpoint:** full `management warehouse` suite
passed **2877 tests, 3 skipped, `OK`** after the parser/reservation/stock
hardening slice. Focused stale-stock, paylink-reason, UI-action and variant
authority regressions are green; Django check, migration drift, compileall and
`git diff --check` are green. Production MariaDB has migration `0145` applied,
but a disposable concurrent MariaDB test database is still required.
Django check, migration drift, compileall and `git diff --check` are green.
Commit `0ad694bc` is deployed. A separate disposable MariaDB gate is still
missing, so `F-TEST-002` / `IMP-094` remain open.

**W8 update 2026-08-04:** `221cf37d` added the T42 gate; the 75-test focused
run, `manage.py check` and migration-drift are green after rebase on current
`main`. Production reports `running=True`, `alive=True`, empty `last_error`
and zero `UNKNOWN`/`DEAD_LETTER` outbox rows.

**Recovery update 2026-08-05:** `93ae8684` passed 134 focused tests, check,
migration drift and compileall. Production `reconcile_ig_commercial_episodes
--passes 3` returned zero remaining deals/reviews/attributions, then static,
compress, playbook seed, payment backstop and daemon restart completed. Final
status: `running/alive`, `instagram_login`, heartbeat 1.0 s, all three working
queues zero. This is the live MySQL evidence for T43, not a disposable test DB.

**W9 graph/prompt update 2026-08-05:** historical foundation `29684475` was
extended by `e44d1440`/`0ad694bc`. Current full suite is 2675 (3 skipped), with
188 focused tests. Production product 110 prompt is exact variant 81, thermo
green, 1450 грн, oversize XS/M; false product-wide sizes are absent. This is
production read-only evidence, not the still-missing disposable MariaDB test
gate.

**W9 availability update 2026-08-05:** `17f5b672` is deployed with exact
warehouse/catalog decisions, aggregate basket checks and ambiguity fail-closed
coverage; `90fdd0ec` added proposal reservation wiring and `0144`, and
`1849441d` added `0145` revision/lock safety, reason-preserving stock
escalation and bounded commerce-turn parser integration. T47 remains PARTIAL
until readiness/alternative consumers and the disposable MariaDB allocation gate
are complete.
