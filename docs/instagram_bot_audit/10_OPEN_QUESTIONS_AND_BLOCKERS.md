# 10_OPEN_QUESTIONS_AND_BLOCKERS — остаток без маскировки

## Implementation остаток

Канонический список и checkbox: `07_IMPLEMENTATION_PLAN.md`.

- W4B: закрыта; `IMP-058` и `IMP-089` имеют code, tests и production evidence.
- W5: `IMP-028` (full size/sales prompt protocol), `IMP-095` (white 1090 грн
  variant data with real images/rules).
- W8: `IMP-044`–`046`, `060`–`061`, `094`, `096`, `100`, `101`; partial `043`, `077`.
- W9: `IMP-081`–`088` (the first five have branch-only code, not production).
- W10: `IMP-090`–`093`.
- W11: `IMP-098` — F-CORE-003…006, F-PAY-010, F-SCORE-010 и partial-остатки
  F-SEC-004/009. F-CORE-007 уже закрыта IMP-073; F-SCORE-012 остаётся в IMP-046.

## Product/data blockers

1. Production product 110 has only the thermochromic green/oversize variant
   (`variant_id=81`, 1450 грн). The white 1090 грн variant cannot be fabricated
   without authoritative white images and fit/size rules (`F-DATA-016`).
2. Advertisement attribution has no source fields in historical payloads;
   implementation cannot invent campaign data (`IMP-043`).
3. Imported conversation role provenance is ambiguous (`F-DATA-015`), so text
   similarity is not accepted as a backfill proof (`IMP-096`).

## Branch-only / WIP blockers

- Five product-reselection commits are preserved but require rebase, unified
  tests, MySQL proof and deploy (`IMP-081…085`).
- The W6-era untracked stock-policy tests are requirements to port onto current
  main, not production code (`F-CAT-004`, `IMP-084/086`).
- The assisted-checkout worktree's 390px breakpoint change is uncommitted and
  has no acceptance evidence; it is not counted as done.
- Dirty Meta/ingress worktree changes are based on an older runtime and are not
  evidence against current `instagram_login`; see source matrix.

## Known test baseline

The full management suite has a separately recorded pre-existing failure set
(`F-TEST-002`, `IMP-094`). A focused green package is required for each slice;
no full-suite failure is silently attributed to the current checkpoint.
