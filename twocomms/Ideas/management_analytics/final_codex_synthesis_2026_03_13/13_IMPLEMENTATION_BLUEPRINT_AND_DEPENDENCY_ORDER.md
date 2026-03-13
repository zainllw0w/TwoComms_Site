# Implementation Blueprint And Dependency Order

## Canonical Role

This file is the strict build order for the future implementation file. It is not a wish-list; it is a dependency-safe sequence over the current codebase.

## Phase Order

| Phase | Goal | Main result |
|---|---|---|
| `0` | freeze canonical contract | no drift before coding |
| `1` | models, versions, day ledger, readiness | safe data foundation |
| `2` | dedupe/follow-up hardening | identity and workload safety |
| `3` | shadow score engine and snapshots | parallel analytics without payroll impact |
| `4` | manager/admin UI surfaces | explainable, action-first visibility |
| `5` | payroll-safe logic and appeals | money-safe interpretation |
| `6` | telephony preparation | data ingestion without pressure |
| `7` | telephony and QA soft launch | supervisor/coaching maturity |
| `8` | validation and activation decisions | bounded production promotion |
| `9` | optional DTF read-only bridge | separate late-phase extension |

## Strict Dependency Rules

### Phase 0 must settle

- authority package path and reading order;
- source coverage matrix;
- unresolved drifts such as `xml_connected` points;
- extend vs create map;
- service decomposition target.

### Phase 1 must deliver before score work

- `ComponentReadiness`;
- `NightlyScoreSnapshot`;
- `CommandRunLog`;
- `ManagerDayStatus`;
- `ManagementStatsConfig` extensions;
- version fields and seeding.

### Phase 2 must deliver before scoring consequences

- normalization pipeline;
- shared-phone handling;
- import burst grace;
- ownership-safe duplicate review;
- reminder and overload semantics.

### Phase 3 must remain non-punitive

- shadow MOSAIC only;
- KPD still active;
- snapshots and confidence visible to admin;
- no payroll switch.

## Code Landing Sequence

### Models and migrations first

1. extend `ManagementStatsConfig`
2. add readiness model
3. add snapshot model
4. add run log
5. add day ledger
6. only later add telephony models

### Services next

1. `score_service`
2. `trust_service`
3. `churn_service`
4. `dedupe_service`
5. `snapshot_service`
6. `payroll_service`
7. `forecast_service`
8. `advice_service`

### Views and templates after payload stability

1. extend `stats_views.py`
2. add UI payload builders
3. split `stats.html` and admin templates into components
4. extend payouts and appeals surfaces
5. only then activate richer badges and compare drawers

## Command Blueprint

Required command family:
- `compute_nightly_scores`
- `send_management_reminders`
- `check_duplicate_queue`
- `seed_management_defaults`
- later `process_telephony_webhooks`
- later `reconcile_call_records`

All commands need:
- lock or idempotency;
- run log;
- clear failure status;
- post-run health data.

## Acceptance Gates By Phase

### Phase 1

- no existing page broken;
- new models migrate safely;
- versions and readiness states readable.

### Phase 2

- duplicate flow is deterministic and conservative;
- imported backlog no longer punishes instantly;
- reminder logic remains low-noise.

### Phase 3

- KPD and shadow MOSAIC coexist;
- snapshots are versioned and idempotent;
- admin can compare without payroll consequence.

### Phase 4

- manager sees freshness, confidence and explainability;
- admin sees health and queue presets;
- mobile manager flows remain usable.

### Phase 5

- no cliff penalties;
- freeze and appeals are visible and reviewable;
- repeat/reactivation/rescue logic is explained.

### Phase 6-7

- provider outage cannot become manager fault;
- QA remains coaching-first until reliable.

## Build Order Inside The Future Implementation File

The implementation file should be grouped in this order:
1. assumptions and unresolved explicit decisions;
2. model changes and migrations;
3. config, versions and seeds;
4. services;
5. commands/jobs;
6. views/templates/assets;
7. tests;
8. rollout and rollback;
9. deploy and verification.

## Existing Production Realities To Preserve

- current KPD remains until shadow validation is complete;
- current Telegram admin logic is reused;
- current shop, CP and payout systems are extended, not re-invented;
- `views.py` and `stats_service.py` require decomposition, not infinite growth.

## Implementation Mistakes To Avoid

- starting UI before payload and version contracts;
- activating score-sensitive logic before tests and snapshots;
- bundling too many models into one risky migration;
- adding telephony dependency before telephony health exists.
