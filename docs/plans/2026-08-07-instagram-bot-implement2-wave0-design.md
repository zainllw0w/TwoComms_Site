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

The compatibility policy is conservative:

- preserve current direct versions when they install cleanly on Python 3.14;
- update a direct pin only when required for Python 3.14, security, or a proven
  transitive constraint;
- pin every previously floating direct dependency;
- do not copy the current production drift into the lock without validating
  imports and focused application tests.

## Deploy Boundary

The deploy path is divided into explicit phases:

1. resolve the project and virtualenv paths;
2. install the exact lock artifact;
3. run `pip check` and exact installed-version verification;
4. only then run migrations, static collection, compression, and restart;
5. emit the deployed SHA and step evidence.

Any required dependency, verification, migration, or static-collection failure
terminates the deploy. Passenger restart and bot-daemon ensure must not run
after a failed required phase. Compression remains independently classified and
must not hide failures from earlier required phases.

The shell entry point accepts explicit path overrides for tests while retaining
the current production defaults. Subprocess tests use a temporary project and
fake commands, proving ordering and fail-closed behavior without touching a
real environment.

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

## Error Handling and Observability

- Dependency failures retain the complete install log and print a concise final
  error with the failed phase.
- Exact version drift is reported as expected versus installed distributions.
- No secret values, environment dumps, customer text, or raw provider payloads
  enter evidence artifacts.
- CI and production logs include the Git SHA, Python version, lock digest, and
  final phase status.
- A failed phase leaves the old application process running and does not touch
  the restart marker.

## Test Strategy

P0.5A follows strict red-green-refactor cycles for:

1. required dependency failure prevents every later deploy command;
2. version-verification failure prevents migrations/restart;
3. a successful gate preserves the intended command order;
4. the baseline runner works from two cwd values;
5. network-disabled tests reject an unmocked external connection;
6. generated dependency lock and direct specification are synchronized;
7. Python 3.14 clean-environment installation and application imports pass.

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

Audit registers `00`, relevant `03/05/06`, `07`, `08`, `09`, `10`, `12`, `13`,
and `14` are updated synchronously. A parent item remains partial when only its
named sub-slice is complete.

## Explicit Non-Goals

- No webhook-locking or reply-boundary behavior changes in Wave 0.
- No writes to production business rows for testing.
- No import of whole dirty historical worktrees.
- No broad dependency upgrade merely because a newer release exists.
- No synthetic Meta, Gemini, Telegram, payment, or advertising events.
