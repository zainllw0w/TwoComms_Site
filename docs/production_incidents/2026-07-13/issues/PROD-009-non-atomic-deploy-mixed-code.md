# PROD-009 — In-place deploy exposes mixed old/new code to live workers

**Priority:** P1
**State:** confirmed deploy hazard; latest workers recovered after restart
**Owner:** deployment/operations

## Observed incidents

### ProductCatalog on 13 July

- Product Catalog feature commit completed around 14:55; the follow-up model fix around 15:00.
- Settings/URL files changed while existing workers were still serving; restart marker appeared around 15:02:59.
- Retained stderr contains 14 repeats of:

```text
RuntimeError: Model class product_catalog.models.ColorProfile ... isn't in an application in INSTALLED_APPS
```

- `/bot/api/status/` returned 503 at 14:41:55 and a product request failed at 14:57, within the deployment window.
- Current source does contain `product_catalog` in `INSTALLED_APPS` and includes its URLs. The mismatch is therefore best explained by an old worker with already-loaded settings lazily importing newly pulled URL/model files, not a persistent omission in current source.

### Earlier management schema/code skew

`/bot/api/clients/` queried `hidden_at` while the worker's loaded model did not contain that field. Migration 0074 and current model do contain it. This is another mixed worker/release example.

### Earlier cart symbol skew

Three retained `/cart/` errors called a removed `storefront.views.process_guest_order`. Current source calls `create_order` after a 6 July change. This is historical/resolved in code but lacks a deploy invariant preventing the same class of skew.

## Root cause

`git pull` mutates source files beneath live multi-process Python workers. Imports are lazy and module state is per process, so requests can combine old settings/model registry with new URL/view files until every worker restarts. Migrations/static/compressor changes introduce additional partial states.

## Implementation plan

1. Define an immutable release directory per revision or, if hosting prevents symlink switching, use a maintenance gate around pull/preflight/restart.
2. Build/preflight before traffic:
   - import WSGI application and every URLconf;
   - `manage.py check --deploy`;
   - `showmigrations --plan` and apply required migrations;
   - collect static and run offline compressor validation;
   - run narrow host/health smoke tests.
3. Switch/restart workers as one controlled step; wait for readiness before reopening traffic.
4. Store build revision/start time in health and structured logs.
5. Define rollback that restores code, compatible schema expectations and asset manifest together.
6. Add a deploy lock so overlapping agents/jobs cannot pull/restart concurrently.

## Acceptance criteria

- A synthetic request loop sees only old or new revision, never mixed failures.
- Product Catalog model/URL imports succeed in a fresh production-settings process before restart.
- Migration and static/compressor readiness are gates, not post-deploy repair.
- All workers report the same revision after deployment.
- Rollback is documented and rehearsed without destructive Git commands.

## Runtime recovery safeguards (2026-08-17)

The production recovery work adds the following gates to the release path:

- production settings fail closed when the selected production environment does
  not provide a MySQL/MariaDB database; SQLite is not an implicit fallback;
- release preparation verifies the reviewed `requirements.lock` digest, the
  immutable wheelhouse manifest, CloudLinux runtime bindings, and a typed
  MariaDB probe before activation;
- the `mysqlclient` artifact is built against the pinned MariaDB Connector/C
  3.3.19 source and the wheel gate proves DECIMAL/CHAR/field metadata plus one
  uniquely loaded bundled connector without `LD_PRELOAD`;
- release pruning is dry-run by default, runs under the deploy lock, and
  rejects both active venv and active static targets (including their parents
  and descendants);
- recovery and rollback preserve the authoritative MariaDB schema and data;
  no database reset or destructive migration is part of this path.
