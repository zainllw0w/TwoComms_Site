# Governance, Data Model, Jobs And Rollout

## Canonical Role

This file turns the design into an executable governance contract: versions, snapshots, incidents, jobs, seeding, migrations, stale policy and rollout safety.

## Required New Structural Elements

### Version-bearing snapshot

Every score snapshot must store:
- `formula_version`
- `defaults_version`
- `snapshot_schema_version`
- `payload_version`
- `score_confidence`
- `snapshot_freshness_seconds`
- `job_run_id`
- working/capacity context

### Command log

`CommandRunLog` or equivalent must store:
- command name;
- start/finish times;
- status;
- rows processed;
- warnings count;
- short error excerpt;
- affected version or snapshot scope.

### Day ledger

Day ledger or equivalent must support:
- day status;
- capacity factor;
- source reason;
- reintegration flag;
- relation to force majeure or system incidents.

## Required Incident Classes

- `SNAPSHOT_STALE`
- `CACHE_PRESSURE`
- `TELEPHONY_OUTAGE`
- `REMINDER_STORM`
- `DUPLICATE_QUEUE_BACKLOG`
- `PAYOUT_REVIEW_BLOCK`

Each class must be visible to admin and drive downstream safe behavior.

## Command Execution Contract

For any major command such as:
- nightly score computation;
- reminders;
- duplicate queue scan;
- telephony webhook processing;
- call reconciliation.

Required semantics:
- lock or idempotency guard;
- run id;
- safe retry;
- after-run health record;
- no partial-silent success.

## Stale Snapshot Policy

If the latest score-sensitive snapshot is stale:
- manager/admin surfaces remain visible;
- they show explicit `STALE`;
- admin health widget flags the incident;
- payout-adjacent simulation must not pretend to be current truth.

## Migration And Seeding Rules

### Migration rules

- small migrations;
- reversible `RunPython` where applicable;
- one new model per migration where practical;
- post-migration verification queries required.

### Seeding rules

Initial seeds are mandatory for:
- `ComponentReadiness`;
- version defaults;
- incident/status enums where DB-backed;
- initial config extensions for `ManagementStatsConfig`.

## Backfill Rules

Any analytics-sensitive new field must define:
- default value;
- backfill rule;
- verification query;
- whether it is authoritative immediately or starts as `shadow/admin-only`.

## Rollout Contract

### State management

Feature activation must be DB-backed or equivalent runtime-visible state, not hidden in ad hoc constants only.

### No-surprise rule

When score-visible semantics change:
- admin sees version delta and reason;
- manager sees short human-readable notice;
- validation window resets if the score meaning changed materially.

### Operational rollout guardrails

- bi-weekly DICE checkpoint is mandatory during shadow rollout and activation review;
- total manager-facing process overhead from the new contour must stay within `+10%`, or rollout is treated as UX/process regression;
- if overhead or confusion exceeds the guardrail, hold activation and simplify before expanding scope.

## Code Structure Hardening

### Decomposition rules

- do not extend `views.py` as a single god file forever;
- do not keep every new computation inside `stats_service.py`;
- split into services by score, churn, payroll, snapshot, dedupe, forecast and advice domains.

### Template decomposition

Heavy manager/admin pages should use includes for radar, simulator, rescue, timeline and explanation blocks.

## Existing Production Realities To Preserve

- short-lived stats cache already exists;
- cron-friendly execution is the normative stack;
- command + Telegram integration pattern already exists;
- current app structure is large and sensitive to unbounded file growth.

## Implementation Landing

- add `ComponentReadiness`, `NightlyScoreSnapshot`, `CommandRunLog`, `ManagerDayStatus`;
- extend `ManagementStatsConfig`;
- introduce service modules before business logic explosion;
- add admin health widget reading versions, freshness and last successful run.

## Implementation Mistakes To Avoid

- silent config drift;
- partial cron success that looks healthy in UI;
- runtime reading from docs instead of code/config;
- migration without backfill and verification plan;
- feature activation without logged state change.
