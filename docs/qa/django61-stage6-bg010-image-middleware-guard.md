# Django 6.1 Stage 6: image middleware fail-closed guard

Date: 2026-08-18

Scope: `DJ6-BG-010`

Source baseline: `34f2517c4df4ea2e7c04ab0f6e7a152d83171279`

Runtime: CPython `3.14.6`, Django `6.1`

## Guard contract

`ImageOptimizationMiddleware` now raises Django's `MiddlewareNotUsed` while
the request-path optimizer has no proven durable worker, atomic media-write
contract, or browser asset verification. The guard runs before a
`ThreadPoolExecutor` or `optimized_cache` directory can be created.

The legacy `IMAGE_OPTIMIZATION_MIDDLEWARE_ENABLED` and
`IMAGE_OPTIMIZATION_ALLOW_ON_DEMAND` flags cannot bypass the guard. Enabling
the middleware therefore requires a reviewed code change after the dormant
request-path implementation is replaced by a proven pre-generation design;
an environment-only rollout is intentionally impossible.

The middleware path remains in the existing `MIDDLEWARE` list. Django catches
`MiddlewareNotUsed` while building the handler and omits this middleware from
the request/response chain.

## Evidence

The regression contract was run RED first. Both cases failed with
`MiddlewareNotUsed not raised` on the source baseline. After the guard:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
cd twocomms
"$TWC_PYTHON" manage.py test \
  twocomms.tests_image_middleware_guard \
  --settings=test_settings_no_network_non_dtf --noinput -v 2
```

Result: `2/2 OK`. The two cases cover default-disabled settings and an
attempted legacy-flag opt-in. Both assert that executor and media-directory
creation remain untouched.

The adjacent middleware suite and Django check also passed:

```bash
"$TWC_PYTHON" manage.py test \
  twocomms.tests_image_middleware_guard twocomms.tests_middleware \
  --settings=test_settings_no_network_non_dtf --noinput -v 1
"$TWC_PYTHON" manage.py check \
  --settings=test_settings_no_network_non_dtf --database=default
```

Result: `5/5 OK`; system check identified no issues. A local
`WSGIHandler()` construction also completed with the guarded middleware
skipped.

## Boundaries

No settings capability, task backend, Redis, Stage 5, Stage 7, migration,
production database, server, push, or deployment path changed. `DJ6-BG-004`,
the worker/backend decisions, and every Stage 6 exit-gate item remain open.
