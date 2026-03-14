# Score, MOSAIC, EWR And Confidence

## Canonical Role

This file defines the score contract for the target system:
- KPD remains legacy production during transition;
- MOSAIC is the target canonical score model;
- EWR is the core `Result` implementation;
- `score_confidence` is a mandatory safety key;
- `Wilson` and `EWR-v2` are diagnostic/shadow tools, not immediate production replacements.

## Canonical Axes And Weights

### Nominal weights

| Axis | Weight |
|---|---:|
| `Result` | `0.40` |
| `SourceFairness` | `0.10` |
| `Process` | `0.20` |
| `FollowUp` | `0.10` |
| `DataQuality` | `0.10` |
| `VerifiedCommunication` | `0.10` |

### Phase-0 effective redistribution

While `VerifiedCommunication` is `DORMANT`, weights are redistributed over active axes only:
- `Result` 44.4%
- `SourceFairness` 11.1%
- `Process` 22.2%
- `FollowUp` 11.1%
- `DataQuality` 11.1%

## KPD -> MOSAIC Transition Map

| Current KPD component | Canonical target |
|---|---|
| Effort from active time and points | partly absorbed by `Result/EWR` and operational layers; active time stays existing legacy signal until explicit decision |
| Quality from success-weighted outcomes | replaced by `Result/EWR` |
| Ops from CP, shops, invoices | split across `Process`, portfolio and communication layers |
| Penalty from follow-up and reports | replaced by `FollowUp` and `DataQuality` |

## Calculation Order

1. compute raw axis values in `0..1`;
2. apply `ACTIVE/SHADOW/DORMANT` readiness filtering;
3. compute weighted raw score;
4. split into `verified_slice` and `evidence_sensitive_slice`;
5. apply production trust only to `evidence_sensitive_slice`;
6. apply evidence gate;
7. apply dampener;
8. apply onboarding protection if active;
9. compute `score_confidence`;
10. persist snapshot with versions and freshness.

## Axis-To-Slice Contract

| Component | Verified slice | Evidence-sensitive slice | Status |
|---|---:|---:|---|
| Paid outcome | 100% | 0% | `authoritative` |
| Revenue from verified orders | 100% | 0% | `authoritative` |
| Admin-confirmed commercial milestone | 60% | 40% | `authoritative` |
| CRM-only progress | 0% | 100% | `authoritative` |
| Effort term | 0% | 100% | `authoritative` |
| `SourceFairness` | 0% | 100% | `authoritative` |
| `Process` | 0% | 100% | `authoritative` |
| `FollowUp` | 0% | 100% | `authoritative` |
| `DataQuality` | 0% | 100% | `authoritative` |
| `VerifiedCommunication` | phase-dependent | phase-dependent | `dormant` until telephony maturity |

## EWR Contract

### Canonical production formula

```python
def compute_ewr(
    orders: int,
    contacts_processed: int,
    revenue: float,
    *,
    conversion_baseline: float = 0.0248,
    target_weekly_revenue: float = 50_000,
    target_contacts: int = 80,
) -> float:
    expected_orders = contacts_processed * conversion_baseline

    if expected_orders >= 1:
        outcome = min(2.0, orders / expected_orders)
    elif orders > 0:
        outcome = 2.0
    else:
        outcome = 0.5

    normalized_outcome = min(1.0, outcome / 2.0)
    effort = min(1.0, contacts_processed / max(1, target_contacts))
    revenue_progress = min(1.0, revenue / max(1, target_weekly_revenue))

    return round(min(1.0, 0.40 * normalized_outcome + 0.35 * effort + 0.25 * revenue_progress), 4)
```

### Production-safe rules

- low-sample no-order windows stay neutral, not punitive-zero;
- revenue stays soft, not single-order dominating;
- rolling smoothing must use working observations only;
- effort must not become a reward for empty grind;
- `target_contacts = 80/week` is a normalization baseline, not the manager stretch target.

### Shadow/admin-only extensions

| Signal | Status | Use |
|---|---|---|
| `EWR-v2` with effort-quality factor | `shadow/admin-only` | compare against current EWR |
| `Wilson` conversion diagnostic | `shadow/admin-only` | conservative small-sample reading |
| `ewr_v1_vs_v2_delta` | `shadow/admin-only` | validation only |

## Churn Contract For Portfolio And Admin Surfaces

Churn is a portfolio/rescue/admin signal first. It must remain explicit enough that rescue ranking and `Expected LTV Loss` do not drift into hand-wavy proxy math.

```python
def compute_churn_weibull(
    days_since_last_order: int,
    avg_interval: float,
    std_interval: float,
    order_count: int,
    *,
    expected_next_order: int | None = None,
) -> float:
    if expected_next_order is not None and days_since_last_order < expected_next_order:
        return 0.05

    if order_count < 5:
        if avg_interval <= 0:
            return 0.5
        logistic = 1 / (1 + math.exp(-3.0 * (days_since_last_order - avg_interval) / avg_interval))
        return round(min(1.0, max(0.0, logistic)), 4)

    lambda_param = avg_interval + 0.5 * max(1.0, std_interval)
    k_param = min(10.0, max(1.0, avg_interval / max(1.0, std_interval)))
    churn = 1 - math.exp(-pow(days_since_last_order / max(1.0, lambda_param), k_param))
    return round(min(1.0, max(0.0, churn)), 4)
```

Mandatory rules:
- `Weibull` is the primary churn model when `order_count >= 5`;
- if `order_count < 5`, use logistic fallback instead of fake precision;
- `expected_next_order` / planned-gap state must return near-neutral churn instead of false panic;
- `k` must stay capped at `10.0` to avoid overflow and false mathematical certainty;
- churn may drive portfolio health, rescue ranking, `Expected LTV Loss` and admin diagnostics, but not direct punitive payroll truth before separate validation.

## SourceFairness Contract

### Production-safe rules

- fairness must compare against source difficulty, not reward warm-cherry-picking;
- low sample stays near neutral;
- authoritative comparison is blocked when source normalization or team comparability is insufficient.

### Mandatory split

| Mode | Rule |
|---|---|
| `assignment_fairness` | measures difficulty of the base actually assigned to the manager |
| `self_selected_mix` | diagnostic signal for warm-source cherry-picking |

`assignment_fairness` may affect authoritative score. `self_selected_mix` is `shadow/admin-only`.

## Trust Contract

### Production trust

- narrow range: `0.85 .. 1.05`;
- applied only to the evidence-sensitive slice;
- repeat pattern + sufficient N required before negative production impact;
- telephony and QA terms are inactive before maturity.

### Diagnostic trust

- longer horizon;
- can include richer anomaly patterns;
- never direct payroll truth.

## Gates And Dampener

### Evidence gate levels

| Level | Gate |
|---|---:|
| `Paid` | `100` |
| `Admin-confirmed` | `78` |
| `CRM-timestamped` | `60` |
| `Self-reported only` | `45` |

Admin/shadow interpretation may use richer sub-levels, but production gate remains conservative.

### Dampener

- counts critically weak operational axes;
- never bypassed by portfolio bonus;
- does not include `VerifiedCommunication` while dormant;
- does not silently zero out verified results.

## Score Confidence Contract

### Canonical numeric formula

```python
def compute_score_confidence(
    verified_coverage: float,
    sample_sufficiency: float,
    stability: float,
    recency: float,
) -> float:
    score = (
        0.35 * verified_coverage
        + 0.25 * sample_sufficiency
        + 0.20 * stability
        + 0.20 * recency
    )
    return round(max(0.0, min(1.0, score)), 4)
```

### Reading bands

| Band | Meaning |
|---|---|
| `HIGH >= 0.80` | escalation-eligible discussion |
| `MEDIUM 0.50-0.79` | coaching / support / review |
| `LOW < 0.50` | observation only |

### Required fields behind the score

- `verified_coverage`
- `sample_sufficiency`
- `stability`
- `recency`
- `snapshot_freshness_seconds`
- `working_day_factor`

## Additional Canonical Diagnostics

| Signal | Status |
|---|---|
| `discipline_debt_10d` | `shadow/admin-only` |
| `churn_confidence` | `shadow/admin-only` |
| `stale_snapshot_flag` | `authoritative` for rendering/state |
| `source_mix_self_selection_flag` | `shadow/admin-only` |

## Implementation Landing

- extend `ManagementStatsConfig` with MOSAIC/defaults versions;
- create `ComponentReadiness`;
- create `NightlyScoreSnapshot`;
- add new score services instead of inflating current `stats_service.py` further;
- keep KPD callable during transition;
- extend `stats_views.py` and `stats.html` to render both current and shadow logic safely.

## Implementation Mistakes To Avoid

- hard-switching KPD off before shadow validation;
- treating `score_confidence` as UI decoration only;
- letting stale snapshots look fresh;
- comparing cross-version snapshots without version fields;
- rewarding self-selected warm mix through `SourceFairness`;
- making `Wilson` or `EWR-v2` production truth before validation.
