# Test Strategy, Validation And Acceptance

## Canonical Role

This file defines the minimum verification contract before any implementation is considered safe. Money-sensitive logic without automated verification is not acceptable.

## Required Test Families

### Formula unit tests

- `test_ewr.py`
- `test_mosaic.py`
- `test_trust.py`
- `test_gates.py`
- `test_dampener.py`
- `test_onboarding.py`
- `test_churn_weibull.py`
- `test_score_confidence.py`

### Payroll and day-ledger tests

- `test_soft_floor.py`
- `test_commission.py`
- `test_rescue_spiff.py`
- `test_day_status.py`
- `test_reintegration.py`

### Dedupe and follow-up tests

- `test_dedupe.py`
- `test_followup_state.py`
- `test_import_burst_grace.py`
- `test_shared_phone_policy.py`

### Snapshot and versioning tests

- `test_snapshot_schema.py`
- `test_snapshot_idempotency.py`
- `test_defaults_parity.py`
- `test_payload_versioning.py`

### UI and integration tests

- score payload rendering tests;
- stale banner/state tests;
- appeal CTA visibility tests;
- admin health widget tests.

## Golden-Case Requirement

Core formulas must have fixed golden cases:
- fixed input;
- expected output;
- tolerance;
- explicit version.

This is mandatory for:
- EWR;
- MOSAIC composition;
- repeat commission;
- rescue SPIFF;
- churn portfolio aggregation.

## Scenario Regression Suite

Minimum regression scenarios:
- vacation week;
- sick day;
- tech failure day;
- onboarding day 10 / 20 / 30;
- long-leave reintegration;
- import burst;
- shared phone duplicate;
- stale snapshot;
- telephony outage;
- accepted appeal recalculation;
- tiny-team benchmark suppression.

## Validation Window Contract

Before production activation of MOSAIC or materially changed score logic:
- shadow period at least 8 weeks;
- no unexplained divergence over accepted threshold;
- fresh validation window after any major formula semantics change;
- admin approval logged.

## Required Validation Metrics

- `CV-R²`
- bootstrap confidence interval
- `Kendall tau`
- top-bucket lift
- adjacent-window ranking stability

## Acceptance Conditions By Layer

### Score layer

- versioned snapshots persist correctly;
- stale policy works;
- confidence and breakdown fields exist;
- KPD and shadow MOSAIC can coexist.

### Payroll layer

- no cliff penalty;
- capacity-aware proration verified;
- freeze reason and appeal path visible;
- verified revenue truth preserved.

### Dedupe/follow-up layer

- exact/last7/fuzzy path works deterministically;
- import burst grace verified;
- reminder dedupe and digest logic covered.

### Telephony/QA layer

- webhook idempotency;
- reconciliation status stored;
- QA versioning and sampling flow covered;
- outage suppression path tested.

## Existing Production Realities To Preserve

- use current Django test infrastructure as starting point, not a brand new testing universe;
- align tests with existing models and routes;
- respect current caching and Telegram-heavy patterns in integration tests where relevant.

## Implementation Mistakes To Avoid

- shipping formulas without golden tests;
- treating validation as “just correlation”;
- skipping version parity checks between docs and config;
- testing only happy path and not scenario regressions.
