# Production Runtime Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep production on the authoritative MariaDB runtime after a release-artifact cleanup incident and prevent silent SQLite fallback, unsafe artifact pruning, and recurrence of the MariaDB Connector/C loader failure.

**Architecture:** The production settings fail closed whenever the production env file is selected without a configured database. The release tooling installs a hash-pinned mysqlclient wheel with one bundled MariaDB provider and runs a read-only typed database probe before activation; the operational prune helper refuses active venv/static targets and their parents, uses the deployment lock, and defaults to dry-run. The immediate server recovery remains an atomic runtime switch plus CloudLinux app environment update; no schema reset or data deletion is part of this change.

**Tech Stack:** Django 6.1, CPython 3.14.6, mysqlclient, MariaDB Connector/C, CloudLinux selector, Python unittest/Django test runner.

---

### Task 1: Make production database selection fail closed

**Files:**
- Modify: `twocomms/twocomms/production_settings.py`
- Test: `twocomms/twocomms/tests_production_env.py`

1. Add a failing test for a selected `.env.production` without `DB_ENGINE`, `DB_NAME`, or `DB_USER`.
2. Run the focused test and confirm it fails because SQLite is currently selected.
3. Raise `ImproperlyConfigured` for that production selection; retain SQLite only for explicit non-production/local test settings.
4. Run the focused production environment and engine-policy tests.

### Task 2: Add a typed MariaDB runtime probe and loader contract

**Files:**
- Create: `scripts/verify_production_database.py`
- Modify: `scripts/deploy_release.py`
- Test: `tests/test_verify_production_database.py`
- Test: `tests/test_deploy_release.py`

1. Add tests that require the probe to report the database engine and reject a corrupted `cursor.description`/Decimal conversion.
2. Run them red.
3. Implement a read-only probe for `SELECT VERSION(), @@sql_mode`, a string result, a DECIMAL result, and field metadata; require MySQL/MariaDB and exactly one wheel-local Connector/C provider with no `LD_PRELOAD`.
4. Remove inherited `LD_PRELOAD` from staged/maintenance/health environments and fail the typed probe unless exactly one wheel-local Connector/C provider is loaded.
5. Run focused tests and the existing deploy-release suite.

### Task 3: Add fail-closed release-artifact pruning

**Files:**
- Create: `scripts/prune_release_artifacts.py`
- Test: `tests/test_prune_release_artifacts.py`
- Modify: `docs/production_incidents/2026-07-13/issues/PROD-009-non-atomic-deploy-mixed-code.md`

1. Add red tests for active external venv symlink targets, parent directories, lock contention, and dry-run default.
2. Implement explicit path resolution, active-target/parent rejection, deployment lock acquisition, and opt-in deletion only for validated release children.
3. Run the focused tests and `git diff --check`.

### Task 4: Publish and recover production safely

1. Commit only the scoped runtime/ops files on the isolated branch and push to `main` after review.
2. On production, use the existing staged CloudLinux-bound candidate, keep `LD_PRELOAD` unset, and atomically switch the stable venv symlink.
3. Run `check --deploy`, `migrate --check`, the typed MariaDB probe, and representative HTTP/health checks. Never run destructive migrations or database reset commands.
4. Update the bounded cron contracts, restart Passenger once, and record deployed SHA, runtime target, DB engine/version, and zero schema drift.
