# 12_SOURCE_RECONCILIATION — main, ветки, worktree и WIP

Проверка выполнена 2026-08-03. Статус `IN MAIN` означает, что результат уже
доступен из текущего `main`; `SUPERSEDED` означает, что перенос патча откатил
бы более новую реализацию; `BRANCH-ONLY` означает сохранённый, но не deployed
код; `WIP` — незакоммиченная работа, не имеющая статуса реализации.

| Источник | Фактическое содержимое | Статус / действие |
|---|---|---|
| `codex/ig-bot-w1-data-safety`, W2/W3/W4/W4C/W4D | safety, ingress, buyer truth, model dialogue, echo/media | IN MAIN; отражено IMP-001…024/063…076 |
| `.claude/worktrees/ig-bot-w1` | old W6 arbiter/FSM/journal + untracked stock-policy tests | Arbiter/FSM/journal IN MAIN via `34d1e165`; stock requirements recorded as F-CAT-004 and IMP-084/086; do not copy old base |
| `codex/ig-bot-w4-completion` | alert implementation commit `31f8151f`; dirty paginator | alert commit is branch source already recorded; paginator is SUPERSEDED by W7 `bca7e4e2` and must not be cherry-picked |
| `codex/ig-followup-policies` worktree | dirty W4B event/claim/objection files on old base | functionality IN MAIN via `c00c8c5a`/`d0098d0b`; old diff would delete newer migrations; do not cherry-pick |
| `codex/ig-bot-variant-pricing` | pricing/follow-up branch and dirty old-base diff | IMP-080 and W4B are IN MAIN; no additional unique deployed requirement found |
| `codex/ig-bot-imp058-funnel-analytics` | durable funnel event/drop-off analytics, production timestamp regression fix, tests and migration `0133` | IN MAIN and deployed as `274c2c61`/`79882368`/`92d46c5a`; do not resurrect the pre-fix dirty diff |
| `codex/ig-bot-imp058-funnel-analytics` (IMP-089 continuation) | bounded superseded-invoice lifecycle, migration `0134`, legacy materialization and polling recovery | IN MAIN and deployed as `280c07e8`; 104 focused tests and production check-only proof; no historical lifecycle rows existed to exercise live polling |
| `codex/ig-order-fulfillment-links` `20dd44b2` | searchable order assignment drawer | Semantics IN MAIN via W7; old commit is not a safe cherry-pick |
| local `codex/instagram-assisted-checkout` | five product-reselection code commits `61ad2cb8`, `a8ccfa63`, `468fe2ba`, `e9d982df`, `dc9889c3` | BRANCH-ONLY; absent from historical `origin/codex/instagram-assisted-checkout`, but preserved as remote `codex/ig-w9-local-preservation-20260804` at `bdbabdc9`. Port to current `main`, tests, MariaDB gate and deploy still required |
| assisted-checkout dirty CSS/test | mobile breakpoint 390px | WIP only; not counted and not integrated |
| `codex/ig-refresh-dedup` / `codex/instagram-login-runtime` | old refresh/runtime history | IN MAIN through `7fe26280` and later main commits; no extra branch closure |
| `codex/ig-crm-master-audit` dirty worktree | Meta host/token/webhook/account-mode patch on old Facebook-Login base | WIP/SUPERSEDED for current runtime; preserve source branch, do not infer production status; Meta contract remains IMP-041/061 and related findings |
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

During a future port, `a8ccfa63`/`468fe2ba` must not introduce
`Product.final_price` into graph/candidate pricing. That would recreate
F-CAT-003: product 110 would quote 1090 although its only real thermo variant
is 1450; product 91 must retain the 800–950 fit range. The port must consume
the current variant/fit pricing read-model, reject duplicate option paths such
as `/black/black/`, and commit trusted URL color/fit constraints into the
durable selection before Gemini.

## Reconciliation result

All known sources are represented locally: completed work is in `08_COMPLETION_LOG`
and `07`, branch-only work is in `10`/this matrix and `07`, detailed findings are
in `03`, detailed improvements are in `05`, and `07` contains an individual
checkbox for every `F-*` and `IMPR-*`. The next checkpoint is unambiguous in `00`.
