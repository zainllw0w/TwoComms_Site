# 09_DEPLOYMENT_LOG — production evidence

Production host: `195.191.25.63`, path
`/home/qlknpodo/TWC/TwoComms_Site/twocomms`, branch `main`, database
`qlknpodo_MySQL_DB` (MariaDB/MySQL). Secrets are intentionally omitted.

## Current production checkpoint (2026-08-05)

`origin/main`, local `main` and production are synchronized at
`13bedf8f059178eaafbb578523882e0154f69155`. The server pull was fast-forward
only; tracked files are clean (existing untracked operational logs/scripts were
preserved). Migration `management.0143_igfollowuptask_event_continuation` is
applied. `manage.py check`, migration drift, static/compression and the focused
254-test event/FSM/checkout/restock gate plus authoritative-price/live-visual
gates passed. `run_instagram_bot --ensure` reports one
daemon, `running=True`, `alive=True`, provider `instagram_login`, fresh
heartbeat, empty `last_error` and zero pending reply/notification queues.

The deployed slices are `IMP-103` (commits `4dfff3a2`, `35d3bd93`), `IMP-104`
(`1f5dcb70`, `7fdbe613`, `1f8cead2`) and sender-action observability
(`13bedf8f`).

## IMP-102 durable follow-up delivery FSM deploy (2026-08-05)

Коммиты `0d4d38c0`, `0e9e9ba5`, `4cb86743` и `414e639e` опубликованы в
`origin/main` и fast-forwarded на production. Применена migration
`management.0141_igfollowuptask_delivery_fsm`. Локально прошли 23/23 focused и
160/160 expanded regression tests, Django check, migration drift, compileall и
`git diff --check`.

Production HEAD:
`414e639eced30a01ff2c5553b08605099465478c`. `status_snapshot()` подтвердил
`is_enabled=True`, `state='running'`, `running=True`, `daemon_online=True`,
`alive=True`, `provider_transport='instagram_login'`, `last_error=''`; daemon
ровно один. Read-only delivery audit: `processing=[]`, `ambiguous=[]`,
`sent_without_message=[]`, `delivery_reviews=[]`.

## F-CAT-007 variant-specific prompt parity deploy (2026-08-05)

`e44d1440` bound catalog sizes to exact `variant + fit`; `0ad694bc` separated an
authoritative empty size contract from absence of a variant-specific source.
Both commits are in `origin/main` and production. Product 110 now enters the
bot prompt as `variant_id=81`, thermo green, exact 1450 грн, oversize sizes
XS/M; the false product-wide `XS/S/M/L/XL/XXL` row is absent.

Verification: 188 focused tests and the full management suite 2675 passed
(3 skipped); Django check, migration drift, compileall and diff check passed.
Final production runtime on `0ad694bc`: one daemon, `running=True`,
`alive=True`, provider `instagram_login`, heartbeat 0.1 s, `last_error=''`,
pending replies/notifications = `0/0`.

## IMP-082/083 typed graph/ranker historical foundation deploy (2026-08-05)

`29684475` was pushed to `main` and fast-forwarded on production. `migrate`
reported no pending migrations; `manage.py check`, migration drift and scoped
compileall passed. `tmp/restart.txt` caused the old daemon to release its lock;
`run_instagram_bot --ensure` spawned one daemon on the deployed code.

Production MariaDB read-only proof built graph digest
`38f2c7df99c9c042c179bc96e0736185b03cfb1f29381722b96c8ce41b7a7b8e`:
product 91 has exact fit prices 800/950 грн; product 110 has only thermo
`variant_id=81` at exact 1450 грн. Hard `color=termo-zelena`, `fit=oversize`,
`size=M` resolves one candidate; `size=L` resolves none. Final runtime:
one daemon, `running=True`, `alive=True`, `instagram_login`, heartbeat 0.5 s,
`last_error=''`, active reply/notification/analysis queues zero. Server tracked
files are clean; unrelated untracked operational files remain untouched.

## F-PAY-015 daemon reconciliation deploy (2026-08-05)

`93ae8684` was pushed to `main` and fast-forwarded on production. `migrate`
reported no pending migrations, `manage.py check` passed, and
`reconcile_ig_commercial_episodes --passes 3` returned
`deals=0, reviews=0, attributions=0`. Static collection, compression, playbook
seed and bounded payment backstop completed; the backstop processed zero
projections/orders. After `tmp/restart.txt`, `run_instagram_bot --ensure`
spawned the new daemon.

Final production evidence: server HEAD `93ae8684`; `running=True`, `alive=True`,
state `running`, provider `instagram_login`, heartbeat age 1.0 second,
`last_error=''`, pending replies/notifications/analysis = `0/0/0`. Client `59`
has separate terminal episodes `2`, `3`, `7`; episodes `2` and `7` are
`lost / superseded_duplicate_payment_review`, episode `3` is fulfilled, and
`current_commercial_episode_id` is null.

## IMP-094 deployment checkpoint (2026-08-04)

`15147ded` was fast-forwarded to `main` and pulled on production. `manage.py
check` and `makemigrations --check --dry-run` passed. Touching
`tmp/restart.txt` stopped the old daemon as designed, but the scheduled
watchdog did not relaunch it promptly; the standard singleton-safe
`run_instagram_bot --ensure` restored the worker. Final `status_snapshot()`:
`is_enabled=True`, `state='running'`, `running=True`, `alive=True`, transport
`instagram_login`, `last_error=''`. No production database was used for tests;
the disposable MariaDB gate in IMP-094 remains open.

## IMP-077 / F-OPS-009 deployment checkpoint (2026-08-04)

`221cf37d` was rebased on the then-current `main`, fast-forwarded to production
with `git pull --ff-only`, and introduced no migrations. Server `manage.py
check` passed; `run_instagram_bot --ensure` reported `daemon alive — ok`.
`status_snapshot()` then confirmed `state='running'`, `running=True`,
`alive=True`, `provider_transport='instagram_login'`, empty `last_error` and
`notification_pending=notification_failed=notification_unknown=notification_dead_letter=0`.
The server contains unrelated untracked operational files; no tracked file was
overwritten outside the fast-forward.

| Date | SHA | Verification | Runtime |
|---|---|---|---|
| 2026-08-03 | `2a89d860` | payment backstop/contract | daemon online |
| 2026-08-03 | `cd070cba` | 9 policies/25 steps, policy tests | `instagram_login` |
| 2026-08-03 | `efc0ee10` / `4ba4212d` | fulfillment + MySQL migration | last_error empty |
| 2026-08-03 | `d0098d0b` | migration 0132, objection tests, InnoDB tables | daemon online |
| 2026-08-03 | `65bbde3e` | IMP-057 docs checkpoint | heartbeat observed |
| 2026-08-03 | `6b86e103` | check, migration drift, compileall, 45 IG tests | `enabled=True`, `transport=instagram_login`, `last_error=''` |
| 2026-08-03 | `afd16725` | audit source reconciliation and canonical docs | docs-only; runtime remains online |
| 2026-08-03 | `59f5a67b` | final validation report included and deployed | docs-only; runtime remains online |
| 2026-08-03 | `c409f7a3` | canonical checkbox plan, registers and source reconciliation; server pull, Django check, migration-drift check and restart | `running`; daemon online; `instagram_login`; no recorded error |
| 2026-08-03 | `92d46c5a` | migration `0133`; check/migration drift/collectstatic/compress; backfill 5; silence scan 96; raw-event reconciliation | `running`; heartbeat fresh; `instagram_login`; `last_error=''` |
| 2026-08-03 | `280c07e8` | migration `0134`; 104 payment/lifecycle tests; superseded invoice polling and check-only proof | `running`; `last_error=''` |
| 2026-08-03 | `6883ac2c` | final IMP-089 code/doc checkpoint; server pull, migrate/check, check-only and runtime verification | `running`; heartbeat 0.6s; `last_error=''` |
| 2026-08-03 | `e04c1c24` | final audit evidence checkpoint; docs-only fast-forward | runtime unchanged; `running`; `last_error=''` |
| 2026-08-04 | `15147ded` | IMP-094 SQLite gate stabilization; production check/migration-drift; daemon recovery | `running`; `alive=True`; `instagram_login`; `last_error=''` |
| 2026-08-04 | `221cf37d` | IMP-077 terminal monitor/key/dedupe completion; focused 75 tests, production check and daemon ensure | `running`; `alive=True`; terminal outbox `0/0` |
| 2026-08-05 | `93ae8684` | F-PAY-015; 134 local tests, MySQL reconcile x3, static/compress, payment backstop, restart | `running`; `alive=True`; `instagram_login`; heartbeat 1.0s; queues `0/0/0` |
| 2026-08-05 | `29684475` | IMP-082/083 partial; 31/230/2672/202 local gates, MySQL graph 91=800/950 and 110=1450, hard incompatible size rejected | one daemon; `running`; `alive=True`; heartbeat 0.5s; queues `0/0/0` |
| 2026-08-05 | `e44d1440` / `0ad694bc` | F-CAT-007 fixed; 188 focused, 2675 full suite, exact variant+fit prompt price/size contract | one daemon; `running`; `alive=True`; heartbeat 0.1s; reply/notification queues `0/0` |
| 2026-08-05 | `0d4d38c0` / `0e9e9ba5` / `4cb86743` / `414e639e` | IMP-102/F-FUP-013; migration `0141`, 23 focused / 160 expanded, check/drift/compileall/diff | one daemon; `running`; `alive=True`; `instagram_login`; delivery queues empty |

For `6b86e103`, server `git pull --ff-only` completed, `manage.py check` returned
no issues, `makemigrations --check --dry-run` returned `No changes detected`,
and `tmp/restart.txt` was touched. Server HEAD equals the SHA above. The server
worktree has unrelated untracked operational files; no tracked production file
was overwritten outside the requested commit.

For the docs checkpoint `afd16725`, server `git pull --ff-only` completed and
server HEAD was verified as `afd16725f10a07b18406767061c016eb4e0aaefd`. Existing
production DB proof after the pull: `enabled=True`, `transport=instagram_login`,
heartbeat age about 1 second, `last_error=''`. The production user cannot create
the Django test database (`1044 Access denied`), so the focused test command was
not executed on the live DB; the 45/45 result remains the prior isolated gate.

The final validation report commit `59f5a67b` was then pulled with `--ff-only`;
server HEAD was verified as `59f5a67ba7a4e0b89881141aadd966411832c7ca`.

The canonical-plan commit `c409f7a3` was subsequently pushed and pulled with
`git pull --ff-only origin main`; server HEAD was verified as
`c409f7a32d84e02ae9a92d93ba27bb0e176980c4`. `python manage.py check` returned
no issues, `python manage.py makemigrations --check --dry-run` returned `No
changes detected`, and `tmp/restart.txt` was touched to request a Passenger
restart. The runtime evidence was queried through the current
`management.services.instagram_bot.status_snapshot()` API: `is_enabled=True`,
`state='running'`, `alive=True`, `running=True`,
`provider_transport='instagram_login'`, database and daemon heartbeat ages
`0.0` seconds, and `last_error=''`.

For IMP-058, `origin/main` was advanced through `274c2c61`, `79882368` and
`92d46c5a`; the server pulled `92d46c5a` fast-forward and applied
`management.0133_ig_funnel_step_analytics` on MariaDB. Production commands
reported `{'candidates': 5, 'created': 5, 'applied': True}` for canonical
backfill and `{'scanned': 100, 'matched': 96, 'applied': True}` for deterministic
silence facts. The final MySQL/API check reported 197
`IgFunnelStepEvent` rows, 96 `IgFunnelDropOff` rows, 17 event types, and
`status_snapshot()` returned `state='running'`, `daemon_online=True`, a fresh
heartbeat and empty `last_error`.

For IMP-089, `git pull --ff-only` advanced production through `280c07e8` and
applied `management.0134_ig_deal_invoice_lifecycle` on MariaDB. The bounded
check-only command reported `projections=0 provider_invoices=0
superseded_invoices=0 orders=0`; the lifecycle table had zero rows because no
historical superseded invoice IDs exist on this production dataset. The daemon
briefly reported a transient worker error during restart and recovered to
`running=True` with `last_error=''`; no customer messages were sent.

The final consolidation commit `6883ac2c` was then pulled fast-forward. The
server confirmed migration `0134` as applied, `poll_ig_deal_payments
--check-only --limit 50` returned zero candidates, lifecycle rows remained 0,
and `status_snapshot()` reported `is_enabled=True`, `state='running'`,
daemon_online=True`, heartbeat age about 0.6 seconds, transport
`instagram_login`, and empty `last_error`.
