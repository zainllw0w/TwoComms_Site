# 06_TEST_MATRIX — acceptance coverage

Статусы: `GREEN` — есть свежий автоматический evidence; `PARTIAL` — часть
контракта покрыта; `OPEN` — нужен отдельный implementation/live gate.

| ID | Сценарий | Статус | Evidence / остаток |
|---|---|---|---|
| T01 | Новый Instagram-вопрос | GREEN | IG intelligence/reply tests |
| T02 | UA/RU/EN и смена языка | GREEN | language/prompt tests |
| T03 | Реклама/ad context | PARTIAL | ad source absent: IMP-043 |
| T04 | Товар/размер/цвет/количество | PARTIAL | variant price green; full reselection IMP-081…088 |
| T05 | Payment link и expiry | GREEN | invoice TTL/payment tests |
| T06 | Успешная оплата | GREEN | payment truth/order tests |
| T07 | Duplicate payment webhook | GREEN | idempotency/payment tests |
| T08 | Pixel+CAPI | PARTIAL | related checkout contract; live evidence separate |
| T09 | Неуспешная оплата | GREEN | payment truth tests |
| T10 | Manager takeover | GREEN | ownership/takeover tests |
| T11 | Bot pause | GREEN | pause boundary tests |
| T12 | Follow-up payment link | GREEN | policy/event/claim tests |
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
| T41 | Full management suite from both working directories | GREEN (SQLite) | 2619 tests, 3 skipped, `OK` from worktree root and from `twocomms`; MariaDB parity remains IMP-094 |
| T42 | Terminal Telegram outcome and lifecycle alert isolation | GREEN | 75 focused notification/lifecycle/send regressions: no retry for UNKNOWN/DEAD_LETTER, redacted bounded summary, distinct lifecycle keys and one failed-paylink alert; IMP-077 |
| T43 | Superseded payment review не объединяет коммерческие episodes | GREEN | 134 local commercial/payment tests; production MySQL reconcile x3 = zero remainder; client 59 separate terminal episodes, daemon running/alive on `93ae8684` |
| T44 | Verified sales semantics и inventory policy | PARTIAL | migrations `storefront.0088`/`fable5.0008`, InnoDB tables, 77 policies and append-only triggers verified; runtime/admin consumer + disposable MariaDB test gate remain IMP-081 |

**Fresh local gate for current checkpoint:** full `management` suite passed
2619 tests with 3 skipped from both supported CWDs; focused branch gate passed
136 tests and the detached-worker/recovery smoke package passed 6 tests.
`git diff --check` is clean. Commit `15147ded` is deployed; production
`check`/migration-drift and daemon recovery are green. A separate disposable
MariaDB gate is still missing, so `F-TEST-002` / `IMP-094` remain open.

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
