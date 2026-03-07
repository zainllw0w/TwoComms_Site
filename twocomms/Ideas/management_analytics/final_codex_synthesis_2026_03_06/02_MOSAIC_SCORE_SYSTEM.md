# MOSAIC Score System

## 1. Что изменено после Opus-аудита

После разбора `opus_4.6_codex_final_synthesis_report.md` я усилил MOSAIC в тех местах, где критика была справедливой:
- добавил конкретные стартовые числа и пресеты,
- сделал `Result` revenue-aware,
- вернул micro-feedback, но без превращения всей системы в event-chaos,
- зафиксировал phase-dependent verified weighting,
- добавил adaptive recalibration для source baselines,
- оставил `Seasonal Ladder` базой и добавил `Glicko-2` как optional advanced layer, а не как mandatory core.

## 2. Три слоя score

### 2.1 Authoritative layer
Это главный слой для KPI, админа, heatmap, зарплаты и review.

Его единица:
- `manager_score_day`,
- `admin_score_day`.

### 2.2 Micro-feedback layer
Это слой моментальной обратной связи для менеджера.

Он:
- показывает эффект маленьких действий в течение дня,
- не пересчитывает payroll в real time,
- не должен ломать базовую математику,
- агрегируется в оси MOSAIC ночью.

### 2.3 Comparative layer
По умолчанию используется `Seasonal Ladder`.

`Glicko-2` включается только когда:
- накоплено минимум `90 дней` достаточно чистых исторических данных,
- активных менеджеров `>= 5`,
- есть стабильный `trust` и `verified` coverage,
- команда реально хочет игровой рейтинг как отдельный слой, а не как единственную истину.

## 3. Базовая формула дня

### 3.1 Итоговая формула
`base_day = 0.40 * Result + 0.15 * SourceFairness + 0.15 * Process + 0.10 * FollowUp + 0.10 * DataQuality + 0.10 * VerifiedCommunication`

Это обновление после аудита Opus:
- `Result` усилил с `35%` до `40%`,
- `SourceFairness` снизил с `20%` до `15%`,
- потому что fairness должен защищать от несправедливости, но не затмевать коммерческий итог.

### 3.2 Почему именно так
- `Result` должен быть самым тяжёлым блоком.
- `SourceFairness` важен, но не может быть сильнее фактической коммерции.
- `Process` и `FollowUp` должны удерживать реальную повседневную работу.
- `DataQuality` и `VerifiedCommunication` делают систему устойчивой к фейку и самообману.

## 4. Result axis

### 4.1 Структура Result
`Result = 0.35 * NewPaid + 0.20 * RepeatPaid + 0.25 * WeightedRevenue + 0.20 * VerifiedMilestones`

### 4.2 Почему не чистый счётчик заказов
Одна из главных справедливых претензий в Opus-аудите:
- сделка на `500k` не может весить как сделка на `5k`,
- но и одна большая сделка не должна убивать поведенческий баланс всей системы.

### 4.3 WeightedRevenue
Вместо грубых ступенчатых множителей использую сглаженную нормализацию:

`weighted_revenue_score = min(100, 100 * sqrt(revenue_period / revenue_target_period))`

Причины выбора:
- крупная сделка даёт заметное преимущество,
- но не делает score полностью заложником крупного чека,
- уменьшается эффект случайного one-off windfall.

### 4.4 VerifiedMilestones
Чтобы не было “всё или ничего” между холодной работой и оплатой:
- подтверждённый КП,
- подтверждённый callback,
- подтверждённый invoice stage,
- подтверждённая test-growth step,
- QA-confirmed long-cycle progress,

дают вклад в `VerifiedMilestones`, но не заменяют `NewPaid` и `RepeatPaid`.

## 5. SourceFairness axis

### 5.1 Смысл
SourceFairness защищает менеджера от тупого наказания за плохую базу и одновременно поднимает требования к тем, кто работает с тёплыми или входящими лидами.

### 5.2 Стартовые baselines
Это стартовые числа, а не вечная истина.

| Source type | Starting baseline |
|---|---:|
| `cold_xml` | `1.5%` |
| `parser_cold` | `3.0%` |
| `manual_hunt` | `6.0%` |
| `warm_reactivation` | `18.0%` |
| `hot_inbound` | `30.0%` |

### 5.3 Adaptive recalibration
Чтобы baselines не застыли:
- пересмотр `1 раз в квартал`,
- только при достаточном объёме данных,
- только на verified outcomes,
- с floor/cap, чтобы не реагировать на случайный шум.

Режим recalibration:
- не ниже `-25%` и не выше `+25%` от прошлого baseline за один цикл,
- для малых выборок baseline не двигается,
- для спорных источников админ видит warning, а не auto-change.

## 6. Process axis

### 6.1 Что входит
- next action set,
- stage progression,
- CP linkage,
- approved invoice flow,
- long-cycle continuity,
- no stalled clusters,
- incoming lead response discipline.

### 6.2 Новые добавления после аудита
В эту ось теперь явно входят:
- `Lead Response Time Score`,
- `Pipeline Regression Index`,
- `Long-Cycle Deal Closure Multiplier` для verified long-cycle closes.

### 6.3 Логика long-cycle multiplier
Идею Opus принимаю, но ограничиваю:
- multiplier применяем только к verified long-cycle deals,
- нужен минимум `3` логированных взаимодействия,
- не применяем к ownership-transferred or duplicate-tainted cases,
- cap обязателен.

## 7. FollowUp axis

### 7.1 Основные сигналы
- callback on time,
- reschedule before breach,
- stale shops handled,
- test shops reviewed on time,
- rescue list handled.

### 7.2 Micro-feedback возврат
Идею Gemini здесь возвращаю, но как bounded stream:
- exact callback in tolerance window,
- late callback,
- forgotten callback,
- clean reschedule,
- meaningful reactivation.

Micro layer:
- видна менеджеру сразу,
- не идёт напрямую в payroll,
- overnight меняет итоговые оси максимум на ограниченную величину.

## 8. DataQuality axis

### 8.1 Что входит
- valid reasons,
- reason diversity,
- no duplicate stuffing,
- no blank/garbage outcomes,
- clean ownership changes,
- no suspicious overrides.

### 8.2 Конкретные red flags
После Opus-аудита фиксирую starting thresholds:
- `same_reason_share > 60%` при `n >= 10` = red flag,
- `duplicate_override_rate > 3%` = caution,
- `duplicate_override_rate > 6%` = critical,
- `manual_override_without_evidence > 2` за неделю = caution,
- `manual_override_without_evidence > 5` за неделю = critical.

## 9. VerifiedCommunication axis

### 9.1 Что входит
- email CP logs,
- telephony calls,
- system timestamps,
- follow-up completion,
- QA-reviewed outcomes,
- manager-to-client reply evidence.

### 9.2 Phase-dependent weighting
Opus справедливо указал: до телефонии этот блок нельзя требовать одинаково жёстко.

Финальное решение:

| Telephony maturity | VerifiedCommunication cap | Trust expectation |
|---|---:|---:|
| `manual_only` | `60` | низкий, но рабочий |
| `soft_launch` | `80` | средний |
| `supervised` | `100` | высокий |

То есть до зрелой телефонии система не убивает менеджеров за отсутствие ещё не внедрённого verified channel.

## 10. Gate system

### 10.1 Итоговые tiers

| Сценарий | Cap |
|---|---:|
| Есть оплаченная или админ-подтверждённая ключевая конверсия | `100` |
| Нет оплаты, но есть verified commercial progress | `78` |
| Есть только self-reported activity и слабый verified progress | `60` |
| `3+` рабочих дня без verified progress + callback breaches | `45` |

### 10.2 Важное уточнение
Это именно `рабочие`, а не календарные дни.

Это исправляет справедливую уязвимость, на которую указал Opus.

## 11. Trust coefficient

### 11.1 Формула
`trust = clamp(0.70, 1.10, 0.78 + 0.18*verified_ratio + 0.08*qa_reliability + 0.06*reason_quality - 0.06*duplicate_abuse - 0.06*anomaly_penalty)`

### 11.2 Практические пороги
Стартовые практические уровни:
- `short_call_mismatch > 8%` = caution,
- `short_call_mismatch > 15%` = critical,
- `missed_callback_rate > 15%` = caution,
- `missed_callback_rate > 25%` = critical,
- `qa_kappa < 0.60` = QA unreliable, stop punitive use,
- `qa_kappa 0.60..0.79` = coaching only,
- `qa_kappa >= 0.80` = score-safe.

## 12. Итоговые score

### 12.1 Manager
`manager_score_day = min(base_day, gate_cap) * trust_coeff + portfolio_bonus`

### 12.2 Admin
`admin_score_day = 0.80 * manager_score_day + 0.10 * roi_score + 0.10 * qa_score`

## 13. Portfolio bonus

Теперь фиксирую формулу, а не просто идею.

### 13.1 Диапазон
`portfolio_bonus = 0..10`

### 13.2 Формула
`portfolio_bonus = 4 * portfolio_health_norm + 3 * reactivation_success_norm + 2 * repeat_share_norm + 1 * orphan_discipline_norm`

### 13.3 Жёсткие условия допуска
Бонус считается только если одновременно:
- `portfolio_health >= 70`,
- `callback_sla >= 85%`,
- `critical_qa_incidents = 0`,
- `critical_duplicate_flags = 0`.

## 14. Micro-feedback stream

### 14.1 Зачем он нужен
Здесь Opus был прав: без micro-feedback теряется ощущение “живой системы”.

### 14.2 Что именно возвращаем
Manager-facing micro events:
- `+0.5` точный callback,
- `+0.2` reason with useful detail,
- `+0.1` valid instant hangup / secretary cleanup,
- `-2.0` callback with significant lateness,
- `-5.0` forgotten callback,
- `+15.0` correct invoice without rework,
- `+100.0` paid order.

### 14.3 Ограничения
- micro stream не является payroll truth,
- micro stream не является admin ranking truth,
- overnight micro contribution ограничен,
- micro events without evidence are not counted,
- для слабых команд micro stream можно отключить feature flag-ом.

## 15. Comparative layer

### 15.1 База по умолчанию
`Seasonal Ladder`

### 15.2 Advanced mode
`Glicko-2` можно включить позже как optional comparative engine:
- rating deviation растёт при неактивности,
- rating не падает просто за отпуск или outage,
- comeback после плохой недели быстрее,
- small gaps between managers не должны разъезжаться от одного случайного события.

Это соответствует пользовательскому желанию получить рейтинг “как в играх”, но без внедрения избыточной сложности в базовую версию.

## 16. Explainability

Каждый день менеджер должен видеть:
- итог,
- что толкнуло score вверх,
- что его ограничило,
- какой gate сработал,
- какой trust tier был применён,
- какие 3 действия быстрее всего поднимут tomorrow score.

Если score не объясним, он не будет принят командой.

## 17. Где брать конкретные значения

Все конкретные presets, baselines и thresholds сведены в:
- `12_CALIBRATION_DEFAULTS_AND_PRESETS.md`

MOSAIC должен иметь один центр числовых defaults.
Иначе через месяц система снова расползётся на “версии в разных файлах”.
