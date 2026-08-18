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
- Existing editor status/retry endpoints remain compatible: they can repair or
  observe pending state, but cannot execute image work.
- Derivative publication is atomic and durable: temporary file write, file
  `fsync`, `os.replace`, and parent-directory `fsync`. A failed derivative
  publication raises and the persisted job is not marked complete.

## Evidence

Focused gate:

```text
product_catalog.tests.test_editor: 69 tests OK
storefront.tests.test_image_optimization: 8 tests expected in adjacent gate
```

The cron installer remains idempotent and protected by `flock`; no production
cron installation, database migration, media cleanup, or server mutation was
performed in this slice. Production activation still requires the existing
deployment window and a short live media-volume smoke.
