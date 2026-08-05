# 10_OPEN_QUESTIONS_AND_BLOCKERS — остаток без маскировки

## Implementation остаток

Канонический список и checkbox: `07_IMPLEMENTATION_PLAN.md`.

- W4B: закрыта; `IMP-058` и `IMP-089` имеют code, tests и production evidence.
- W5: `IMP-028` (full size/sales prompt protocol), `IMP-095` (white 1090 грн
  variant data with real images/rules).
- W8: `IMP-044`–`046`, `060`–`061`, `094`, `096`, `100`, `101`; partial `043`.
  F-TEST-004 внутри IMP-094 закрыта на `dd93f9f3`, но disposable MariaDB gate
  и остальные reliability acceptance criteria остаются открыты.
- W9: partial `IMP-081`–`086`; open `IMP-087`–`088`. `IMP-081` foundation is
  production; `IMP-082/083` graph/ranker foundation and prompt parity are
  production `0ad694bc`; `IMP-084` exact availability and proposal reservation
  wiring are production through `90fdd0ec`; `IMP-085` parser/runtime facts and
  `IMP-086` migration `0145` reservation hardening are production through
  `1849441d`; paid commitment capacity guard F-CAT-011 — through `a7857ada`.
  Durable commerce session, candidate anchoring, stale binding,
  relaxed alternatives, full topology, manager-review UI and disposable MariaDB
  concurrency/constraint proof remain open.
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
   implementation cannot invent campaign data (`IMP-043`).
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
- Dirty Meta/ingress worktree changes are based on an older runtime and are not
  evidence against current `instagram_login`; see source matrix.
- Dirty `codex/ig-followup-policies` originally preserved requirements
  `IMP-102/103` and `IMPR-FUP-014/015`. Delivery boundary реализован свежо и
  задеплоен как `IMP-102`/`IMPR-FUP-014`; `IMP-103`/`IMPR-FUP-015` закрыты
  current-base implementation `4dfff3a2`/`35d3bd93` с migration `0143`.
  Old-base code и конфликтующую migration `0131` нельзя cherry-pick wholesale.

## Known test baseline

The latest full `management warehouse` run executed 2877 tests with 3 skipped
and `OK`. It includes the current parser, reservation, stock concurrency,
variant-price and W7 action-label regressions. Earlier IMP-102 gates remain
23/23 focused and 160/160 expanded.
`F-TEST-002` / `IMP-094` remain open because a separately provisioned
disposable MariaDB test database is still unavailable; production is read-only
evidence, not a test target.
