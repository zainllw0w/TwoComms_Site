# MOSAIC Score System

## 1. Что изменено после второго прохода Opus

После анализа `opus_4.6_codex_final_synthesis_report.md` и `opus_4.7_counter_analysis_codex_rejections.md` я усилил MOSAIC ещё раз, но не через бездумное добавление всего подряд.

В authoritative contour я включаю:
- temporal weighting через `EWMA`,
- low-sample protection для `SourceFairness`,
- Bayesian shadow recalibration для baselines,
- bounded `report_integrity` внутри trust,
- discipline floor dampener для катастрофически просевших операционных осей,
- более точные sub-signals для response latency, nurture continuity и data freshness.

В admin/coaching shadow layer я включаю:
- `conversion efficiency vs expected`,
- `mosaic velocity`,
- `workload consistency`,
- `funnel integrity`,
- `client churn risk`,
- `territory balance`.

Что я сознательно **не** включаю в authoritative formula:
- прямой `efficiency modifier` в `Result`, потому что это дублирует `SourceFairness`,
- агрессивный `LCCM x2-x3`,
- DNA-портрет как payroll truth,
- burnout-scoring,
- командный synergy bonus,
- случайные reward-механики.

## 2. Иерархия сигналов

Чтобы система осталась объяснимой и предсказуемой, все сигналы разделены на 4 класса:

### 2.1 Authoritative layer
Это единственный слой, который влияет на:
- KPI truth,
- payroll-adjacent logic,
- admin score,
- consequence ladder,
- formal manager evaluation.

### 2.2 Bounded modifier layer
Это сигналы, которые могут менять authoritative score, но только:
- в узком диапазоне,
- по заранее известным правилам,
- без резких непредсказуемых скачков.

### 2.3 Shadow / coaching layer
Это сигналы для:
- admin dashboard,
- manager hints,
- anomaly detection,
- coaching,
- roadmap decisions.

Они не должны напрямую ломать зарплату.

### 2.4 Future / backlog layer
Это идеи, которые могут быть полезны позже, но пока не должны становиться правдой production score.

## 3. Базовая формула дня

### 3.1 Итоговая формула
`base_day = 0.40 * Result + 0.15 * SourceFairness + 0.15 * Process + 0.10 * FollowUp + 0.10 * DataQuality + 0.10 * VerifiedCommunication`

### 3.2 Почему формула не меняется радикально
- `Result` остаётся главным блоком.
- `SourceFairness` защищает от плохой базы, но не доминирует над коммерцией.
- `Process` и `FollowUp` удерживают дисциплину.
- `DataQuality` и `VerifiedCommunication` не дают системе превратиться в self-reported fantasy.

## 4. Rolling aggregation and temporal precision

### 4.1 Почему равные веса плохи
Обычный `28-day average` даёт дню `-27` почти тот же смысл, что и дню `-1`.
Для управленческой аналитики это создаёт temporal bias:
- быстрый прогресс виден слишком поздно,
- свежая деградация маскируется старым хорошим хвостом.

### 4.2 Финальное решение
Для rolling trends, rolling discipline, shadow comparisons и coaching-summaries используем:

`ewma_metric = Σ(value_day * exp(-lambda * age_days)) / Σ(exp(-lambda * age_days))`

Стартовое значение:
- `lambda = 0.033`
- half-life `≈ 21 календарный день`

### 4.3 Где decay применяется
Применяется:
- в rolling MOSAIC,
- в rolling axis trends,
- в `velocity`,
- в multi-day advice,
- в monthly discipline reviews.

Не применяется:
- к сырому single-day verified event,
- к commission факту,
- к hard paid-order truth.

## 5. Result axis

### 5.1 Структура Result
`Result = 0.35 * NewPaid + 0.20 * RepeatPaid + 0.25 * WeightedRevenue + 0.20 * VerifiedMilestones`

### 5.2 WeightedRevenue
Используется сглаженная нормализация:

`weighted_revenue_score = min(100, 100 * sqrt(revenue_period / revenue_target_period))`

Это даёт:
- ощутимую награду за крупный чек,
- но без доминирования одной случайной сделки.

### 5.3 VerifiedMilestones
`VerifiedMilestones` существует, чтобы холодная B2B-работа не выглядела как ноль между первым касанием и оплатой.

Сюда могут входить:
- подтверждённый `CP sent`,
- подтверждённый callback completion,
- подтверждённый invoice stage,
- подтверждённая test-growth step,
- verified nurture continuity.

### 5.4 Nurture persistence credit
Идею о том, что долгий качественный дожим должен учитываться, я принимаю, но не в форме грубого множителя `x2-x3`.

Финальное правило:
- если paid close произошёл после `>= 21` дня в pipeline,
- есть минимум `3` осмысленных взаимодействия,
- взаимодействия распределены во времени,
- нет duplicate-taint и ownership conflict,

то внутри `VerifiedMilestones` допускается bounded persistence credit:

`persistence_credit = min(10, 4 * log2(1 + days_in_pipeline / 21))`

Это усиливает терпеливую B2B-работу, но не поощряет искусственное затягивание сделки.

## 6. SourceFairness axis

### 6.1 Смысл
SourceFairness защищает менеджера от наказания за сложный source mix и одновременно повышает планку для тёплых и входящих лидов.

### 6.2 Стартовые baselines

| Source type | Starting baseline |
|---|---:|
| `cold_xml` | `1.5%` |
| `parser_cold` | `3.0%` |
| `manual_hunt` | `6.0%` |
| `warm_reactivation` | `18.0%` |
| `hot_inbound` | `30.0%` |

### 6.3 Low-sample protection
Одна из самых справедливых претензий Opus: малые выборки нельзя трактовать как полноценную правду.

Финальное правило:
- `attempts < 5` по source-manager pair:
  - SourceFairness уходит в neutral band,
  - pair исключается из жёсткого сравнения менеджеров.
- `5 <= attempts < 12`:
  - raw score смешивается с neutral score по confidence-weight.
- `attempts >= 12`:
  - полное влияние разрешено.

Confidence blending:

`confidence = min(1, attempts / 12)`

`sf_effective = 50 * (1 - confidence) + sf_raw * confidence`

Дополнительно:
- сравнительные выводы и admin alerts строятся с опорой на Wilson interval,
- low-confidence cases должны маркироваться как `insufficient evidence`.

### 6.4 Adaptive recalibration
Пересмотр baseline всё ещё нужен.

Жёсткое production правило:
- основной baseline layer остаётся управляемым и bounded,
- hard cap `±25%` за квартал сохраняется.

### 6.5 Bayesian shadow recalibration
Opus был прав в одном важном пункте: quarterly review слишком медленный, если рынок изменился раньше.

Финальное решение:
- каждую неделю считаем `shadow posterior` по rolling `90d` verified outcomes,
- используем Beta-style update,
- production baseline не двигается сразу,
- baseline может мягко сдвигаться только если:
- `source_attempts_90d >= 60`,
- отклонение держится `>= 3` weekly snapshots подряд,
- monthly soft move не превышает `±10%`,
- quarterly hard limit остаётся `±25%`.

Итог:
- система быстрее замечает сдвиг рынка,
- но не превращается в нервную auto-recal machine.

## 7. Process axis

### 7.1 Что входит
- next action set,
- stage progression,
- CP linkage,
- approved invoice flow,
- no stalled clusters,
- nurture continuity,
- incoming lead response discipline.

### 7.2 Response latency
`Lead Response Latency` важен, но не для всех источников одинаково.

Используем его только для:
- `hot_inbound`,
- `warm_reactivation`,
- обещанных callbacks,
- admin-approved urgent follow-ups.

Стартовые bands:
- `< 5 минут` = excellent,
- `< 15 минут` = strong,
- `< 1 часа` = acceptable,
- `1-4 часа` = weak,
- `> 4 часов` = breach risk,
- `> 24 часов` = critical.

### 7.3 Pipeline regression
`Pipeline Regression Index` используем как quality signal, а не как автоматическую дубину.

Стартовая интерпретация:
- `< 0.15` = healthy,
- `0.15..0.30` = monitor,
- `> 0.30` = coaching review,
- `> 0.45` = anomaly / qualification problem.

### 7.4 Effort signal
Пользователь прав: система должна различать `15` и `100` качественных касаний.

Но прямой modifier на `Result` я не включаю, потому что это дубль `SourceFairness`.

Финальное решение:
- `meaningful effort intensity` считается как shadow signal,
- идёт в explainability и coaching,
- может слегка влиять только на `Process`, и только если:
- действия meaningful,
- нет duplicate abuse,
- нет garbage outcomes.

Положительный effect ограничен очень жёстко:
- максимум `+5` points inside Process axis,
- отрицательный effect по этому сигналу в payroll contour не применяется.

## 8. FollowUp axis

### 8.1 Основные сигналы
- callback on time,
- reschedule before breach,
- stale shops handled,
- test shops reviewed on time,
- rescue list handled.

### 8.2 Reactivation and churn
FollowUp должен оценивать не только callback punctuality, но и работу с оттоком.

Внутри follow-up logic используем:
- `reactivation success`,
- `churn risk coverage`,
- rescue discipline.

`Predictive churn signal` остаётся простым operational signal:

`churn_signal = (days_since_last_order - avg_order_interval) / max(1, avg_order_interval)`

Он не требует ML.
Он нужен для:
- sorting Action Stack,
- rescue queues,
- portfolio coaching.

## 9. DataQuality axis

### 9.1 Что входит
- valid reasons,
- reason diversity,
- no duplicate stuffing,
- no blank/garbage outcomes,
- clean ownership changes,
- no suspicious overrides,
- timely evidence-backed logging.

### 9.2 Data entry freshness
Opus справедливо напомнил: late batch logging бьёт по качеству данных.

Финальное решение:
- `data_entry_freshness` учитываем как bounded sub-signal,
- положительный effect возможен только если есть source timestamp,
- end-of-day clustered logging считается risk pattern.

Стартовая трактовка:
- `< 10 минут` = strong,
- `10-60 минут` = neutral,
- `> 60 минут` = weak,
- batch logging в конце дня = caution,
- систематический batch logging = admin review.

### 9.3 Конкретные red flags
- `same_reason_share > 60%` при `n >= 10` = red flag,
- `duplicate_override_rate > 3%` = caution,
- `duplicate_override_rate > 6%` = critical,
- `manual_override_without_evidence > 2` за неделю = caution,
- `manual_override_without_evidence > 5` за неделю = critical.

## 10. VerifiedCommunication axis

### 10.1 Что входит
- email CP logs,
- telephony calls,
- system timestamps,
- follow-up completion,
- QA-reviewed outcomes,
- manager-to-client reply evidence.

### 10.2 Phase-dependent weighting

| Telephony maturity | VerifiedCommunication cap | Trust expectation |
|---|---:|---:|
| `manual_only` | `60` | низкий, но рабочий |
| `soft_launch` | `80` | средний |
| `supervised` | `100` | высокий |

Это сохраняет fairness до полной зрелости телефонии.

## 11. Gate system

### 11.1 Итоговые tiers

| Сценарий | Cap |
|---|---:|
| Есть оплаченная или админ-подтверждённая ключевая конверсия | `100` |
| Нет оплаты, но есть verified commercial progress | `78` |
| Есть только self-reported activity и слабый verified progress | `60` |
| `3+` рабочих дня без verified progress + callback breaches | `45` |

### 11.2 Важное уточнение
Это именно `рабочие`, а не календарные дни.

Gate остаётся грубым safety layer.
Он не должен заменять более тонкую аналитику.

## 12. Trust coefficient

### 12.1 Формула
`trust = clamp(0.70, 1.10, 0.78 + 0.16*verified_ratio + 0.08*qa_reliability + 0.04*reason_quality + 0.04*report_integrity - 0.06*duplicate_abuse - 0.06*anomaly_penalty)`

### 12.2 Report integrity
Здесь я принимаю идею `IHS`, но не как психологический ярлык, а как bounded anti-inflation signal.

Используем термин:
- `report_integrity`

Смысл:
- насколько reported statuses и outcomes в resolved cases сходятся с тем, что позже подтвердилось в verified truth.

Guardrails:
- считаем только по `resolved` cases,
- минимум `20` кейсов для полноценного влияния,
- при малой выборке = neutral,
- не штрафуем за lead, который ещё открыт и не дозрел до результата.

### 12.3 Практические пороги
- `short_call_mismatch > 8%` = caution,
- `short_call_mismatch > 15%` = critical,
- `missed_callback_rate > 15%` = caution,
- `missed_callback_rate > 25%` = critical,
- `report_integrity < 0.55` при достаточной выборке = critical review,
- `report_integrity 0.55..0.70` = caution,
- `qa_kappa < 0.60` = QA unreliable, stop punitive use,
- `qa_kappa 0.60..0.79` = coaching only,
- `qa_kappa >= 0.80` = score-safe.

## 13. Discipline floor dampener

### 13.1 Зачем он нужен
Арифметическое среднее действительно может замаскировать катастрофический провал в одной операционной оси.

### 13.2 Но в production-safe виде
Я не включаю грубый штраф по всем осям.

Вместо этого использую `discipline_floor_dampener` только по rolling operational axes:
- `Process`,
- `FollowUp`,
- `DataQuality`,
- `VerifiedCommunication`, если telephony maturity `>= soft_launch`.

`Result` и `SourceFairness` сюда не входят.

### 13.3 Формула
На rolling `10 business days`:

`discipline_axes_below = count(axis < 20 for axis in operational_axes)`

`discipline_floor_dampener = max(0.85, 1 - 0.05 * discipline_axes_below)`

То есть:
- `1` проваленная ось = `-5%`,
- `2` оси = `-10%`,
- `3+` оси = максимум `-15%`.

Не применять:
- в первые `10` рабочих дней менеджера,
- на approved leave,
- при infrastructure incident,
- при manual_only verified maturity для оси `VerifiedCommunication`.

## 14. Итоговые score

### 14.1 Manager
`manager_score_day = min(base_day * discipline_floor_dampener, gate_cap) * trust + portfolio_bonus`

### 14.2 Admin
`admin_score_day = 0.80 * manager_score_day + 0.10 * roi_score + 0.10 * qa_score`

## 15. Portfolio bonus

### 15.1 Диапазон
`portfolio_bonus = 0..10`

### 15.2 Формула
`portfolio_bonus = 4 * portfolio_health_norm + 3 * reactivation_success_norm + 2 * repeat_share_norm + 1 * orphan_discipline_norm`

### 15.3 Жёсткие условия допуска
Бонус считается только если одновременно:
- `portfolio_health >= 70`,
- `callback_sla >= 85%`,
- `critical_qa_incidents = 0`,
- `critical_duplicate_flags = 0`.

## 16. Micro-feedback stream

### 16.1 Что именно возвращаем
Manager-facing micro events:
- `+0.5` точный callback,
- `+0.2` reason with useful detail,
- `+0.1` valid instant hangup / secretary cleanup,
- `-2.0` callback with significant lateness,
- `-5.0` forgotten callback,
- `+15.0` correct invoice without rework,
- `+100.0` paid order.

### 16.2 Ограничения
- micro stream не является payroll truth,
- micro stream не является admin ranking truth,
- overnight contribution ограничен,
- micro events without evidence are not counted,
- для слабых команд micro stream можно отключить feature flag-ом.

## 17. Comparative layer

### 17.1 База по умолчанию
`Seasonal Ladder`

### 17.2 Advanced mode
`Glicko-2` включается только если:
- накоплено минимум `90 дней` достаточно чистых данных,
- активных менеджеров `>= 5`,
- trust и verified coverage стабильны,
- команда реально хочет игровой comparative layer.

## 18. Shadow signals and coaching metrics

Это важный слой, который я добавляю после второго прохода Opus.

### 18.1 Conversion efficiency vs expected
Показывает, насколько менеджер конвертирует выше или ниже ожидаемого для своего source mix.

Использование:
- manager hint,
- admin coaching,
- explanation card.

Не использовать как прямой `Result` modifier, чтобы не дублировать `SourceFairness`.

### 18.2 MOSAIC velocity
`velocity = slope(rolling_mosaic, 14d)`

Использование:
- admin dashboard,
- coaching prioritization,
- trend cards.

Нулевой прямой payroll impact.

### 18.3 Workload consistency
Смотрим на вариативность meaningful work за `14d`.

Использование:
- manager hints,
- admin pattern review,
- anti-burst coaching.

Нулевой прямой payroll impact.

### 18.4 Funnel integrity
Сигнализирует, когда reported pipeline систематически не доезжает до разумной verified конверсии.

Использование:
- admin alert,
- report-integrity investigation,
- coaching queue.

Не является auto-penalty.

### 18.5 Churn risk signal
Используется для:
- Action Stack sorting,
- rescue queues,
- portfolio coaching.

### 18.6 Territory balance
Если один менеджер системно получает source mix сильно хуже/лучше других, admin должен видеть root-cause alert, а не только secondary fairness effects.

## 19. Explainability

Каждый день менеджер должен видеть:
- итог,
- что толкнуло score вверх,
- что его ограничило,
- какой gate сработал,
- какой trust tier применён,
- сработал ли discipline dampener,
- какие 3 действия быстрее всего поднимут tomorrow score.

Admin должен видеть дополнительно:
- velocity,
- conversion efficiency vs expected,
- report integrity,
- funnel integrity,
- territory balance warnings.

## 20. Где брать конкретные значения

Все concrete presets, baselines и thresholds сведены в:
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

MOSAIC должен иметь один numeric center.
Иначе через месяц система снова расползётся на “версии в разных файлах”.
