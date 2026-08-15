# Django 6.1 Upgrade Design

**Status:** Approved for implementation

**Goal:** Move the TwoComms project from Django 5.2.11 to stable Django 6.1 while preserving all existing application and database behavior.

## Scope

This release is a compatibility upgrade only. It includes the direct Django pin, the reproducible lockfile, dependency compatibility changes required by Django 6.1, and small source/test changes only when the upgrade exposes a real incompatibility.

The release explicitly does not enable or refactor around Django 6.1 features such as model field fetch modes, database-level `on_delete` actions, or `MAILERS`. Those changes will be audited and measured in a separate follow-up.

## Constraints

- The authoritative source is the latest `origin/main` commit.
- Existing uncommitted work in the primary checkout must remain untouched.
- The production virtualenv is Python 3.14; the lock must remain reproducible for that runtime.
- Production MariaDB is not a test fixture and must not be modified except by an explicitly required migration (none is expected from a framework-only upgrade).
- The supported deployment path is commit/push to `main`, then the authorized SSH pull, followed by the required runtime checks and restart.

## Approach

Use a dedicated branch from `origin/main` and update the exact-pinned input first. Recompile the hash-locked requirements with the repository compiler and the required `uv`/Python toolchain. Install the resulting lock in a clean Python 3.14 environment and run the existing project gates before touching application code.

If Django 6.1 reveals a compatibility issue, fix only the smallest affected boundary and add a regression test before changing it. No broad ORM rewrite, query optimization, schema change, or behavior change belongs in this release.

## Verification and Release Gates

1. The lock contains `django==6.1` and resolves without dependency conflicts for Python 3.14.
2. A clean environment installs with hashes and reports Django 6.1; `pip check` is clean.
3. The pre-upgrade project passes deprecation-warning tests (`-Wa`) so removals are addressed rather than hidden.
4. The project passes Django system/deployment checks, migration drift checks, Python compilation, the focused compatibility suite, and the full available Django test suite.
5. Static collection/compressor commands complete in the release environment without changing application behavior.
6. The release is committed and pushed to `main` only after the gates pass.
7. Production is fast-forwarded to the exact release SHA, installs the committed lock in the configured Python 3.14 virtualenv, runs checks, restarts Passenger, and reports Django 6.1 plus healthy representative endpoints.

## Rollback

The rollback unit is the previous Git SHA plus the previous `requirements.lock`. If any pre- or post-deploy gate fails, stop the release and restore that pair; do not make speculative production data changes.

## Follow-up

After this release is proven stable, perform a separate audit of Django 5.2-to-6.1 changes and the 6.1 documentation. Candidate work includes targeted `fetch_mode()` adoption with query-count tests, database-level delete actions only after schema review, and `MAILERS` only where multiple mail backends are actually needed.

