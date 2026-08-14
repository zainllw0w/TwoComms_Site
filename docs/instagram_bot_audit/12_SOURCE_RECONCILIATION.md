# 12_SOURCE_RECONCILIATION — main, ветки, worktree и WIP

Проверка дополнена 2026-08-10. Статус `IN MAIN` означает, что результат уже
доступен из текущего `main`; `SUPERSEDED` означает, что перенос патча откатил
бы более новую реализацию; `BRANCH-ONLY` означает сохранённый, но не deployed
код; `WIP` — незакоммиченная работа, не имеющая статуса реализации.

| Источник | Фактическое содержимое | Статус / действие |
|---|---|---|
| `codex/ig-bot-w1-data-safety`, W2/W3/W4/W4C/W4D | safety, ingress, buyer truth, model dialogue, echo/media | IN MAIN; отражено IMP-001…024/063…076 |
| `.claude/worktrees/ig-bot-w1` | old W6 arbiter/FSM/journal + untracked stock-policy tests | Arbiter/FSM/journal IN MAIN via `34d1e165`; stock requirements recorded as F-CAT-004 and IMP-084/086; do not copy old base |
| `codex/ig-bot-w4-completion` | alert implementation commit `31f8151f`; dirty paginator | alert commit is branch source already recorded; paginator is SUPERSEDED by W7 `bca7e4e2` and must not be cherry-picked |
| root `main` worktree | modified `twocomms/management/tests_ig_commerce_state.py` with receipt/reclaim regressions | RELEVANT WIP, not docs scope; preserve and compare with durable-reply worktree before any integration |
| `codex/ig-commerce-durable-state` worktree | modified `services/ig_commerce_state.py`, `services/instagram_bot.py`, `tests_ig_commerce_state.py`; new `services/ig_commerce_replies.py`, `tests_ig_commerce_delivery.py` | Narrow `IMP-087.A` selectively ported/reviewed into `main` as `7ad632de` plus follow-up `ade00668`; production migration `0154` and runtime proof are recorded in `08/09`. Preserve any remaining root-worktree WIP separately; full `IMP-087` remains PARTIAL. |
| `codex/ig-followup-policies` worktree | dirty old-base event/claim/objection code plus unique delivery-FSM and materialized-event requirements | Existing W4B functionality is IN MAIN; delivery and event continuation were reimplemented fresh as IMP-102/103 and IMPR-FUP-014/015. Stale code/migration `0131` must not be cherry-picked wholesale |
| `codex/ig-followup-delivery-fsm` | current-base delivery states, lease/receipt recovery, ambiguous review and finalization race guards | IN MAIN and production through `0d4d38c0`/`0e9e9ba5`/`4cb86743`/`414e639e`; migration `0141` applied, IMP-102 closed |
| `codex/ig-followup-event-continuation` | materialized event key/payload/time, absolute policy offsets, invoice/restock boundary recheck and continuation API | IN MAIN and production through `4dfff3a2`/`35d3bd93`; migration `0143` applied, IMP-103/IMPR-FUP-015 closed |
| `codex/ig-bot-variant-pricing` | pricing/follow-up branch and dirty old-base diff | IMP-080 and W4B are IN MAIN; no additional unique deployed requirement found |
| `codex/ig-bot-imp058-funnel-analytics` | durable funnel event/drop-off analytics, production timestamp regression fix, tests and migration `0133` | IN MAIN and deployed as `274c2c61`/`79882368`/`92d46c5a`; do not resurrect the pre-fix dirty diff |
| `codex/ig-bot-imp058-funnel-analytics` (IMP-089 continuation) | bounded superseded-invoice lifecycle, migration `0134`, legacy materialization and polling recovery | IN MAIN and deployed as `280c07e8`; 104 focused tests and production check-only proof; no historical lifecycle rows existed to exercise live polling |
| `codex/ig-order-fulfillment-links` `20dd44b2` | searchable order assignment drawer | Semantics IN MAIN via W7; old commit is not a safe cherry-pick |
| local `codex/instagram-assisted-checkout` | five historical product-reselection commits `61ad2cb8`, `a8ccfa63`, `468fe2ba`, `e9d982df`, `dc9889c3` | PRESERVED SOURCE; `IMP-081` was reimplemented in current main as `bf4e0d80`/`674d6858`/`3678ddf4`; availability foundation from `e9d982df` was ported as `17f5b672`; `dc9889c3` remains parser source for `IMP-085`; no wholesale cherry-pick |
| `codex/ig-bot-imp028-prompt` | price-aware graph/candidate slice plus exact variant-specific prompt size binding | IN MAIN / production through `e44d1440`/`0ad694bc`; F-CAT-007 fixed, IMP-082/083 remain PARTIAL only for explicit runtime/topology/stale-binding residuals |
| current `main` Implement2 W1.6 slice | typed Gemini JSON response controls, fail-closed legacy adapter, authority/evidence gates, hard-stage runtime guard and migrations `0151`/`0152` | IN MAIN and production as `130cd920`; F-AI-010, F-AI-011 and F-CTX-003 closed after 240/240 tests and read-only production parser/prompt/health proof |
| current `main` Implement2 W1.7 slice | historical attachment provenance/ownership, live-byte claim/reuse, media phase/error telemetry before provider, and historical payment-vision network guard | IN MAIN and production: `214ae4b9` is reachable through merge `b9bab236`; W1.7 follow-up adds the guard/tests. Migration `0153` applied. Production has only historical metadata-only rows and no post-migration live analysis, so `F-AI-018` remains under `IMP-044` |
| `codex/ig-commercial-reconcile-fix` | F-PAY-015 superseded review ownership/backfill fix | IN MAIN and production as `93ae8684`; MySQL reconcile, client 59 and daemon heartbeat verified |
| assisted-checkout dirty CSS/test | mobile breakpoint 390px | WIP only; not counted and not integrated |
| `codex/management-bot-statistics-visuals` | modified `bot_views.py`, `services/ig_funnel_analytics.py`, `templates/management/bot.html`, `tests_ig_clients_ui.py`, `tests_ig_funnel_analytics.py`; untracked plan and `tests_ig_stats_visuals.py`; volatile tracked diff, inspect with fresh `git diff --stat` | CODE WIP for `IMP-093`, uncommitted/unpushed/undeployed. Review event-time metric semantics, rebase on current main and preserve patch-unique tests/UI; do not rewrite from the plan or mark complete. |
| `codex/ig-refresh-dedup` / `codex/instagram-login-runtime` | old refresh/runtime history | IN MAIN through `7fe26280` and later main commits; no extra branch closure |
| `codex/ig-crm-master-audit` dirty worktree | Meta host/token/webhook/account-mode patch on old Facebook-Login base | WIP/SUPERSEDED for current runtime; preserve source branch, do not infer production status; Meta contract remains IMP-041/061 and related findings |
| `codex/ig-lease-docs` dirty worktree | older lease/reclaim documentation | SUPERSEDED by current `00/03/07/13/14`; do not use as status authority |
| current `main` price release | configuration-specific prices, option propagation and fail-closed speech/checkout parity | IN MAIN and production through `1f5dcb70`/`7fdbe613`/`1f8cead2`; IMP-104, F-CAT-008/009 and IMPR-CAT-007 closed |
| current `main` live visuals | typed provider-aware sender action result, redacted delivery logging, bounded typing window and send-boundary permission cleanup | IN MAIN and production through `13bedf8f`/`d3e2c51b`/`0d471ebe`/`c0f9fd1f`/`d84ca10d`; focused sender suite 63/63; mapped to operational sender observability |
| dirty `codex-management-bot-live-visuals` worktree | detached older-base visual selection plan conflict (`AA docs/plans/2026-08-05-management-bot-visual-selection-final.md`) | DIRTY SOURCE only. Current live-visual code is already in main; resolve/preserve any unique planning evidence manually, never cherry-pick or treat the conflicted worktree as newer code. |
| `codex/management-bot-visual-refinement` | four UI code commits and one docs shortlist commit | SUPERSEDED branch base: patch-ids are already in `main` as `d7f10477`/`8a2f9ee1`/`233297b3`/`6e05c6b2`/`e262c0c4`; current-main UI tests 135/135, no cherry-pick |
| current main code slice | delivery marker rollback, tagged-send rollback, pooled Gemini cooldown | IN MAIN and deployed as `6b86e103`; findings F-CORE-018/F-AI-017; IMP-097 |
| current `main` warehouse slice | exact allocation reservation, paid commit without physical warehouse decrement, fulfillment/write-off/reversal links, late-payment overbook state, revision/stale-callback safety and paid commitment capacity guard | IN MAIN and production through `a7857ada`; migrations `0144`/`0145` applied; F-CAT-011 fixed, `IMP-084/086` remain PARTIAL for readiness/alternatives, manager-review UI and disposable MariaDB proof |
| current `main` commerce-turn slice | bounded parser facts, trusted URL product pinning and prompt turn-note integration | IN MAIN and production as `1849441d`; full local gate 2877 OK; `IMP-085` remains PARTIAL because durable session/reducer, candidate anchoring and production-like DB proof are open |
| current `main` prepayment authority slice | human/operator offer + exact customer confirmation, untrusted/multi-amount fail-closed gate | IN MAIN and production as `7440bb98`; F-PAY-010 verified by 41 focused tests and rollback-only MariaDB proof; IMP-098 remains open for unrelated orphan findings |
| current `main` reduced-motion test repair | semantic assertion for both inbox refresh animations inside reduced-motion rule | IN MAIN and production as `dd93f9f3`; F-TEST-004 fixed, inbox/UI 188/188 and full 2897 OK; IMP-094 remains open for disposable MariaDB proof |
| `codex/ig-w22-t41-sanitizer-followup` | disposable MariaDB lifecycle and checkout-concurrency runner slices `d054edf0e`…`8f4459f68`, including strict failure-evidence allowlists | IN MAIN and production through the rebased seven-commit sequence at `9ed640b06c`; exact-main CI `31762702125` proves the narrow lifecycle/checkout gate on MariaDB 11.4.12 with generated schemas and verified cleanup, and the approved SSH `git pull` plus read-only runtime proof are recorded in `09_DEPLOYMENT_LOG.md`. The remaining append-only `TransactionTestCase` classes need individual MariaDB treatment; do not globally weaken triggers. |
| `codex/ig-follow-lifecycle-truth` | authoritative order lifecycle/delivery truth, strict receipt persistence and migration `0156` | IN MAIN and production at `8d8c5d05`; exact MariaDB schema/runtime/no-send proof is recorded in `08`/`09`/`14`. The full `IMP-087` and `IMP-094` scopes remain partial/open; pre-existing storefront migration drift is a separate deployment-gate follow-up. |
| current `main` lease/reclaim and late-payment slice | safe timeout invariant, provider payment timestamp and reallocated-capacity manager review | IN MAIN and production as `18ddc636`/`b23dfeed`; F-CORE-003 closed and F-CAT-011 evidence extended; MariaDB concurrency proof remains open |
| current `main` episode presentation slice | current payment/shipment/filter are separated from lifetime buyer history | IN MAIN and production as `fbe33a68`; F-STATE-011 / IMP-105 closed; this is presentation truth, not durable commerce-session completion |
| `pre-instagram-audit-consolidation-2026-08-03` stash | pre-consolidation local snapshot | ARCHIVE only; no unique audit IDs after comparison |
| `codex/instagram-assisted-checkout-pre-split` | historical branch/ref before assisted-checkout split | HISTORICAL SOURCE only; compare patch-unique requirements against current main and `codex/instagram-assisted-checkout`, never cherry-pick wholesale. |
| `codex/ig-refresh-dedup` stash / old detached worktrees | inbox refresh experiments | Historical/superseded; no unique current audit IDs |

## Branch uniqueness rule

Only patch-unique code is considered for integration. A branch's commit message,
dirty file list or agent report is not evidence of production. For closure, the
task must exist in current `main`, pass its focused/regression gates, be pulled on
the server, and have a deployed SHA in `09_DEPLOYMENT_LOG.md`.

## W9 preservation and price guard (2026-08-04)

The remote assisted-checkout branch is only the historical ancestor; it has no
W9 code commits. The remaining source for `IMP-085` and unported W9 requirements
is protected by remote ref
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
the compatible implementation is already in current `main` with migrations
`0143`, `0144` and `0145`.

## Production/source starting checkpoint for Implement2 (2026-08-07)

Local `main`, `origin/main` and production are synchronized on
`19f5ef70f20e1b3d5da5975786359fe8c7e06df4`; migrations through
`management.0146` are applied. Runtime code checkpoint `98bb160e` and previous
`fbe33a68`, `18ddc636`, `b23dfeed`, `1849441d`, `90fdd0ec` checkpoints are
ancestors, not competing bases. Fresh read-only status found new `F-AI-018`:
analysis job `292`, client `310`, `trigger=manager_message`, attempts 5,
`stale_lease_retry_exhausted`. It is current production evidence, not WIP
completion.

## Reconciliation result

All known sources are represented locally: completed work is in
`08_COMPLETION_LOG` and `07`, branch-only/WIP work is in `10`/this matrix/`13`,
detailed findings are in `03`, improvements are in `05`, and `07` contains an
individual checkbox for every `F-*` and `IMPR-*`. The next execution order is
unambiguous in `14`, reached through `00`.

Fresh 2026-08-07 validation: the local canonical folder contains **343 unique
`F-*`/`IMP-*`/`IMPR-*` IDs** (187 + 105 + 51).
Every ID reachable from historical audit refs is present in that set; the
all-ref minus local comparison is empty. Existing stashes, worktrees and
unreachable-object inventory were preserved and do not replace the canonical
status in local `main`.
