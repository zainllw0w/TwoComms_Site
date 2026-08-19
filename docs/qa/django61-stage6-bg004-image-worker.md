# Django 6.1 Stage 6: image optimization worker

Scope: `DJ6-BG-004`
Runtime: CPython `3.14.6`, Django `6.1`

## Implemented contract

- Web requests persist an `ImageOptimizationJob` and return the durable status;
  `product_catalog.image_jobs` contains no `ThreadPoolExecutor` or request-owned
  worker state.
- `reconcile_image_optimization_jobs` is the sole executor. Each invocation
  has one hard `--max-jobs` budget shared by stale recovery and fresh pending
  work, uses the existing lease/fencing claims, and closes old Django
  connections around each job.
- Production media writes fail closed unless the command receives the explicit
  `--allow-production` authorization. The installer pins
  `twocomms.production_settings`, requires a CloudLinux-bound Python, proves
  MariaDB/`CONN_MAX_AGE=0`/migration `0015`/InnoDB plus the lease and queue
  index schema before touching crontab, rejects a second owner, and bounds the
  process with `timeout` plus `flock`.
- Existing editor status/retry endpoints remain compatible: they can repair or
  observe pending state, but cannot execute image work.
- Derivative publication is atomic and durable: temporary file write, file
  `fsync`, `os.replace`, and parent-directory `fsync`. A failed derivative
  publication raises and the persisted job is not marked complete.

## Evidence

Focused gate:

```text
product_catalog.tests.test_editor.ProductCatalogImageJobTests: 54 tests OK
storefront.tests.test_image_optimization: 8 tests OK
tests.test_install_product_catalog_image_jobs_cron: 6 tests OK
```

The cron installer remains idempotent; no production cron installation,
database migration, media cleanup, or server mutation was performed in this
slice. Production activation still requires the existing deployment window,
an explicit installer invocation and a short live media-volume smoke. The
periodic-owner inventory remains `active:false`, so these guardrails do not
activate image execution.

Fresh read-only production audit on SHA
`b544ea71ea13ded209b5f7b3429544bceb5aff92` confirmed CPython `3.14.6`,
Django `6.1`, applied `product_catalog.0015_reconcile_image_job_schema`, an
empty InnoDB `product_catalog_imageoptimizationjob` table, exact non-null
`varchar(32)` lease token and both `(status, updated_at)` / `(status,
created_at)` queue indexes, plus exactly zero image-cron managed
markers/command owners. No SSH mutation was performed.

The 2026-08-19 Stage 6 MariaDB task-backend activation did not change this
status: `product_catalog_image_jobs` is inventory-only (`active:false`) and
has no cron owner/block on production. It is not a live image-worker rollout.
