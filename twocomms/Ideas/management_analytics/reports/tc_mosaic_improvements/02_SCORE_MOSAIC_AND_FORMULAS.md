# 02. Углубление MOSAIC, EWR, trust, gates и churn-логики

## 1. Что в текущем score-layer уже сильно
Сильные стороны пакета:
- `Result` остаётся доминирующей осью;
- `DORMANT` оси не наказывают менеджера;
- trust не может обнулить verified outcome;
- gate отделён от trust и discipline;
- `EWR` мягко учитывает cold B2B reality;
- `Weibull + logistic fallback + planned gap` уже намного лучше линейной churn-паники;
- `Wilson` возвращён как admin/shadow diagnostic.

Это значит, что score-ядро ломать не надо. Его нужно **сделать точнее и менее неоднозначным**.

## 2. Главные gaps score-layer

### 2.1 Не до конца формализован split между `verified_slice` и `evidence_sensitive_slice`
Это самый неприятный пробел. Концепция правильная, но код без явного mapping почти наверняка разъедется между разработчиками.

### 2.2 `score_confidence` пока больше идея, чем математический контракт
А без этого admin decision safety остаётся partly implicit.

### 2.3 `EWR` всё ещё можно слегка переоценить при долгом пустом grind-е
Текущая формула спасает cold-cycle, но может быть слишком мягкой для менеджера, который долго давит объём без признаков progression.

### 2.4 `SourceFairness` пока не различает тяжёлую назначенную базу и сознательный cherry-picking тёплых источников
Это риск системной несправедливости и скрытого гейминга одновременно.

### 2.5 Churn-model не даёт явного confidence layer
А это нужно, чтобы rescue-top-5 не маскировался под точную математику там, где история слишком мала.

## 3. Главная рекомендация: не менять production-formula резко, а добавить shadow-v2 слой
Я не рекомендую сразу переписывать MOSAIC v1.
Я рекомендую сделать:
- `mosaic_v1_authoritative` — текущий пакет;
- `mosaic_v2_shadow_candidate` — улучшенный контракт для validation;
- сравнивать их в nightly snapshots;
- переводить в production только после bounded validation.

## 4. Что именно я бы улучшил в score-layer

### 4.1 Явный `axis_to_slice_contract`
Нужна таблица вида:

| Axis / subcomponent | Verified slice | Evidence-sensitive slice | Notes |
|---|---:|---:|---|
| Paid outcome | 100% | 0% | strongest truth |
| Admin-confirmed commercial milestone | 60% | 40% | bounded, not equal to paid |
| CRM-only progress | 0% | 100% | fully data-sensitive |
| Revenue from verified orders | 100% | 0% | if invoice/payment confirmed |
| Effort term | 0% | 100% | never verified truth by itself |
| SourceFairness | 0% | 100% | depends on normalization quality |
| Process / FollowUp / DQ | 0% | 100% | discipline-sensitive |
| VerifiedCommunication | phase-dependent | phase-dependent | only after telephony maturity |

Без такой таблицы trust/gate будет трактоваться по-разному.

### 4.2 Явная формула `score_confidence`
Рекомендую такой стартовый контракт:

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

Где:
- `verified_coverage` = доля score-sensitive событий, у которых есть external/admin-confirmed evidence;
- `sample_sufficiency` = насыщение к `1.0` по working-day history и usable event count;
- `stability` = 1 - normalized volatility of rolling mosaic/ewr;
- `recency` = штраф за stale snapshot / stale evidence.

Это не ломает пакет и даёт admin слою честную confidence semantics.

### 4.3 `EWR-v2` как shadow-кандидат
Текущий `EWR` я бы не выбрасывал. Но я бы параллельно тестировал более устойчивый вариант:

```python
def compute_ewr_v2(
    orders: int,
    contacts_processed: int,
    revenue: float,
    rolling_verified_progress_ratio: float,
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

    orders_term = min(1.0, outcome / 2.0)
    effort_raw = min(1.0, contacts_processed / max(1, target_contacts))
    effort_quality_factor = 0.75 + 0.25 * max(0.0, min(1.0, rolling_verified_progress_ratio))
    effort_term = effort_raw * effort_quality_factor
    revenue_term = min(1.0, (revenue / max(1, target_weekly_revenue)) ** 0.5)

    ewr = 0.42 * orders_term + 0.30 * effort_term + 0.28 * revenue_term
    return round(min(1.0, ewr), 4)
```

Почему этот вариант лучше как shadow test:
- он сохраняет cold-safe neutral logic;
- effort не collapses to zero;
- но долгий пустой volume grind начинает стоить чуть меньше;
- revenue term становится действительно “soft”, а не линейным.

### 4.4 EWMA только по рабочим дням
Сейчас принцип правильный, но в реализации нужно не забыть:
- `WEEKEND / HOLIDAY / VACATION / SICK / TECH_FAILURE / FORCE_MAJEURE` не должны ухудшать rolling signals;
- decay guard не должен срабатывать после серии excused days;
- лучше считать rolling по **working observations**, а не по calendar entries.

### 4.5 SourceFairness: assigned vs chosen
Рекомендую разделить два режима:

#### Режим A — `assignment_fairness`
Для случаев, где source mix реально выдан системой/админом.

#### Режим B — `self_selected_mix`
Для случаев, где менеджер сам смещается в тёплые/удобные источники.

В production `SourceFairness` должна вознаграждать только тяжесть реально полученной базы, но не reward-ить сознательный cherry-picking.

### 4.6 `SourceFairness` считать по meaningful/resolved attempts
Не по всем касаниям подряд, а только по:
- meaningful contacts;
- resolved attempts;
- attempts с нормализованным source.

Иначе можно artificially inflate confidence на шуме.

### 4.7 Trust: нейтральный диапазон должен быть действительно нейтральным
Текущая узкая production clamp `[0.85, 1.05]` правильная.
Но я рекомендую уточнить business rule:
- **ACCEPTABLE Phase-0 data = примерно trust 1.00, а не системный бонус**;
- >1.00 менеджер получает только за реально сильную integrity picture;
- penalties ниже 1.00 требуют minimum N и repeat pattern.

Практически это значит:
- либо чуть опустить `TRUST_BASE`,
- либо ввести `neutral calibration target`,
- либо ограничить positive uplift без telephony/QA maturity.

### 4.8 Gate ladder стоит слегка уточнить, а не переписывать
Я бы не ломал `100 / 78 / 60 / 45`, но добавил **sub-ladder для admin/shadow layer**:
- `Paid = 100`
- `Invoice/warehouse-reserved / externally evidenced near-close = 88-90`
- `Admin-confirmed commercial progress = 78`
- `CRM timestamped = 60`
- `Self-reported only = 45`

Это улучшит explainability и rescue/admin surfaces, не делая payout truth грязнее.

### 4.9 Dampener: production оставить, но добавить diagnostic debt signal
Production dampener уже безопасный.
Но admin-only слой можно усилить через `discipline_debt_10d`, который:
- не меняет деньги;
- показывает repeated weak-axis pattern;
- помогает увидеть chronic process debt раньше.

### 4.10 Churn model: нужен `churn_confidence`
Рекомендую рядом с `P(churn)` хранить:

```python
churn_confidence = min(1.0, max(0.0,
    0.50 * min(1.0, order_count / 8)
    + 0.25 * interval_consistency
    + 0.25 * data_freshness
))
```

Тогда:
- `Expected LTV Loss` остаётся главным числом;
- но rescue widget и admin смогут видеть, где это strong estimate, а где proxy.

### 4.11 `Expected LTV Loss` как primary sort, actionability как tiebreaker
Чтобы не ломать логику пакета, я бы не менял primary metric.
Я бы добавил толькo tie-break:
- primary sort = `Expected LTV Loss`
- tiebreak = `rescue_actionability`
- final UI badge = `confidence`

Это улучшит практическую полезность top-5 без отхода от current design.

## 5. Новые безопасные сигналы, которые стоит добавить только в SHADOW/ADMIN
- `discipline_debt_10d`
- `churn_confidence`
- `source_mix_self_selection_flag`
- `ewr_v1_vs_v2_delta`
- `score_confidence`
- `stale_snapshot_flag`

## 6. Наиболее вероятные формульные баги без этих улучшений

### Bug 1 — разные разработчики по-разному поймут slices
Итог: разный trust impact на одинаковый score.

### Bug 2 — календарные выходные будут портить rolling logic
Итог: после отпуска или больничного менеджер “проседает” без реальной вины.

### Bug 3 — SourceFairness reward-ит self-selected warm mix
Итог: fairness layer начинает искажать fairness.

### Bug 4 — churn выглядит точным там, где это прокси
Итог: rescue queue визуально слишком уверенная.

## 7. Что менять в каких файлах
- `02_MOSAIC_SCORE_SYSTEM.md` — slices, score_confidence, shadow-v2 protocol
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md` — новые constants и confidence defaults
- `15_ADMIN_ECONOMICS_AND_EARNED_DAY.md` — validation reading of confidence
- `11_PRODUCT_BACKLOG_FOR_MANAGEMENT_SUBDOMAIN.md` — новые service functions
- `stats_service.py` — реальная реализация
- `NightlyScoreSnapshot` — новые fields

## 8. Очерёдность внедрения
1. slice contract
2. score confidence
3. working-day EWMA
4. SourceFairness hardening
5. EWR-v2 shadow comparison
6. churn confidence
