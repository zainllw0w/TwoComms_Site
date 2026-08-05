# 12_SOURCE_RECONCILIATION — main, ветки, worktree и WIP

Проверка дополнена 2026-08-05. Статус `IN MAIN` означает, что результат уже
доступен из текущего `main`; `SUPERSEDED` означает, что перенос патча откатил
бы более новую реализацию; `BRANCH-ONLY` означает сохранённый, но не deployed
код; `WIP` — незакоммиченная работа, не имеющая статуса реализации.

| Источник | Фактическое содержимое | Статус / действие |
|---|---|---|
| `codex/ig-bot-w1-data-safety`, W2/W3/W4/W4C/W4D | safety, ingress, buyer truth, model dialogue, echo/media | IN MAIN; отражено IMP-001…024/063…076 |
| `.claude/worktrees/ig-bot-w1` | old W6 arbiter/FSM/journal + untracked stock-policy tests | Arbiter/FSM/journal IN MAIN via `34d1e165`; stock requirements recorded as F-CAT-004 and IMP-084/086; do not copy old base |
| `codex/ig-bot-w4-completion` | alert implementation commit `31f8151f`; dirty paginator | alert commit is branch source already recorded; paginator is SUPERSEDED by W7 `bca7e4e2` and must not be cherry-picked |
| `codex/ig-followup-policies` worktree | dirty old-base event/claim/objection code plus unique delivery-FSM and materialized-event requirements | Existing W4B functionality is IN MAIN; delivery and event continuation were reimplemented fresh as IMP-102/103 and IMPR-FUP-014/015. Stale code/migration `0131` must not be cherry-picked wholesale |
| `codex/ig-followup-delivery-fsm` | current-base delivery states, lease/receipt recovery, ambiguous review and finalization race guards | IN MAIN and production through `0d4d38c0`/`0e9e9ba5`/`4cb86743`/`414e639e`; migration `0141` applied, IMP-102 closed |
| `codex/ig-followup-event-continuation` | materialized event key/payload/time, absolute policy offsets, invoice/restock boundary recheck and continuation API | IN MAIN and production through `4dfff3a2`/`35d3bd93`; migration `0143` applied, IMP-103/IMPR-FUP-015 closed |
| `codex/ig-bot-variant-pricing` | pricing/follow-up branch and dirty old-base diff | IMP-080 and W4B are IN MAIN; no additional unique deployed requirement found |
| `codex/ig-bot-imp058-funnel-analytics` | durable funnel event/drop-off analytics, production timestamp regression fix, tests and migration `0133` | IN MAIN and deployed as `274c2c61`/`79882368`/`92d46c5a`; do not resurrect the pre-fix dirty diff |
| `codex/ig-bot-imp058-funnel-analytics` (IMP-089 continuation) | bounded superseded-invoice lifecycle, migration `0134`, legacy materialization and polling recovery | IN MAIN and deployed as `280c07e8`; 104 focused tests and production check-only proof; no historical lifecycle rows existed to exercise live polling |
| `codex/ig-order-fulfillment-links` `20dd44b2` | searchable order assignment drawer | Semantics IN MAIN via W7; old commit is not a safe cherry-pick |
| local `codex/instagram-assisted-checkout` | five historical product-reselection commits `61ad2cb8`, `a8ccfa63`, `468fe2ba`, `e9d982df`, `dc9889c3` | PRESERVED SOURCE; `IMP-081` was reimplemented in current main as `bf4e0d80`/`674d6858`/`3678ddf4`; remaining commits are requirements/source, not safe cherry-picks |
| `codex/ig-bot-imp028-prompt` | price-aware graph/candidate slice plus exact variant-specific prompt size binding | IN MAIN / production through `e44d1440`/`0ad694bc`; F-CAT-007 fixed, IMP-082/083 remain PARTIAL only for explicit runtime/topology/stale-binding residuals |
| `codex/ig-commercial-reconcile-fix` | F-PAY-015 superseded review ownership/backfill fix | IN MAIN and production as `93ae8684`; MySQL reconcile, client 59 and daemon heartbeat verified |
| assisted-checkout dirty CSS/test | mobile breakpoint 390px | WIP only; not counted and not integrated |
| `codex/ig-refresh-dedup` / `codex/instagram-login-runtime` | old refresh/runtime history | IN MAIN through `7fe26280` and later main commits; no extra branch closure |
| `codex/ig-crm-master-audit` dirty worktree | Meta host/token/webhook/account-mode patch on old Facebook-Login base | WIP/SUPERSEDED for current runtime; preserve source branch, do not infer production status; Meta contract remains IMP-041/061 and related findings |
| current `main` price release | configuration-specific prices, option propagation and fail-closed speech/checkout parity | IN MAIN and production through `1f5dcb70`/`7fdbe613`/`1f8cead2`; IMP-104, F-CAT-008/009 and IMPR-CAT-007 closed |
| current `main` live visuals | typed provider-aware sender action result and redacted delivery logging | IN MAIN and production through `13bedf8f`; 19 regression tests; mapped to operational sender observability |
| current main code slice | delivery marker rollback, tagged-send rollback, pooled Gemini cooldown | IN MAIN and deployed as `6b86e103`; findings F-CORE-018/F-AI-017; IMP-097 |
| `pre-instagram-audit-consolidation-2026-08-03` stash | pre-consolidation local snapshot | ARCHIVE only; no unique audit IDs after comparison |
| `codex/ig-refresh-dedup` stash / old detached worktrees | inbox refresh experiments | Historical/superseded; no unique current audit IDs |

## Branch uniqueness rule

Only patch-unique code is considered for integration. A branch's commit message,
dirty file list or agent report is not evidence of production. For closure, the
task must exist in current `main`, pass its focused/regression gates, be pulled on
the server, and have a deployed SHA in `09_DEPLOYMENT_LOG.md`.

## W9 preservation and price guard (2026-08-04)

The remote assisted-checkout branch is only the historical ancestor; it has no
W9 code commits. The sole source of IMP-081…085 is now protected by remote ref
`codex/ig-w9-local-preservation-20260804` at `bdbabdc9`; do not delete that ref
before a verified port lands in `main`. Its code cannot be
cherry-picked: the later migrations are based on `management.0127`, while
current `main` is newer.

The `IMP-082/083` port was rebuilt rather than cherry-picked. Deployed graph
pricing does not read `Product.final_price`: product 110 is exact 1450 for its
only thermo variant and product 91 retains the 800–950 fit range. Duplicate and
incompatible option paths fail closed. `e44d1440`/`0ad694bc` also removed the
old prompt catalog's product-wide size fallback: product 110 now exposes only
oversize XS/M for variant 81. Durable selection before Gemini remains an
explicit IMP-083/087 residual; F-CAT-007 itself is fixed/verified.

## Follow-up worktree boundary (2026-08-05)

The dirty `codex/ig-followup-policies` worktree was not redundant: it preserved
four unique requirements. `IMP-102`/`IMPR-FUP-014` are now closed by a fresh
current-base implementation through `414e639e`, migration `0141`, with
provider-evidenced delivery, lease/receipt recovery and audited ambiguous
resolution. The former `IMP-103`/`IMPR-FUP-015` source backlog is now closed by
the current-base implementation in `4dfff3a2`/`35d3bd93`; stale old-base code
and migration `0131` remain non-importable.

The old branch itself must not be cherry-picked wholesale. It is based on an
old runtime and carries migration `0131`, which conflicts with current history;
the compatible implementation is already in current `main` with migration
`0143`.

## Reconciliation result

All known sources are represented locally: completed work is in `08_COMPLETION_LOG`
and `07`, branch-only work is in `10`/this matrix and `07`, detailed findings are
in `03`, detailed improvements are in `05`, and `07` contains an individual
checkbox for every `F-*` and `IMPR-*`. The next checkpoint is unambiguous in `00`.
