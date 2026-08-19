# Django 6.1 Stage 7 stable parallel shard

Date: 2026-08-19

Scope: `DJ6-TEST-001`

Source baseline: `b544ea71ea13ded209b5f7b3429544bceb5aff92`

Runtime: CPython `3.14.6`, Django `6.1`

## CI scope

The original `storefront.tests.test_product_video --parallel 2` shard was
stable but slower than serial because two Django worker databases were created
for only 11 tests. The workflow now runs that suite explicitly with
`--parallel 1` and parallelizes two larger, process-isolated policy shards via
`scripts/run_django61_ci_shards.py --jobs 2`:

- `django-compatibility`: `tests.test_django61_compatibility`;
- `policy-contracts`: Stage 0 tooling and warning prerequisites, the Instagram
  baseline runner, requirements contracts, and locked-requirements verifier.

The runner rejects runtime drift from CPython 3.14.6/Django 6.1, removes
production DB/provider environment values, selects the no-network non-DTF
settings profile, waits for both child processes, and returns failure if either
shard fails. `tests.test_django61_stage0_contracts` remains a separate serial
workflow-contract step; its coverage is not hidden inside the parallel gate.

## Repeat evidence

The original Django shard was rechecked three times in each mode from
`twocomms/` with the shared project interpreter:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" manage.py test storefront.tests.test_product_video \
  --settings=test_settings_no_network_non_dtf --noinput --parallel 1 -v 1
"$TWC_PYTHON" manage.py test storefront.tests.test_product_video \
  --settings=test_settings_no_network_non_dtf --noinput --parallel 2 -v 1
```

| Original Django shard mode | Runs | Result | Wall-clock range |
| --- | ---: | --- | --- |
| Serial (`--parallel 1`) | 3 | `11/11 OK` each | 2.28-3.41 s |
| Parallel (`--parallel 2`) | 3 | `11/11 OK` each | 3.46-4.00 s |

The replacement process shards were measured through the committed runner.
All 68 selected tests passed on every measured run:

```bash
"$TWC_PYTHON" scripts/run_django61_ci_shards.py --jobs 1 --verbosity 0
"$TWC_PYTHON" scripts/run_django61_ci_shards.py --jobs 2 --verbosity 0
```

| Policy shard mode | Runs | Result | Wall-clock range |
| --- | ---: | --- | --- |
| Serial (`--jobs 1`) | 3 | `68/68 OK` each | 17.33-21.25 s |
| Parallel (`--jobs 2`) | 3 | `68/68 OK` each | 9.70-9.80 s |

Using the conservative fastest-serial/slowest-parallel comparison, local
wall-clock fell by 43.5%. The critical-path reduction is real even though
worker startup and OS scheduling vary; no full-suite speed claim is made.
The exact verbose CI command was also checked once in each mode: `22.71s`
serial versus `13.99s` parallel, with the same `68/68 OK` result.

## Shared-state audit

- Each policy shard is a separate Python process. Module state, environment
  mutations and in-memory caches cannot cross the shard boundary.
- Filesystem-writing contract tests use `TemporaryDirectory`; the shard list
  contains no media/static collector or shared SQLite database writer.
- `test_settings_no_network_non_dtf` installs the external network guard and
  excludes DTF. The runner additionally removes production DB and provider
  credentials before starting children.
- Results are captured independently and rendered in deterministic shard
  order. A failing child cannot be masked by the other shard's success.
- Focused runner contracts cover the exact module allowlist, credential
  stripping, DTF rejection, bounded `--jobs 2`, error propagation and the
  serial `product_video` workflow command.

No production database, runtime, media, DTF surface, deployment command, or
external provider was used. The full non-DTF suite remains serial because its
shared cache/media/SQLite race boundary has not been proven safe. The Stage 7
parallelization exit gate is supported only by these two reviewed process
shards and their measured wall-clock reduction.
