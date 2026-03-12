# MOSAIC Score System

## 1. Роль этого файла
Этот документ фиксирует финальную safe-by-default архитектуру score-системы для `management`.

Его задача:
- снять противоречия между ранними версиями формул;
- зафиксировать финальные веса, guards и фазовую логику;
- приземлить будущую реализацию на текущий `KPD`, а не ломать уже работающий код;
- отделить production-safe слой от coaching/admin-only аналитики.

## 2. Переходный мост: KPD -> MOSAIC
В текущем коде `management/stats_service.py` уже существует рабочий `KPD`. Его не нужно удалять или заменять одним рывком.

Финальная стратегия перехода:
- `KPD` остаётся рабочей production-метрикой текущего UI;
- `MOSAIC` сначала считается в `shadow mode`;
- обе системы некоторое время живут параллельно;
- только после сверки и admin sign-off MOSAIC начинает участвовать в production-решениях.

MOSAIC не "переписывает историю", а аккуратно вырастает из текущих:
- `points`;
- `follow-ups`;
- `reports`;
- `active time`;
- `advice`;
- payout и admin-данных.

## 3. Component Readiness Registry

### 3.1 Статусы
Каждый компонент аналитической системы обязан иметь статус:
- `ACTIVE` — реально работает и может участвовать в боевых формулах;
- `SHADOW` — уже считает данные, но не влияет на деньги;
- `DORMANT` — ещё не внедрён и не имеет права штрафовать менеджера.

### 3.2 Текущий реестр

| Компонент | Статус | Комментарий |
|---|---|---|
| CRM Data Entry | `ACTIVE` | `Client`, `Report`, `Shop`, `ManagementLead` уже живут в коде |
| Points / KPD | `ACTIVE` | current production score |
| Follow-Up Tracking | `ACTIVE` | есть `ClientFollowUp` и статусная машина |
| Report Discipline | `ACTIVE` | есть `on_time / late / missing` |
| Active Time | `ACTIVE` | есть `ManagementDailyActivity` |
| Source Analysis | `ACTIVE` | есть базовая логика, но нужна новая калибровка |
| Advice System | `ACTIVE` | уже работает в `stats_service.py` |
| MOSAIC Composer | `DORMANT` | новая композиция пока не внедрена |
| IP Telephony | `DORMANT` | реального telephony integration ещё нет |
| QA Scorecard | `DORMANT` | оценки звонков пока нет |
| Portfolio Health | `SHADOW` | логика нужна, но текущая история заказов мала |
| Anti-gaming | `DORMANT` | допускается только при достаточном `N` |
| Validation Suite | `DORMANT` | до `>=3 managers` и `>=60 дней` запуск запрещён |

### 3.3 Инвариант
Если компонент `DORMANT`, его эффект равен нейтрали, а не нулю. Нулевая ось штрафует менеджера за отсутствие системы, а не за его работу.

## 4. Иерархия сигналов

### 4.1 Authoritative production layer
В боевой score-контур могут попадать только:
- `Result`;
- `SourceFairness` с low-sample guardrails;
- `Process`;
- `FollowUp`;
- `DataQuality`;
- `VerifiedCommunication`, но только после telephony maturity.

### 4.2 Bounded modifier layer
Это ограничители и корректоры:
- `trust_production`;
- `gate_cap`;
- `dampener`;
- `portfolio_bonus`.

### 4.3 Shadow / admin layer
Это сигналы для диагностики и coaching:
- `trust_diagnostic`;
- anti-gaming heuristics;
- seasonal hints;
- benchmarking;
- call QA analytics;
- velocity / consistency / anomaly views.

## 5. Финальная конфигурация осей

### 5.1 Номинальные веса

| Ось | Вес |
|---|---:|
| `Result` | 0.40 |
| `SourceFairness` | 0.10 |
| `Process` | 0.20 |
| `FollowUp` | 0.10 |
| `DataQuality` | 0.10 |
| `VerifiedCommunication` | 0.10 |

### 5.2 Phase-0 перераспределение
Пока телефония не активна, `VerifiedCommunication` считается `DORMANT`, поэтому веса перераспределяются:

| Ось | Effective weight without telephony |
|---|---:|
| `Result` | 44.4% |
| `SourceFairness` | 11.1% |
| `Process` | 22.2% |
| `FollowUp` | 11.1% |
| `DataQuality` | 11.1% |
| `VerifiedCommunication` | 0% |

Это обязательное production-safe правило, а не временная эвристика.

## 6. Последовательность расчёта

### 6.1 High-level flow
1. Посчитать оси в шкале `0..1`.
2. Взять только `ACTIVE` оси и перераспределить веса.
3. Собрать `raw_axes_score`.
4. Разделить score на более верифицированный и более чувствительный к качеству данных slices.
5. Применить `trust_production` только к чувствительному к качеству данных slice.
6. Ограничить результат через `gate_cap`.
7. Применить `dampener`.
8. Применить `portfolio_bonus`, но только через `dampener`.
9. Применить onboarding protection, если менеджер ещё в переходном режиме.

### 6.2 Нормативная формула
```text
raw_axes_score =
  sum(adjusted_weight_k * axis_k)

score_before_gate =
  verified_slice
  + trust_production * evidence_sensitive_slice

score_capped =
  min(score_before_gate * 100, gate_cap)

score_after_dampener =
  score_capped * dampener
  + portfolio_bonus * dampener

manager_score_day =
  apply_onboarding_floor(score_after_dampener, days_active)
```

### 6.3 Что нельзя нарушать
- `Result` должен оставаться доминирующей осью.
- `trust` не может обнулять уже верифицированный outcome.
- `portfolio_bonus` не может обходить дисциплинарный слой.
- `gate` отвечает за уровень подтверждённости, а не подменяет trust и dampener.

## 7. Result axis = EWR

### 7.1 Почему старая логика недостаточна
При текущей cold B2B конверсии около `2.48%` много полностью нормальных дней заканчиваются без заказа. Чистый "result by orders" делает такие дни искусственно нулевыми.

### 7.2 Финальная формула
`Result` реализуется как `EWR = Effort-Weighted Result`.

```python
def compute_ewr(
    orders: int,
    contacts_processed: int,
    revenue: float,
    *,
    conversion_baseline: float = 0.0248,
    target_weekly_revenue: float = 50_000,
) -> float:
    expected_orders = contacts_processed * conversion_baseline

    if expected_orders >= 1:
        outcome = min(2.0, orders / expected_orders)
    elif orders > 0:
        outcome = 2.0
    else:
        outcome = 0.0

    target_contacts = 80  # Нижняя ожидаемая недельная база для 2 orders/week при current conversion.
    effort = min(1.0, contacts_processed / max(1, target_contacts))
    revenue_progress = min(1.0, revenue / max(1, target_weekly_revenue))

    normalized_outcome = min(1.0, outcome / 2.0)
    ewr = 0.40 * normalized_outcome + 0.35 * effort + 0.25 * revenue_progress
    return round(min(1.0, ewr), 4)
```

### 7.3 Правила EWR
- считать по rolling window, а не по single-day volatility;
- effort не должен награждать пустую активность;
- lucky small-sample days не должны автоматически давать max result;
- revenue нормализуется мягко, чтобы единичный крупный order не ломал score.
- `target_contacts = 80/week` используется как статистический baseline для Result normalization, а не как universal stretch-target для операционного режима менеджера.

## 8. SourceFairness v2

### 8.1 Назначение
`SourceFairness` нужен, чтобы менеджер на более тяжёлой базе не выглядел автоматически хуже менеджера на тёплом входящем потоке.

### 8.2 Базовый принцип
- сравнение идёт по отношению к ожидаемой конверсии источника;
- в authoritative layer попадает только bounded и low-sample-safe версия;
- source baselines и difficulty multipliers хранятся в `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`.

### 8.3 Финальная защита от маленькой выборки
```python
def compute_sf_confidence(total_attempts: int) -> float:
    return min(1.0, total_attempts / 100)

def compute_source_fairness(score_ratio: float, total_attempts: int) -> float:
    confidence = compute_sf_confidence(total_attempts)
    sf_raw = max(0.0, min(1.0, score_ratio))
    return round((1.0 - confidence) * 1.0 + confidence * sf_raw, 4)
```

Правило интерпретации:
- `<20 attempts` — практически нейтральный режим;
- `20..99 attempts` — blended mode;
- `>=100 attempts` — full effect.

### 8.4 Когда authoritative comparison запрещён
- если нет хотя бы двух менеджеров с meaningful data;
- если source ещё не нормализован;
- если данных по source слишком мало;
- если период слишком короткий для внятного сравнения.

## 9. Process axis

### 9.1 Что входит
`Process` описывает качество прохождения рабочего потока:
- response latency в разумных пределах;
- наличие next step;
- pipeline movement;
- отсутствие бессмысленных stage regressions;
- documented handoff между действиями.

### 9.2 Почему вес стал 20%
Для маленькой команды управленческая проблема чаще проявляется не в отсутствии способностей, а в регулярности исполнения. Поэтому Process получает больший вес, но всё ещё не может доминировать над Result.

### 9.3 Что нельзя включать
- raw click count;
- активность ради активности;
- full-time pressure itself without evidence of useful work.

## 10. FollowUp axis

### 10.1 Что считается
- due follow-ups;
- completed on time;
- rescheduled with reason;
- overdue backlog;
- reactivation priority handling.

### 10.2 Нейтраль при нуле задач
Если у менеджера нет due follow-ups в окне, ось не падает к нулю и считается нейтральной.

### 10.3 Лимит физической пропускной способности
`MAX_FOLLOWUPS_PER_DAY = 25` обязателен.

Избыточное количество задач:
- не превращается в автоматический дисциплинарный провал;
- перераспределяется;
- поднимает admin alert, если перегрузка системная.

## 11. DataQuality axis

### 11.1 Что входит
- обязательные причины для слабых исходов;
- валидный next step;
- отсутствие impossible sequences;
- отсутствие шаблонного batch logging;
- чистота критичных CRM-полей.

### 11.2 Что explicitly исключено
`website_url` не входит в боевой DataQuality score, пока это поле не стало реально используемым и массово заполняемым.

### 11.3 Главные red flags
- missing reason after negative outcome;
- follow-up without due date;
- repeated copy-paste notes;
- suspicious batch logging;
- unresolved duplicate conflict.

## 12. VerifiedCommunication axis

### 12.1 Статус по умолчанию
До подключения IP-телефонии эта ось находится в статусе `DORMANT`.

### 12.2 Что будет считаться после активации
- provider-confirmed calls;
- call duration and connect outcomes;
- QA-reviewed calls;
- voice-backed evidence for disputes.

### 12.3 Запреты до активации
Нельзя:
- считать ось нулевой;
- включать её в production payroll-safe scoring;
- использовать её внутри dampener.

## 13. Production Trust и Diagnostic Trust

### 13.1 Production Trust
Боевой trust должен быть узким, объяснимым и некарательным.

```python
def compute_trust_production(
    report_integrity: float,
    reason_quality: float,
    duplicate_abuse: float,
    anomaly_penalty: float,
    *,
    verified_ratio: float | None = None,
    qa_reliability: float | None = None,
    telephony_active: bool = False,
    qa_active: bool = False,
) -> float:
    base = 0.97
    base += 0.04 * report_integrity
    base += 0.02 * reason_quality
    base -= 0.05 * duplicate_abuse
    base -= 0.05 * anomaly_penalty

    if telephony_active and verified_ratio is not None:
        base += 0.04 * verified_ratio
    if qa_active and qa_reliability is not None:
        base += 0.02 * qa_reliability

    return round(max(0.85, min(1.05, base)), 4)
```

### 13.2 Diagnostic Trust
`trust_diagnostic` нужен только для admin/coaching:
- смотрит на 90-day window;
- может использовать Beta/ratio-style trend;
- не влияет на деньги напрямую.

## 14. Gate model

### 14.1 Финальные уровни current phase

| Уровень | Доказательство | Gate |
|---|---|---:|
| `Paid` | order / invoice / склад / 1С | 100 |
| `Admin-confirmed` | CRM + подтверждённый внешний след | 78 |
| `CRM-timestamped` | событие в CRM с системным timestamp | 60 |
| `Self-reported only` | статус без внешнего подтверждения | 45 |

### 14.2 Смысл gate
Gate отвечает только за уровень подтверждённости результата. Это не trust, не discipline score и не consequence ladder.

## 15. Финальный dampener

### 15.1 Логика
Dampener смотрит на количество критически слабых operational axes, а не на абстрактное среднее.

### 15.2 Формула
```python
def compute_dampener_final(process_val: float, followup_val: float, dq_val: float) -> float:
    active = [process_val, followup_val, dq_val]
    below_count = sum(1 for value in active if value < 0.20)
    dampener = max(0.85, 1.0 - 0.05 * below_count)

    if all(value < 0.20 for value in active):
        dampener = 0.80

    return round(dampener, 4)
```

### 15.3 Что важно
- `VerifiedCommunication` не участвует, пока она DORMANT;
- `portfolio_bonus` проходит через dampener;
- dampener не должен быть скрытым способом обнулить score.

## 16. Специальные guards

### 16.1 Onboarding floor
- `1..14` день: floor active;
- `15..28` день: floor линейно затухает;
- `29+` день: стандартный режим.

### 16.2 Weekend / excused / tech failure
- штрафные дисциплинарные проверки не применяются на нерабочие и excused дни;
- при `TECH_FAILURE` и `Force Majeure` score и trust freeze, а не деградируют;
- weekly activity может видеть эти дни, но daily judgement должен учитывать статус дня.

### 16.3 Single-manager mode
Если meaningful data есть фактически только у одного менеджера, межменеджерные сравнения не используются как authoritative input.

### 16.4 Статистические guards
- `MIN_OBSERVATIONS_GAMING = 20`;
- `MIN_DAYS_FOR_EWMA = 42`;
- `MIN_ORDERS_INDIVIDUAL = 5`;
- seasonality stays `DORMANT` until real calibration.

## 17. Shadow rollout
- manager UI может видеть decomposition, Radar preview и recovery hints;
- admin UI видит одновременно current `KPD` и shadow `MOSAIC`;
- расчётные данные складываются в nightly snapshots для сверки.

## 18. Приземление в текущий код

### 18.1 Основные точки будущего внедрения
- `management/stats_service.py` — расчёт осей, KPD bridge, shadow MOSAIC payload;
- `management/models.py` — snapshots, status models, optional evidence models;
- `management/stats_views.py` — manager/admin score surfaces;
- `management/templates/management/stats.html` — Radar, decomposition, shadow labels;
- `management/templates/management/admin.html` — admin diagnostics, readiness state, freeze/review controls;
- `management/management/commands/` — nightly score computation.

### 18.2 Что нельзя делать в коде
- нельзя удалять текущий `KPD` до успешной shadow-сверки;
- нельзя делать MOSAIC единственным источником payroll-истины на первом проходе;
- нельзя зашивать в боевые формулы компоненты, которых ещё нет в проде.
