# Canonical Defaults Registry

## Canonical Role

This file restores a single-source registry for the most important constants and defaults. It exists to reduce implementation drift and spare the next agent from reconstructing numbers from multiple thematic files.

## Usage Rule

- if a value affects formulas, gates, thresholds, working interpretation or rollout defaults, it should be visible here;
- this registry is a planning contract, not a runtime data source;
- unresolved drifts stay marked as unresolved and must not be silently normalized.

## Legacy Carryover Defaults That Still Matter During Transition

| Constant | Current code reality | Status |
|---|---:|---|
| `TARGET_CLIENTS_DAY` | `20` | existing legacy UI/KPD carryover |
| `TARGET_POINTS_DAY` | `100` | existing legacy UI/KPD carryover |
| `LEAD_ADD_POINTS` | `2` | existing lead-flow carryover |
| `LEAD_BASE_PROCESSING_PENALTY` | `2` | existing lead-flow carryover |
| `ACTIVE_NORM_MINUTES` | `240` | existing KPD carryover |
| `POINTS_NORM` | `180` | existing KPD carryover |
| `MAX_EFFORT` | `2.2` | existing KPD carryover |
| `REMINDER_WINDOW_MINUTES` | `15` | existing reminder carryover |

Unresolved drift:
- `xml_connected` points differ between prior docs and current code and must be decided explicitly in the implementation file.

## Operating Modes

| Mode | Min daily contacts | Target contacts | New paid/week | Total orders/week |
|---|---:|---:|---:|---:|
| `TESTING` | 10 | 20 | 1 | 1 |
| `NORMAL` | 15 | 35 | 1 | 2 |
| `HARDCORE` | 20 | 50 | 2 | 3 |

## Core Commercial Defaults

| Constant | Value |
|---|---:|
| `NEW_ORDER_RATE` | `2.5%` |
| `REPEAT_ORDER_RATE` | `5.0%` |
| `REACTIVATION_RATE` | `3.5%` |
| `REPEAT_ACTIVE_CUTOFF_DAYS` | `180` |
| `CONVERSION_BASELINE` | `0.0248` |
| `TARGET_WEEKLY_REVENUE` | `50_000` |
| `TARGET_CONTACTS_WEEK` | `80` |

## MOSAIC Weights

| Axis | Weight |
|---|---:|
| `Result` | `0.40` |
| `SourceFairness` | `0.10` |
| `Process` | `0.20` |
| `FollowUp` | `0.10` |
| `DataQuality` | `0.10` |
| `VerifiedCommunication` | `0.10` |

## Gate Defaults

| Level | Gate |
|---|---:|
| `Paid` | `100` |
| `Admin-confirmed` | `78` |
| `CRM-timestamped` | `60` |
| `Self-reported only` | `45` |

## Trust Defaults

| Constant | Value |
|---|---:|
| `TRUST_BASE` | `0.97` |
| `TRUST_PRODUCTION_MIN` | `0.85` |
| `TRUST_PRODUCTION_MAX` | `1.05` |
| `TRUST_REPORT_INTEGRITY_WEIGHT` | `0.04` |
| `TRUST_REASON_QUALITY_WEIGHT` | `0.02` |
| `TRUST_DUPLICATE_ABUSE_WEIGHT` | `-0.05` |
| `TRUST_ANOMALY_WEIGHT` | `-0.05` |

## Confidence And Statistical Defaults

| Constant | Value |
|---|---:|
| `SF_NEAR_NEUTRAL_UNDER` | `20 attempts` |
| `SF_FULL_CONFIDENCE_AT` | `100 attempts` |
| `MIN_OBSERVATIONS_GAMING` | `20` |
| `MIN_DAYS_FOR_EWMA` | `42` |
| `EWMA_HALF_LIFE_DAYS` | `21` |
| `EWMA_ACCELERATED_HALF_LIFE_DAYS` | `10` |
| `EWMA_DECAY_GUARD_RATIO` | `0.30` |
| `WILSON_Z_90` | `1.645` |
| `MIN_DAYS_FOR_VALIDATION` | `60` |

## Follow-Up And Reminder Defaults

| Constant | Value |
|---|---:|
| `MAX_FOLLOWUPS_PER_DAY` | `25` |
| `FOLLOWUP_SLA_TARGET` | `80%` |
| `OVERDUE_ESCALATION_LEVEL_1` | `2` |
| `OVERDUE_ESCALATION_LEVEL_2` | `5` |
| `OVERDUE_ESCALATION_LEVEL_3` | `10` |

## DMT / Earned Day Defaults

| Constant | Value |
|---|---:|
| `DMT_MIN_CRM_CONTACTS` | `5` |
| `DMT_MIN_CRM_UPDATES` | `1` |
| `DMT_MIN_MEANINGFUL_CALLS` | `2` |
| `MEANINGFUL_CALL_SECONDS` | `30` |

## Onboarding And Reintegration Defaults

| Constant | Value |
|---|---:|
| `ONBOARDING_DAYS_FULL_PROTECTION` | `14` |
| `ONBOARDING_DECAY_DAYS` | `14` |
| `ONBOARDING_FLOOR_SCORE` | `40` |
| `REINTEGRATION_DAYS_STAGE_1` | `2` |
| `REINTEGRATION_CAPACITY_STAGE_1` | `0.6` |
| `REINTEGRATION_DAYS_STAGE_2` | `3` |
| `REINTEGRATION_CAPACITY_STAGE_2` | `0.8` |

## Portfolio And Rescue Defaults

| Constant | Value |
|---|---:|
| `HEALTHY_MAX_DAYS` | `35` |
| `WATCH_MAX_DAYS` | `55` |
| `RISK_MAX_DAYS` | `75` |
| `MIN_ORDERS_FOR_INDIVIDUAL_HEALTH` | `5` |
| `CHURN_WEIBULL_MIN_ORDERS` | `5` |
| `CHURN_LOGISTIC_K` | `3.0` |
| `CHURN_PLANNED_GAP_NEUTRAL` | `0.05` |
| `CHURN_K_CAP` | `10.0` |
| `SOFT_FLOOR_CAP_AMOUNT` | `120_000` |
| `RESCUE_SPIFF_FLOOR` | `500` |
| `RESCUE_SPIFF_RATE` | `1.0%` |
| `RESCUE_SPIFF_CAP` | `2_000` |
| `RESCUE_POOL_MAX_PER_DAY` | `3` |

## Forecast Defaults

| Constant | Value |
|---|---:|
| `PIPELINE_STAGE_WEIGHT_COLD` | `0.15` |
| `PIPELINE_STAGE_WEIGHT_INTEREST` | `0.35` |
| `PIPELINE_STAGE_WEIGHT_CP_SENT` | `0.60` |
| `PIPELINE_STAGE_WEIGHT_NEGOTIATION` | `0.80` |
| `PIPELINE_STAGE_WEIGHT_INVOICE` | `1.00` |
| `PIPELINE_REACTIVATION_MULTIPLIER` | `0.70` |

## Existing Advice And Config Carryover

These are implementation-significant carryovers:
- `ManagementStatsConfig` already stores `kpd_weights` and `advice_thresholds`;
- new MOSAIC/defaults versions should extend this model, not bypass it;
- existing advice thresholds stay relevant during transition and should be migrated, not silently dropped.

## Implementation Rule

The future implementation file must include a dedicated constants/config section based on this registry and must list unresolved drifts separately instead of burying them inside service code.
