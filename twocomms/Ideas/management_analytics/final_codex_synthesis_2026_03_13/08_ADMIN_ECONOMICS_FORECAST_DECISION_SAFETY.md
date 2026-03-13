# Admin Economics, Forecast And Decision Safety

## Canonical Role

Admin economics is an admin-only decision layer. It must improve decision quality without becoming a hidden payroll verdict engine.

## Core Rule

`score_confidence` is the primary routing key for admin interpretation.

| Confidence | Allowed admin use |
|---|---|
| `LOW` | observation only |
| `MEDIUM` | coaching, support, pipeline review |
| `HIGH` | escalation-eligible discussion, staffing/lead-mix interpretation |

## Required Admin Economics Blocks

### Cost and contribution

- cost model by manager and period;
- contribution proxy;
- break-even point;
- payback progress;
- payback risk by month end.

### Forecast

Dashboard must show:
- optimistic;
- base;
- pessimistic;
- confidence note.

Forecast must explain which factors move the band:
- stage aging;
- verified coverage;
- repeat concentration;
- recent conversion trend;
- pipeline freshness.

### Cohort and retention

Required cohort table:
- 30d repeat
- 60d repeat
- 90d repeat
- 180d repeat

This is required to distinguish first-order closers from durable retention builders.

## Concentration And Rescue Reading

### Revenue concentration

Required signal:

```python
concentration_top3 = top3_repeat_revenue / max(1, total_repeat_revenue)
```

This must be visible because one manager can look excellent through 2-3 legacy clients alone.

### Rescue ROI

Admin-only signal:

```python
rescue_roi = rescued_revenue_90d / max(1, rescue_spiff_paid + estimated_rescue_time_cost)
```

This is for economics governance, not manager punishment.

## Forecast Safety Rules

### Aging penalty

Weighted pipeline must include age semantics:
- within SLA -> `1.0`
- `<= 2x SLA` -> `0.85`
- older -> `0.65`

### Confidence-aware interpretation

Stale, low-volume or low-verified pipeline must not look precise.

## Score-To-Money Validation

Snapshots must allow comparison of:
- current KPD;
- shadow MOSAIC;
- EWR;
- Wilson diagnostic;
- repeat/new revenue;
- portfolio health;
- follow-up discipline;
- report integrity.

Validation is not limited to raw correlation. Required metrics:
- bootstrap confidence intervals;
- `CV-R²`;
- `Kendall tau`;
- top-bucket lift;
- ordering stability across adjacent windows.

Any major formula change resets the validation window.

## Optional Admin Diagnostics

Allowed only if explicit and disclosed:
- workload consistency / active-tab pattern;
- onboarding amortization horizon;
- rescue time cost proxy;
- source acquisition cost proxy.

These signals are `admin-only` and never silent employee surveillance.

## Existing Production Realities To Preserve

- `ManagementDailyActivity` already exists as current KPD input;
- payout and rejection workflows already exist;
- current code already stores and uses invoice-linked accruals;
- snapshots should become the preferred admin source for heavy analytics.

## Implementation Landing

- extend snapshot payloads;
- extend admin pages and admin payload builders;
- add cohort/concentration/forecast helpers in dedicated services;
- keep the layer explicitly separated from payroll truth in copy and workflow.

## Implementation Mistakes To Avoid

- letting admin economics bypass confidence routing;
- showing one forecast number without band and freshness;
- hiding concentration risk behind strong repeat revenue;
- using optional diagnostics as employee scoring truth.
