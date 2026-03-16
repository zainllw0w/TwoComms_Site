# Calibration Defaults and Presets

## 1. Зачем этот файл

После двух проходов Opus стало ясно:
без единого числового центра система быстро превращается в красивый, но противоречивый набор идей.

Этот файл — canonical source для стартовых defaults.

## 2. Operating modes

| Mode | Daily meaningful contacts | Weekly new paid clients | Callback SLA | Report compliance | Duplicate abuse ceiling |
|---|---:|---:|---:|---:|---:|
| `TESTING` | `20` | `1` | `80%` | `85%` | `< 5%` |
| `NORMAL` | `35` | `2` | `85%` | `90%` | `< 3%` |
| `HARDCORE` | `50` | `3` | `90%` | `95%` | `< 2%` |

Default for TwoComms:
- probation = `TESTING`,
- standard = `NORMAL`.

## 3. SourceFairness baselines

| Source type | Starting baseline |
|---|---:|
| `cold_xml` | `1.5%` |
| `parser_cold` | `3.0%` |
| `manual_hunt` | `6.0%` |
| `warm_reactivation` | `18.0%` |
| `hot_inbound` | `30.0%` |

## 4. Recalibration policy

### 4.1 Hard production policy
- cadence = `quarterly`,
- data source = verified outcomes only,
- min sample size required,
- max move per quarter = `±25%`,
- no recalibration on low-confidence sample.

### 4.2 Bayesian shadow policy
- window = rolling `90d`,
- review cadence = weekly shadow estimate,
- min source attempts for soft movement = `60`,
- persistence requirement = `3` consecutive weekly deviations,
- max soft move per month = `±10%`,
- quarterly hard cap still wins.

## 5. Rolling aggregation defaults

- rolling window = `28 календарных дней`,
- aggregation = `EWMA`,
- `lambda = 0.033`,
- half-life `≈ 21 дней`.

Применять для:
- rolling MOSAIC,
- rolling axis trends,
- velocity,
- multi-day coaching summaries.

## 6. Low-sample protection defaults

Для `SourceFairness`:
- `attempts < 5` = neutral band + excluded from hard comparison,
- `5 <= attempts < 12` = confidence-blended,
- `attempts >= 12` = full effect allowed.

Confidence:

`confidence = min(1, attempts / 12)`

`sf_effective = 50 * (1 - confidence) + sf_raw * confidence`

Wilson-style interval использовать для:
- admin conclusions,
- comparison labels,
- insufficient-evidence warnings.

## 7. Gate defaults

| Gate tier | Cap | Condition |
|---|---:|---|
| `verified_conversion` | `100` | paid/admin-confirmed conversion |
| `verified_progress` | `78` | no paid yet, but real verified commercial motion |
| `self_reported_only` | `60` | only weak evidence |
| `breach_and_stale` | `45` | `3+` business days without verified progress + callback breaches |

## 8. Discipline floor dampener

Operational axes:
- `Process`
- `FollowUp`
- `DataQuality`
- `VerifiedCommunication`, only if maturity `>= soft_launch`

Defaults:
- critical floor = `20`,
- rolling basis = `10 business days`,
- penalty per axis below floor = `-5%`,
- max total dampening = `-15%`.

Do not apply:
- first `10` working days,
- approved leave,
- infrastructure incident,
- `manual_only` mode for `VerifiedCommunication`.

## 9. Trust anomaly thresholds

| Signal | Caution | Critical |
|---|---:|---:|
| duplicate override rate | `> 3%` | `> 6%` |
| same reason share | `> 45%` | `> 60%` |
| short-call mismatch | `> 8%` | `> 15%` |
| missed callback rate | `> 15%` | `> 25%` |

For same reason share:
- apply only when `n >= 10`.

## 10. Report integrity thresholds

Only evaluate on:
- resolved cases,
- enough sample,
- evidence-backed status chains.

Defaults:
- min resolved sample = `20`,
- `>= 0.85` = strong integrity,
- `0.70..0.84` = neutral/good,
- `0.55..0.69` = caution,
- `< 0.55` = critical review.

## 11. Verified communication maturity

| Telephony maturity | Axis cap | Notes |
|---|---:|---|
| `manual_only` | `60` | do not punish for absent telephony data |
| `soft_launch` | `80` | partial telephony evidence available |
| `supervised` | `100` | full verified comm logic active |

## 12. Response latency defaults

Apply to:
- `hot_inbound`,
- `warm_reactivation`,
- promised callbacks,
- admin-approved urgent follow-ups.

| Response latency | Interpretation |
|---|---|
| `< 5 минут` | excellent |
| `< 15 минут` | strong |
| `< 1 часа` | acceptable |
| `1-4 часа` | weak |
| `> 4 часов` | risk |
| `> 24 часов` | critical |

## 13. Portfolio bonus defaults

Eligibility:
- `portfolio_health >= 70`,
- `qa_avg >= 80`,
- `callback_sla >= 85%`,
- `critical_complaints = 0`,
- and either `repeat_share >= 30%` or `successful_reactivations >= 2`.

Bonus:
- `+0.5%` to repeat commission rate.

## 14. Fashion wholesale portfolio cadence

| State | Days since meaningful contact |
|---|---:|
| `Healthy` | `0-21` |
| `Watch` | `22-35` |
| `Risk` | `36-45` |
| `Rescue` | `46-60` |
| `Reassign Eligible` | `61+` |

## 15. Long-cycle persistence defaults

For bounded persistence credit:
- minimum pipeline age = `21 дней`,
- minimum meaningful interactions = `3`,
- interactions must be spaced over the cycle,
- cap = `10` milestone points,
- disable on duplicate-tainted or ownership-conflicted cases.

## 16. Micro-feedback defaults

Visible manager stream:
- `+0.5` exact callback,
- `+0.2` good reason detail,
- `+0.1` valid instant hangup cleanup,
- `-2.0` significantly late callback,
- `-5.0` forgotten callback,
- `+15.0` correct invoice without rework,
- `+100.0` paid order.

Rules:
- no direct payroll impact,
- evidence required,
- overnight bounded influence only.

## 17. Comparative engine modes

### Default
`Seasonal Ladder`

### Optional advanced mode
`Glicko-2`

Enable only if:
- `>= 5` active managers,
- `>= 90 days` of clean data,
- stable trust and verified coverage,
- explicit product decision.
