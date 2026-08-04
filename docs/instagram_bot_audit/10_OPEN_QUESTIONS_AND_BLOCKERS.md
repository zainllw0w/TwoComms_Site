# 10_OPEN_QUESTIONS_AND_BLOCKERS — остаток без маскировки

## Implementation остаток

Канонический список и checkbox: `07_IMPLEMENTATION_PLAN.md`.

- W4B: закрыта; `IMP-058` и `IMP-089` имеют code, tests и production evidence.
- W5: `IMP-028` (full size/sales prompt protocol), `IMP-095` (white 1090 грн
  variant data with real images/rules).
- W8: `IMP-044`–`046`, `060`–`061`, `094`, `096`, `100`, `101`; partial `043`.
- W9: partial `IMP-081`–`083`; open `IMP-084`–`088`. `IMP-081` foundation is
  production; `IMP-082/083` graph/ranker foundation and prompt parity are
  production `0ad694bc`, while runtime commerce session, stale binding, relaxed
  alternatives and full topology remain open.
- W10: `IMP-090`–`093`.
- W11: `IMP-098` — F-CORE-003…006, F-PAY-010, F-SCORE-010 и partial-остатки
  F-SEC-004/009. F-CORE-007 уже закрыта IMP-073; F-SCORE-012 остаётся в IMP-046.
- W12: `IMP-102` — provider-evidenced follow-up delivery FSM; `IMP-103` —
  materialized event-driven policy continuation with pre-send fact recheck.

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
  `IMP-084/085` still require a current-base port, unified tests, MySQL proof
  and deploy.
- The W6-era untracked stock-policy tests are requirements to port onto current
  main, not production code (`F-CAT-004`, `IMP-084/086`).
- The assisted-checkout worktree's 390px breakpoint change is uncommitted and
  has no acceptance evidence; it is not counted as done.
- Dirty Meta/ingress worktree changes are based on an older runtime and are not
  evidence against current `instagram_login`; see source matrix.
- Dirty `codex/ig-followup-policies` contains unique requirements now preserved
  as `IMP-102/103` and `IMPR-FUP-014/015`, but its old-base code and conflicting
  migration `0131` must not be cherry-picked wholesale.

## Known test baseline

The full management suite is currently green on SQLite: 2675 tests, 3 skipped.
`F-TEST-002` / `IMP-094` remain open because a separately provisioned disposable
MariaDB test database is still unavailable; production is read-only evidence,
not a test target.
