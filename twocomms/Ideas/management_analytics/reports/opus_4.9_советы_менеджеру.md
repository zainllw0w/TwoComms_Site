# 🧠 Інтелектуальна Система Динамічних Порад v2.0

> **Дата**: 07.03.2026 | **Оновлено**: 07.03.2026 v2.0
> **Ціль**: 230+ порад з індивідуальними тригерами, формулами, ескалацією, прогнозуванням
> **Принцип**: КОЖНА порада = окреме правило з точною формулою КОЛИ показувати, з ДИНАМІЧНИМИ даними

---

# 🔧 ЯДРО: Dynamic Intelligence Engine (DIE)

## Архітектура системи

```
┌──────────────────────────────────────────────────────┐
│              DYNAMIC INTELLIGENCE ENGINE              │
├──────────────────────────────────────────────────────┤
│                                                       │
│  1. DELTA CALCULATOR                                  │
│     ├── today vs yesterday (daily delta Δ)           │
│     ├── this_week vs last_week (weekly delta Δ7)     │
│     ├── trend_14d (slope of 14-day line)             │
│     └── month_projected = now + trend × remaining     │
│                                                       │
│  2. ESCALATION STATE MACHINE                          │
│     💡 Info → 🟢 Helpful → 🟡 Warning → 🔴 Critical → ⛔ Emergency │
│     Кожен совет може РОСТИ по ескалації!             │
│                                                       │
│  3. PREDICTIVE ENGINE                                 │
│     ├── forecast_score (next 7/14/30 days)           │
│     ├── forecast_revenue (based on score trend)       │
│     ├── churn_probability (per client)               │
│     └── dmt_risk (will DMT be met today?)            │
│                                                       │
│  4. PER-TIP RULE                                      │
│     Кожен совет має СВОЄ унікальне правило з:        │
│     ├── formula (точна формула тригера)               │
│     ├── threshold (порогове значення)                 │
│     ├── escalation_chain (як ескалується)             │
│     ├── cooldown (мінімум днів між повторами)         │
│     ├── channel (dashboard/telegram/push)             │
│     └── dynamic_data (які % та числа вставляти)      │
│                                                       │
│  5. TELEGRAM DELIVERY                                 │
│     ├── 09:00 — Morning brief (top 3 tips)           │
│     ├── 14:00 — DMT checkpoint (if not met)          │
│     ├── 17:00 — End-of-day summary                   │
│     └── INSTANT — ⛔ Emergency + 🔴 Critical only    │
│                                                       │
└──────────────────────────────────────────────────────┘
```

## Delta Calculator (Формули порівняння)

```python
# ═══════ CORE DELTA FORMULAS ═══════

# 1. DAILY DELTA (% зміни від вчора)
daily_delta_pct = ((today_value - yesterday_value) / max(1, yesterday_value)) × 100
# Example: "Ваша продуктивність сьогодні -54% від вчорашньої"

# 2. WEEKLY DELTA (% зміни від минулого тижня)
weekly_delta_pct = ((this_week_avg - last_week_avg) / max(1, last_week_avg)) × 100
# Example: "Конверсія цього тижня +18% порівняно з минулим"

# 3. TREND SLOPE (нахил лінійної регресії за N днів)
trend_slope = linear_regression_slope(daily_values, N_days)
# Positive = ascending, Negative = descending
# Example: "Ваш score зростає з швидкістю +0.3 бали/день"

# 4. MOVING AVERAGE (7-day rolling)
ma_7 = sum(daily_values[-7:]) / 7
ma_7_prev = sum(daily_values[-14:-7]) / 7
ma_delta = ((ma_7 - ma_7_prev) / max(1, ma_7_prev)) × 100
# Example: "Середня продуктивність за тиждень зросла на 12%"

# 5. AXIS VELOCITY (швидкість зміни осі MOSAIC)
axis_velocity = (axis_value_today - axis_value_7d_ago) / 7
# Example: "FollowUp зростає +1.5/день — продовжуйте!"

# 6. CONVERSION RATE DELTA
conv_delta = current_period_conversion - prev_period_conversion
conv_delta_pct = (conv_delta / max(0.001, prev_period_conversion)) × 100
# Example: "Конверсія впала на 35% з минулого тижня (2.1% → 1.4%)"

# 7. REVENUE PACE vs TARGET
revenue_pace = (current_revenue / days_elapsed) × total_business_days
pace_vs_target = ((revenue_pace - monthly_target) / monthly_target) × 100
# Example: "При поточному темпі revenue = 320K₴ (на 15% менше від цілі)"

# 8. PIPELINE HEALTH INDEX
phi = (active_leads × avg_stage_probability × avg_deal_value) / monthly_target
# phi > 1.0 = enough pipeline, < 0.5 = danger
# Example: "Pipeline покриває лише 45% від місячної цілі ⚠️"

# 9. EFFICIENCY RATIO (output per effort)
efficiency = revenue_attributed / max(1, total_actions)
eff_delta = ((efficiency_today - efficiency_7d_avg) / max(1, efficiency_7d_avg)) × 100
# Example: "Ефективність +23%: кожна дія приносить більше revenue"

# 10. RISK COMPOSITE SCORE
risk_score = (
    (1 - dmt_pass_rate_7d) × 30            # DMT ризик
  + max(0, -score_trend_14d × 10) × 25     # Score falling
  + (overdue_callbacks / max(1, total_callbacks)) × 20  # Callback ризик
  + (suspended_days / days_elapsed) × 15    # Stake ризик
  + (1 - conversion_rate / baseline) × 10   # Conversion ризик
)
# 0-25 = 🟢, 25-50 = 🟡, 50-75 = 🔴, 75+ = ⛔
```

## Escalation State Machine

```
Кожен тип поради має ЛАНЦЮЖОК ЕСКАЛАЦІЇ.
Якщо ситуація не покращується → порада АВТОМАТИЧНО переходить на вищий рівень.

═══════════════════════════════════════════════════════
   💡 INFO          Інформаційна. Без терміновості.
        │ +1 day if not addressed
        ▼
   🟢 HELPFUL       Корисна порада. Дія рекомендована.
        │ +2 days if situation worsens
        ▼
   🟡 WARNING       Попередження. Потребує уваги сьогодні.
        │ +1 day if continues OR metric drops further
        ▼  
   🔴 CRITICAL      Критично. Негативний вплив на score/salary.
        │ +2 days if no action
        ▼
   ⛔ EMERGENCY     Адмін повідомлений. Потрібна зустріч.
═══════════════════════════════════════════════════════

ПРИКЛАД ЕСКАЛАЦІЇ (Callback SLA):

Day 1: Callback SLA = 78% (< 80%)
  → 🟡 "Callback SLA 78%, нижче мінімуму 80%. Ризик: DMT не виконано."

Day 2: Callback SLA = 72% (still < 80%)
  → 🔴 "Callback SLA 72%, 2-й день нижче порогу! DMT за вчора: FAIL. Ставка -682₴."

Day 3: Callback SLA = 65% (worsening)
  → ⛔ "Callback SLA 65%, 3-й день! Адміну надіслано alert. Призупинено: 2,046₴."

ПРИКЛАД ЕСКАЛАЦІЇ (Конверсія):

Week 1: Conversion 1.4% (baseline 1.5%) 
  → 💡 "Конверсія (1.4%) трохи нижче baseline (1.5%). Поки норма."

Week 2: Conversion 1.0% (-29% від baseline)
  → 🟡 "Конверсія впала до 1.0% (-33% від baseline). Рекомендуємо перевірити скрипт."

Week 3: Conversion 0.6% (-60% від baseline)
  → 🔴 "Конверсія КРИТИЧНО низька: 0.6% (-60%). Це впливає на Result та revenue."

Week 4: Conversion 0.3%
  → ⛔ "Конверсія 0.3%. Адмін: потрібна зустріч. Прогноз revenue: -45K₴/міс."
```

## Структура Правила Кожного Совета

```python
# КОЖЕН СОВЕТ — це об'єкт TipRule з унікальними параметрами:

class TipRule:
    tip_id: int                    # Унікальний ID (#1 - #230)
    category: str                  # Result/SF/Process/FU/DQ/VC/DMT/Score/Efficiency
    
    # ═══ TRIGGER (коли показувати) ═══
    formula: str                   # Точна формула перевірки
    threshold: dict                # Порогові значення для кожного рівня
    check_frequency: str           # "hourly" | "daily" | "weekly"
    check_time: str                # "09:00" | "14:00" | "realtime"
    
    # ═══ ESCALATION (як ескалується) ═══
    escalation_chain: list         # [💡, 🟢, 🟡, 🔴, ⛔]
    escalation_conditions: dict    # Що має статися для переходу на вищий рівень
    de_escalation: str             # Як зняти (metric recovery)
    
    # ═══ DELIVERY (як доставляти) ═══
    channels: list                 # ["dashboard", "telegram", "push"]
    cooldown_days: int             # Мін. днів між повторами цього совета
    telegram_instant: bool         # Чи надсилати в Telegram одразу (тільки 🔴/⛔)
    
    # ═══ DYNAMIC DATA (що вставляти в текст) ═══
    dynamic_vars: list             # Які змінні вставляти: ["{delta_pct}", "{current_value}"]
    template: str                  # Текст з {placeholders}

# ПРИКЛАД:
TipRule(
    tip_id=204,
    category="Result",
    formula="daily_delta_pct(contacts) < -40",
    threshold={
        "💡": "delta < -20%",
        "🟡": "delta < -40%",
        "🔴": "delta < -60%",
        "⛔": "delta < -80% OR consecutive_drops >= 3"
    },
    check_frequency="daily",
    check_time="17:00",
    escalation_chain=["💡", "🟡", "🔴", "⛔"],
    escalation_conditions={
        "💡→🟡": "next_day delta still < -40%",
        "🟡→🔴": "2 consecutive days < -40% OR single day < -60%",
        "🔴→⛔": "3+ days OR admin_notified"
    },
    de_escalation="daily_delta_pct > 0 for 2 consecutive days",
    channels=["dashboard", "telegram"],
    cooldown_days=1,
    telegram_instant=False,  # True only for ⛔
    dynamic_vars=["delta_pct", "today_contacts", "yesterday_contacts"],
    template="Продуктивність впала на {delta_pct}% від вчора ({today_contacts} vs {yesterday_contacts} контактів). {recommendation}"
)
```

## Telegram Delivery Schedule

```
╔══════════════════════════════════════════════════════════════╗
║  TELEGRAM ІНТЕГРАЦІЯ — Розклад та Правила                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📱 09:00 MORNING BRIEF                                     ║
║  ├── Top 3 relevant tips (пріоритет: 🔴 > 🟡 > 🟢)         ║
║  ├── "Сьогодні у вас: 4 callbacks, 2 pending CP, 1 test"   ║
║  ├── "Вчорашній score: 74 (↑2). Тренд: ascending."         ║
║  └── "DMT статус: 0/5 контактів, 0/2 callbacks."           ║
║                                                              ║
║  ⏰ 14:00 DMT CHECKPOINT (тільки якщо DMT не виконано)       ║
║  ├── "⚠️ 14:00 — DMT ще не виконано!"                       ║
║  ├── "Потрібно: ще {remaining_contacts} контактів"          ║
║  └── "Callbacks: {done}/{total} (потрібно {remaining})"     ║
║                                                              ║
║  🌆 17:00 END-OF-DAY SUMMARY                                ║
║  ├── "Score сьогодні: {score} ({delta} від вчора)"          ║
║  ├── "Micro-feedback: {micro_summary}"                       ║
║  ├── "DMT: {status}. Ставка: {earned/suspended}"            ║
║  ├── "Callbacks on-time: {pct}%"                            ║
║  └── "Top 2 рекомендації на завтра: ..."                    ║
║                                                              ║
║  🚨 INSTANT (будь-коли, тільки для ⛔ та 🔴)                ║
║  ├── ⛔ DMT 3+ fails → "[УВАГА] Адміну надіслано alert"     ║
║  ├── ⛔ Score drop > 10 pts в 1 день → "КРИТИЧНЕ ПАДІННЯ"   ║
║  ├── 🔴 Забутий callback → "Забутий callback: {client}"    ║
║  └── 🔴 Pipeline = 0 → "Pipeline ПУСТИЙ!"                  ║
║                                                              ║
║  ПРАВИЛА:                                                    ║
║  ├── Max 5 повідомлень/день (INSTANT не рахується)          ║
║  ├── Cooldown: не повторювати той самий совет < 24 години    ║
║  ├── Мute hours: 21:00-08:00 (крім ⛔ Emergency)            ║
║  ├── Менеджер може /mute на 1/4/8 годин                     ║
║  └── /settings — налаштувати канали та час                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

# КАТЕГОРІЯ 1: RESULT (Конверсія та Дохід) — Tips 1-30

## 🔴→⛔ Critical (з ескалацією)

**#1** "Сьогодні **{result_actions}** дій по pipeline (вчора: **{yesterday_actions}**, Δ: **{delta_pct:+.0f}%**). {time_warning}"
- **Формула**: `result_actions = count(crm_events WHERE type IN ('status_change','cp_sent','call','order') AND date=today)`
- **Поріг ескалації**:
  - `💡 12:00`: result_actions = 0 → "Поки 0 дій. Ще є час."
  - `🟡 14:00`: result_actions = 0 → "⚠️ 14:00 без жодної дії. Ризик порожнього дня."
  - `🔴 16:00`: result_actions = 0 → "КРИТИЧНО: 16:00 і 0 дій! Score ≈ 0 за Result."
  - `⛔ 17:00 + 2 дні`: result_actions = 0 × 2 days → "Адмін сповіщений. 2 дні без дій."
- **DeEscalation**: result_actions >= 3 → reset
- **Dynamic**: delta_pct = ((today - yesterday) / max(1, yesterday)) × 100
- **Канал**: Dashboard + Telegram (🟡 at 14:00, 🔴/⛔ instant)
- **Cooldown**: 1 день (перевірка погодинна)

**#2→#3** "Вже **{days}** робочих днів без оплаченого замовлення. Gate-ліміт: ваш MAX бал = **{gate_cap}**. {recovery_hint}"
- **Формула**: `days = count(business_days WHERE paid_orders = 0 consecutive)`
- **Поріг ескалації** (АВТОМАТИЧНА ЕСКАЛАЦІЯ по днях):
  - `🟢 days = 1-2`: "Немає оплат 2 дні. Поки норма — gate не активний."
  - `🟡 days = 3`: "3 дні без оплат. Gate = 78. 1 оплата = reset!"
  - `🔴 days = 5`: "5 днів! Gate = 60. Зверніться до адміна."
  - `⛔ days = 7`: "7 днів без конверсій! Gate = 45. Адмін сповіщений."
- **Dynamic**: gate_cap = {3d: 78, 5d: 60, 7d: 45}. recovery_hint з формули
- **Канал**: Dashboard постійно + Telegram при ескалації
- **Cooldown**: показувати щодня поки active

**#4** "Тренд Result знижується **{trend_days}** днів (slope: **{slope:+.2f}**/день). Прогноз Result через 7 днів: **{predicted_result:.0f}**."
- **Формула**: `slope = linear_regression_slope(result_daily, 14). predicted = result_today + slope × 7`
- **Поріг ескалації**:
  - `💡 slope -0.2..-0.5`: "Легке зниження. Зверніть увагу."
  - `🟡 slope -0.5..-1.0`: "Тренд негативний. Рекомендуємо action plan."
  - `🔴 slope < -1.0`: "КРИТИЧНЕ падіння! Прогноз: Result {predicted:.0f} через тиждень."
  - `⛔ slope < -1.0 AND 14+ days`: "Системна проблема. Потрібна зустріч з адміністратором."
- **Dynamic**: trend_days, slope, predicted — обчислюються щодня
- **Канал**: Dashboard + Telegram weekly (🔴/⛔ instant)
- **Cooldown**: 3 дні

**#5** "Pipeline: **{pipeline_count}** активних лідів (тиждень тому: **{pipeline_7d}**, Δ: **{pipeline_delta:+d}**). {severity_msg}"
- **Формула**: `pipeline_count = count(leads WHERE status IN active_statuses). pipeline_delta = pipeline_count - pipeline_7d_ago`
- **Поріг ескалації**:
  - `💡 pipeline 10-15`: "Pipeline скорочується. Рекомендуємо додати лідів."
  - `🟡 pipeline 5-9`: "Pipeline МАЛИЙ. Ризик revenue через 2-3 тижні."
  - `🔴 pipeline 1-4`: "Pipeline КРИТИЧНО малий! Лише {count} лідів."
  - `⛔ pipeline = 0`: "Pipeline ПУСТИЙ! Revenue → 0 через 2-3 тижні. Адмін сповіщений."
- **DeEscalation**: pipeline >= 15 → reset to 💡
- **Канал**: Dashboard + Telegram для 🔴/⛔
- **Cooldown**: 1 день

## 🟡 Important

**#6** "Конверсія з холодних: **{cold_conv:.1f}%** (baseline: **{baseline:.1f}%**, Δ: **{conv_gap:+.1f}pp**). {recommendation}"
- **Формула**: `conv_gap = cold_conv - baseline. conv_ratio = cold_conv / baseline`
- **Поріг ескалації**:
  - `💡 conv_ratio 0.7-0.85`: "Трохи нижче baseline. Поки в нормі."
  - `🟡 conv_ratio 0.5-0.7`: "Конверсія на {(1-conv_ratio)*100:.0f}% нижче! Перевірте скрипт."
  - `🔴 conv_ratio < 0.5`: "Конверсія ВДВІЧІ нижче за baseline! Критична проблема."
  - `⛔ conv_ratio < 0.3 AND N >= 20`: "Конверсія аномально низька. Адмін сповіщений."
- **Dynamic**: cold_conv, baseline, conv_gap, recommendation (автоматично)
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 7 днів

**#7** "**{stalled_cp_count}** лідів з КП 'висять' більше **{avg_stalled_days:.0f}** днів. Потенційний revenue: **{potential_rev:.0f}K₴**. Перезвоніть!"
- **Формула**: `stalled_cp = leads WHERE stage='cp_sent' AND days > 7. potential_rev = sum(estimated_deal_value) × stage_probability`
- **Поріг ескалації**:
  - `🟢 count 1-2`: "Є {count} застряглих КП. Час follow-up."
  - `🟡 count 3-5`: "{count} КП без відповіді! Revenue потенціал: {rev}K₴."
  - `🔴 count > 5 OR days > 14`: "КРИТИЧНО: {count} КП заморожені {avg_days}+ днів!"
- **Канал**: Dashboard + Telegram (🔴 instant)
- **Cooldown**: 3 дні

**#8** "Найбільша угода = **{max_deal_pct:.0f}%** місячного revenue ({max_deal_value:.0f}K₴ з {total:.0f}K₴). Індекс диверсифікації: **{diversification:.0f}/100**."
- **Формула**: `max_deal_pct = (max_deal / total_revenue) × 100. diversification = 100 × (1 - HHI) // Herfindahl-Hirschman Index`
- **Поріг ескалації**:
  - `💡 max_deal_pct 40-60%`: "Залежність від однієї угоди. Диверсифікуйте."
  - `🟡 max_deal_pct 60-75%`: "⚠️ {max_deal_pct:.0f}% revenue = 1 клієнт! Ризик нестабільності."
  - `🔴 max_deal_pct > 75%`: "КРИТИЧНА залежність: {max_deal_pct:.0f}% revenue від 1 клієнта!"
- **Канал**: Dashboard
- **Cooldown**: 14 днів

**#9** "Repeat share: **{repeat_pct:.0f}%** (ціль: ≥30%). Missing revenue: ≈**{missing_rev:.0f}K₴**/міс. Комісія repeat = 5% vs 2.5% new."
- **Формула**: `repeat_pct = repeat_revenue / total_revenue × 100. missing_rev = (0.30 - repeat_pct/100) × total_revenue if repeat_pct < 30`
- **Поріг ескалації**:
  - `💡 repeat_pct 25-30%`: "Майже на цілі! Ще 1-2 повторних = бонус."
  - `🟡 repeat_pct 15-25%`: "Repeat = {repeat_pct:.0f}%. Фокус на existing clients."
  - `🔴 repeat_pct < 15%`: "Repeat КРИТИЧНО низький: {repeat_pct:.0f}%! 5% комісія не працює."
- **Dynamic**: repeat_pct, missing_rev, рекомендації по конкретних клієнтах
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 7 днів

**#10** "🎉 Вчора: **{yesterday_paid}** нових оплат (+**{paid_delta}** від позавчора)! Revenue: **{yesterday_rev:.0f}K₴**. {streak_msg}"
- **Формула**: `paid_delta = yesterday_paid - day_before_paid. streak = consecutive_days_with_paid`
- **Dynamic**: streak_msg = "Серія {streak} днів з оплатами!" if streak >= 3
- **Канал**: Dashboard + Telegram 09:00 (позитивне підкріплення)
- **Cooldown**: 1 день

**#11** "Revenue тижня: **{rev_week:.0f}K₴** / **{target:.0f}K₴** (**{pct:.0f}%** від цілі). Δ від минулого тижня: **{week_delta:+.0f}K₴** ({week_delta_pct:+.0f}%)."
- **Формула**: `pct = rev_week / target × 100. week_delta = rev_week - last_week_rev`
- **Поріг**: `🟢 pct >= 100%` (святкування) → `🟡 pct 70-99%` → `🔴 pct < 70%`
- **Канал**: Dashboard + Telegram (п'ятниця 17:00)
- **Cooldown**: 7 днів

**#12** "**{test_count}** лідів на 'тестова розкладка' (**{test_days_avg:.0f}** днів avg). Ймовірність конверсії: **{conv_prob:.0f}%**. Очікувана revenue: **{expected_rev:.0f}K₴**."
- **Формула**: `conv_prob = stage_conversion_rate('test_order'). expected_rev = test_count × conv_prob × avg_test_deal_value`
- **Канал**: Dashboard
- **Cooldown**: 5 днів

**#13** "Funnel stuck: останні **{n}** лідів не пройшли далі '{max_stage}'. Конверсія з цієї стадії: **{stage_conv:.1f}%** (норма: **{baseline_conv:.1f}%**)."
- **Формула**: `n = count(last_leads WHERE max_stage = 'interested'). stage_conv = conversions_from_stage / attempts`
- **Поріг ескалації**:
  - `🟡 n >= 8`: "Воронка застрягла. Рекомендуємо: {specific_advice}."
  - `🔴 n >= 15`: "КРИТИЧНО: {n} лідів без прогресу! Проблема у підході до продажу."
- **Dynamic**: specific_advice на основі current max_stage
- **Канал**: Dashboard + Telegram
- **Cooldown**: 5 днів

**#14** "Середній чек: **{avg_check:.0f}₴** (команда: **{team_avg:.0f}₴**, Δ: **{check_delta:+.0f}₴**, **{check_delta_pct:+.0f}%**). {advice}"
- **Формула**: `check_delta = avg_check - team_avg. check_delta_pct = (check_delta / team_avg) × 100`
- **Поріг ескалації**:
  - `💡 delta -15..-30%`: "Чек трохи нижче. Спробуйте upsell."
  - `🟡 delta -30..-50%`: "Чек на {abs(delta_pct):.0f}% нижче команди! Cross-sell?"
  - `🔴 delta < -50%`: "Чек ВДВІЧІ менше за команду! Перевірте асортимент."
- **Канал**: Dashboard weekly
- **Cooldown**: 7 днів

**#15** "Weighted Revenue Score: **{wr_score:.0f}/100** (Δ від минулого тижня: **{wr_delta:+.0f}**). Зона: **{zone}**. Revenue map: ≈**{expected_rev:.0f}K₴**/міс."
- **Формула**: `wr_delta = wr_score - wr_score_prev_week. zone = score_to_zone(wr_score). expected_rev = score_to_money(wr_score)`
- **Dynamic**: zone = 🔴/🟡/🟢/🏆, expected_rev з кореляційної таблиці
- **Канал**: Dashboard
- **Cooldown**: 7 днів

## 🟢 Helpful

**#16** "Найкращий час для closing-дзвінків для вашого портфеля: 10:00-12:00. Спробуйте планувати важливі дзвінки на цей час."
- **Тригер**: `personal_best_hours` analysis shows peak conversion window
- **Чому**: Golden Hour концепція — індивідуальний оптимум

**#17** "Ви закрили 0 нових клієнтів з категорії 'manual_hunt'. Можливо, власні пошукові ліди потребують іншого підходу."
- **Тригер**: `conversion_rate('manual_hunt') = 0 AND count >= 5`
- **Чому**: Джерело-специфічна нуль-конверсія

**#18** "Якщо закриєте ще 1 повторне замовлення цього тижня, ваш repeat_share перейде 30% — це покращить Portfolio Bonus."
- **Тригер**: `repeat_share BETWEEN 25% AND 30%` AND close to threshold
- **Чому**: Motivate through proximity to portfolio bonus threshold

**#19** "Порада: клієнти з першим замовленням 30+ днів тому мають найвищу ймовірність повторного. Зверніть увагу на 5 таких."
- **Тригер**: `count(clients WHERE first_order 30-45 days ago AND no repeat) >= 3`
- **Чому**: Window для repeat activation

**#20** "VerifiedMilestones = 42/100. Підтверджуйте КП, callbacks та invoices — вони дають бали навіть без оплати."
- **Тригер**: `verified_milestones_score < 50`
- **Чому**: Менеджер не знає що verified steps = score points

## 💡 Growth

**#21** "Цикл продажу: **{your_cycle:.0f}** днів (топ команди: **{best_cycle:.0f}**, команда avg: **{team_cycle:.0f}**, Δ: **{cycle_gap:+.0f}** днів). {speed_advice}"
- **Формула**: `cycle_gap = your_cycle - team_cycle. speed_ratio = your_cycle / best_cycle`
- **Поріг**: `💡 speed_ratio 1.0-1.3` → `🟡 1.3-1.8` → `🔴 > 1.8`
- **Dynamic**: speed_advice = "Прискорення follow-up на {shortening} днів = +{impact:.0f}K₴/міс"
- **Канал**: Dashboard weekly
- **Cooldown**: 14 днів

**#22** "Source mix цього місяця: warm **{warm_conv}** конверсій / cold **{cold_conv}** конверсій. Баланс: **{balance_ratio:.0f}%** vs optimal **70/30**."
- **Формула**: `balance_ratio = cold_conv / (warm_conv + cold_conv) × 100`
- **Поріг**: `💡 ratio < 20%` → `🟡 ratio < 10%` ("SF під загрозою") → `🔴 ratio = 0%`
- **Dynamic**: рекомендоване кількість cold calls/day
- **Канал**: Dashboard weekly
- **Cooldown**: 7 днів

**#23** "Останні **{n}** угод — всі в '{segment}'. Portfolio concentration = **{concentration:.0f}%**. Рекомендація: {diversify_to}."
- **Формула**: `concentration = same_segment_deals / total_deals × 100`
- **Поріг**: `💡 concentration > 60%` → `🟡 > 80%` → `🔴 = 100%`
- **Dynamic**: diversify_to = найменш представлений сегмент з вашого регіону
- **Канал**: Dashboard
- **Cooldown**: 14 днів

**#24** "Efficiency: **{calls_week}** дзвінків → **{conv_week}** конверсій (**{conv_rate:.1f}%**). Прогноз: +**{add_calls}** дзвінків = +**{add_conv:.1f}** конверсій = +**{add_rev:.0f}K₴**."
- **Формула**: `add_conv = add_calls × conv_rate. add_rev = add_conv × avg_deal_value`
- **Dynamic**: Лінійна проекція з поточного conversion rate
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 7 днів

**#25** "🔮 Score forecast: при поточному тренді (**{slope:+.2f}**/день) через 30 днів: **{forecast_30d:.0f}** (зараз: **{current:.0f}**, Δ: **{delta_30:+.0f}**). Revenue forecast: **{rev_forecast:.0f}K₴**."
- **Формула**: `forecast_30d = current + slope × 30. rev_forecast = score_to_money(forecast_30d)`
- **Dynamic**: slope з 14-day linear regression
- **Канал**: Dashboard + Telegram monthly
- **Cooldown**: 14 днів

**#26** "**{big_clients_count}** клієнтів з великим 1-м замовленням (>{threshold:.0f}K₴) без follow-up. Потенційний repeat revenue: **{potential:.0f}K₴**."
- **Формула**: `big_clients = clients WHERE first_order_value > 30K AND days_since > 14 AND no_followup`
- **Поріг**: `🟢 count = 1` → `🟡 count 2-3` → `🔴 count > 3`
- **Dynamic**: potential = big_clients × avg_repeat_rate × avg_order_value
- **Канал**: Dashboard + Telegram
- **Cooldown**: 7 днів

**#27** "VerifiedMilestones: **{vm_now}/100** (Δ за тиждень: **{vm_delta:+d}**). Це ≈ **{score_impact:+.1f}** балів до Result навіть без нових оплат!"
- **Формула**: `vm_delta = vm_now - vm_prev_week. score_impact = vm_delta × 0.15`
- **Dynamic**: Показує точний вплив на Result axis
- **Канал**: Dashboard
- **Cooldown**: 7 днів

**#28** "Cross-sell можливість: **{clients_count}** клієнтів з 1 категорією. Потенціал: +**{cross_sell_rev:.0f}K₴** (+**{check_increase:.0f}%** avg check)."
- **Формула**: `cross_sell_rev = clients_count × avg_cross_sell × probability. check_increase = cross_sell_rev / current_avg_check × 100`
- **Канал**: Dashboard weekly
- **Cooldown**: 14 днів

**#29** "🏆 Score **{score}** — ваш рекорд за {period}! (попередній max: **{prev_max}**, Δ: **{record_delta:+d}**). Що зробили:
{top_3_actions_today}"
- **Формула**: `record = score > max(ALL historical_scores). top_3_actions = today's biggest micro contributers`
- **Dynamic**: Автоматично визначає top-3 дії що дали найбільше micro бали
- **Канал**: Dashboard + Telegram
- **Cooldown**: once per record

**#30** "Pipeline value (weighted): **{pipeline_val:.0f}K₴** / ціль **{target:.0f}K₴** (**{coverage:.0f}%** покриття). Δ від минулого тижня: **{pipe_delta:+.0f}K₴**."
- **Формула**: `pipeline_val = Σ(lead_value × stage_probability). coverage = pipeline_val / weekly_target × 100`
- **Поріг**: `🟢 coverage > 100%` → `🟡 coverage 50-100%` → `🔴 coverage < 50%`
- **Канал**: Dashboard
- **Cooldown**: 3 дні

---

# КАТЕГОРІЯ 2: SOURCE FAIRNESS — Tips 31-50

**#31** "⚠️ 90% ваших дзвінків — з теплих лідів. SourceFairness знижується. Додайте 5 холодних на день."
- **Тригер**: `warm_share > 80%`
- **Чому**: SF axis penalizes over-reliance on warm

**#32** "Ваша конверсія з cold_xml (2.8%) вище baseline (1.5%). Відмінна робота з холодними!"
- **Тригер**: `cold_xml_conversion > baseline × 1.5`
- **Чому**: Позитивне підкріплення за складну роботу

**#33** "Новий baseline для 'parser_cold' оновлено до 3.2%. Ваша конверсія (3.5%) все ще вище — добре."
- **Тригер**: `quarterly_recalibration_applied = True`
- **Чому**: Прозорість при зміні baselines

**#34** "Ви отримали 8 inbound лідів цього тижня. Baseline для inbound = 30% конверсії. Очікується ≈ 2.4 оплати."
- **Тригер**: `inbound_leads_this_week >= 5`
- **Чому**: Показати очікування при хороших лідах

**#35** "З 12 холодних лідів конвертовано 0. Середнє для команди з холодних = 1.5%. Потрібна допомога зі скриптом?"
- **Тригер**: `cold_leads >= 10 AND cold_conversions = 0`
- **Чому**: Кілька стандартних відхилень нижче норми

**#36** "SourceFairness = 92. Ви ефективно працюєте зі всіма типами лідів — чудовий баланс."
- **Тригер**: `source_fairness_score >= 85`
- **Чому**: Визнання збалансованої роботи

**#37** "Ви обробили 5 inbound і 40 cold. Пропорція хороша. SF враховує складність кожного джерела."
- **Тригер**: source mix within expected range
- **Чому**: Transparency — менеджер розуміє як SF рахується

**#38** "Порада: manual_hunt ліди мають baseline 6%. Ваші власні пошукові контакти перспективніші ніж XML."
- **Тригер**: `manual_hunt_conversion > cold_xml_conversion × 2`
- **Чому**: Заохочення самостійного пошуку

**#39** "warm_reactivation baseline = 18%. Ви повернули 3 з 20 старих клієнтів (15%). Ще 1 — і ви на рівні норми."
- **Тригер**: `reactivation_rate BETWEEN baseline×0.7 AND baseline`
- **Чому**: Close to target motivation

**#40** "⚠️ Мало даних для SF розрахунку (тільки 4 ліда з cold_xml). Поки SF нейтральне — додайте ще контактів."
- **Тригер**: `sample_size < 10 FOR source_type`
- **Чому**: Wilson score protection → neutral

**#41** "Ви працюєте тільки з одним типом лідів. Різноманітність джерел = вищий SF і стабільніший score."
- **Тригер**: `source_types_used = 1`
- **Чому**: Monoculture risk

**#42** "Відмінно! Конверсія з 'warm_reactivation' = 25% (вище baseline 18%). Це показує сильну навичку утримання."
- **Тригер**: `reactivation_conversion >= baseline × 1.3`
- **Чому**: Skill recognition

**#43** "Порада: inbound ліди — перші 30 хвилин критичні. Ваш середній час відповіді: 2 години. Спробуйте швидше."
- **Тригер**: `avg_inbound_response_time > 60 min`
- **Чому**: Lead Response Time Score

**#44** "3 холодних ліда відмовили з причиною 'вже працюють з іншим постачальником'. Спробуйте скрипт порівняння."
- **Тригер**: `common_rejection_reason = 'competitor' AND count >= 3`
- **Чому**: Pattern-based coaching

**#45** "Ваш SF тренд ↑ 3 тижні поспіль. Збалансована робота = стабільний score — продовжуйте!"
- **Тригер**: `sf_weekly_improvement 3 consecutive weeks`
- **Чому**: Trend recognition

**#46** "CRM показує 15 lідів з типом 'unknown'. Вкажіть правильне джерело — це вплине на SF розрахунок."
- **Тригер**: `count(leads WHERE source_type='unknown') >= 5`
- **Чому**: DataQuality + SF interaction

**#47** "Порада: якщо отримуєте менше inbound за колег, SF це враховує і не штрафує вас. Фокус на якість cold."
- **Тригер**: `inbound_count < team_avg × 0.3 AND cold_count > team_avg`
- **Чому**: Fairness explanation — менеджер не винен у розподілі лідів

**#48** "Ваша конверсія з ручного пошуку (8%) — найвища в команді. Подумайте про збільшення цього каналу."
- **Тригер**: `manual_hunt_conversion = team_max`
- **Чому**: Capitalize on strength

**#49** "За тиждень ви обробили 60 контактів з 3 різних джерел. Оптимальний мікс для SF = 3-4 джерела."
- **Тригер**: `source_diversity >= 3`
- **Чому**: Good practice reinforcement

**#50** "SF Score оновлено: 71 → 75 за цей тиждень. Збалансований підхід до лідів дає результат!"
- **Тригер**: `sf_weekly_change >= 3`
- **Чому**: Progress visibility

---

# КАТЕГОРІЯ 3: PROCESS (Pipeline Management) — Tips 51-70

**#51** "⚠️ У вас 8 лідів 'заморожені' на одній стадії більше 10 днів. Перемістіть або закрийте їх."
- **Тригер**: `stalled_leads_10d >= 5`
- **Чому**: Process axis штрафує stalled clusters

**#52** "Порада: після відправки КП зателефонуйте протягом 48 годин. Ваш середній час follow-up після КП: 5 днів."
- **Тригер**: `avg_post_cp_followup > 72h`
- **Чому**: Pipeline velocity improvement

**#53** "Pipeline має 15 лідів, але 12 на стадії 'зацікавлений'. Намагайтесь просунути хоча б 3 до КП."
- **Тригер**: `pipeline_stage_concentration('interested') > 80%`
- **Чому**: Bottleneck detection

**#54** "Ви отримали новий лід 4 години тому. Перший контакт протягом 1 години = 7x вища конверсія (InsideSales.com)."
- **Тригер**: `new_lead_no_contact AND hours_since_assignment > 2`
- **Чому**: Lead Response Time Score

**#55** "Кожен лід має мати 'наступний крок'. Зараз у 6 лідів немає запланованої дії."
- **Тригер**: `leads_without_next_action >= 3`
- **Чому**: Process axis: next action set

**#56** "Long-cycle deal (клієнт 35 днів у pipeline) — це нормально для B2B. Продовжуйте nurture!"
- **Тригер**: `lead_in_pipeline > 30d AND verified_interactions >= 3`
- **Чому**: Long-Cycle Multiplier encouragement

**#57** "Порада: стадія 'negotiating' має 35% конверсії. У вас 3 ліда тут — очікується ~1 оплата."
- **Тригер**: `leads_in_negotiating >= 2`
- **Чому**: Pipeline probability awareness

**#58** "Process Score = 85 — вище за середнє! Ваш pipeline організований правильно."
- **Тригер**: `process_score >= 80`
- **Чому**: Recognition

**#59** "⚠️ 5 лідів додано сьогодні без 'наступного кроку'. Вкажіть дату callback або дію для кожного."
- **Тригер**: `today_new_leads_without_action >= 3`
- **Чому**: Process discipline

**#60** "Ви переміщуєте ліди по стадіях швидше ніж минулого тижня. Pipeline Velocity +15%!"
- **Тригер**: `pipeline_velocity_change > 10%`
- **Чому**: Positive trend recognition

**#61** "Порада: не тримайте 'мертвих' лідів. Закрийте тих, хто не відповідає 3+ тижні — це покращить Process."
- **Тригер**: `leads_no_response_21d >= 3`
- **Чому**: Pipeline hygiene

**#62** "У pipeline 25+ лідів. Це може бути забагато. Оптимум: 15-20 активних лідів одночасно."
- **Тригер**: `active_pipeline > 25`
- **Чому**: Overloaded pipeline = lower quality per lead

**#63** "КП відправлено 3 клієнтам, але жоден не переглянув email. Спробуйте зателефонувати — можливо, КП у спамі."
- **Тригер**: `cp_sent_no_open 3d >= 2` (if email tracking available)
- **Чому**: Pipeline stage verification

**#64** "Ваш Pipeline Regression Index покращився! Менше лідів повертається на попередні стадії."
- **Тригер**: `PRI_weekly_change > 0`
- **Чому**: PRI improvement recognition

**#65** "Порада: лід 'Fashion World' на стадії 'тестова розкладка' вже 12 днів. Час дізнатися результат тесту."
- **Тригер**: `specific_lead.stage = 'test' AND days > 10`
- **Чому**: Stage-specific follow-up prompt

**#66** "Ви додали КП до 4 лідів без попереднього дзвінка. КП після розмови конвертує у 3x краще."
- **Тригер**: `cp_without_prior_call >= 3`
- **Чому**: Process quality advice

**#67** "3 ваших ліда перемістились з 'зацікавлений' до 'КП відправлено' сьогодні. Process Score ↑!"
- **Тригер**: `stage_progressions_today >= 3`
- **Чому**: Real-time progress acknowledgment

**#68** "Порада: invoice stage = 55% конверсії. Якщо отримаєте invoice від 2 поточних клієнтів, прогноз: +1 оплата."
- **Тригер**: `leads_in_invoice >= 1`
- **Чому**: Pipeline probability coaching

**#69** "Pipeline порожній на наступний тиждень (0 запланованих callbacks, 0 pending CP). Заплануйте роботу!"
- **Тригер**: `next_week_planned_actions = 0`
- **Чому**: Forward planning

**#70** "Lead Response Time Score = 92. Ви відповідаєте на нових лідів швидко — це цінується системою."
- **Тригер**: `lrts >= 85`
- **Чому**: LRTS recognition

---

# КАТЕГОРІЯ 4: FOLLOW-UP (Callbacks та Утримання) — Tips 71-100

**#71** "🔴 **{overdue_count}** прострочених callbacks! (вчора: **{overdue_yesterday}**, Δ: **{overdue_delta:+d}**). FollowUp score impact: **{fu_impact:-.1f}** балів."
- **Формула**: `overdue_count = count(callbacks WHERE due_date < today AND not_completed). fu_impact = overdue_count × -2.0`
- **Поріг ескалації**:
  - `🟡 count = 1-2`: "Є {count} прострочених. Виконайте сьогодні."
  - `🔴 count 3-5`: "OVERDUE: {count} прострочених! FollowUp –{fu_impact:.1f}."
  - `⛔ count > 5 OR 3+ days`: "Адмін сповіщений. {count} overdue {days}+ днів!"
- **DeEscalation**: overdue_count = 0 → reset
- **Канал**: Dashboard + Telegram INSTANT для 🔴/⛔
- **Cooldown**: 1 день

**#72** "Callback SLA: **{sla_pct:.0f}%** (вчора: **{sla_yesterday:.0f}%**, Δ: **{sla_delta:+.0f}pp**). DMT мінімум: 80%. {dmt_risk_msg}"
- **Формула**: `sla_pct = completed_on_time / total_due × 100. sla_delta = sla_today - sla_yesterday`
- **Поріг ескалації**:
  - `🟢 sla >= 85%`: "Норма! DMT умова виконана."
  - `🟡 sla 75-84%`: "⚠️ SLA {sla_pct:.0f}%, нижче DMT (80%)! Ставка під загрозою."
  - `🔴 sla 60-74%`: "SLA КРИТИЧНО: {sla_pct:.0f}%! DMT FAIL. Ставка -682₴."
  - `⛔ sla < 60% OR 3 days < 80%`: "SLA {sla_pct:.0f}% 3-й день! Адмін alert. Призупинено: {suspended}₴."
- **Dynamic**: dmt_risk_msg = "Потрібно ще {needed} on-time callbacks" або "✅ DMT met!"
- **Канал**: Dashboard + Telegram (🟡 at 14:00, 🔴/⛔ instant)
- **Cooldown**: 1 день

**#73** "Ви забули перезвонити клієнту 'Tech Store' (запланований вчора). Перезвоніть сьогодні — micro-feedback: -2.0."
- **Тригер**: `specific_callback_overdue = yesterday`
- **Чому**: Micro-feedback awareness + specific action

**#74** "5 callbacks на сьогодні — усі виконані вчасно! FollowUp Score ↑. Micro: +2.5 бали."
- **Тригер**: `today_callbacks_all_on_time = True`
- **Чому**: Positive reinforcement micro-feedback

**#75** "Callback SLA за тиждень: 88% — вище мінімуму (85%). Прогрес!"
- **Тригер**: `weekly_callback_sla >= 85 AND was_below_85_last_week`
- **Чому**: Recovery recognition

**#76** "Порада: перенесіть callback якщо не можете зателефонувати. Перенесення = 0 штрафу. Забутий = -5.0."
- **Тригер**: `approaching_callback AND busy_schedule_detected`
- **Чому**: Reschedule vs forget — explain difference

**#77** "Клієнт 'Beauty Hub' у статусі 'Watch' (22 дні без контакту). Зателефонуйте щоб не перейшов у 'Risk'."
- **Тригер**: `client.health = 'Watch'`
- **Чому**: Portfolio health degradation prevention

**#78** "⚠️ **{risk_clients}** клієнтів у статусі 'Risk' (avg **{avg_days_silent:.0f}** днів без контакту). Churn probability: **{churn_pct:.0f}%** avg. Потенційна втрата: **{potential_loss:.0f}K₴**."
- **Формула**: `churn_pct = avg(min(100, (days_silent/expected_interval - 1) × 50 + 15)). potential_loss = sum(client_ltv) × churn_pct`
- **Поріг ескалації**:
  - `🟡 risk_clients = 1`: "1 клієнт у 'Risk'. Churn: {pct:.0f}%."
  - `🔴 risk_clients 2-3`: "{count} клієнтів у 'Risk'! Потенційна втрата: {loss}K₴."
  - `⛔ risk_clients > 3 OR any rescue`: "КРИТИЧНО: {count}+ клієнтів зникають! Revenue під загрозою."
- **Dynamic**: churn_pct, avg_days_silent, potential_loss обчислюються per-client
- **Канал**: Dashboard + Telegram для 🔴/⛔
- **Cooldown**: 3 дні

**#79** "Клієнт 'Green Market' у статусі 'Rescue' (46 днів). Якщо не зв'яжетесь протягом 14 днів — передадуть іншому."
- **Тригер**: `client.health = 'Rescue'`
- **Чому**: Reassign Eligible warning

**#80** "Ви повернули клієнта зі статусу 'Risk' до 'Healthy'! 🎉 Reactivation success = + Portfolio bonus sub-score."
- **Тригер**: `client_health_change FROM 'Risk' TO 'Healthy'`
- **Чому**: Reactivation recognition

**#81** "Callback з клієнтом 'Sport Zone' — ідеальний за часом! +0.5 micro бали."
- **Тригер**: `callback_completed_within_tolerance`
- **Чому**: Micro-feedback instant positive

**#82** "Каденс: **{your_interval:.1f}** днів avg між callbacks (оптимум: **{optimal:.0f}-{optimal2:.0f}**, дельта: **{interval_delta:+.1f}** днів). {cadence_advice}"
- **Формула**: `your_interval = avg(days_between_callbacks). interval_delta = your_interval - optimal_mid`
- **Поріг**: `💡 delta 0.5-1.5` → `🟡 delta 1.5-3.0` → `🔴 delta > 3.0`
- **Dynamic**: cadence_advice на основі B2B/B2C типу клієнтів
- **Канал**: Dashboard weekly
- **Cooldown**: 7 днів

**#83** "Порада: клієнти, яких ви 'підігріваєте' 3+ місяці, конвертують у 40% випадків (проти 15% cold). Терпіння = прибуток."
- **Тригер**: `long_cycle_leads >= 2 AND no_outcome_yet`
- **Чому**: Long-cycle encouragement with data

**#84** "Сьогодні 0 запланованих callbacks. Рекомендація: запланувати 3-5 на завтра перед кінцем дня."
- **Тригер**: `tomorrow_planned_callbacks = 0`
- **Чому**: Forward planning

**#85** "Ви перенесли callback 3 рази поспіль. Клієнт може відчути ненадійність. Зателефонуйте сьогодні."
- **Тригер**: `same_callback_rescheduled >= 3`
- **Чому**: Chronic reschedule detection

**#86** "Test-магазин 'Urban Style' активний 7 днів. Перевірте продажі та запропонуйте розширити асортимент."
- **Тригер**: `test_store_active_days >= 7`
- **Чому**: Test → Full conversion window

**#87** "4 клієнти не відповіли на останній дзвінок. Спробуйте інший канал: SMS або Telegram."
- **Тригер**: `unanswered_callbacks_in_row >= 2 FOR client`
- **Чому**: Channel switching advice

**#88** "Portfolio Health: 78% — вище порогу для Portfolio Bonus (70%). Утримуйте!"
- **Тригер**: `portfolio_health >= portfolio_bonus_threshold`
- **Чому**: Threshold awareness

**#89** "Repeat reactivation цього місяця: 4 клієнта повернулись. Це дає +3 до portfolio_bonus. 💰"
- **Тригер**: `reactivation_count >= 3`
- **Чому**: Portfolio bonus sub-score recognition

**#90** "⚠️ Забутий callback — micro: -5.0 балів. Щоб відновити, потрібні 10 ідеальних callbacks."
- **Тригер**: `forgotten_callback_event`
- **Чому**: Show magnitude of forgotten vs on-time

**#91** "Порада: запланований callback на 09:00 — це занадто рано для деяких клієнтів. Оптимум: 10:00-11:00."
- **Тригер**: `callback_scheduled < 09:30`
- **Чому**: Best-time coaching

**#92** "Ви виконали 100% callbacks вже 5 днів поспіль! Серія ✅ — FollowUp Score стабільно зростає."
- **Тригер**: `consecutive_100pct_callback_days >= 5`
- **Чому**: Streak recognition

**#93** "🔮 Churn alert: '{client_name}' замовляв кожні **{expected_interval}** днів. Вже **{actual_days}** (Δ: **{overdue:+d}**). Churn probability: **{churn_pct:.0f}%**. Revenue risk: **{risk_rev:.0f}K₴**."
- **Формула**: `churn_pct = min(100, (actual_days/expected_interval - 1) × 50 + 15). risk_rev = client_avg_order × expected_orders_year`
- **Поріг ескалації**:
  - `🟢 churn 15-30%`: "Час нагадати про себе."
  - `🟡 churn 30-60%`: "Затримка! Клієнт '{name}' може піти."
  - `🔴 churn 60-85%`: "КРИТИЧНО: '{name}' churn {pct:.0f}%! Revenue risk: {rev}K₴."
  - `⛔ churn > 85%`: "'{name}' майже втрачений! Останній шанс зателефонувати."
- **Dynamic**: per-client формула churn, risk_rev з LTV
- **Канал**: Dashboard + Telegram для 🔴/⛔
- **Cooldown**: 3 дні per client

**#94** "Порада: після оплати нового замовлення — зателефонуйте через 7 днів. 'Як товар? Що ще потрібно?'"
- **Тригер**: `paid_order recent AND no_post_sale_followup`
- **Чому**: Retention best practice

**#95** "Orphan alert: клієнт 'Light Store' не має запланованих дій і немає менеджера-responsibility. Візьміть або передайте."
- **Тригер**: `client.has_no_owner OR client.has_no_next_action`
- **Чому**: Orphan client discipline

**#96** "FollowUp trend: **{fu_w1:.0f}**→**{fu_w2:.0f}**→**{fu_w3:.0f}** за 3 тижні (Δ: **{fu_total_delta:+.0f}**). Вплив на MOSAIC: ≈**{mosaic_impact:+.1f}** балів. {trend_msg}"
- **Формула**: `fu_total_delta = fu_w3 - fu_w1. mosaic_impact = fu_total_delta × fu_weight. trend_msg = "↑ ascending" if ascending else "↓ FALLING"`
- **Поріг**: `🟢 ascending 3w` (позитивне) → `🟡 descending 2w` → `🔴 descending 3w`
- **Dynamic**: Точний вплив на MOSAIC score
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 7 днів

**#97** "Порада: callback у п'ятницю після 16:00 рідко відповідають. Перенесіть на понеділок ранок."
- **Тригер**: `callback_scheduled Friday after 16:00`
- **Чому**: Statistical pattern → practical advice

**#98** "Сьогодні виконали callback з результатом 'Замовив!' 🎉 +100 micro балів! Відмінна робота."
- **Тригер**: `callback_result = 'ordered'`
- **Чому**: Maximum micro-feedback event

**#99** "Ваша 'persistence' з складними лідами = 71/100. B2B вимагає 7-12 контактів — не здавайтеся рано!"
- **Тригер**: `persistence_score < 75 AND early_abandonments >= 3`
- **Чому**: Persistence encouragement

**#100** "Callback SLA за місяць: 86%. Мінімум для Portfolio Bonus: 85%. Тримайтесь!"
- **Тригер**: `monthly_callback_sla BETWEEN 85% AND 90%`
- **Чому**: Proximity to bonus threshold

---

# КАТЕГОРІЯ 5: DATA QUALITY (CRM Гігієна) — Tips 101-125

**#101** "🔴 **{same_reason_pct:.0f}%** ваших причин відмови = '{top_reason}' (вчора: **{prev_pct:.0f}%**, Δ: **{delta:+.0f}pp**). Поріг red flag: >50%. {action}"
- **Формула**: `same_reason_pct = count(reasons = top_reason) / total_reasons × 100`
- **Поріг ескалації**:
  - `🟡 pct 40-55%`: "Причини одноманітні. Додайте деталі."
  - `🔴 pct 55-75%`: "RED FLAG: {pct:.0f}% однакові! Trust під загрозою."
  - `⛔ pct > 75%`: "КРИТИЧНО: {pct:.0f}% = 1 причина! Trust penalty активний."
- **Dynamic**: top_reason, same_reason_pct, delta від минулого тижня
- **Канал**: Dashboard + Telegram для 🔴/⛔
- **Cooldown**: 3 дні

**#102** "⚠️ 4 ліда додані з порожніми контактними даними. Заповніть телефон або email."
- **Тригер**: `leads_with_empty_contact >= 3`
- **Чому**: Incomplete data = unusable lead

**#103** "5 CRM записів вчора без причини результату. Вкажіть результат: замовив, відмовив, передзвонити."
- **Тригер**: `crm_entries_without_outcome >= 3 yesterday`
- **Чому**: DataQuality: no blank outcomes

**#104** "Порада: причини відмови — цінні дані! 'Дорого', 'не мій асортимент', 'вже є постачальник' — кожна допомагає."
- **Тригер**: `reason_diversity < 3 types in last 20 records`
- **Чому**: Reason diversity sub-metric education

**#105** "DataQuality = 91! Ваші CRM дані — одні з найчистіших у команді. Це підвищує trust coefficient."
- **Тригер**: `data_quality_score >= 88`
- **Чому**: Recognition of excellent data hygiene

**#106** "⚠️ Виявлено 2 можливих дублікати: 'Fashion Store' і 'FashionStore UA'. Перевірте та об'єднайте якщо це один клієнт."
- **Тригер**: `fuzzy_duplicate_detected`
- **Чому**: Duplicate stuffing prevention

**#107** "3 override-а ownership цього тижня. Більше 3 = caution. Переконайтесь що кожен обґрунтований."
- **Тригер**: `ownership_overrides_week >= 3`
- **Чому**: duplicate_override_rate threshold

**#108** "Вказано 'зацікавлений' для 8 лідів поспіль. Такий pattern рідкісний. Перевірте об'єктивність оцінки."
- **Тригер**: `consecutive_same_status >= 7`
- **Чому**: IHS / pattern detection

**#109** "Порада: мінімум 3 різних типи результатів щодня роблять DataQuality стабільним: дзвінок, КП, відмова, callback."
- **Тригер**: `daily_outcome_types < 2`
- **Чому**: Diversity guidance

**#110** "Micro: +0.2 за детальну причину відмови! ('Вже працює з X, ціна Y, повернутися через Z місяців')"
- **Тригер**: `detailed_reason_logged`
- **Чому**: Micro-feedback for quality reason

**#111** "⚠️ Ви видалили 3 ліда сьогодні. Audit log зафіксував. Не видаляйте — змініть статус на 'Відмовив'."
- **Тригер**: `leads_deleted_today >= 2`
- **Чому**: Audit trail protection

**#112** "Телефон клієнта 'Green Shop' = некоректний формат. Виправте — це впливає на DataQuality."
- **Тригер**: `phone_format_invalid`
- **Чому**: Data validation

**#113** "У 15 лідів немає категорії товару. Вкажіть: fashion/food/beauty/horeca — це допомагає системі аналізувати."
- **Тригер**: `leads_without_category >= 10`
- **Чому**: Segmentation data needed for analytics

**#114** "DataQuality trend ↑: 72→78→84 за 3 тижні. CRM стає чистішим — trust coefficient зростає!"
- **Тригер**: `dq_3week_ascending`
- **Чому**: Trend recognition

**#115** "Micro: +0.1 за коректне закриття ліда-секретаря (instant hangup cleanup). Це покращує якість бази."
- **Тригер**: `valid_instant_hangup_cleanup`
- **Чому**: Micro-feedback for correct classification

**#116** "⚠️ Duplicate abuse rate = 4%. Порог caution = 3%. Перевірте останні дублікати."
- **Тригер**: `duplicate_abuse_rate > 3%`
- **Чому**: Trust coefficient penalty threshold

**#117** "Порада: якщо клієнт змінив назву компанії — оновіть CRM, не створюйте нового ліда."
- **Тригер**: generic periodic tip
- **Чому**: Duplicate prevention best practice

**#118** "Ваші CRM записи за вчора успішно верифіковані. 0 невідповідностей! Trust ↑"
- **Тригер**: `daily_verification_passed`
- **Чому**: Trust building confirmation

**#119** "3 ліда мають статус 'test_order' більше 14 днів. Оновіть: або 'paid' або 'rejected'."
- **Тригер**: `stale_test_status >= 3`
- **Чому**: Data freshness

**#120** "Порада: нотатки до ліда ('Любить класичний стиль, замовляє на сезон') = якісніший наступний дзвінок."
- **Тригер**: `leads_without_notes > 50% of portfolio`
- **Чому**: CRM utilization best practice

**#121** "Reason quality score: 82/100. Ваші причини деталізовані і корисні — це підвищує DataQuality ось."
- **Тригер**: `reason_quality >= 80`
- **Чому**: Reason quality recognition

**#122** "Suspicious override: ви змінили статус ліда з 'відмовив' на 'зацікавлений' без нового дзвінка. Поясніть причину."
- **Тригер**: `status_rollback_without_new_interaction`
- **Чому**: Anti-abuse / honest reporting

**#123** "Порада: заповнюйте CRM відразу після дзвінка, не в кінці дня. Якість записів вища на 40% (Harvard BR)."
- **Тригер**: `avg_time_between_call_and_crm_entry > 4h`
- **Чому**: Data quality best practice with research

**#124** "5 manual overrides цього тижня без evidence. Порог critical = 5. Будь ласка, додавайте причину."
- **Тригер**: `manual_override_without_evidence >= 5`
- **Чому**: Trust coefficient critical threshold

**#125** "DataQuality покращився до 85 — тепер ваш trust coefficient максимальний. Це впливає на ВСІ осі MOSAIC!"
- **Тригер**: `dq_crosses_85_threshold`
- **Чому**: Show DQ → trust → all axes impact

---

# КАТЕГОРІЯ 6: VERIFIED COMMUNICATION — Tips 126-140

**#126** "VerifiedComm = 55/100. Логуйте emails та дзвінки в CRM — це підвищує вашу верифіковану базу."
- **Тригер**: `verified_comm_score < 60`
- **Чому**: VC axis improvement guidance

**#127** "📧 КП відправлено через систему — це автоматично +1 verified event. Відмінно!"
- **Тригер**: `cp_sent_via_system`
- **Чому**: System-logged = automatically verified

**#128** "Phase-dependent cap: зараз telephony = manual_only. VerifiedComm cap = 60. Це нормально — система не штрафує."
- **Тригер**: `telephony_maturity = 'manual_only'`
- **Чому**: Phase-dependent explanation

**#129** "3 callbacks без CRM запису. Логуйте результат кожного дзвінка — це verified communication evidence."
- **Тригер**: `callbacks_without_crm_log >= 3`
- **Чому**: Missing verification

**#130** "Порада: прикріпіть скріншот переписки з клієнтом до ліда — це найсильніший verified evidence."
- **Тригер**: `leads_with_zero_attachments > 80%`
- **Чому**: Evidence quality improvement

**#131** "Micro: +15.0 за correct invoice без rework! Чистий invoice = вищий VerifiedComm."
- **Тригер**: `clean_invoice_submitted`
- **Чому**: High-value micro event

**#132** "QA score = 85. QA-reviewed outcomes дають найвищий verified вклад. Продовжуйте!"
- **Тригер**: `qa_score >= 80`
- **Чому**: QA → VerifiedComm linkage

**#133** "VerifiedComm зросла з Telephony soft_launch: cap тепер 80 замість 60. Більше можливостей для росту!"
- **Тригер**: `telephony_maturity_changed TO 'soft_launch'`
- **Чому**: Phase transition notification

**#134** "5 email-листувань залоговано за тиждень. Це +5 verified events. VerifiedComm ↑"
- **Тригер**: `weekly_verified_emails >= 5`
- **Чому**: Activity → score linkage

**#135** "Порада: follow-up email після дзвінка ('Дякую за розмову, ось КП...') = 2 verified events за 1 контакт."
- **Тригер**: generic tip when `verified_count < team_avg`
- **Чому**: Double-tap technique

**#136** "System timestamps показують 8 CRM записів за 2 хвилини. Реальна обробка? Підозріла швидкість."
- **Тригер**: `burst_crm_entries > 5 in 3 minutes`
- **Чому**: Anti-abuse timestamp check

**#137** "VerifiedComm = 78. До максимального cap (80 при soft_launch) — 2 бали. Майже maximum!"
- **Тригер**: `vc_score NEAR telephony_cap`
- **Чому**: Near-cap motivation

**#138** "Manager-to-client reply evidence: 3 підтверджених відповіді клієнтів на ваші листи. Це цінний evidence."
- **Тригер**: `client_replies_logged >= 3`
- **Чому**: Bidirectional communication value

**#139** "Порада: при IP-телефонії ваші дзвінки будуть автоматично верифіковані. Поки — логуйте вручну."
- **Тригер**: `telephony_maturity = 'manual_only'` AND periodic
- **Чому**: Future feature preview

**#140** "QA-reviewed 5 з 10 ваших результатів. Рівень довіри QA: κ = 0.82 (score-safe). Ваші результати надійні."
- **Тригер**: `qa_coverage >= 50% AND qa_kappa >= 0.80`
- **Чому**: QA reliability confirmation

---

# КАТЕГОРІЯ 7: EARNED DAY / DMT — Tips 141-165

**#141** "✅ DMT виконано! Ставка за сьогодні (+682₴) нарахована. Залишилось 12 робочих днів."
- **Тригер**: `dmt_met_today = True`
- **Чому**: Daily stake confirmation

**#142** "⚠️ 14:00, DMT ще не виконано. Потрібно: ≥5 контактів + 80% callbacks. Ставка (682₴) під загрозою."
- **Тригер**: `dmt_not_met AND time > 14:00`
- **Чому**: DMT deadline warning

**#143** "💛 DMT не виконано сьогодні. Ставка 682₴ призупинена. Виконайте завтра — і вона повернеться."
- **Тригер**: `dmt_failed_today AND consecutive_fails = 1`
- **Чому**: First suspension notification

**#144** "🟠 Другий день без DMT. Призупинено 1,364₴. Відновлення: 2 успішних дні поспіль."
- **Тригер**: `consecutive_dmt_fails = 2`
- **Чому**: Escalation level 2

**#145** "🔴 3 дні без DMT. Адміністратору надіслано повідомлення. Призупинено: 2,046₴."
- **Тригер**: `consecutive_dmt_fails = 3`
- **Чому**: Admin notification trigger

**#146** "⛔ 5 днів без DMT. Ставка заморожена до зустрічі з адміністратором."
- **Тригер**: `consecutive_dmt_fails = 5`
- **Чому**: Meeting required trigger

**#147** "✅ DMT відновлено! Вчорашня призупинена ставка (+682₴) повернута. Загалом earned: 8,864₴."
- **Тригер**: `suspended_stake_released`
- **Чому**: Recovery confirmation

**#148** "2 дні поспіль DMT met — прискорене відновлення! +1 додатковий призупинений день повернуто."
- **Тригер**: `consecutive_dmt_pass >= 2 AND pending_suspended > 0`
- **Чому**: Accelerated recovery

**#149** "Ви працюєте в суботу! DMT met → бонусна ставка +682₴. 💪"
- **Тригер**: `weekend_work AND dmt_met`
- **Чому**: Weekend bonus earned

**#150** "DMT Statistics: 18/20 днів earned (90%). Лише 2 пропуски — відмінна дисципліна!"
- **Тригер**: `dmt_pass_rate >= 85%`
- **Чому**: Monthly DMT summary recognition

**#151** "Порада: DMT мінімальний — 5 контактів + 80% callbacks. Ви можете більше! Зробіть 20+ = ваш score зросте."
- **Тригер**: `daily_contacts BETWEEN 5 AND 8`
- **Чому**: DMT is floor, not ceiling

**#152** "Сьогодні 3 контакти і 70% callbacks. До DMT: ще 2 контакти + 2 callbacks. У вас є час!"
- **Тригер**: `approaching_dmt_deadline AND partially_met`
- **Чому**: Specific remaining actions to meet DMT

**#153** "Лікарняний зафіксовано. DMT не потрібен. Ставка нараховується повністю."
- **Тригер**: `legitimate_absence = 'sick_leave'`
- **Чому**: Legitimate absence confirmation

**#154** "Тиждень без жодного suspended day! Повна ставка: 3,410₴. Стабільно 💪"
- **Тригер**: `weekly_suspended_days = 0`
- **Чому**: Perfect week recognition

**#155** "Ваш DMT pass rate (75%) нижче за команду (88%). Зосередьтесь на мінімумі — 5 контактів щодня."
- **Тригер**: `dmt_rate < team_avg × 0.9`
- **Чому**: Below-average awareness

**#156** "📊 Earned Day stats: ставка earned 12,276₴ + commission 4,200₴ = 16,476₴ projected."
- **Тригер**: `mid_month_summary`
- **Чому**: Financial transparency

**#157** "Порада: зробити 5 контактів = 1 година роботи. DMT — це мінімум на який здатний кожен."
- **Тригер**: `dmt_failed AND contacts = 0`
- **Чому**: Perspective on how easy DMT is

**#158** "Державне свято зафіксовано. DMT не потрібен. Гарного відпочинку! 🎉"
- **Тригер**: `national_holiday = True`
- **Чому**: Holiday confirmation

**#159** "Погоджена відпустка (3 дні). Ставка нараховується повністю. Гарного відпочинку!"
- **Тригер**: `approved_vacation = True`
- **Чому**: Vacation stake confirmation

**#160** "⚠️ Інфраструктурний збій CRM зафіксовано. DMT не рахується. Ставка = earned."
- **Тригер**: `infrastructure_outage = True`
- **Чому**: No-fault protection

**#161** "Probation Stage A: ваш DMT знижений (3 контакти + 50% callbacks). Після 5 днів — стандартний DMT."
- **Тригер**: `probation_stage = 'A'`
- **Чому**: New employee onboarding

**#162** "Probation Stage B: стандартний DMT (5 контактів + 80% callbacks) тепер активний."
- **Тригер**: `probation_stage_change TO 'B'`
- **Чому**: Stage transition

**#163** "Адміністратор вручну відновив 2 призупинених дні. Ставка оновлена: +1,364₴."
- **Тригер**: `admin_manual_release`
- **Чому**: Admin override confirmation

**#164** "Ваша projected gross salary: 22,000₴ (ставка + комісія). На 5,000₴ більше ніж мінімальна."
- **Тригер**: `projected_salary > base × 1.3`
- **Чому**: Financial motivation

**#165** "100% DMT pass за місяць! Максимальна ставка: 15,000₴ + commission. 🏆"
- **Тригер**: `monthly_dmt_rate = 100%`
- **Чому**: Perfect month celebration

---

# КАТЕГОРІЯ 8: MOSAIC SCORE & TREND — Tips 166-185

**#166** "📊 MOSAIC: **{score:.0f}** (Δ від вчора: **{daily_delta:+.0f}**, від тижня: **{weekly_delta:+.0f}**). Драйвер: **{best_axis}** ({best_val:.0f}). Слабкість: **{worst_axis}** ({worst_val:.0f}, Δ: **{worst_delta:+.0f}**)."
- **Формула**: `daily_delta = score_today - score_yesterday. weekly_delta = score_today - score_7d_ago. best/worst = max/min axes`
- **Dynamic**: Автоматично: best_axis, worst_axis, всі deltas
- **Канал**: Dashboard постійно + Telegram 17:00 (end-of-day)
- **Cooldown**: 1 день

**#167** "Score trend ↑ **{ascending_days}** днів: **{score_start:.0f}**→**{score_now:.0f}** (slope: **{slope:+.2f}**/день). Прогноз через 7 днів: **{forecast_7d:.0f}**. {motivation}"
- **Формула**: `slope = trend_slope(7d). forecast_7d = score_now + slope × 7`
- **Dynamic**: motivation = "Якщо продовжите, через місяць: {forecast_30:.0f} (зона: {zone})!"
- **Канал**: Dashboard + Telegram
- **Cooldown**: 3 дні

**#168** "⚠️ Score trend ↓ **{descending_days}** днів: **{score_start:.0f}**→**{score_now:.0f}** (Δ: **{drop:-.0f}**, slope: **{slope:+.2f}**/день). Причина: **{root_cause_axis}** ({axis_drop:-.0f}). {recovery_action}"
- **Формула**: `root_cause_axis = axis with biggest negative delta. recovery_action = specific improvement for that axis`
- **Поріг ескалації**:
  - `🟡 descending 3-5 days`: "Score знижується. Зосередьтесь на {axis}."
  - `🔴 descending 5-7 days`: "Score ПАДАЄ {drop:.0f} балів за тиждень! Потрібна дія."
  - `⛔ descending 7+ days OR drop > 15`: "КРИТИЧНЕ падіння! Адмін сповіщений."
- **DeEscalation**: 3 ascending days → reset
- **Канал**: Dashboard + Telegram (🔴/⛔ instant)
- **Cooldown**: 1 день

**#169** "Ваш score gate = 78 (немає оплати, є verified progress). 1 оплата = gate відкривається до 100!"
- **Тригер**: `active_gate_cap = 78`
- **Чому**: Gate education — what unlocks 100

**#170** "Trust coefficient = 1.05 (вище 1.0). Це множник на ваш score — чим вищий trust, тим більший бал!"
- **Тригер**: `trust_coeff > 1.0`
- **Чому**: Trust = multiplier education

**#171** "Trust знизився до 0.85 через anomaly_penalty. Причина: short_call_mismatch > 8%."
- **Тригер**: `trust_dropped AND anomaly_penalty > 0`
- **Чому**: Trust penalty transparency

**#172** "Portfolio bonus = 7/10! 4 під-компоненти: health(85) + reactivation(60) + repeat(40) + orphan(90)."
- **Тригер**: `portfolio_bonus_calculated`
- **Чому**: Portfolio bonus breakdown

**#173** "🎯 Action Plan: щоб підняти score з **{score_now:.0f}** до **{target_score:.0f}**: найшвидше — покращити **{worst_axis}** (+**{needed_pts:.0f}** pts). Топ-3 дії: {action_1}, {action_2}, {action_3}."
- **Формула**: `target_score = score_now + 4. worst = min(axes). needed_pts = (target_score - score_now) / axis_weight`
- **Dynamic**: action_1/2/3 автоматично на основі worst_axis:
  - FollowUp: "виконайте всі callbacks", "перенесіть а не забудьте", "зателефонуйте Risk клієнтам"
  - Result: "перезвоніть stalled CP", "закрийте test orders", "додайте нових лідів"
  - DataQuality: "деталізуйте причини", "заповніть порожні поля", "оновіть stale statuses"
- **Канал**: Dashboard + Telegram 09:00 (morning brief)
- **Cooldown**: 3 дні

**#174** "Score = 82 — ваша зона: 🟢 Solid. Менеджери з 80-89 в середньому генерують 480K₴/міс."
- **Тригер**: `score >= 80`
- **Чому**: Score-to-money zone feedback

**#175** "Новий рекорд MOSAIC: 87! Попередній рекорд: 84. Ви стабільно зростаєте! 🎉"
- **Тригер**: `score = alltime_max`
- **Чому**: Personal best recognition

**#176** "Micro stream за сьогодні: +0.5 +0.5 +0.2 -2.0 +0.5 +100 = +99.7. Оплачене замовлення = основний вклад."
- **Тригер**: `end_of_day_micro_summary`
- **Чому**: Micro-feedback daily summary

**#177** "Consistency Factor = 0.96 (добре). Ваша робота рівномірна по днях. Це покращує DataQuality ось."
- **Тригер**: `wci >= 0.85`
- **Чому**: WCI recognition

**#178** "⚠️ Consistency Factor = 0.72 (нижче норми). Вчора 50 дій, сьогодні 5. Спробуйте рівномірніше."
- **Тригер**: `wci < 0.75`
- **Чому**: WCI warning with context

**#179** "Efficiency modifier = 1.08 (+8% на Result). Ваша конверсія вище за очікувану для ваших джерел!"
- **Тригер**: `efficiency_modifier > 1.05`
- **Чому**: Efficiency bonus recognition

**#180** "Score прогноз на наступний місяць: 78. Покращення +4. При цьому estimated revenue: 390K₴."
- **Тригер**: `monthly_forecast_available`
- **Чому**: Score + revenue monthly forecast

**#181** "Harmonic warning: FollowUp = 18 (нижче floor 20). Це знижує base_day на -8%."
- **Тригер**: `any_axis < CRITICAL_FLOOR(20)`
- **Чому**: Harmonic penalty active

**#182** "Вітаємо! Усі 6 осей MOSAIC вище 50. Balanced profile = стабільний score."
- **Тригер**: `all_axes >= 50`
- **Чому**: Balance achievement

**#183** "Ваш MOSAIC Velocity: +1.2/день (ascending). Серед найшвидших у команді!"
- **Тригер**: `velocity > team_avg × 1.3`
- **Чому**: Velocity recognition

**#184** "Confidence Score вашого рейтингу: 88%. Адміністратор може прийняти рішення на основі цих даних."
- **Тригер**: `confidence_score >= 80`
- **Чому**: Score reliability indicator

**#185** "Score стабільний 75±2 вже 2 тижні. Для прориву: збільште Result (conversion) або FollowUp (callbacks)."
- **Тригер**: `score_plateau 14d AND volatility < 3`
- **Чому**: Plateau breakthrough guidance

---

# КАТЕГОРІЯ 9: EFFICIENCY & GROWTH — Tips 186-200

**#186** "Ваш Daily Processing: 47 contacts/day equivalent. Середнє команди: 32. Ви обробляєте на 47% більше!"
- **Тригер**: `daily_processing > team_avg × 1.3`
- **Чому**: Processing capacity recognition

**#187** "Порада: ви робите 60 дзвінків, конверсія 1.2%. Якщо покращити конверсію до 2%, revenue подвоїться без додаткових зусиль."
- **Тригер**: `high_volume_low_conversion`
- **Чому**: Quality vs quantity coaching

**#188** "Payback Speed: ви окупились на Day 7. Решта місяця = чистий прибуток для компанії! 🎉"
- **Тригер**: `payback_day_reached`
- **Чому**: Financial milestone celebration

**#189** "⚠️ Payback forecast: при поточному темпі — Day 19. Ризик: не окупитися до кінця місяця."
- **Тригер**: `payback_projected > 18`
- **Чому**: Payback at risk alert

**#190** "Persistence Score: 85. Ви не здаєтесь при перших відмовах — це ключова B2B навичка!"
- **Тригер**: `persistence >= 80`
- **Чому**: B2B persistence recognition

**#191** "⚠️ 4 ліда закриті після 1-2 контактів. B2B вимагає 7-12 спроб. Не здавайтесь рано!"
- **Тригер**: `early_abandonments >= 3 AND avg_attempts < 3`
- **Чому**: Persistence coaching

**#192** "Churn Warning: клієнт 'Best Fashion' зазвичай замовляє раз на 20 днів. Пройшло 32. Зателефонуйте!"
- **Тригер**: `churn_signal > 1.5 FOR specific_client`
- **Чому**: Predictive churn → specific action

**#193** "Порада: ваші найкращі дні (score 80+) — вівторок і четвер. Плануйте важливі дзвінки на ці дні."
- **Тригер**: `best_day_pattern_detected`
- **Чому**: Personal pattern coaching

**#194** "Вітаємо з першим місяцем! Ваш MOSAIC зріс з 45 до 68. Прогрес: +23 бали!"
- **Тригер**: `days_employed = 30`
- **Чому**: First month milestone

**#195** "Ви конвертуєте 'thinking' клієнтів у 28% випадків (команда: 15%). Відмінна persistency!"
- **Тригер**: `psr > team_avg × 1.5` (Follow-Up Conversion Rate)
- **Чому**: PSR/persuasion skill recognition

**#196** "Порада: 3 ваших кращих клієнта дали 60% revenue. Диверсифікуйте — залежність від 3 клієнтів небезпечна."
- **Тригер**: `top_3_clients_revenue_share > 55%`
- **Чому**: Concentration risk

**#197** "Score 90+ вже 5 днів! Якщо утримаєте — це найвища зона. Estimated revenue: 650K₴/міс! 🏆"
- **Тригер**: `consecutive_days_score_90plus >= 5`
- **Чому**: Elite performance sustain motivation

**#198** "Growth: за 3 місяці ваш MOSAIC: 58→68→74. Прогноз через 3 місяці: 84 🚀"
- **Тригер**: `3month_trend_available AND ascending`
- **Чому**: Long-term growth trajectory

**#199** "Порада: оберіть 1 слабку ось і зростіть на 10+ пунктів. Це автоматично підніме загальний MOSAIC на ~3 бали."
- **Тригер**: `score_plateau AND min_axis_gap > 20`
- **Чому**: Strategic improvement targeting

**#200** "🏆 Achievement unlocked: 'MOSAIC Maestro' — усі 6 осей вище 75 одночасно! Це рідкісне досягнення."
- **Тригер**: `all_axes >= 75`
- **Чому**: Achievement system — balanced excellence

---

---

# КАТЕГОРІЯ 10: 🧠 ДИНАМІЧНІ ІНТЕЛЕКТУАЛЬНІ ПОРАДИ — Tips 201-230

> Ці поради використовують Delta Calculator, Predictive Engine, та Cross-Metric Correlation.
> Кожна порада містить ДИНАМІЧНІ дані (відсотки, дельти, прогнози) обчислені в реальному часі.

## DELTA-BASED (порівняння з попереднім періодом)

**#201** "📉 Продуктивність сьогодні: {today_contacts} контактів — на **{delta_pct}%** менше ніж вчора ({yesterday_contacts}). Напрямки для покращення: {weakest_actions}."
- **Формула**: `daily_delta_pct = ((today_contacts - yesterday_contacts) / yesterday_contacts) × 100`
- **Поріг**: `💡 delta < -20%` → `🟡 delta < -40%` → `🔴 delta < -60%` → `⛔ delta < -80%`
- **Ескалація**: якщо 2 дні поспіль delta < -40% → автоматично 🔴
- **DeEscalation**: delta > 0% два дні поспіль → зняти
- **Канал**: Dashboard + Telegram 17:00
- **Cooldown**: 1 день

**#202** "📊 Конверсія цього тижня: {conv_this_week}% — на **{conv_delta}%** {вище/нижче} ніж минулого ({conv_last_week}%). {recommendation}"
- **Формула**: `conv_delta = ((conv_week - conv_prev_week) / conv_prev_week) × 100`
- **Поріг**: `💡 delta < -15%` → `🟡 delta < -30%` → `🔴 delta < -50%` → `⛔ 3 weeks descending`
- **Ескалація**: 2 тижні поспіль conv_delta < -30% → 🔴. 3 тижні → ⛔ + admin alert
- **Канал**: Dashboard + Telegram (понеділок 09:00)
- **Cooldown**: 7 днів (weekly metric)

**#203** "📈 Revenue pace: {revenue_pace}K₴/міс — на **{pace_delta}%** {вище/нижче} за ціль ({target}K₴). {forecast_message}"
- **Формула**: `pace = (revenue_mtd / days_elapsed) × business_days. pace_delta = ((pace - target) / target) × 100`
- **Поріг**: `💡 pace_delta < -10%` → `🟡 < -20%` → `🔴 < -35%` → `⛔ < -50%`
- **Dynamic**: forecast_message = "При поточному темпі: {forecast}K₴" або "Для досягнення цілі потрібно {daily_needed}₴/день"
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 3 дні

**#204** "📉 MOSAIC score впав на **{score_drop}** балів за день ({yesterday_score} → {today_score}). Причина: {axis_with_biggest_drop} (-{axis_drop})."
- **Формула**: `score_drop = yesterday_score - today_score. axis_drops = [axis_yesterday - axis_today for each axis]`
- **Поріг**: `💡 drop > 3` → `🟡 drop > 5` → `🔴 drop > 8` → `⛔ drop > 12`
- **Ескалація**: 🔴 instant якщо drop > 10 (single day catastrophic)
- **Канал**: Dashboard + Telegram INSTANT для 🔴/⛔
- **Cooldown**: 1 день

**#205** "📊 FollowUp axis змінився на **{fu_delta}** за тиждень ({fu_last_week} → {fu_this_week}). {trend_interpretation}"
- **Формула**: `fu_delta = fu_this_week - fu_last_week. trend_interpretation = "ascending ↑" if fu_delta > 0 else "ПАДАЄ ↓"`
- **Поріг**: `💡 abs(fu_delta) > 5` → `🟡 fu_delta < -8` → `🔴 fu_delta < -15` → `⛔ fu_delta < -20`
- **Dynamic**: Показує вплив на score: "Це змінює загальний MOSAIC на ~{fu_delta × 0.10} балів."
- **Канал**: Dashboard
- **Cooldown**: 3 дні

**#206** "📉 Кількість дзвінків: {calls_today} (вчора: {calls_yesterday}, тиждень тому: {calls_7d_ago}). Тренд: **{trend_word}**."
- **Формула**: `trend_slope = linear_regression_slope(daily_calls, 7). trend_word = "зростає" if slope > 0.5 else "стабільний" if abs(slope) < 0.5 else "знижується"`
- **Поріг**: `💡 slope < -1.0` → `🟡 slope < -2.0` → `🔴 slope < -3.0` → `⛔ slope < -5.0`
- **Канал**: Telegram 17:00
- **Cooldown**: 2 дні

**#207** "📊 DataQuality змінився: {dq_prev} → {dq_now} ({dq_delta:+d}). {interpretation}"
- **Формула**: `dq_delta = dq_now - dq_prev_week`
- **Поріг**: `🟢 dq_delta > 5` (позитивне) → `🟡 dq_delta < -5` → `🔴 dq_delta < -10`
- **Dynamic**: interpretation = причина зміни: "3 ліда без контактів" або "покращена деталізація причин"
- **Канал**: Dashboard
- **Cooldown**: 3 дні

## PREDICTIVE (прогнозування)

**#208** "🔮 Прогноз score через 7 днів: **{predicted_score}** ({current_score} {direction} {change}). {action_needed}"
- **Формула**: `predicted_score = current_score + trend_slope_7d × 7`
- **Поріг**: `💡 always show` → `🟡 predicted < 60` → `🔴 predicted < 50` → `⛔ predicted < 40`
- **Dynamic**: action_needed = "Зосередьтесь на {weakest_axis}" або "Тренд позитивний — утримуйте!"
- **Канал**: Dashboard + Telegram (понеділок)
- **Cooldown**: 7 днів

**#209** "🔮 Прогноз revenue на кінець місяця: **{forecast_revenue}K₴**. Сценарії: оптиміст {opt}K₴ | база {base}K₴ | песиміст {pess}K₴."
- **Формула**: `base = (revenue_mtd / days_elapsed) × business_days. opt = base × 1.15. pess = base × 0.75`
- **Поріг**: `🟢 base > target` → `🟡 base 80-100% target` → `🔴 base < 80% target` → `⛔ all scenarios < target`
- **Канал**: Dashboard + Telegram weekly
- **Cooldown**: 7 днів

**#210** "🔮 DMT ризик сьогодні: **{dmt_risk}%**. {risk_explanation}"
- **Формула**: `dmt_risk = 100 × (1 - current_contacts/5) × (1 - callback_sla/80) if time > 12:00 else 0`
- **Поріг**: `💡 risk < 30%` → `🟡 risk 30-60%` → `🔴 risk > 60%` → `⛔ risk > 80% AND time > 15:00`
- **Dynamic**: risk_explanation = "Потрібно ще {remaining_contacts} контактів та {remaining_callbacks} callbacks"
- **Канал**: Telegram 14:00 (checkpoint)
- **Cooldown**: не повторювати в той же день після DMT met

**#211** "🔮 Клієнт '{client_name}' — прогноз churn: **{churn_pct}%**. {churn_reason}"
- **Формула**: `churn_pct = min(100, (days_since_last_contact / expected_interval - 1) × 50 + base_churn_15)`
- **Поріг**: `💡 churn 30-50%` → `🟡 churn 50-70%` → `🔴 churn > 70%` → `⛔ churn > 90%`
- **Dynamic**: churn_reason = "Зазвичай замовляє кожні {interval} днів, вже пройшло {actual} днів"
- **Ескалація**: churn > 70% AND client_revenue > 30K → instant 🔴
- **Канал**: Dashboard + Telegram для 🔴
- **Cooldown**: 3 дні per client

**#212** "🔮 Прогноз зарплати: **{projected_salary}₴** (ставка {stake}₴ + комісія {commission}₴). {comparison}"
- **Формула**: `stake = dmt_pass_rate × base_salary. commission = projected_revenue × avg_commission_rate`
- **Dynamic**: comparison = "На {delta}₴ {більше/менше} ніж минулого місяця"
- **Канал**: Dashboard (weekly update)
- **Cooldown**: 7 днів

**#213** "🔮 Якщо покращити {weakest_axis} на 10 пунктів: MOSAIC +{score_impact}, прогноз revenue +{revenue_impact}K₴/міс."
- **Формула**: `score_impact = 10 × axis_weight. revenue_impact = score_to_money_slope × score_impact`
- **Dynamic**: weakest_axis вираховується автоматично, score_to_money з кореляційної таблиці
- **Канал**: Dashboard + Telegram (weekly growth tip)
- **Cooldown**: 14 днів

## CROSS-METRIC CORRELATION (зв'язки між метриками)

**#214** "⚡ FollowUp падає (-{fu_drop}) → але Result стабільний ({result}). Ризик: через 2-3 тижні Result теж впаде (repeat orders знизяться)."
- **Формула**: `fu_trend_14d < -0.3 AND result_trend_14d >= 0`
- **Поріг**: `🟡 always` → `🔴 if fu < 40` → `⛔ if fu < 30`
- **Reasoning**: FollowUp → repeat orders → delay → Result drops in 2-3 weeks
- **Канал**: Dashboard + Telegram
- **Cooldown**: 7 днів

**#215** "⚡ Багато дзвінків ({calls}/день) але конверсія падає ({conv}%). Рекомендація: зменшити кількість, збільшити якість кожного дзвінка."
- **Формула**: `calls_daily > team_avg × 1.3 AND conversion_rate < baseline × 0.7`
- **Поріг**: `🟡 conv < baseline × 0.7` → `🔴 conv < baseline × 0.5`
- **Канал**: Dashboard
- **Cooldown**: 5 днів

**#216** "⚡ DataQuality високий ({dq}) + Trust високий ({trust}) → але Result низький ({result}). Проблема не в даних, а в продажних навичках."
- **Формула**: `dq > 80 AND trust > 1.0 AND result < 40`
- **Поріг**: `🟡 always` → `🔴 if result < 30`
- **Reasoning**: Good data + low results = skill gap, not process gap
- **Канал**: Dashboard (admin also sees this pattern)
- **Cooldown**: 14 днів

**#217** "⚡ Score росте ({score_trend:+.1f}/день) але DMT pass rate падає ({dmt_rate}%). Парадокс: score не утримається без daily discipline."
- **Формула**: `score_trend_7d > 0.3 AND dmt_pass_rate_7d < 85%`
- **Поріг**: `🟡 always`
- **Reasoning**: Rising score from past micro, but falling DMT = future score collapse
- **Канал**: Dashboard + Telegram
- **Cooldown**: 5 днів

## INTELLIGENT CONTEXT-AWARE (контекстні)

**#218** "📅 Понеділок — найважливіший день тижня для вас. Статистика: ваші ПН дають {mon_pct}% тижневого результату."
- **Формула**: `is_monday AND personal_monday_weight > 0.25`
- **Dynamic**: mon_pct обчислюється з history
- **Канал**: Telegram 09:00 (only on Mondays)
- **Cooldown**: 7 днів

**#219** "📅 П'ятниця — час планувати наступний тиждень. У вас {next_week_callbacks} callbacks та {next_week_cp} pending КП."
- **Формула**: `is_friday AND time > 15:00`
- **Dynamic**: auto-count next week actions
- **Канал**: Telegram 15:00 (only on Fridays)
- **Cooldown**: 7 днів

**#220** "🧮 Ваша 'Price per Contact' = {ppc}₴. Кожен контакт коштує компанії {ppc}₴. Конверсія покращить цей показник."
- **Формула**: `ppc = total_monthly_cost / total_contacts_this_month`
- **Поріг**: `💡 always` → `🟡 ppc > team_avg × 1.5` → `🔴 ppc > team_avg × 2.0`
- **Канал**: Dashboard (weekly update)
- **Cooldown**: 7 днів

**#221** "🎯 Milestone Alert: ви на {n} контактів від {milestone_name}! ({current}/{target})"
- **Формула**: `(target - current) / target < 0.1 AND target - current <= 5`
- **Milestones**: 50/100/200/500 contacts, 10/25/50 paid orders, 100K/500K revenue
- **Канал**: Dashboard + Telegram
- **Cooldown**: once per milestone

**#222** "🔄 Порівняння з минулим місяцем: Score {score_now} vs {score_prev} ({score_delta:+d}). Revenue {rev_now}K₴ vs {rev_prev}K₴ ({rev_delta:+.0f}K₴)."
- **Формула**: `day_of_month >= 15 (mid-month comparison)`
- **Dynamic**: all values from prev month same period
- **Канал**: Dashboard + Telegram
- **Cooldown**: 15 днів (once per period)

**#223** "⏱️ Ваш найефективніший час: {best_hours}. Конверсія в ці години: {best_conv}% (середня: {avg_conv}%). Плануйте важливі дзвінки на цей час."
- **Формула**: `best_hours = hours WHERE conversion > avg_conversion × 1.5 (based on 30d data)`
- **Канал**: Dashboard + Telegram (weekly)
- **Cooldown**: 14 днів

**#224** "📊 Ваш Risk Composite Score: **{risk_score}/100**. Ризики: DMT({dmt_risk}), Score({score_risk}), Callbacks({cb_risk}), Conversion({conv_risk})."
- **Формула**: risk_score (from Delta Calculator section above)
- **Поріг**: `🟢 < 25` → `🟡 25-50` → `🔴 50-75` → `⛔ > 75`
- **Канал**: Dashboard daily + Telegram for 🔴/⛔
- **Cooldown**: 1 день

**#225** "💰 Break-even update: ви окупились на **Day {be_day}** ({be_day <= 10 ? "швидко! 🏆" : "нормально"}). Решта місяця = прибуток."
- **Формула**: `cumulative_revenue >= cumulative_cost AND not_yet_notified_this_month`
- **Канал**: Dashboard + Telegram (once when triggered)
- **Cooldown**: 30 днів (once per month)

**#226** "📊 Weekly Performance Summary: Score {score_avg} ({score_trend}), Revenue {rev_week}K₴, DMT {dmt_rate}%, Callbacks {cb_sla}%."
- **Формула**: `is_sunday OR is_monday_morning`
- **Dynamic**: All weekly aggregated metrics
- **Канал**: Telegram (Sunday evening or Monday morning)
- **Cooldown**: 7 днів

## ESCALATION-AWARE (поради які автоматично серйознішають)

**#227** "🔄 Overdue callbacks: Day 1: {count_d1} overdue → Day 2: {count_d2} → Day 3: {count_d3}. **Тренд: {trend}.**"
- **Ескалація повна**:
  - `🟢 Day 1, count ≤ 2`: "У вас {count} прострочених. Виконайте сьогодні."
  - `🟡 Day 2, count ≤ 3`: "Другий день з простроченими! {count} callbacks потребують уваги."
  - `🔴 Day 2+, count ≥ 4`: "КРИТИЧНО: {count} прострочених 2+ днів! FollowUp ось під загрозою."
  - `⛔ Day 3+, count ≥ 5`: "Адміну надіслано alert. {count} прострочених 3+ днів."
- **DeEscalation**: overdue_count = 0 → reset to 🟢
- **Канал**: Dashboard + Telegram (🔴/⛔ instant)

**#228** "🔄 Pipeline depletion: {pipeline_count} лідів → {pipeline_7d_ago} тиждень тому ({pipeline_delta:+d}). **{severity}**"
- **Ескалація повна**:
  - `💡 pipeline 10-15`: "Pipeline скорочується. Додайте нових лідів."
  - `🟡 pipeline 5-9`: "Pipeline МАЛИЙ: лише {count} лідів. Ризик у наступних тижнях."
  - `🔴 pipeline 1-4`: "Pipeline КРИТИЧНО малий! Лише {count} лідів. Revenue під загрозою."
  - `⛔ pipeline 0`: "Pipeline ПУСТИЙ! Без нових лідів revenue = 0 через 2-3 тижні."
- **DeEscalation**: pipeline > 15 → reset to 🟢
- **Канал**: Dashboard + Telegram для 🔴/⛔

**#229** "🔄 Score consistency: MOSAIC був {score_max} → {score_min} → {score_now} за 7 днів. Волатильність: **{volatility}**."
- **Ескалація повна**:
  - `💡 volatility < 5`: "Score стабільний ±{volatility}. Добре!"
  - `🟡 volatility 5-10`: "Score 'скаче': max {max}, min {min}. Стабілізуйте щоденну роботу."
  - `🔴 volatility > 10`: "Score НЕСТАБІЛЬНИЙ (±{volatility}). Велика варіація по днях = ризик."
- **Канал**: Dashboard weekly
- **Cooldown**: 7 днів

**#230** "🔄 Salary projection trending: цього місяця projected **{salary_now}₴** vs минулий **{salary_prev}₴** ({salary_delta:+.0f}₴)."
- **Ескалація повна**:
  - `🟢 salary_delta > 0`: "Зарплата зростає! На {salary_delta}₴ більше за минулий місяць."
  - `🟡 salary_delta -2000..0`: "Зарплата трохи нижче. Причина: {reason}."
  - `🔴 salary_delta < -2000`: "Зарплата ЗНАЧНО нижче (-{abs(salary_delta)}₴). {top_reason}."
  - `⛔ salary_delta < -5000`: "Зарплата прогнозується на {salary_delta}₴ менше! Потрібна дія."
- **DeEscalation**: salary_delta > 0 за 5 днів → reset
- **Канал**: Dashboard + Telegram weekly

---

# ТЕХНІЧНИЙ ДОДАТОК v2.0

## Повна таблиція ескалації для всіх 230 порад

```python
# ═══ ESCALATION RULES PER TIP CATEGORY ═══

ESCALATION_MAP = {
    # CATEGORY: (initial_level, escalation_condition, de_escalation)
    
    "Result_dropout": {
        "💡": "daily_result_actions = 0 before 12:00",
        "🟡": "daily_result_actions = 0 at 14:00",
        "🔴": "daily_result_actions = 0 at 16:00 OR 2 consecutive zero-days",
        "⛔": "3+ consecutive zero-days",
        "de_esc": "daily_result_actions >= 3",
    },
    
    "Conversion_drop": {
        "💡": "weekly_conv < baseline × 0.85",
        "🟡": "weekly_conv < baseline × 0.70",
        "🔴": "weekly_conv < baseline × 0.50 OR 2 weeks declining",
        "⛔": "3 weeks declining OR weekly_conv < baseline × 0.30",
        "de_esc": "weekly_conv >= baseline × 0.85 for 1 week",
    },
    
    "Callback_SLA": {
        "💡": "daily_sla < 85%",
        "🟡": "daily_sla < 80% (DMT threshold)",
        "🔴": "daily_sla < 70% OR 2 consecutive days < 80%",
        "⛔": "3+ consecutive days < 80%",
        "de_esc": "daily_sla >= 85% for 2 consecutive days",
    },
    
    "Pipeline_health": {
        "💡": "active_pipeline 10-15",
        "🟡": "active_pipeline 5-9",
        "🔴": "active_pipeline 1-4",
        "⛔": "active_pipeline = 0",
        "de_esc": "active_pipeline >= 15",
    },
    
    "DMT_fail": {
        "💛": "1 consecutive fail",
        "🟠": "2 consecutive fails",
        "🔴": "3 consecutive fails (admin notified)",
        "⛔": "5+ consecutive fails (meeting required)",
        "de_esc": "2 consecutive DMT pass",
    },
    
    "Score_drop": {
        "💡": "daily drop 3-5 points",
        "🟡": "daily drop 5-8 points",
        "🔴": "daily drop 8-12 points",
        "⛔": "daily drop > 12 points OR 3 consecutive drops > 5",
        "de_esc": "score ascending 3 consecutive days",
    },
    
    "DataQuality_decline": {
        "💡": "weekly dq_delta -3 to -5",
        "🟡": "weekly dq_delta -5 to -10",
        "🔴": "weekly dq_delta < -10 OR dq < 60",
        "⛔": "dq < 40 (trust coefficient severely impacted)",
        "de_esc": "weekly dq_delta > 0 for 2 weeks",
    },
    
    "Revenue_pace": {
        "💡": "pace < target × 0.90",
        "🟡": "pace < target × 0.80",
        "🔴": "pace < target × 0.65",
        "⛔": "pace < target × 0.50 AND days_remaining < 10",
        "de_esc": "pace >= target × 0.90",
    },
    
    "Client_churn": {
        "💡": "churn_probability 30-50%",
        "🟡": "churn_probability 50-70%",
        "🔴": "churn_probability > 70%",
        "⛔": "churn_probability > 90% AND client_ltv > 50K₴",
        "de_esc": "new interaction logged → churn recalculated",
    },
    
    "Salary_projection": {
        "💡": "projected < prev_month - 1000₴",
        "🟡": "projected < prev_month - 2000₴",
        "🔴": "projected < prev_month - 4000₴",
        "⛔": "projected < base_salary (15000₴)",
        "de_esc": "projected >= prev_month for 5 consecutive days",
    },
}
```

## Priority Engine (які поради показувати першими)

```python
def select_tips_for_today(manager):
    """Вибирає top-N порад для менеджера на сьогодні."""
    
    all_triggered = []
    for tip in ALL_TIPS:
        level = evaluate_tip(tip, manager)
        if level is not None:
            all_triggered.append((tip, level))
    
    # Sort: ⛔ > 🔴 > 🟡 > 🟢 > 💡
    PRIORITY = {"⛔": 5, "🔴": 4, "🟡": 3, "🟢": 2, "💡": 1}
    all_triggered.sort(key=lambda t: PRIORITY[t[1]], reverse=True)
    
    # Anti-spam: max per category
    selected = []
    category_count = defaultdict(int)
    
    for tip, level in all_triggered:
        if level in ("⛔", "🔴"):
            selected.append((tip, level))  # Always show critical
            continue
        
        if len(selected) >= MAX_TIPS_PER_DAY:
            break
        if category_count[tip.category] >= MAX_SAME_CATEGORY_PER_DAY:
            continue
        if tip.tip_id in recently_shown(manager, tip.cooldown_days):
            continue
            
        selected.append((tip, level))
        category_count[tip.category] += 1
    
    return selected


def evaluate_tip(tip, manager):
    """Обчислює поточний рівень ескалації для совета."""
    
    value = compute_formula(tip.formula, manager)
    
    for level in reversed(tip.escalation_chain):  # ⛔ first
        if value meets tip.threshold[level]:
            # Check escalation history
            prev_level = get_previous_level(tip, manager)
            if prev_level and PRIORITY[level] > PRIORITY[prev_level]:
                log_escalation(tip, manager, prev_level, level)
            return level
    
    return None  # Tip not triggered
```

## Feedback Loop v2.0

```python
# Менеджер може реагувати на кожну пораду:

REACTIONS = {
    "👍": {
        "action": "boost_similar_priority",
        "delta": +0.1,
        "analytics": "Track which tips correlate with score improvement",
    },
    "👎": {
        "action": "reduce_similar_priority",
        "delta": -0.2,  # Stronger negative (менеджер знає краще)
        "limit": "After 3 👎 on same tip → suppress for 30 days",
    },
    "✅ Виконано": {
        "action": "track_compliance",
        "analytics": "compliance_rate = done_tips / shown_tips",
        "reward": "High compliance → fewer tips needed (system learns)",
    },
    "⏰ Пізніше": {
        "action": "reschedule",
        "delay": "4 hours OR next morning",
    },
    "❓ Поясни": {
        "action": "show_detailed_explanation",
        "content": "Full formula + why this matters + axis impact + score impact",
    },
}

# SELF-LEARNING:
# Система відстежує: які поради → покращення score?
# Після 3+ місяців: автоматично підвищує пріоритет порад з високим impact.
# Tips з consistently 👎 або zero correlation → депріоритизуються.
```

## Telegram Bot Commands

```
/tips          — показати поточні 3 активні поради
/score         — поточний MOSAIC + дельта від вчора
/dmt           — DMT статус + що залишилось
/week          — тижневий підсумок
/forecast      — прогноз score + revenue
/salary        — прогноз зарплати
/portfolio     — Portfolio Health overview
/streak        — поточна серія (DMT/callbacks)
/mute 1h/4h/8h — вимкнути на час
/settings      — налаштування каналів
/explain {tip} — детальне пояснення поради
/history       — історія порад за тиждень
```

---

> [!IMPORTANT]
> **v2.0 Changes**: Додано Dynamic Intelligence Engine з 10 Delta формулами, Escalation State Machine (💡→🟢→🟡→🔴→⛔) для КОЖНОГО типу поради, 30 нових інтелектуальних порад (#201-230) з динамічними даними ({delta_pct}%, {predicted_score}, {churn_pct}%, etc.), Telegram delivery schedule з 4 touchpoints (09:00/14:00/17:00/instant), Predictive Engine для score/revenue/churn/DMT forecasting, Cross-Metric Correlation tips, Self-Learning feedback loop, та Telegram Bot commands. Загалом 230 порад з індивідуальними правилами ескалації та de-ескалації.

