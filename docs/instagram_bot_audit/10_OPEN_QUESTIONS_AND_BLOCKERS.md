# 10_OPEN_QUESTIONS_AND_BLOCKERS — остаток без маскировки

## Implementation остаток

Канонический per-ID checkbox: `07_IMPLEMENTATION_PLAN.md`; полный остаток:
`13_UNCLOSED_FINDINGS_RAW.md`; активный порядок: `14_IMPLEMENT2.md`.

- W4B: закрыта; `IMP-058` и `IMP-089` имеют code, tests и production evidence.
- W5: `IMP-028` (full size/sales prompt protocol), `IMP-095` (white 1090 грн
  variant data with real images/rules).
- W8: `IMP-044`–`046`, `060`–`061`, `094`, `096`, `100`, `101`; partial `043`.
  `IMP-044` теперь также несёт `F-AI-018`: fresh manager-message analysis job
  исчерпал stale leases без typed provider/process telemetry.
  F-TEST-004 внутри IMP-094 закрыта на `dd93f9f3`, но disposable MariaDB gate
  и остальные reliability acceptance criteria остаются открыты.
- W9: partial `IMP-081`–`088`. `IMP-081` foundation is
  production; `IMP-082/083` graph/ranker foundation and prompt parity are
  production `0ad694bc`; `IMP-084` exact availability and proposal reservation
  wiring are production through `90fdd0ec`; `IMP-085` parser/runtime facts and
  `IMP-086` migration `0145` reservation hardening are production through
  `1849441d`; paid commitment capacity guard F-CAT-011 — through `a7857ada`.
  Durable commerce session, candidate anchoring, stale binding,
  relaxed alternatives, full topology, manager-review UI and disposable MariaDB
  concurrency/constraint proof remain open. `IMP-087` дополнительно имеет
  uncommitted narrow receipt-backed WIP в `ig-commerce-durable-state`; это не
  shipment. `IMP-088` имеет digest/proposal API foundation, но freshness,
  отдельный review UI, audit/backfill и unified MariaDB/deploy proof открыты.
- Payment findings are not greenfield: `F-PAY-002/003/006` are PARTIAL because
  reservation/TTL/access/share-token foundation and `ig-deal:{deal.pk}`
  materialization exist. Remaining blockers are production reachability,
  legacy `ig-episode:*` compatibility/two-deals regression and payer/recipient E2E.
- W10: `IMP-090`–`093`.
- W11: `IMP-098` — F-CORE-003…006, F-SCORE-010 и partial-остатки
  F-SEC-004/009. F-PAY-010 закрыта отдельным production-срезом `7440bb98`;
  F-CORE-007 уже закрыта IMP-073; F-SCORE-012 остаётся в IMP-046.
- W12: закрыта — `IMP-102` provider-evidenced delivery FSM и `IMP-103`
  materialized event-driven policy continuation с immutable event facts,
  absolute timeline и pre-send invoice/restock recheck; production `434428ad`.

## Product/data blockers

1. Production product 110 has only the thermochromic green/oversize variant
   (`variant_id=81`, 1450 грн). The white 1090 грн variant cannot be fabricated
   without authoritative white images and fit/size rules (`F-DATA-016`).
2. Advertisement attribution has no source fields in historical payloads;
   implementation cannot invent campaign data (`F-DATA-004`, `IMP-043`). This
   finding is `BLOCKED`, while truthful `source unknown` and actor separation
   can be implemented independently.
3. Imported conversation role provenance is ambiguous (`F-DATA-015`), so text
   similarity is not accepted as a backfill proof (`IMP-096`).

## Branch-only / WIP blockers

- Historical product-reselection commits remain preserved. Do not cherry-pick
  them wholesale: `IMP-081` and partial `IMP-082/083` were ported independently;
  `IMP-084` foundation and proposal reservation are now on current `main` as
  `90fdd0ec`; parser `IMP-085` and migration `0145` are deployed in `1849441d`.
  Unified disposable MariaDB proof and the remaining runtime/UI gates are open.
- The W6-era untracked stock-policy tests are requirements to port onto current
  main, not production code (`F-CAT-004`, `IMP-084/086`).
- The assisted-checkout worktree's 390px breakpoint change is uncommitted and
  has no acceptance evidence; it is not counted as done.
- `codex-management-bot-statistics-visuals` is code WIP, not plan-only: modified
  `bot_views.py`, `ig_funnel_analytics.py`, `bot.html` and tests plus new plan/
  test files (volatile tracked diff; снять свежий `git diff --stat`). Review/rebase it for `IMP-093`; do not copy
  files wholesale and do not discard it.
- Dirty `codex-management-bot-live-visuals` and historical
  `codex/instagram-assisted-checkout-pre-split` are source-reconciliation rows,
  not merge authorities. Preserve and compare patch-unique requirements only.
- Dirty Meta/ingress worktree changes are based on an older runtime and are not
  evidence against current `instagram_login`; see source matrix.
- Dirty `codex/ig-followup-policies` originally preserved requirements
  `IMP-102/103` and `IMPR-FUP-014/015`. Delivery boundary реализован свежо и
  задеплоен как `IMP-102`/`IMPR-FUP-014`; `IMP-103`/`IMPR-FUP-015` закрыты
  current-base implementation `4dfff3a2`/`35d3bd93` с migration `0143`.
  Old-base code и конфликтующую migration `0131` нельзя cherry-pick wholesale.

## Historical test baselines; not the next definitive gate

One recorded full `management warehouse` run executed 2877 tests with 3 skipped
and `OK`. It includes the current parser, reservation, stock concurrency,
variant-price and W7 action-label regressions. Earlier IMP-102 gates remain
23/23 focused and 160/160 expanded.
`F-TEST-002` / `IMP-094` remain open because a separately provisioned
disposable MariaDB test database is still unavailable; production is read-only
evidence, not a test target. `06_TEST_MATRIX.md` also records a later 2897-test
checkpoint; neither historical count replaces the exact command/evidence ledger
required by `14_IMPLEMENT2.md`.

## Database boundary for every next agent

- Local SQLite is only a fast unit/regression layer. It does not contain the
  authoritative conversations/products/deals/payments and cannot prove MariaDB
  locks, races, collation, max length, triggers or migration rollback.
- Production MariaDB/MySQL `qlknpodo_MySQL_DB` is the primary source for real
  business/data conclusions. Discovery is read-only with minimal PII output.
- Destructive/concurrency acceptance requires a separate disposable MariaDB
  schema. Production must never be used as a fixture DB merely to close a test.
