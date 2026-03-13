# Payroll, KPI, Portfolio And Earned Day

## Canonical Role

This file defines money-safe operational rules:
- payroll truth stays grounded in verified revenue;
- KPI and day rhythm guide behavior, but do not create cliff-shocks;
- portfolio and rescue logic must remain explainable and auditable;
- appeals and freeze reasons are mandatory.

## Financial Core

| Component | Rule |
|---|---|
| Base salary | preserved as existing business layer |
| New order commission | `2.5%` |
| Repeat commission | `5.0%` |
| Reactivation | `3.5%` after `>180` days |
| Rescue SPIFF | scaled `500-2000 UAH`, verified and attributed only |

Money does not depend directly on shadow MOSAIC.

## Weekly KPI Contract

### Operating modes

| Mode | Min daily contacts | Target contacts | New paid/week | Total orders/week |
|---|---:|---:|---:|---:|
| `TESTING` | 10 | 20 | 1 | 1 |
| `NORMAL` | 15 | 35 | 1 | 2 |
| `HARDCORE` | 20 | 50 | 2 | 3 |

### Capacity-aware interpretation

Weekly KPI must be prorated by actual usable capacity.

```python
def compute_working_factor(capacity_factors: list[float], nominal_workdays: int = 5) -> float:
    usable = sum(max(0.0, min(1.0, x)) for x in capacity_factors)
    return round(usable / max(1, nominal_workdays), 4)
```

Required consequences:
- vacation/sick/force-majeure weeks cannot look like weak KPI weeks;
- half-day / internal / training work cannot be forced into fake full-day semantics;
- soft-floor eligibility uses the same working-factor reality.

## Day Ledger Contract

### Required statuses

- `WORKING`
- `WEEKEND`
- `HOLIDAY`
- `VACATION`
- `SICK`
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

### Required additional fields

- `capacity_factor`
- `source_reason`
- `reintegration_flag`
- optional subtype like `TRAINING / INTERNAL / FIELD`

Onboarding protection is separate from absence semantics.

## Reintegration Contract

After long absence:
- `VACATION >= 5 working days`
- `SICK >= 5 working days`
- `FORCE_MAJEURE >= 3 working days`

reintegration mode is mandatory:
- first 2 working days after return -> `capacity_factor = 0.6`
- next 3 working days -> `capacity_factor = 0.8`
- then normal mode

## Soft Floor Cap Contract

### Preserved production-safe logic

```python
def compute_repeat_commission(
    repeat_revenue: float,
    new_clients_this_week: int,
    *,
    target_new_clients: int = 1,
    cap_amount: float = 120_000,
) -> float:
    base_rate = 0.05
    shortfall = max(0, target_new_clients - new_clients_this_week)

    if shortfall == 0:
        return round(repeat_revenue * base_rate, 2)

    penalty_rate = 0.045 if shortfall == 1 else 0.035
    penalized = min(repeat_revenue, cap_amount)
    regular = max(0, repeat_revenue - cap_amount)
    return round(penalized * penalty_rate + regular * base_rate, 2)
```

### Hardening rules

- eligibility uses working-factor-adjusted target;
- shortfall reason must be stored;
- week boundary or holiday pattern must not create lottery-like repeat penalties;
- reactivation revenue stays a separate class and must not masquerade as healthy repeat.

## Portfolio Health Contract

### Baseline states

| State | Days since expected order |
|---|---:|
| `Healthy` | 0-35 |
| `Watch` | 35-55 |
| `Risk` | 55-75 |
| `Rescue` | 75+ |

### Required drivers

- days since last and expected order;
- planned gap and snooze;
- churn probability where history is sufficient;
- shop health and stale shop signals;
- overdue test-shop signals;
- test-to-full conversion as retained relationship evidence;
- successful reactivation trail;
- rescue actionability and load state.

### Shop lifecycle carryover contract

The existing shop subsystem must not disappear during implementation.

Required treatment:
- `stale_shops_count` and overdue test signals are `authoritative` portfolio-health inputs;
- `tests_converted_total` is mandatory retained business evidence and must survive the transition;
- `test-to-full conversion` may be used as `shadow/admin-only` result/process carryover until validated for broader score consequence;
- live portfolio ownership must use `Shop.managed_by`, not `Shop.created_by`.

### Planned gap / snooze contract

Must store:
- reason;
- until date;
- approver;
- confidence;
- audit trail of extension or expiry.

## Rescue Contract

### Queue rules

- primary sort = `Expected LTV Loss`;
- tie-break = `rescue_actionability`;
- explicit `confidence` badge required;
- no more than `3` new rescue cases/day without admin override;
- `DQ grace` or unresolved integrity issues must suppress aggressive rescue overload.

### SPIFF rules

- only for verified rescued orders from the rescue queue;
- requires attribution trail;
- value is scaled, not flat.

## Earned Day Contract

### Minimum vs pace distinction

Manager UI and admin logic must separate:
- `Minimum achieved`
- `Target pace achieved`
- `Recovery needed`

`Earned Day` is not equal to healthy target pace.

### Phase-aware DMT

Phase 0:
- `>=5` CRM contacts
- `>=1` meaningful CRM update
- report submitted or valid exception

Phase 1+:
- Phase 0 rules stay
- add `>=2` meaningful calls `>30s`

### Failure semantics

Gap categories must be split:
- `performance_gap`
- `reporting_gap`
- `system_gap`

## Freeze, Appeals And Disputes

### Required dispute flows

- scoring appeal;
- payout dispute;
- freeze review;
- ownership-sensitive commission dispute.

### Minimum SLA

- payout dispute preliminary response within 1 working day;
- scoring appeal within 2 working days;
- accepted appeal restores frozen value or recalculation queue automatically.

### Existing reality to preserve

- `ManagerCommissionAccrual.frozen_until` already exists;
- `ManagerPayoutRequest` workflow already exists;
- Telegram-driven reason/rejection flows already exist and should be aligned, not replaced.

## Manager/Admin Surfaces

### Manager must see

- current new/repeat/reactivation accruals;
- freeze reason if any;
- shadow hold-harmless delta;
- earned day explanation;
- salary simulator with confidence/state labels.

### Admin must see

- accrual decomposition;
- rescue attribution evidence;
- earned day ledger;
- appeals queue;
- score-to-money validation and confidence reading.

## Implementation Landing

- extend `ManagementStatsConfig` and payout-related payloads;
- add `ManagerDayStatus` or equivalent ledger;
- add `ScoreAppeal` or aligned workflow model;
- extend existing payout/admin views instead of parallel rewrite;
- preserve shop-health/test-conversion computation path instead of replacing it with generic retention placeholders;
- connect portfolio, rescue and payout logic through snapshots and explicit trails.

## Implementation Mistakes To Avoid

- cliff penalty reintroduction in any form;
- using calendar week without capacity-aware proration;
- mixing data error with performance failure;
- silently hiding freeze reasons;
- rewarding manual rescue claims without attribution evidence;
- forcing telephony into phase-0 payroll.
