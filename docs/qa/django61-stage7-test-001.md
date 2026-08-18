# Django 6.1 Stage 7 stable parallel shard

Date: 2026-08-18

Scope: `DJ6-TEST-001`

Source baseline: `90b437e11dcc0c1bd873f4478da8d66409688b3d`

Runtime: CPython `3.14.6`, Django `6.1`

## CI scope

The existing `storefront.tests.test_product_video` compatibility suite is the
only Django suite run with `--parallel 2` in `django61-gate.yml`. It uses
`test_settings_no_network_non_dtf`, has 11 exact test cases, and does not
include DTF labels.

This is a bounded stability change, not a full-suite parallelization or a
performance claim. The Stage 7 parallel-speed exit gate remains open: process
and SQLite setup make this small shard slower in the local measurement.

## Repeat evidence

Each command completed three consecutive times from `twocomms/` with the
shared project interpreter:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" manage.py test storefront.tests.test_product_video \
  --settings=test_settings_no_network_non_dtf --noinput --parallel 1 -v 1
"$TWC_PYTHON" manage.py test storefront.tests.test_product_video \
  --settings=test_settings_no_network_non_dtf --noinput --parallel 2 -v 1
```

| Mode | Runs | Result | Wall-clock range |
| --- | ---: | --- | --- |
| Serial (`--parallel 1`) | 3 | `11/11 OK` each | 1.40-1.42 s |
| Parallel (`--parallel 2`) | 3 | `11/11 OK` each | 2.05-2.11 s |

The initial direct serial CI command also completed `11/11 OK`. The parallel
runner created worker databases `default_1.sqlite3` and `default_2.sqlite3`;
no worker used the base in-memory database as a shared writable file.

## Shared-state audit

- The no-network settings define the default database as SQLite `:memory:`.
  Django creates isolated worker clones for `--parallel 2`.
- Both cache aliases use `LocMemCache`, which is process-local. This shard does
  not mutate cache state.
- The selected tests create only ORM `Category` and `Product` rows with URLs;
  they do not assign an `ImageField` or `FileField`. A before/after filesystem
  snapshot found zero files under the configured `MEDIA_ROOT` in both states.
- `test_network_guard` is installed before the base settings load and the
  profile reports `TEST_NETWORK_POLICY=deny-external`. Feed-task calls in the
  selected suite are patched.

No production database, runtime, media, DTF surface, deployment command, or
external provider was used. The full non-DTF suite remains serial because its
shared cache/media/SQLite race boundary has not been proven safe.
