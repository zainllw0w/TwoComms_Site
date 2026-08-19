# Django 6.1 Stage 6: bounded worker budget and no-send canary gate

Scope: non-DTF only. Date: 2026-08-19.

## Purpose

`scripts/verify_django61_stage6_task_budget_gate.py` validates a sanitized,
read-only host snapshot against the policy in
`docs/qa/django61-stage6-task-budget-policy.json`. It requires an explicit
per-account MariaDB connection count; global MariaDB counters are rejected as
a substitute. It also requires concrete FD and process measurements.

The cron shell uses `exec flock`, so the launcher budget is bounded to three OS
processes (`flock`, `timeout`, and one Python worker), one MariaDB connection
and 32 FDs. The gate retains one
database connection, 64 FDs and one process as headroom. These values are an
admission ceiling, not proof that the host has capacity: a fresh
CloudLinux-bound snapshot remains mandatory.

Every snapshot must include a timezone-aware `captured_at` no older than 24
hours, provenance `{ "source": "cloudlinux-bound-python", "kind":
"read-only" }`, `runtime.cloudlinux_bound=true`, and
`database.engine="django.db.backends.mysql"` with
`database.conn_max_age=0`. SQLite, a missing wrapper proof, or a stale
snapshot fails closed.

The canary is inspected statically. It must remain
`task_runtime.tasks.no_send_canary`, with only a keyword-only `marker`
argument and a docstring plus one pure return of
`{"external_io": false, "marker": marker}`. Helper calls, assignments,
provider/network imports, enqueue, persistence, or context-aware execution
fail closed. The validator does not enqueue or execute the canary.

## Invocation

```text
.venv/bin/python scripts/verify_django61_stage6_task_budget_gate.py \
  --policy docs/qa/django61-stage6-task-budget-policy.json \
  --snapshot /secure/read-only/stage6-task-budget-snapshot.json \
  --repo-root .
```

## Exit-gate boundary

This implementation leaves Stage 6 exit gates open. `DJ6-TASK-001` and the
connection/FD/process exit gate require: a fresh production snapshot yielding
`status=ok`, a no-send enqueue/restart/reclaim canary executed by one bounded
owner, and evidence that existing cron remains the rollback path. This commit
does not run SSH, change cron, create a migration, or execute a task.

## Delivery evidence

SHA `6fd1aa5253209aa8af3b6c57d291a23f2c802e40` was fast-forwarded to the
production checkout on 2026-08-19. A read-only CloudLinux-bound probe confirmed
CPython `3.14.6`, Django `6.1`, `django.db.backends.mysql`, MariaDB and
`CONN_MAX_AGE=0`; the tracked checkout was clean. The probe also confirmed that
`task_runtime.0001_initial` is not applied and the durable cron marker is
absent. The deployment therefore delivered dormant guardrails only and did not
activate a worker, create data, change schema, or install cron.
