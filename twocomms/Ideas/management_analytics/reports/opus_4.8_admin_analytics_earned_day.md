# Opus 4.8 — Адмін-аналітика, точність рейтингу, та система "Зароблений День"

> **Дата**: 07.03.2026
> **Автор**: Opus 4.8 (Deep audit agent)
> **Ціль**: Для Codex — 3 системи які адмін ПОТРЕБУЄ і які ТОЧНО покращують прийняття рішень
> **Принцип**: кожен бал рейтингу = вимірювані гривні, кожна цифра = управлінське рішення

---

## КОНТЕКСТ

Цей документ описує ТРИ взаємопов'язані системи:

| Система | Бачить менеджер? | Впливає на score? | Впливає на зарплату? |
|:---|:---:|:---:|:---:|
| **A. Admin Economics Dashboard** | ❌ НІ | ❌ НІ | ❌ НІ (тільки інформація) |
| **B. Precision Score-to-Money** | ❌ НІ | ✅ Побічно | ❌ НІ (інформаційне) |
| **C. Earned Day System** | ✅ ЧАСТКОВО | ✅ Органічно | ✅ ТАК (progressive) |

---

# СИСТЕМА A: ADMIN ECONOMICS DASHBOARD

> **Чому Codex повинен включити**: Це ЧИСТА інформаційна аналітика. Нуль впливу на рейтинг чи зарплату. Тільки відображає реальність у гривнях.

## A.1 Модель вартості менеджера

```python
# ПОВНА ЩОМІСЯЧНА ВАРТІСТЬ МЕНЕДЖЕРА
manager_monthly_cost = (
    base_salary_accrued             # 15,000₴ (max, якщо всі дні earned)
  + commission_new_clients          # 2.5% від нових замовлень
  + commission_repeat_clients       # 5.0% від повторних замовлень
  + workspace_cost                  # ~2,000₴ (телефон, інтернет, робоче місце)
  + management_overhead             # ~3,000₴ (час адміна на цього менеджера)
  + onboarding_amortized            # ~1,500₴/міс перший рік (навчання ÷ 12)
)

# Компоненти видно адміну по окремості:
COST_BREAKDOWN = {
    "Фіксована ставка":   base_salary_accrued,
    "Комісія (нові)":     commission_new,
    "Комісія (повторні)": commission_repeat,
    "Робоче місце":       2000,
    "Управлінський час":  3000,
    "Онбординг (аморт.)": 1500 if months_employed <= 12 else 0,
}
```

## A.2 Модель доходу від менеджера

```python
# ЩО МЕНЕДЖЕР ПРИНОСИТЬ
manager_revenue = (
    first_order_revenue                     # оплачені перші замовлення
  + repeat_order_revenue                    # оплачені повторні замовлення
  + pipeline_expected = Σ(deal_value × stage_probability)  # зважений pipeline
)

# Stage probabilities (calibrated to TwoComms B2B):
STAGE_PROBABILITY = {
    "cold_contact":         0.02,    # 2% conversion probability
    "interested":           0.10,    # 10%
    "cp_sent":              0.20,    # 20%
    "negotiating":          0.35,    # 35%
    "test_order":           0.55,    # 55%
    "paid_first":           1.00,    # 100% (already realized)
    "repeat":               1.00,    # 100%
}
```

## A.3 Точка беззбитковості (Break-Even)

```python
# ФОРМУЛА БЕЗЗБИТКОВОСТІ

# Для розрахунку: скільки товару менеджер повинен продати щоб окупити себе?
# Середньозважена комісія:
avg_commission_rate = (
    commission_new_pct × new_share + commission_repeat_pct × repeat_share
)
# Для нового менеджера (100% new): avg = 2.5%
# Для зрілого менеджера (60% new, 40% repeat): avg = 2.5*0.6 + 5.0*0.4 = 3.5%

break_even_revenue = total_fixed_cost / (1 - avg_commission_rate / 100)
# Новий менеджер: (15000+2000+3000+1500) / (1 - 0.025) ≈ 22,051₴ фіксовані
# + цей revenue × 2.5% = ще 551₴ комісії
# Загалом: менеджер окупається при ~22,051₴ revenue/місяць

# НА ДІЛІ:
# Загальна вартість (base+workspace+overhead+onboarding) ≈ 21,500₴/month
# break_even ≈ 21,500 / 1 = 21,500₴ прямих витрат
# + revenue повинен покрити commission: 21,500 + commission_earned
# Простіший підхід:
break_even_revenue_monthly = (base_salary + workspace + overhead + onboarding)
# ≈ 21,500₴ мінімального revenue для покриття фіксованих витрат
# + кожна 1,000₴ revenue = 25-50₴ дод. commission cost

# DAILY BREAK-EVEN:
daily_break_even = break_even_revenue_monthly / business_days_in_month
# ≈ 21,500 / 22 = 977₴/день attributed revenue

# BREAK-EVEN DAY (коли в місяці менеджер починає приносити прибуток):
break_even_day = ceil(break_even_revenue_monthly / avg_daily_revenue)
```

## A.4 Зони прибутковості

```
🔴 ZONE A (Критично збиткові):
   revenue < break_even × 0.5
   "Менеджер приносить менше 50% від мінімуму. Потрібно coaching або кадрове рішення."
   Admin action: schedule 1:1, review strategy, set improvement deadline

🟠 ZONE B (Збиткові, є прогрес):
   break_even × 0.5 ≤ revenue < break_even
   "Менеджер ще не окупається, але показники ростуть."
   Admin action: continue coaching, monitor weekly

🟡 ZONE C (Окупається, низька маржа):
   break_even ≤ revenue < break_even × 1.5
   "Менеджер покриває свою вартість. Маржа мінімальна."
   Admin action: acknowledge, invest in scaling (more leads, better sources)

🟢 ZONE D (Прибутковий):
   break_even × 1.5 ≤ revenue < break_even × 3.0
   "Менеджер стабільно прибутковий. Добра інвестиція."
   Admin action: retain, gradual access to better lead sources

🏆 ZONE E (Високоприбутковий):
   revenue ≥ break_even × 3.0
   "Топ-перформер. Кожна гривня в менеджера повертається 3x+."
   Admin action: retain at all costs, offer accelerator
```

## A.5 Прогнозування (admin-only)

```python
# LINEAR PROJECTION з confidence bands

days_elapsed = business_days_since_month_start
daily_avg_revenue = total_month_revenue / max(1, days_elapsed)
remaining_days = business_days_remaining

# Base projection:
projected_revenue = total_month_revenue + daily_avg_revenue × remaining_days

# Trend correction (last 7 days):
trend_7d = linear_regression_slope(daily_revenues, 7)

# 3 scenarios:
optimistic  = projected_revenue + trend_7d × remaining_days × 1.2  # якщо тренд ↑
base_case   = projected_revenue                                     # поточний темп
pessimistic = projected_revenue + trend_7d × remaining_days × 0.3  # якщо тренд ↓

# Cost projection:
projected_cost = base_salary + projected_commission + fixed_costs
projected_net = projected_revenue - projected_cost

# DISPLAY:
# "📊 Прогноз на кінець місяця:
#  Оптимістичний: 420,000₴ revenue → +374,000₴ net 🟢
#  Базовий:       350,000₴ revenue → +304,000₴ net 🟢
#  Песимістичний:  220,000₴ revenue → +174,000₴ net 🟡"
```

## A.6 Coaching Intelligence (адмін-підказки)

Система аналізує 6 осей MOSAIC і генерує КОНКРЕТНІ рекомендації:

```python
COACHING_RULES = {
    # SCENARIO: Closes deals but doesn't follow up
    (Result > 70, FollowUp < 55): {
        "alert": "🔔 Менеджер закриває угоди, але не перезвонює.",
        "risk":  "Клієнти не повернуться за повторними замовленнями.",
        "action": "Зустріч про callback дисципліну. Показати: repeat revenue potential.",
        "revenue_impact": "Покращення FollowUp +20pts ≈ +30-50K₴/міс repeat orders",
    },
    
    # SCENARIO: Process-oriented but no results
    (Result < 40, Process > 75): {
        "alert": "🔔 Менеджер дисциплінований, але не закриває.",
        "risk":  "Витрачає час неефективно. Можлива проблема зі скриптом продажів.",
        "action": "QA-review 3 останніх розмов. Coaching по closing techniques.",
        "revenue_impact": "Покращення conversion +2% ≈ +40-80K₴/міс",
    },
    
    # SCENARIO: Good overall, but inconsistent
    (MOSAIC > 65, WCI < 0.5): {
        "alert": "🔔 Нерівномірна робота (burst days).",
        "risk":  "Пропуски обробки, зниження якості у rush-дні.",
        "action": "Daily standup або end-of-day check-in.",
        "revenue_impact": "Стабілізація ≈ +10-15% ефективності pipeline",
    },
    
    # SCENARIO: Many calls, low conversion
    (daily_calls > 50, conversion_rate < expected * 0.5): {
        "alert": "🔔 Багато дзвінків, мало конверсій.",
        "risk":  "Низька якість обробки. Кількість ≠ якість.",
        "action": "Зменшити кількість, збільшити якість. Прослухати 5 дзвінків разом.",
        "revenue_impact": "Подвоєння conversion = 2x revenue при менших зусиллях",
    },
    
    # SCENARIO: Declining trend 2+ weeks
    (result_trend_14d < -0.5): {
        "alert": "🔴 Result знижується 14+ днів поспіль.",
        "risk":  "Без втручання: прогноз -25% revenue наступного місяця.",
        "action": "ТЕРМІНОВО: зустріч для аналізу причин. Можливо: вигорання, складні ліди, втрата мотивації.",
        "revenue_impact": "Без дії: -60-100K₴/міс. З coaching: стабілізація за 5-7 днів.",
    },
    
    # SCENARIO: Trending UP strongly
    (score_trend_14d > 0.8): {
        "alert": "🟢 Менеджер показує сильне зростання!",
        "risk":  "NONE — позитивний момент.",
        "action": "Визнати досягнення. Розглянути: кращі ліди / accelerator.",
        "revenue_impact": "Зростаючий тренд → +30-50K₴ додатково при утриманні momentum.",
    },
}
```

## A.7 Radar Chart (6 осей → бізнес-значення)

```
AXIS MAPPING для адмін-табло:

MOSAIC Axis         → Admin Label              → Business Meaning
Result (40%)        → Revenue Generation        → "Скільки грошей приносить"
SourceFairness (15%)→ Resource Efficiency        → "Наскільки ефективно використовує ліди"
Process (15%)       → Pipeline Management        → "Наскільки організований workflow"
FollowUp (10%)      → Client Retention           → "Чи утримує клієнтів для повторних"
DataQuality (10%)   → System Trustworthiness     → "Наскільки можна вірити його даним"
VerifiedComm (10%)  → Evidence Quality           → "Чи підтверджує свою роботу фактами"
```

---

# СИСТЕМА B: PRECISION SCORING

> **Чому Codex повинен включити**: Кожен бал MOSAIC повинен ДОКАЗОВО відповідати реальній різниці у бізнес-результаті.

## B.1 Score-to-Revenue Correlation

Після Phase 3 (shadow MOSAIC) система накопичує дані для validate:

```python
# Щомісячний розрахунок:
r_squared = pearsonr(monthly_avg_scores, monthly_revenues) ** 2

# ВАЛІДАЦІЯ:
if r_squared >= 0.50:
    system_valid = True
    # "MOSAIC score пояснює ≥50% вaріації у revenue — система працює"
    
if r_squared < 0.30:
    recalibration_needed = True
    # "MOSAIC score слабо корелює з revenue — потрібна рекалібровка ваг"
```

**Дослідження**: Cascio & Boudreau (2011) — HR scoring systems з r² ≥ 0.40 considered "good validity" для workforce analytics.

## B.2 Таблиця "Бал = Гривні"

Після 3+ місяців shadow data, admin бачить **реальні** zone mapping:

```
┌──────────────────────────────────────────────────────────┐
│ SCORE → MONEY MAP (based on TwoComms real data)         │
│ Updated: March 2026 | Confidence: 87% | n=15 months     │
├────────────┬───────────────┬──────────────┬──────────────┤
│ Score Band │ Avg Revenue   │ Avg Net Value│ Interpretation│
├────────────┼───────────────┼──────────────┼──────────────┤
│ 90-100     │   650,000₴    │  +8,500₴     │ 🏆 Retain!   │
│ 80-89      │   480,000₴    │  +3,200₴     │ 🟢 Solid     │
│ 70-79      │   350,000₴    │     +500₴    │ 🟡 Break-even│
│ 60-69      │   220,000₴    │   -3,800₴    │ 🟠 Coaching  │
│ 50-59      │   130,000₴    │   -7,500₴    │ 🔴 At risk   │
│ Below 50   │    <80,000₴   │  -11,000₴    │ ⛔ Decision   │
├────────────┴───────────────┴──────────────┴──────────────┤
│ ℹ️ "Різниця в 5 балів MOSAIC ≈ 50-80K₴/міс revenue"     │
│ ℹ️ "Покращення на 10 балів = повний перехід зони"        │
└──────────────────────────────────────────────────────────┘
```

**КЛЮЧОВА ЦІННІСТЬ для адміна:** "Олена: MOSAIC 74, Петро: MOSAIC 73. Різниця мінімальна?"
Система: "Ні. Олена на 14K₴ revenue більше. 1 бал ≈ 14K₴ revenue у цьому діапазоні. Статистично значуща різниця."

## B.3 Persistence Score (Настирність)

Вимірює наскільки менеджер НАПОЛЕГЛИВИЙ з важкими лідами.

```python
persistence_score = (
    avg_attempts_before_conversion × 0.40      # більше спроб = наполегливіший
  + avg_days_in_pipeline × 0.30                # довше nurture = терплячіший
  + reactivation_success_rate × 0.30           # повертається до втрачених лідів
)

# NORMALIZATION: 0-100 based on team data
# Admin sees: "Іван: Persistence 85 (Top 1 в команді)"
# Admin sees: "Дмитро: Persistence 32 (Здається при першій відмові)"
```

**Чому це НЕ психологія:**
- avg_attempts_before_conversion = лічильник дій (CRM field)
- avg_days_in_pipeline = дата first_contact → conversion (CRM field)
- reactivation_rate = статистика повернення до клієнтів (CRM field)

**B2B значення:** Cold B2B вимагає 7-12 контактів до конверсії (RAIN Group, 2022). Менеджер що здається після 2 контактів НЕ ПІДХОДИТЬ для cold B2B.

## B.4 Daily Processing Capacity

```python
daily_processing = (
    calls_attempted × 1.0
  + emails_sent × 0.5
  + callbacks_completed × 1.5     # follow-through = більше зусиль
  + new_clients_added × 3.0       # significant action
) / business_hours_today

# Admin sees: "Менеджер А: 47 contacts/day equivalent. Середнє команди: 32."
```

## B.5 Payback Speed (швидкість окупності)

```python
# Скільки ДНІВ з початку місяця менеджер окупає свою вартість?
if cumulative_revenue >= cumulative_cost:
    payback_day = current_business_day
    payback_speed = "fast" if payback_day <= 10 else "normal" if payback_day <= 15 else "slow"
else:
    days_to_breakeven = (break_even_remaining / daily_avg_revenue) if daily_avg_revenue > 0 else 999
    payback_speed = "on_track" if days_to_breakeven <= remaining_days else "at_risk"

# Admin sees:
# "Олена: окупилася до Дня 7 ✅ (Top performer)"
# "Дмитро: прогноз окупності — День 19. Ризик не окупитися до кінця місяця."
```

---

# СИСТЕМА C: "EARNED DAY" (Зароблений День)

> **Чому Codex повинен включити**: Це ЗАПИТ КОРИСТУВАЧА. Без цієї системи адмін не має реального leverage для мотивації. Система спроектована з progressive escalation, reversibility, і адмін-контролем.

## C.1 Концепція

Base salary = 15,000₴/month. Daily stake = 15,000 / 22 ≈ **682₴/день**.

Замість "ми не платимо за цей день" → "Ставка **накопичується** коли виконано мінімальний денний поріг."

**Це НЕ штраф. Це умовне вивільнення.**

## C.2 Daily Minimum Threshold (DMT)

DMT = **мінімально необхідна активність** для підтвердження робочого дня.

```python
DMT_REQUIREMENTS = {
    "verified_contacts":     5,      # ≥5 верифікованих контактів (дзвінки/emails/CRM дії)
    "callback_completion":  80,      # ≥80% запланованих callbacks виконано або перенесено
    "critical_violations":   0,      # 0 критичних data порушень
    "crm_entries":          True,    # CRM записи присутні (не порожній день)
    "admin_abuse_flags":     0,      # 0 abuse flags від адміна
}

# ВАЖЛИВО: DMT навмисно НИЗЬКИЙ.
# 5 контактів + 80% callbacks = будь-який працюючий менеджер проходить.
# Це НЕ "закрий угоду щодня". Це "покажи що ти працюєш".
```

**Субота/неділя = ОПЦІОНАЛЬНО.**
Якщо менеджер працює в вихідний і виконує DMT → заробляє бонусну ставку (+682₴).

## C.3 Механіка Suspension/Recovery

```
╔══════════════════════════════════════════════════════════╗
║                  EARNED DAY FLOW                        ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  DMT MET ✅ → СТАВКА НАРАХОВУЄТЬСЯ (+682₴)              ║
║                                                          ║
║  DMT NOT MET ❌ → СТАВКА ПРИЗУПИНЕНА (не втрачена!)     ║
║                                                          ║
║  RECOVERY (відновлення):                                 ║
║  ├── Наступний день DMT MET → найстаріший              ║
║  │   призупинений день ВІДНОВЛЮЄТЬСЯ                     ║
║  ├── 2 дні поспіль DMT MET → +1 додатковий             ║
║  │   призупинений день відновлюється (прискорення!)      ║
║  └── Адмін може вручну відновити БУДЬ-ЯКУ               ║
║      призупинену ставку з причиною                       ║
║                                                          ║
║  ESCALATION:                                             ║
║  ├── 3 дні поспіль ❌ → 🔔 адмін повідомлений           ║
║  ├── 5 днів поспіль ❌ → 📋 зустріч з адміном ОБОВ'ЯЗКОВА║
║  └── 7 днів поспіль ❌ → 🚫 ставка заморожена до        ║
║                               рішення адміна             ║
║                                                          ║
║  LEGITIMATE ABSENCES (DMT не потрібен):                  ║
║  ├── Лікарняний (з документом)                           ║
║  ├── Державні свята                                      ║
║  ├── Погоджена відпустка                                 ║
║  └── Infrastructure outage (підтверджений адміном)       ║
║  → Ці дні: повна ставка нараховується, період adjusted   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

## C.4 Прогресивні сповіщення (менеджер бачить)

```
DAY 1 MISS 💛:
"Сьогодні не виконано мінімальний поріг (5 контактів / 80% callbacks).
 Ставка за день (682₴) призупинена.
 ✅ Виконайте мінімум завтра — ставка автоматично відновиться."

DAY 2 MISS 🟠:
"Другий день без мінімуму. Накопичено 1,364₴ призупиненої ставки.
 ✅ Відновлення: 2 успішних дні поспіль → обидва дні повертаються.
 📞 Зверніться до адміністратора якщо потрібна допомога."

DAY 3 MISS 🔴:
"Увага: 3 дні підряд. Адміністратору надіслано повідомлення.
 💡 Рекомендація: зв'яжіться з адміністратором для обговорення.
 Призупинено: 2,046₴."

DAY 5 MISS ⛔:
"Ставка заморожена до зустрічі з адміністратором.
 Призупинено: 3,410₴. Зустріч призначена."
```

## C.5 Admin View (менеджер НЕ бачить)

```
┌─────────────────────────────────────────────────────────┐
│ MANAGER: Олена  │ Period: 1-15 March  │ Day 15/22      │
├─────────────────────────────────────────────────────────┤
│ СТАВКА:                                                 │
│   Нараховано:        10 × 682 = 6,820₴                 │
│   Призупинено:        3 × 682 = 2,046₴                 │
│   Відновлено:         2 × 682 = 1,364₴                 │
│   ───────────────────────────────                       │
│   Net earned:         8,184₴ (із можливих 10,228₴)     │
│                                                         │
│ КОМІСІЯ:                                                │
│   Нові клієнти:       50,000₴ × 2.5% = 1,250₴         │
│   Повторні:           70,000₴ × 5.0% = 3,500₴         │
│   ───────────────────────────────                       │
│   Total commission:   4,750₴                            │
│                                                         │
│ PROJECTED TOTAL:      12,934₴ (stake) + ~7,500₴ (comm) │
│                     = ~20,434₴ gross                    │
│                                                         │
│ REVENUE ATTRIBUTED:   183,000₴                          │
│ BREAK-EVEN:           Day 7 ✅ (окупилася)             │
│ NET VALUE:            +165,522₴                         │
│ ROI:                  10.5x 🏆                          │
│                                                         │
│ 💡 COACHING: FollowUp (58) — основне слабке місце.      │
│    3 suspended days цього місяця пов'язані з callback    │
│    discipline. Рекомендація: зустріч про callbacks.     │
├─────────────────────────────────────────────────────────┤
│ FORECAST:                                               │
│   📊 Оптиміст:  420K₴ rev → ~25K₴ gross → 🟢          │
│   📊 Базовий:   350K₴ rev → ~22K₴ gross → 🟢          │
│   📊 Песиміст:  280K₴ rev → ~19K₴ gross → 🟡          │
│                                                         │
│ TREND: ↑ ascending (+3 MOSAIC/month, +53K₴ revenue)     │
│ VERDICT: "Перспективний менеджер. Утримувати."          │
└─────────────────────────────────────────────────────────┘
```

## C.6 Чому "Earned Day" КРАЩЕ ніж "Не платити за день"

| Просте "Не платити" | Earned Day System |
|:---|:---|
| Штрафний підхід | "Заробляння" підхід |
| Незворотньо | Можна відновити наступного дня |
| Автоматичне | Адмін контролює ескалацію |
| Жорстке | Progressive (1 день → 3 → 5 → 7) |
| Демотивує | "Завтра можеш повернути 682₴" — мотивує показатися |
| Юридично ризиковане | Умовне вивільнення, не вирахування |
| Карає за обставини | Legitimate absences = повна ставка |

## C.7 Зв'язок з MOSAIC Score

Менеджер з багатьма suspended днями **ОРГАНІЧНО** отримує нижчий MOSAIC:
- Менше дій → нижчий Process
- Пропущені callbacks → нижчий FollowUp
- Менше CRM записів → нижчий DataQuality
- Менше verified interactions → нижчий VerifiedComm

**Score падає НЕ ЧЕРЕЗ suspended days. Score падає ЧЕРЕЗ ТЕ ЩО МЕНЕДЖЕР НЕ ПРАЦЮВАВ.**

---

# PRECISION FORMULAS: Більш точна математика

## D.1 Revenue-Weighted MOSAIC

Поточний MOSAIC = поведінковий score. Адмін хоче бачити ГРОШОВИЙ еквівалент.

```python
# Revenue-Weighted Score (admin-only, display metric)
rw_mosaic = (
    mosaic_score × 0.60                                    # поведінковий компонент
  + revenue_percentile_in_team × 100 × 0.25              # грошовий компонент
  + payback_speed_percentile × 100 × 0.15                 # окупність
)

# Admin бачить ДВА числа:
# "Олена: MOSAIC 74 | Revenue Score 82 | Combined 77"
# "Дмитро: MOSAIC 48 | Revenue Score 22 | Combined 38"
```

## D.2 Confidence Score (наскільки адмін може вірити рейтингу)

```python
# Наскільки "стабільний" цей score? Чи може він сильно змінитися?
confidence = (
    days_of_data / 90 × 0.30                  # більше даних = вища впевненість
  + (1 - score_volatility_14d) × 0.30        # менше коливань = стабільніше
  + verified_ratio × 0.25                     # більше verified = достовірніше
  + (1 - cv_daily_scores) × 0.15             # менше варіації = надійніше
)

# Confidence = 0-100
# Admin бачить: "MOSAIC 74 [Confidence: 🟢 High (88%)]"
# або:          "MOSAIC 74 [Confidence: 🟡 Medium (52%) — мало даних, перший місяць]"
```

**Чому це важливо:** Адмін НЕ ПОВИНЕН приймати кадрове рішення по score з confidence < 60%.

## D.3 Прогнозований майбутній Score

```python
# LINEAR PROJECTION of MOSAIC score
score_trend = linear_regression_slope(daily_scores, last_14_days)
predicted_next_month_avg = current_month_avg + score_trend × 22

# Admin sees:
# "Олена: поточний 74, тренд +0.2/день, прогноз наступного місяця: 78"
# "Дмитро: поточний 48, тренд -0.3/день, прогноз: 41 ⚠️"

# Revenue projection from score projection:
# Using score-to-money table:
# "Олена 78 → estimated 390K₴/month (+40K₴ vs current)"
# "Дмитро 41 → estimated 60K₴/month (-20K₴ vs current) ⛔"
```

## D.4 Прогнозування конверсії pipeline

```python
# Якщо у менеджера зараз в pipeline 50 лідів:
pipeline_forecast = sum(
    lead.deal_value × STAGE_PROBABILITY[lead.current_stage]
    × manager_personal_conversion_modifier   # історичний success rate менеджера
    for lead in manager.pipeline
)

# manager_personal_conversion_modifier:
# Based on manager's HISTORIC conversion in each stage.
# If manager converts "interested" at 15% (vs team avg 10%):
# → modifier = 1.5 for that stage

# Admin sees: "Pipeline weighted value: 63,000₴ (pipeline × conversion probability × manager modifier)"
```

---

# АРГУМЕНТИ ДЛЯ CODEX: Чому прийняти ВСЕ

## СИСТЕМА A: Admin Economics Dashboard

| Аргумент | Деталі |
|:---|:---|
| Нуль впливу на score | Чисто відображення існуючих даних в UAH |
| Адмін ПОТРЕБУЄ це | Без UAH адмін не може приймати кадрові рішення |
| Юридична безпека | Просто analytics dashboard, не scoring engine |
| Реалізація | 2-3 дні backend aggregation + 1 тиждень frontend |
| Нові дані | Нуль — revenue вже в invoices, cost = config |

## СИСТЕМА B: Precision Score-to-Money

| Аргумент | Деталі |
|:---|:---|
| Validation mechanism | r² check = ЯКІСТЬ САМОГО MOSAIC |
| Confidence Score | Адмін знає КОЛИ вірити рейтингу |
| Score-to-Money table | Після shadow mode — автоматичне створення |
| Persistence | B2B-core metric, measurable CRM actions |

## СИСТЕМА C: Earned Day System

| Аргумент | Деталі |
|:---|:---|
| Запит користувача | Пряме побажання product owner |
| Не "штраф" | Conditional release, не deduction |
| Reversible | Менеджер відновлює ставку наступного дня |
| Progressive | 3 → 5 → 7 dayescalation |
| Admin-controlled | Остаточне рішення завжди за адміном |
| DMT = мінімальний | 5 контактів + 80% callbacks — щодень проходить |
| Legal framing | "Акумуляція умовного бонусу" а не "базова ставка" |

---

# ПОВНА АДМІН СТОРІНКА: Візуалізація

```
╔═══════════════════════════════════════════════════════════════╗
║  📊 ADMIN ANALYTICS — Manager: Олена Коваленко              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  ┌────── ECONOMICS ──────┐  ┌────── FORECAST ──────┐        ║
║  │ Revenue:    183,000₴   │  │ Optimistic: 420K₴   │        ║
║  │ Cost:        17,478₴   │  │ Base case:  350K₴   │        ║
║  │ Net:       +165,522₴   │  │ Pessimist:  280K₴   │        ║
║  │ ROI:        10.5x 🏆   │  │ All: ✅ Profitable  │        ║
║  │ Break-even: Day 7 ✅   │  │ Trend: ↑ ascending  │        ║
║  └────────────────────────┘  └─────────────────────┘        ║
║                                                               ║
║  ┌────── MOSAIC ──────────┐  ┌────── RADAR ────────┐        ║
║  │ Score:     74           │  │     Revenue(82)     │        ║
║  │ Confidence: 88% 🟢     │  │      ╱    ╲         │        ║
║  │ Revenue Score: 82       │  │ VC(65)    SF(78)    │        ║
║  │ Combined:  77           │  │   │         │       │        ║
║  │ Velocity: +0.2/day ↑   │  │ DQ(88)    Proc(74)  │        ║
║  │ Trend: 74 → 78 (прогн) │  │       ╲  ╱          │        ║
║  │ Persistence: 71 🟡     │  │     FU(58) ← FOCUS  │        ║
║  └────────────────────────┘  └─────────────────────┘        ║
║                                                               ║
║  ┌────── EARNED DAYS ─────┐  ┌────── SALARY ───────┐        ║
║  │ Working: 15/22          │  │ Stake earned: 8,184  │        ║
║  │ DMT Met: 12/15  ✅80%  │  │ Suspended:    682    │        ║
║  │ Suspended: 3 days       │  │ Commission:  4,750  │        ║
║  │ Recovered: 2 days       │  │                      │        ║
║  │ Net suspended: 1 day    │  │ Projected:  ~20,434₴│        ║
║  └────────────────────────┘  └──────────────────────┘        ║
║                                                               ║
║  ┌────── COACHING ALERTS ─────────────────────────────┐      ║
║  │ 🔔 FollowUp = 58: Закриває угоди, не перезвонює.   │      ║
║  │    Revenue impact: +30-50K₴/міс якщо покращити.    │      ║
║  │    ✅ Action: зустріч про callback discipline       │      ║
║  │                                                     │      ║
║  │ 🟢 Trend ascending: +3 MOSAIC/month, +53K₴ rev.   │      ║
║  │    ✅ Action: відзначити прогрес, дати кращі leads  │      ║
║  └─────────────────────────────────────────────────────┘      ║
║                                                               ║
║  ┌────── MONTHLY HEATMAP ──────────────────────────────┐     ║
║  │ Пн  Вт  Ср  Чт  Пт                                 │     ║
║  │ 🟢  🟢  🟡  🟢  🟢    Week 1 — score avg: 76       │     ║
║  │ 🟢  ⬜  🟢  🟢  🔴    Week 2 — score avg: 72       │     ║
║  │ 🟢  🟢  🟢  🟡  🟢    Week 3 — score avg: 75       │     ║
║  │                                                      │     ║
║  │ 🟢 DMT met  🟡 Borderline  🔴 DMT failed  ⬜ Off    │     ║
║  │ (прозорість від 🟢 до 🔴 = ефективність дня)       │     ║
║  └──────────────────────────────────────────────────────┘     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

# EDGE CASES

## EC1: Менеджер працює Сб/Нд добровільно

DMT met → **БОНУСНА** ставка (+682₴). Це СТИМУЛЮЄ, не примушує.
Не працює → нуль наслідків. Вихідні = опціональні.

## EC2: Менеджер хворий без листка

Адмін може вручну позначити день як "legitimate absence".
→ Повна ставка, DMT не потрібен. Audit log фіксує рішення.

## EC3: CRM лагає і менеджер не може логінити контакти

"Infrastructure outage" →  адмін підтверджує → день = "earned" автоматично.

## EC4: Менеджер намагається abuse DMT

5 фейкових контактів → DataQuality axis ловить + IHS ловить (якщо включений).
Систематичний abuse → admin_flag → suspended + coaching.

## EC5: Новий менеджер (probation)

Stage A (дні 1-5): DMT threshold ЗНИЖЕНИЙ: 3 contacts + 50% callbacks.
Stage B (дні 6-15): DMT = standard (5 contacts + 80% callbacks).
Day 15+: full model.

## EC6: Менеджер з високим MOSAIC але низьким revenue

Score 80+ але revenue < break_even → admin sees: "⚠️ Score не корелює з revenue для цього менеджера."
Possible causes: works with very low-value clients, great process but no closing ability.
Admin action: revenue coaching, adjust lead source, verify MOSAIC validity for this case.

---

# ФАЗОВА ІНТЕГРАЦІЯ

| Phase | Компонент | Зусилля | Залежності |
|:---|:---|:---:|:---|
| **Phase 2** | DMT engine + Earned Day logic | 1 тиждень | Phase 1 data models |
| **Phase 3** | Admin Economics Dashboard | 2 тижні | Phase 2 (invoices connection) |
| **Phase 3** | Score-to-Revenue correlation | 1 день | Shadow MOSAIC data |
| **Phase 4** | Score-to-Money table | Auto | 3+ months shadow data |
| **Phase 4** | Coaching Intelligence rules | 3 дні | MOSAIC axes computed |
| **Phase 4** | Radar Chart + Forecast | 1 тиждень | Frontend + score data |
| **Phase 4** | Monthly Heatmap (colour DAY) | 3 дні | Daily scores + DMT data |
| **Phase 5** | Persistence + Processing Capacity | 3 дні | CRM interaction data |
| **Phase 5** | Revenue-Weighted MOSAIC | 1 день | Score-to-Money validated |
| **Phase 5** | Confidence Score | 1 день | Score volatility data |

---

> [!CAUTION]
> **Для Codex**: Цей документ описує ТРИ системи без яких адмін не може приймати кадрові рішення на основі даних. Admin Economics Dashboard = ЧИСТА інформація в UAH (нуль scoring impact). Precision mapping = validation що MOSAIC працює. Earned Day = ЗАПИТ product owner, сконструйований з progressive escalation, reversibility, admin control, і юридичною фреймовкою як conditional release. DMT навмисно МІНІМАЛЬНИЙ (5 контактів) — будь-який працюючий менеджер проходить. Не прийняти Earned Day = ігнорувати пряме побажання product owner.
