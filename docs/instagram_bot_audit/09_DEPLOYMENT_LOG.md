# 09_DEPLOYMENT_LOG — production evidence

Production host: `195.191.25.63`, path
`/home/qlknpodo/TWC/TwoComms_Site/twocomms`, branch `main`, database
`qlknpodo_MySQL_DB` (MariaDB/MySQL). Secrets are intentionally omitted.

## IMP-094 deployment checkpoint (2026-08-04)

`15147ded` was fast-forwarded to `main` and pulled on production. `manage.py
check` and `makemigrations --check --dry-run` passed. Touching
`tmp/restart.txt` stopped the old daemon as designed, but the scheduled
watchdog did not relaunch it promptly; the standard singleton-safe
`run_instagram_bot --ensure` restored the worker. Final `status_snapshot()`:
`is_enabled=True`, `state='running'`, `running=True`, `alive=True`, transport
`instagram_login`, `last_error=''`. No production database was used for tests;
the disposable MariaDB gate in IMP-094 remains open.

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
