# Calibration Defaults and Presets

## 1. Роль этого файла
Этот файл является единым реестром стартовых чисел, guard-значений и preset-логики для management analytics.

Главное правило:
- всё, что влияет на формулы и thresholds, должно быть перечислено здесь;
- всё, что не прошло сверку с кодом, хостингом и current data reality, сюда не попадает.

## 2. Operating modes

| Mode | Min daily contacts | Target contacts | New paid / week | Total orders / week |
|---|---:|---:|---:|---:|
| `TESTING` | 10 | 20 | 1 | 1 |
| `NORMAL` | 15 | 35 | 1 | 2 |
| `HARDCORE` | 20 | 50 | 2 | 3 |

## 3. Core commercial defaults

| Константа | Значение | Комментарий |
|---|---:|---|
| `NEW_ORDER_RATE` | `2.5%` | бизнес-инвариант |
| `REPEAT_ORDER_RATE` | `5.0%` | бизнес-инвариант |
| `CONVERSION_BASELINE` | `0.0248` | ориентир из текущих данных |
| `TARGET_WEEKLY_REVENUE` | `50_000` грн | базовый target для `EWR` |
| `TARGET_CONTACTS_WEEK` | `80` | статистический baseline для `EWR`, не равен stretch-target из operating modes |

## 4. MOSAIC nominal weights

| Ось | Вес |
|---|---:|
| `Result` | `0.40` |
| `SourceFairness` | `0.10` |
| `Process` | `0.20` |
| `FollowUp` | `0.10` |
| `DataQuality` | `0.10` |
| `VerifiedCommunication` | `0.10` |

## 5. Source defaults

| Source | Baseline conversion | Difficulty multiplier |
|---|---:|---:|
| `prom.ua` | `0.030` | `1.00` |
| `google_maps` | `0.020` | `1.15` |
| `instagram` | `0.015` | `1.25` |
| `recommendations` | `0.080` | `0.85` |
| `repeat_client` | `0.150` | `0.70` |
| `other` | `0.020` | `1.00` |

## 6. Points defaults

| Outcome | Points | Source-adjusted |
|---|---:|---|
| `ORDER` | 45 | yes |
| `XML_CONNECTED` | 35 | yes |
| `TEST_BATCH` | 25 | yes |
| `WAITING_PAYMENT` | 20 | yes |
| `CP_SENT / SENT_EMAIL` | 15 | yes |
| `THINKING` | 10 | yes |
| `SENT_MESSENGER` | 8 | yes |
| `WROTE_IG` | 6 | yes |
| `EXPENSIVE` | 4 | no |
| `NO_ANSWER` | 4 | no |
| `NOT_INTERESTED` | 3 | no |
| `INVALID_NUMBER` | 2 | no |
| `OTHER` | 2 | no |

### 6.1 Production targets
- `TARGET_POINTS_DAY = 120`
- `COMM_NORMALIZATION = 2.5`
- `MIN_HOURS_FOR_EFFICIENCY = 4`

## 7. SourceFairness confidence guards

| Константа | Значение |
|---|---:|
| `SF_NEAR_NEUTRAL_UNDER` | `20 attempts` |
| `SF_FULL_CONFIDENCE_AT` | `100 attempts` |
| `SF_MANAGER_COMPARISON_MIN_MANAGERS` | `2` |

## 8. Gate defaults

| Level | Gate |
|---|---:|
| `Paid` | `100` |
| `Admin-confirmed` | `78` |
| `CRM-timestamped` | `60` |
| `Self-reported only` | `45` |

## 9. Trust defaults

| Константа | Значение |
|---|---:|
| `TRUST_PRODUCTION_MIN` | `0.85` |
| `TRUST_PRODUCTION_MAX` | `1.05` |
| `TRUST_BASE` | `0.97` |
| `TRUST_REPORT_INTEGRITY_WEIGHT` | `0.04` |
| `TRUST_REASON_QUALITY_WEIGHT` | `0.02` |
| `TRUST_DUPLICATE_ABUSE_WEIGHT` | `-0.05` |
| `TRUST_ANOMALY_WEIGHT` | `-0.05` |

## 10. Dampener defaults

| Константа | Значение |
|---|---:|
| `WEAK_AXIS_THRESHOLD` | `0.20` |
| `DAMPENER_STEP` | `0.05` |
| `DAMPENER_FLOOR` | `0.85` |
| `TOTAL_COLLAPSE_DAMPENER` | `0.80` |

Правило:
- считаются только активные operational axes;
- `VerifiedCommunication` не участвует, пока она `DORMANT`.

## 11. Follow-up defaults

| Константа | Значение |
|---|---:|
| `MAX_FOLLOWUPS_PER_DAY` | `25` |
| `FOLLOWUP_SLA_TARGET` | `80%` |
| `OVERDUE_ESCALATION_LEVEL_1` | `2` |
| `OVERDUE_ESCALATION_LEVEL_2` | `5` |
| `OVERDUE_ESCALATION_LEVEL_3` | `10` |

## 12. DMT / Earned Day defaults

### 12.1 Phase 0
- `DMT_MIN_CRM_CONTACTS = 5`
- `DMT_MIN_CRM_UPDATES = 1`

### 12.2 Phase 1+
- Phase 0 rules остаются;
- `DMT_MIN_MEANINGFUL_CALLS = 2`
- `MEANINGFUL_CALL_SECONDS = 30`

## 13. Onboarding defaults

| Константа | Значение |
|---|---:|
| `ONBOARDING_DAYS_FULL_PROTECTION` | `14` |
| `ONBOARDING_DECAY_DAYS` | `14` |
| `ONBOARDING_FLOOR_SCORE` | `40` |

## 14. Portfolio defaults

### 14.1 Default health thresholds

| State | Days |
|---|---:|
| `Healthy` | `0-35` |
| `Watch` | `35-55` |
| `Risk` | `55-75` |
| `Rescue` | `75+` |

### 14.2 Dynamic health guards

| Константа | Значение |
|---|---:|
| `MIN_ORDERS_FOR_INDIVIDUAL_HEALTH` | `5` |
| `MIN_HEALTH_DAYS_FLOOR_HEALTHY` | `7` |
| `MIN_HEALTH_DAYS_FLOOR_WATCH` | `14` |
| `MIN_HEALTH_DAYS_FLOOR_RISK` | `21` |

## 15. Payroll safety defaults

| Константа | Значение |
|---|---:|
| `SOFT_FLOOR_CAP_AMOUNT` | `120_000` грн |
| `SOFT_FLOOR_RATE_SHORTFALL_1` | `4.5%` |
| `SOFT_FLOOR_RATE_SHORTFALL_2PLUS` | `3.5%` |

## 16. Statistical guards

| Константа | Значение |
|---|---:|
| `MIN_OBSERVATIONS_GAMING` | `20` |
| `MIN_DAYS_FOR_EWMA` | `42` |
| `EWMA_HALF_LIFE_DAYS` | `21` |
| `EWMA_LAMBDA_FLOOR` | `0.05` |
| `MIN_MANAGERS_FOR_VALIDATION` | `3` |
| `MIN_DAYS_FOR_VALIDATION` | `60` |

## 17. Seasonality defaults
Seasonality stays `DORMANT` by default.

Правило:
- до накопления достаточной истории `seasonal_index = 1.0`;
- seasonal coefficients не участвуют в production payroll-safe logic.

## 18. Day status defaults
- `WORKING`
- `WEEKEND`
- `EXCUSED`
- `TECH_FAILURE`
- `FORCE_MAJEURE`

## 19. Freeze / review defaults

| Константа | Значение |
|---|---:|
| `MAX_APPEALS_PER_WEEK_FOR_SCORING` | `3` |
| `DATA_INTEGRITY_APPEALS_LIMIT` | unlimited with review |
| `RED_CARD_DEFAULT` | freeze, not automatic trust drop |

## 20. Execution defaults

Нормативный background stack:
- `management commands + cron`
- `FileBasedCache`
- DB snapshots / DB queues

Что считается invalid default:
- hard dependency on `Redis`
- hard dependency on `Celery`
- hard dependency on `pg_trgm`

## 21. Что делать при изменении констант
Любое изменение из этого файла должно:
- быть задокументировано в decision log;
- иметь явный reason;
- не включаться silently в production payroll logic;
- отражаться в future implementation plan и tests.
