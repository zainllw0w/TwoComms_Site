# Calibration Defaults and Presets

## 1. Зачем этот файл

После Opus-аудита стало ясно, что архитектура без числового центра быстро превращается в набор красивых идей.

Этот файл — единственный canonical источник стартовых defaults.

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

- cadence = `quarterly`,
- data source = verified outcomes only,
- min sample size required,
- max move per cycle = `±25%`,
- no recalibration on low confidence sample.

## 5. Gate defaults

| Gate tier | Cap | Condition |
|---|---:|---|
| `verified_conversion` | `100` | paid/admin-confirmed conversion |
| `verified_progress` | `78` | no paid yet, but real verified commercial motion |
| `self_reported_only` | `60` | only weak evidence |
| `breach_and_stale` | `45` | `3+` business days without verified progress + callback breaches |

## 6. Trust anomaly thresholds

| Signal | Caution | Critical |
|---|---:|---:|
| duplicate override rate | `> 3%` | `> 6%` |
| same reason share | `> 45%` | `> 60%` |
| short-call mismatch | `> 8%` | `> 15%` |
| missed callback rate | `> 15%` | `> 25%` |

For same reason share:
- apply only when `n >= 10`.

## 7. Verified communication maturity

| Telephony maturity | Axis cap | Notes |
|---|---:|---|
| `manual_only` | `60` | do not punish for absent telephony data |
| `soft_launch` | `80` | partial telephony evidence available |
| `supervised` | `100` | full verified comm logic active |

## 8. Portfolio bonus defaults

Eligibility:
- `portfolio_health >= 70`,
- `qa_avg >= 80`,
- `callback_sla >= 85%`,
- `critical_complaints = 0`,
- and either `repeat_share >= 30%` or `successful_reactivations >= 2`.

Bonus:
- `+0.5%` to repeat commission rate.

## 9. Fashion wholesale portfolio cadence

| State | Days since meaningful contact |
|---|---:|
| `Healthy` | `0-21` |
| `Watch` | `22-35` |
| `Risk` | `36-45` |
| `Rescue` | `46-60` |
| `Reassign Eligible` | `61+` |

## 10. Micro-feedback defaults

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

## 11. Comparative engine modes

### Default
`Seasonal Ladder`

### Optional advanced mode
`Glicko-2`

Enable only if:
- `>= 5` active managers,
- `>= 90 days` of clean data,
- stable trust and verified coverage,
- explicit product decision.
