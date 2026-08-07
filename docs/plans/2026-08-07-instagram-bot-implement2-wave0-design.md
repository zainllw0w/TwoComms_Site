# Instagram Bot Implement2 Wave 0 Design

## Purpose

Wave 0 establishes a reproducible, fail-closed release boundary before any
customer-facing Instagram bot behavior changes. It closes the known deployment
ambiguity where a required dependency installation can fail while `deploy.sh`
continues into migrations and restart.

The work is split into two independently reviewable sub-slices:

1. **P0.5A:** deterministic Python 3.14 dependencies, a testable fail-closed
   deploy gate, and a cwd-independent no-network baseline runner.
2. **P0.5B:** a disposable MariaDB 11.4 runner and CI proof for migrations,
   constraints, maximum lengths, locks, rollback fixtures, and race contracts.

No feature slice begins until both gates are usable. W1.1
(`F-CORE-004` / `IMP-098.A`) is the first customer-path change after Wave 0.

## Current Evidence

- Local `main`, `origin/main`, GitHub `main`, and production are at
  `bc7a7c8522f5dd0b018bee83850b634ad198dd26`.
- Production is healthy enough to release: webhook ingress and the bot daemon
  are running, and dangerous inbound/outbox queues are empty.
- `deploy.sh` masks `pip install -r requirements.txt` failures with a
  non-fatal fallback.
- Production has 21 installed-version differences from `requirements.txt`.
- `cffi==1.17.1` repeatedly failed to build under production Python 3.14.
- Three runtime packages are not pinned: `google-analytics-data`,
  `google-auth`, and `openai`.
- Production `cryptography==46.0.6` and `PyJWT==2.12.1` have published
  advisories; fixed compatible releases are `50.0.0` and `2.13.0`.
- The existing disposable-MariaDB settings profile is fail closed, but no
  repeatable MariaDB instance/runner currently executes it.
- The focused baseline has 14 passing contract tests. In a clean worktree,
  normal `check` and migration-drift commands require an explicit non-production
  `SECRET_KEY`; copying production `.env` is neither necessary nor acceptable.

## Dependency Architecture

`twocomms/requirements.in` becomes the human-maintained list of direct runtime
dependencies. Existing dependencies are required by default. A package may be
moved to an optional group only after its import sites have an explicit,
tested feature-disabled behavior.

`twocomms/requirements.lock` becomes the generated Python 3.14/Linux install
artifact. It contains exact transitive versions and hashes. Resolution is
performed for the production interpreter/platform contract, not from whatever
packages happen to be installed on the developer machine.

`twocomms/requirements.txt` remains a compatibility entry point during the
transition and delegates to the lock artifact. CI verifies that regenerating
the lock from the direct specification produces no diff.

The release environment is fresh, not an in-place reconciliation. Exact lock
verification rejects unexpected distributions except an explicit bootstrap
allowlist for packaging tools. This prevents an old Celery/provider extra from
silently changing runtime behavior after the lock becomes authoritative.

The compatibility policy is conservative:

- preserve current direct versions when they install cleanly on Python 3.14;
- update a direct pin only when required for Python 3.14, security, or a proven
  transitive constraint;
- pin every previously floating direct dependency;
- make a runtime-imported transitive such as `PyJWT` explicit;
- do not copy the current production drift into the lock without validating
  imports and focused application tests.

## Staged Deploy Boundary

The server deploy path is divided into explicit phases:

1. acquire a deploy lock and fetch the target SHA into an isolated server
   worktree without changing the live checkout;
2. create the CPython 3.14 venv and static root at their final immutable
   versioned paths, then install from the CI-produced, manifest-verified
   wheelhouse with `--no-index --find-links` and the exact lock artifact;
3. run `pip check`, strict installed-version verification, imports, no-network
   tests, Django checks, lock-digest/source-contract validation, empty
   migration-plan proof,
   `collectstatic`, compressor build, and staged render before touching the live
   app;
4. activate the bot maintenance lease and stop the CloudLinux Passenger
   application;
5. fast-forward the live checkout, then atomically switch stable symlinks to
   immutable, already-verified release directories for the venv and static
   root, retaining the previous SHA/venv/static targets for rollback;
6. start the app/bot and run health proof;
7. emit exact SHA, lock, environment, switch, rollback, and health evidence.

Any pre-switch failure leaves the live checkout, venv, app, and bot untouched.
Any post-switch failure before a database change restores the previous
checkout/venv and restarts the previous app. Wave 0 contains no migrations and
must fail if the target introduces an unapplied migration. Every later
migration-bearing slice needs its own backup, expand/contract compatibility,
and rollback decision before this gate may apply it.

The shell entry point is a thin wrapper over a stdlib release orchestrator.
Tests use temporary live/stage directories and a fake command runner to prove
ordering, fixed command construction, atomic switch, rollback, evidence, and
CloudLinux/bot maintenance behavior without touching a real environment.

Lock regeneration and wheelhouse creation are immutable CI-only acceptance
gates using pinned `uv 0.12.2` and `git diff --exit-code`. CI publishes a
SHA256-manifested wheelhouse artifact keyed by the reviewed commit. Production
receives that artifact in a staging directory, verifies its manifest digest,
and installs only with `--no-index --find-links`; a missing or mismatched
wheelhouse fails before maintenance. Production never contacts a package index
to re-resolve dependencies and verifies the reviewed lock digest, exact target
SHA, and strict installed distribution set.

The active cPanel `VIRTUAL_ENV` path is a stable symlink. A venv is created and
verified at its final immutable versioned path, never renamed after creation;
this preserves the absolute shebangs in `bin/*`. The first Wave 0 bootstrap
fetches the target SHA and runs the target orchestrator from an isolated server
worktree with the system Python. It enables maintenance and stops Passenger
only inside that orchestrator, so no new code runs on the old environment
between bootstrap and the verified switch.

Once an owned maintenance lease is acquired, every failure before or during the
switch must release that lease and restore the old app/daemon state. A failed
stop, fast-forward, symlink switch, static build, start, or health check must
record the original error and cleanup result; a cleanup failure is independently
red. Tracked legacy deploy scripts are inventoried against server cron/operator
usage and either delegate to this orchestrator or are retired with evidence.

## Baseline Runner

A root-level runner owns the mandatory local gate. It:

- resolves paths relative to its own file rather than caller cwd;
- uses a documented Python interpreter override;
- supplies a non-production structural-check `SECRET_KEY` without reading or
  copying production secrets;
- disables external network access for the mandatory test profile;
- runs the focused stable suite, Django check, migration drift, compileall, and
  diff validation;
- writes a machine-readable evidence summary with command, interpreter,
  settings profile, DB engine, test count, skips/failures, and network policy;
- restores all mutable process state between repeated runs.

The runner must pass from both the Git root and an unrelated cwd. A pre-existing
failure is classified and fixed in its own test-first change before feature
work continues.

Wave 0 also closes the known order-dependent telephony test instead of merely
excluding it. Acceptance includes three fresh full `management` suite runs
from the documented root/app cwd values plus the shorter mandatory runner.

## Disposable MariaDB Boundary

Production MariaDB is never a test target. The MariaDB gate uses the existing
`test_settings_mariadb.py` fail-closed namespace and dedicated credentials.

The same script is usable in two environments:

- developer/agent execution against an explicitly provisioned disposable
  instance;
- GitHub Actions with a MariaDB 11.4 service container and an isolated database
  user/schema.

The gate applies the real migration graph and runs the DB-sensitive suites for
locks, uniqueness, `varchar(max_length)`, JSON/collation behavior, reclaim races,
and rollback fixtures. It always destroys the disposable schema/container state.
It refuses production-like database names or hosts through the existing settings
guard before opening a cursor.

The production verifier's database identity and maintenance guards remain
unchanged. Its rollback implementation is extracted into an always-rollback,
no-network reusable contract that the disposable MariaDB suite calls directly;
the production command continues to own live-only authorization.

## Error Handling and Observability

- Dependency failures retain the complete install log and print a concise final
  error with the failed phase.
- Exact version drift is reported as expected versus installed distributions.
- No secret values, environment dumps, customer text, or raw provider payloads
  enter evidence artifacts.
- CI and production logs include the Git SHA, Python version, lock digest, and
  final phase status.
- A pre-switch failure leaves the old application running. A post-switch
  failure records rollback state and restores the retained release before the
  application is started again.

## Test Strategy

P0.5A follows strict red-green-refactor cycles for:

1. required dependency failure prevents every later deploy command;
2. version-verification failure prevents migrations/restart;
3. a successful gate preserves the intended command order;
4. the baseline runner works from two cwd values;
5. network-disabled tests reject an unmocked external connection;
6. generated dependency lock and direct specification are synchronized;
7. Python 3.14 clean-environment installation and application imports pass on
   the x86_64 glibc 2.28 compatibility floor;
8. the order-dependent telephony failure has a root-cause regression and three
   full stable management-suite runs.

P0.5B acceptance requires:

1. MariaDB 11.4 migrations complete from an empty schema;
2. the fail-closed settings guard rejects production names/hosts;
3. DB-sensitive lock/constraint/max-length tests pass;
4. rollback fixtures leave no test rows;
5. the CI service is destroyed after the job;
6. the exact workflow run and commit SHA are recorded in the audit ledger.

## Release Protocol

Each sub-slice receives specification review and code-quality review. The
verified branch is fast-forwarded into local `main`, pushed to `origin/main`,
deployed with a fast-forward-only server pull, and checked for exact SHA,
migrations, dependency state, daemon heartbeat, queues, and persisted evidence.

Audit rows stay `PARTIAL` through the first production deploy. Only after live
proof is collected are completion marks written in a post-deploy evidence
commit, pushed, and fast-forwarded on the server so the final server SHA again
equals `origin/main`.

Audit registers `00`, relevant `03/05/06`, `07`, `08`, `09`, `10`, `12`, `13`,
and `14` are updated synchronously. A parent item remains partial when only its
named sub-slice is complete.

## Explicit Non-Goals

- No webhook-locking or reply-boundary behavior changes in Wave 0.
- No writes to production business rows for testing.
- No import of whole dirty historical worktrees.
- No broad dependency upgrade merely because a newer release exists.
- No synthetic Meta, Gemini, Telegram, payment, or advertising events.
- No retirement of legacy deploy entry points until read-only server/cron usage
  proves whether they are active; the bypass risk is recorded for its own slice.
