# 📊 Hybrid Efficiency System (HES) — Полная спецификация

> **Документ создан на основе глубокого анализа через 8 этапов секвентивного мышления с 5 ветвями размышлений (C-deep, C-metrics, C-formula, C-admin, C-anti-game)**

## Оглавление
1. [Философия системы](#1-философия-системы)
2. [4-уровневая таксономия метрик](#2-таксономия-метрик)
3. [Формула HES](#3-формула-hes)
4. [Provisional Points — отложенное начисление](#4-provisional-points)
5. [Anti-Gaming механизмы](#5-anti-gaming-механизмы)
6. [Admin-tunable конфигурация](#6-admin-tunable-конфигурация)
7. [Trust Ratio — детектор аномалий](#7-trust-ratio)
8. [Интеграция с Heatmap](#8-интеграция-с-heatmap)
9. [Модели данных](#9-модели-данных)
10. [Сценарии атак и защита](#10-сценарии-атак)

---

## 1. Философия системы

> [!IMPORTANT]
> **Главный принцип**: Итоговый результат важнее промежуточных действий. Менеджер не должен за 1 час выполнить KPI отправкой КП в мессенджеры, где администратор не может проверить. **Перезвон по итоговому результату — это то, что важно.**

### 1.1 Три столпа HES

```
┌─────────────────────────────────────────────────────────┐
│                        HES Score                        │
│                                                         │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│   │ RESULTS  │   │ QUALITY  │   │ ACTIVITY │           │
│   │   60%    │   │   25%    │   │   15%    │           │
│   │ (default)│   │ (default)│   │ (default)│           │
│   └──────────┘   └──────────┘   └──────────┘           │
│                                                         │
│   Не подделать    Детектируем    Мин. порог             │
│   (оплата =       копипаст       + лог. шкала          │
│    реальная)      причин         + velocity cap         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Ключевая идея: "Нельзя подделать оплату"

> В бизнес-модели пользователя: **магазин добавлен = уже оплатил**. Это значит что Result Score НЕЛЬЗЯ подделать — деньги реальные. Поэтому Results имеют 60% веса по умолчанию, и в формуле это **непробиваемый щит** от любого гейминга.

### 1.3 Почему НЕ чистый ELO / KPD

| Подход | Проблема | HES решает |
|--------|----------|------------|
| Чистый ELO | Один показатель, не учитывает бизнес-специфику | Мульти-компонентный |
| Текущий KPD (4 компонента) | Не различает "честную" vs "нечестную" работу | Trust Ratio + Provisional |
| Points-only | Легко сгеймить количеством | Лог. шкала + velocity cap |
| Revenue-only | Слишком зависит от удачи | Quality + Activity как стабилизаторы |

---

## 2. Таксономия метрик (4 уровня доверия)

### TIER 1 — HARD RESULTS (не подделать, максимальная ценность)

| Метрика | Источник | Почему безопасна |
|---------|----------|------------------|
| Магазины подключены | Shop model, status=connected | Подключён = оплатил |
| Выручка | WholesaleInvoice, status=paid | Реальные деньги |
| Повторные заказы | WholesaleInvoice, repeat=True | Клиент вернулся |
| Retention rate | % магазинов с повторным заказом | Агрегат |

### TIER 2 — VERIFIABLE ACTIONS (верифицируемые, средняя ценность)

| Метрика | Источник | Верификация |
|---------|----------|-------------|
| КП отправлено через email | CommercialOfferEmailLog | Лог в БД |
| Follow-up выполнен | FollowUp model, status=completed | Системно |
| "Не интересно" с причиной | CallAttempt + NotInterestedReason | Проверяется |
| ≥3 попытки дозвона | CallAttempt count per client | Подсчётно |
| Отчёт сдан вовремя | DailyReport, submitted_at < deadline | Таймстемп |

### TIER 3 — SELF-REPORTED (самоотчётные, низкая ценность)

| Метрика | Источник | Риск |
|---------|----------|------|
| Звонки с личного телефона | Нет логов (личный тел., нет IP-телефонии) | ⚠️ Невозможно верифицировать |
| КП через мессенджер | Нет логов в системе | ⚠️ Невозможно верифицировать |
| Время на сайте | _update_last_seen | ⚠️ Вкладка открыта = "работает" |

> [!WARNING]
> **Текущая реальность**: Менеджеры звонят с ЛИЧНЫХ телефонов. Корпоративной IP-телефонии НЕТ. Записи разговоров отсутствуют. Это значит что ВСЕ данные о звонках — self-reported.

### TIER 4 — SYSTEM METRICS (пассивные, фоновая ценность)

| Метрика | Источник | Назначение |
|---------|----------|------------|
| Активное время на сайте | Actual clicks, не idle | Фоновый индикатор |
| Скорость реакции на лида | Время от created_at до assignment | Отзывчивость |
| Dismissed vs followed advice | AdviceDismiss model | Обучаемость |

> [!TIP]
> **Правило распределения**: Tier 1 метрики → Result Score (60%). Tier 2 → Quality Score (25%). Tier 3+4 → Activity Score (15%). Чем менее верифицируема метрика — тем меньше её вес.

---

## 3. Формула HES

### 3.1 Основная формула

```
HES = Result_Score × W_result + Quality_Score × W_quality + Activity_Score × W_activity

Где: W_result + W_quality + W_activity = 1.0
Defaults: W_result=0.60, W_quality=0.25, W_activity=0.15

Все Score нормализованы к 0-100 шкале.
HES итоговый: 0-100 (может быть >100 при перевыполнении)
```

### 3.2 Result Score (0-100+)

```python
def calculate_result_score(manager, period, config):
    """
    Считает ЖЁСТКИЕ результаты.
    Единственное что ДЕЙСТВИТЕЛЬНО важно.
    """
    # Подключённые магазины (добавлен = оплатил)
    shops = shops_connected_in_period(manager, period)
    shops_target = config.shops_target  # admin-tunable, default 2/week
    shops_score = min(40, (shops / shops_target) * 40)
    # 40 pts max: 2 shops/week target → 20 pts each

    # Выручка
    revenue = revenue_in_period(manager, period)
    revenue_target = config.revenue_target  # admin-tunable, default 50k/month
    revenue_score = min(30, (revenue / revenue_target) * 30)
    # 30 pts max

    # Повторные заказы (бонус — мотивация вести клиента)
    repeat_orders = repeat_orders_in_period(manager, period)
    repeat_score = min(20, repeat_orders * 5)
    # 20 pts max: 4+ повторных = максимум

    # Конверсия (processed → connected)
    processed = total_processed(manager, period)
    conversion = shops / max(1, processed)
    conversion_baseline = config.conversion_baseline  # default 0.05 (5%)
    conversion_score = min(10, (conversion / conversion_baseline) * 10)
    # 10 pts max

    return shops_score + revenue_score + repeat_score + conversion_score
    # Максимум: 100. Может быть >100 при перевыполнении.
```

### 3.3 Quality Score (0-100)

```python
def calculate_quality_score(manager, period, config):
    """
    Считает КАЧЕСТВО обработки.
    Это "умный" компонент — отличает честную работу от гейминга.
    """
    # 1. Причины отказа (0-30)
    total_not_interested = count_not_interested(manager, period)
    with_reason = count_not_interested_with_reason(manager, period)
    if total_not_interested > 0:
        reason_rate = with_reason / total_not_interested
        # Бонус за разнообразие причин (анти-копипаст)
        unique_reasons = count_unique_reasons(manager, period)
        diversity_bonus = min(1.2, unique_reasons / max(1, total_not_interested * 0.3))
        reason_score = min(30, reason_rate * 30 * diversity_bonus)
    else:
        reason_score = 15  # нет "не интересно" = нейтрально

    # 2. Callback completion rate (0-25)
    total_callbacks = count_callback_scheduled(manager, period)
    completed_callbacks = count_callback_completed(manager, period)
    if total_callbacks > 0:
        callback_rate = completed_callbacks / total_callbacks
        callback_score = callback_rate * 25
    else:
        callback_score = 12.5  # нет запланированных = нейтрально

    # 3. Provisional → Confirmed rate (0-25)
    total_interested = count_marked_interested(manager, period)
    confirmed_interested = count_interested_that_converted(manager, period)
    if total_interested > 0:
        confirm_rate = confirmed_interested / total_interested
        confirm_score = confirm_rate * 25
    else:
        confirm_score = 12.5

    # 4. Report & follow-up discipline (0-20)
    reports_on_time = count_reports_on_time(manager, period)
    total_reports = count_reports_expected(manager, period)
    followups_completed = count_followups_before_due(manager, period)
    total_followups = count_followups_total(manager, period)

    report_score = (reports_on_time / max(1, total_reports)) * 10
    followup_score = (followups_completed / max(1, total_followups)) * 10

    return reason_score + callback_score + confirm_score + report_score + followup_score
```

### 3.4 Activity Score (0-100, логарифмическая шкала)

```python
import math

def calculate_activity_score(manager, period, config):
    """
    Считает ОБЪЁМ активности.
    ЛОГАРИФМИЧЕСКАЯ шкала — больше != сильно лучше.
    Velocity cap — нельзя набрать за 1 час.

    Функция: log2(x+1) × multiplier, capped.
    При x=8: log2(9)=3.17 → хорошо
    При x=32: log2(33)=5.04 → немного лучше
    При x=100: log2(101)=6.66 → едва заметно лучше
    """
    # 1. Обработано клиентов (0-30, лог)
    processed = clients_processed(manager, period)
    processed_target = config.min_processed_daily * period_days(period)
    processed_score = min(30, math.log2(processed + 1) / math.log2(processed_target + 1) * 30)

    # 2. КП отправлено, ТОЛЬКО ВЕРИФИЦИРОВАННЫЕ email (0-20, лог)
    verified_cp = verified_cp_sent(manager, period)
    cp_score = min(20, math.log2(verified_cp + 1) * 5)

    # 3. Время на сайте (0-15, линейная до cap)
    active_minutes = actual_active_minutes(manager, period)  # реальные клики, не idle
    target_minutes = config.min_active_minutes_daily * period_days(period)
    time_score = min(15, (active_minutes / max(1, target_minutes)) * 15)

    # 4. Уникальные лиды (0-20, diversity requirement)
    unique_leads = unique_leads_worked(manager, period)
    leads_target = config.min_unique_leads_daily * period_days(period)
    leads_score = min(20, (unique_leads / max(1, leads_target)) * 20)

    # 5. Streak (0-15, последовательные рабочие дни)
    streak_days = consecutive_active_days(manager, period)
    streak_score = min(15, streak_days * 3)  # 5 дней подряд = максимум

    raw_score = processed_score + cp_score + time_score + leads_score + streak_score

    # === VELOCITY CAP ===
    # Проверяем: не набрал ли менеджер все очки за 1-2 часа?
    hourly_peak = max_activity_points_per_hour(manager, period)
    if hourly_peak > config.velocity_cap_per_hour:
        velocity_penalty = 0.7  # -30% штраф
    else:
        velocity_penalty = 1.0

    return raw_score * velocity_penalty
```

---

## 4. Provisional Points — Отложенное начисление

> [!IMPORTANT]
> **Ключевая анти-гейминг инновация**: "Заинтересован" = не факт. Баллы за промежуточные статусы начисляются УСЛОВНО и подтверждаются (или отзываются) позже.

### 4.1 Как работает

```
Менеджер обрабатывает клиента:

Status = "Interested"
  → Немедленно: +0.3 балла (20% от 1.5)
  → Таймер: 7 дней на подтверждение
  → Клиент заказал? → +1.2 дополнительно (итого 1.5)
  → Клиент не ответил? → -0.2 (итого 0.1, "penalty за ложный сигнал")

Status = "Callback"
  → Немедленно: +0.2 балла (20% от 1.0)
  → Таймер: 48 часов на перезвон
  → Перезвонил? → +0.8 дополнительно (итого 1.0)
  → Не перезвонил? → -0.2 (итого 0)

Status = "Connected" (магазин добавлен)
  → Немедленно: +3.0 балла (100% — подтверждение = оплата)
  → Никакого таймера — это ФИНАЛЬНЫЙ результат

Status = "Not Interested" (с причиной)
  → Немедленно: +0.5 балла (100%)
  → Без причины: 0 баллов
```

### 4.2 Модель

```python
class ProvisionalPoint(models.Model):
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    call_attempt = models.ForeignKey(CallAttempt, on_delete=models.CASCADE)

    class PointStatus(models.TextChoices):
        PROVISIONAL = "provisional", "Очікує підтвердження"
        CONFIRMED = "confirmed", "Підтверджено"
        EXPIRED = "expired", "Не підтверджено (минув термін)"
        REVOKED = "revoked", "Відкликано"

    status = models.CharField(max_length=20, choices=PointStatus.choices, default=PointStatus.PROVISIONAL)
    immediate_points = models.FloatField(default=0)   # начислено сейчас
    pending_points = models.FloatField(default=0)      # ожидает подтверждения
    final_points = models.FloatField(null=True)        # итоговое начисление
    expires_at = models.DateTimeField()                 # когда истечёт ожидание
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["manager", "status", "-expires_at"]),
        ]
```

### 4.3 Cron для подтверждения/отзыва

```python
# Запуск каждый час (или в 00:00 вместе с heatmap)
def process_provisional_points():
    expired = ProvisionalPoint.objects.filter(
        status=ProvisionalPoint.PointStatus.PROVISIONAL,
        expires_at__lte=timezone.now()
    )
    for pp in expired:
        # Проверить: клиент конвертировался?
        if pp.client.call_result == CallResult.CONNECTED:
            pp.status = ProvisionalPoint.PointStatus.CONFIRMED
            pp.final_points = pp.immediate_points + pp.pending_points
        else:
            pp.status = ProvisionalPoint.PointStatus.EXPIRED
            pp.final_points = max(0, pp.immediate_points - 0.2)  # small penalty
        pp.confirmed_at = timezone.now()
        pp.save()
```

---

## 5. Anti-Gaming механизмы

### 5.1 Таблица сценариев атак

| # | Сценарий | Описание | Защита HES | Эффективность защиты |
|---|----------|----------|------------|---------------------|
| 1 | CP Bomber | 50 КП через мессенджер за 1 час | Лог. шкала + velocity cap + channel penalty | ⚡ Максимум 9.75% от HES |
| 2 | Status Flipper | Все клиенты "заинтересованы" без реального контакта | Provisional points + конверсия = 0 → Quality = 0 | ⚡ 0 Quality Score |
| 3 | Tab Sitter | Браузер открыт 8 часов, ничего не делает | Только реальные клики, 15% max weight, 15 pts cap | ⚡ Максимум 2.25% от HES |
| 4 | Fake Client | Друг "покупает" | Оплата реальна, revenue есть, но нет повторных | ⚠️ Частично проходит (разово) |
| 5 | Reason Farmer | Копипаст одной причины 100 раз | Diversity bonus < 1.0, reason_score × 0.3-0.5 | ⚡ Quality Score -50% |
| 6 | Call Logger | Записывает фейковые CallAttempt | CallAttempt → Provisional → НУЖЕН результат | ⚡ Без результата = 0 |
| 7 | 1-Hour Sprinter | Делает всю "работу" за 1 час | Velocity cap = -30%, streak = 0, diversity = low | ⚡ HES cap ~35-40% |
| 8 | Bulk Excel Entry | Вносит 30 клиентов за 10 минут в конце дня | Batch Entry Mode — исключение velocity cap | ✅ Легитимный сценарий |
| 9 | Callback Ignorer | Обещает перезвонить, не перезванивает | Escalating penalty: 3 дня → автозакрытие с -points | ⚡ Quality Score → 0 |

### 5.2 Velocity Cap (ограничение скорости)

```python
def check_velocity(manager, period):
    """
    Проверяет: не набрал ли менеджер все баллы за 1-2 часа?
    Если да — штраф -30% к Activity Score.
    
    ИСКЛЮЧЕНИЕ: Batch Entry Mode (Excel → сайт в конце дня)
    Менеджер может не иметь доступа к сайту весь день (например,
    работает с Excel-таблицей) и вносить данные одним блоком.
    В этом случае velocity cap НЕ применяется к DATA ENTRY,
    но Activity Score всё равно ниже (нет streak, нет online time).
    """
    # Группируем действия по часам
    actions = ManagerAction.objects.filter(
        manager=manager, created_at__date__in=period_dates(period)
    ).extra(
        select={'hour': "date_trunc('hour', created_at)"}
    ).values('hour').annotate(
        action_count=Count('id'),
        points_earned=Sum('points')
    ).order_by('-points_earned')

    if not actions:
        return 1.0  # no penalty

    max_hourly_actions = actions[0]['action_count'] or 0
    total_actions = sum(a['action_count'] for a in actions)
    concentration = max_hourly_actions / max(1, total_actions)

    # BATCH ENTRY DETECTION:
    # Если все действия — create_client/update_client (не fake_cp или status_flip)
    # и у менеджера нет other suspicious patterns → allow
    hourly_types = ManagerAction.objects.filter(
        manager=manager, created_at__date__in=period_dates(period),
        created_at__hour=actions[0].get('hour', '').hour if actions[0] else 0
    ).values_list('action_type', flat=True)
    
    batch_entry_types = {'create_client', 'update_client', 'add_note', 'set_result'}
    is_batch_entry = set(hourly_types).issubset(batch_entry_types)

    if is_batch_entry and concentration > 0.6:
        # Это batch entry — не штрафуем velocity, но Activity Score
        # всё равно ниже из-за отсутствия online time / streaks
        return 1.0

    if concentration > 0.6:
        return 0.7  # -30% penalty
    elif concentration > 0.4:
        return 0.85  # -15% penalty
    return 1.0  # нормально
```

> [!WARNING]
> **Batch Entry сценарий**: Менеджер мог весь день работать без доступа к сайту (звонки, Excel-табличка), а в конце дня внёс всё разом. Это ЛЕГИТИМНО. Velocity cap не штрафует batch entry создания клиентов, но Activity Score всё равно будет ниже из-за: нет online time (time_score=0), нет streak (если несколько дней так), нет верифицированных КП через email (cp_score=0 если слал через мессенджер).

### 5.3 Channel Penalty (штраф за неверифицируемые каналы)

> [!IMPORTANT]
> **Текущая реальность**: Записи разговоров НЕТ (личные телефоны). Поэтому `phone_with_record` = будущий сценарий (IP-телефония). Сейчас ВСЕ звонки = `phone_no_record`.

```python
CHANNEL_MULTIPLIERS = {
    "email_verified": 1.0,        # КП через сайт → логируется в CommercialOfferEmailLog
    "callback_confirmed": 0.9,    # Перезвон произошёл (клиент обработан повторно) — ВЕРИФИЦИРУЕМО!
    "phone_with_record": 1.0,     # БУДУЩЕЕ: IP-телефония с записью (см. 05_IP_TELEPHONY.md)
    "messenger": 0.5,             # КП через мессенджер — невозможно проверить
    "phone_no_record": 0.4,       # Звонок с личного тел. — self-reported (ТЕКУЩАЯ РЕАЛЬНОСТЬ)
    "unknown": 0.3,               # Канал не указан
}
# ПРИМЕЧАНИЕ: callback_confirmed = когда менеджер обещал перезвонить
# И ДЕЙСТВИТЕЛЬНО перезвонил (есть повторная обработка клиента).
# Это единственный верифицируемый "телефонный" action сейчас.
```

### 5.4 Diversity Requirement

> [!IMPORTANT]
> **Калибровка на B2B cold calling**: Target 5 лидов/день был СЛИШКОМ низким. В реальности:
> - При самостоятельном поиске контактов: **20 контактов/день** (текущая норма владельца)
> - При работе с парсинг-базой (Google Maps): **50+ контактов/день**
> - Учитывая что ~50-70% не берут трубку → нужно звонить 50, чтобы поговорить с 15-25
> - B2B wholesale clothing cold call → deal conversion: **1-3%**

```python
def diversity_check(manager, date, config):
    """
    Менеджер должен работать с ≥N РАЗНЫМИ лидами в день.
    Иначе Activity Score урезается.
    
    DEFAULT VALUES (admin-tunable):
    - TESTING:  15 уникальных лидов/день (адаптация)
    - NORMAL:   25 уникальных лидов/день (стандарт)
    - HARDCORE:  35 уникальных лидов/день (опытные)
    
    Источник: B2B cold-calling benchmarks:
    - ~50-70% не берут трубку → нужно больше контактов
    - Конверсия холодный → сделка: 1-3% (B2B wholesale)
    - Для 2 shops/week нужно ~100-200 контактов/неделю
    """
    unique_leads = CallAttempt.objects.filter(
        manager=manager, created_at__date=date
    ).values('client').distinct().count()

    target = config.min_unique_leads_daily  # TESTING=15, NORMAL=25, HARDCORE=35

    if unique_leads >= target:
        return 1.0
    elif unique_leads >= target * 0.5:
        return 0.7  # половину нормы = 70% Activity
    else:
        return 0.4  # <50% нормы = 40% Activity
```

### 5.5 Callback Penalty (Escalating — «Не перезвонил»)

> [!IMPORTANT]
> **Новый механизм**: Если менеджер обещал перезвонить, но не перезвонил — эскалирующие уведомления и штрафы.

```python
def check_overdue_callbacks(manager, date):
    """
    Проверяет просроченные callback'и и применяет эскалацию.
    Запускается ежедневно в 08:00 (утро следующего дня).
    """
    overdue = ClientFollowUp.objects.filter(
        owner=manager,
        status=ClientFollowUp.Status.OPEN,
        due_at__lt=timezone.now(),
    ).select_related('client')
    
    for followup in overdue:
        days_overdue = (date - followup.due_at.date()).days
        
        if days_overdue == 1:
            # ДЕНЬ 1: Мягкое напоминание
            send_callback_reminder(manager, followup, level='warning')
            # Telegram: "⚠️ Ви не перезвонили [клiєнт]. Перезвоніть сьогодні."
            
        elif days_overdue == 2:
            # ДЕНЬ 2: Предупреждение о штрафе
            send_callback_reminder(manager, followup, level='urgent')
            # Telegram: "🔴 Другий день без перезвону! Бали знімуться через 24 год."
            
        elif days_overdue >= 3:
            # ДЕНЬ 3+: Автозакрытие + штраф
            followup.status = ClientFollowUp.Status.MISSED
            followup.save()
            # Telegram: "❌ Перезвон до [клiєнт] прострочено 3+ днi. Бали знято."
            # Provisional points revoked
            ProvisionalPoint.objects.filter(
                manager=manager, client=followup.client,
                status=ProvisionalPoint.PointStatus.PROVISIONAL
            ).update(
                status=ProvisionalPoint.PointStatus.REVOKED,
                final_points=0
            )
```

### 5.6 «Не відповідає» — 3 попытки (не 5!)

> [!WARNING]
> **Исправление**: Ранее бвло 5 попыток. Владелец уточнил: **3 попытки**, потому что до 3 раз человек может просто быть занят. Обязательно перезванивать!

```python
class NoAnswerHandler:
    MAX_ATTEMPTS = 3  # НЕ 5! Владелец: "до 3 раз может быть занят"
    COOLDOWN_HOURS = 24  # Минимум 24ч между попытками

    def process(self, client, manager):
        attempts = CallAttempt.objects.filter(
            client=client, manager=manager,
            result=CallResult.NO_ANSWER
        ).count()

        if attempts >= self.MAX_ATTEMPTS:
            # 3 попытки = можно закрыть с баллами
            return {
                "allow_close": True,
                "points": 0.5, 
                "message": "Можна закрити (3 спроби)",
                "mark_as": "не відповідає"  # специальный статус
            }
        else:
            # Создать follow-up на перезвон ОБЯЗАТЕЛЬНО
            next_call = timezone.now() + timedelta(hours=self.COOLDOWN_HOURS)
            FollowUp.objects.create(
                client=client, due_at=next_call,
                note=f"Перезвоніть (спроба {attempts + 1}/{self.MAX_ATTEMPTS})"
            )
            return {
                "allow_close": False,
                "points": 0,
                "message": f"Спроба {attempts + 1}/3. Перезвоніть через 24 год"
            }
    
    # ПРИМЕЧАНИЕ: Если менеджер НЕ перезвонил по follow-up → 
    # срабатывает Callback Penalty (§5.5) → уведомление → штраф
```

---

## 6. Admin-Tunable конфигурация

### 6.1 Модель конфигурации

```python
class ManagementEfficiencyConfig(models.Model):
    """
    Конфигурация эффективности — настраивает admin.
    Один активный конфиг для всех, + per-manager override.
    """
    name = models.CharField(max_length=100, default="Default")
    is_active = models.BooleanField(default=True)

    # === WEIGHTS (сумма = 1.0) ===
    weight_result = models.DecimalField(max_digits=3, decimal_places=2, default=0.60)
    weight_quality = models.DecimalField(max_digits=3, decimal_places=2, default=0.25)
    weight_activity = models.DecimalField(max_digits=3, decimal_places=2, default=0.15)

    class DifficultyPreset(models.TextChoices):
        TESTING = "testing", "Тестовый (40/30/30)"
        NORMAL = "normal", "Нормальный (60/25/15)"
        HARDCORE = "hardcore", "Продвинутый (80/15/5)"
        CUSTOM = "custom", "Ручная настройка"

    preset = models.CharField(max_length=20, choices=DifficultyPreset.choices, default=DifficultyPreset.TESTING)

    # === KPI TARGETS (калиброваны для B2B cold-calling wholesale) ===
    shops_target_weekly = models.IntegerField(default=1, help_text="Магазинов/неделю")
    revenue_target_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=30000)
    min_processed_daily = models.IntegerField(default=20, help_text="Мин. обработано/день (20=сам ищет, 50=из базы)")
    min_unique_leads_daily = models.IntegerField(default=15, help_text="Уникальных лидов/день (15/25/35 по preset)")
    min_active_minutes_daily = models.IntegerField(default=120, help_text="Минут активности/день")
    conversion_baseline = models.DecimalField(max_digits=4, decimal_places=3, default=0.020,
        help_text="Baseline конверсия (B2B cold: 1-3%)")
    
    # === ИСТОЧНИК КОНТАКТОВ ===
    class ContactSource(models.TextChoices):
        SELF_FOUND = "self", "Сам ищет контакты"
        PARSED_BASE = "base", "Из парсинг-базы (Google Maps)"
        MIXED = "mixed", "Смешанный"
    
    contact_source = models.CharField(
        max_length=10, choices=ContactSource.choices, default=ContactSource.MIXED,
        help_text="Откуда берёт контакты — влияет на min_processed_daily"
    )

    # === ANTI-GAMING ===
    velocity_cap_per_hour = models.IntegerField(default=30, help_text="Макс. Activity pts/час")
    trust_ratio_alert_threshold = models.DecimalField(max_digits=3, decimal_places=2, default=0.30)
    provisional_confirm_window_days = models.IntegerField(default=7)
    max_no_answer_before_close = models.IntegerField(default=3, help_text="Попыток до закрытия (владелец: 3, не 5!)")
    messenger_activity_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=0.50)
    reason_diversity_min = models.DecimalField(max_digits=3, decimal_places=2, default=0.30,
        help_text="Min % уникальных причин от общего числа")
    callback_penalty_days = models.IntegerField(default=3,
        help_text="Дней до автозакрытия просроченного callback")
    allow_batch_entry = models.BooleanField(default=True,
        help_text="Разрешить batch entry без velocity cap penalty")

    # === PER-MANAGER OVERRIDE ===
    manager_override = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="efficiency_config_overrides",
        help_text="Если указан — конфиг только для этого менеджера"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at"]

    def clean(self):
        total = self.weight_result + self.weight_quality + self.weight_activity
        if abs(total - 1.0) > 0.01:
            raise ValidationError(f"Сумма весов должна = 1.0, сейчас = {total}")

    def save(self, *args, **kwargs):
        # Авто-заполнение при выборе preset
        if self.preset == self.DifficultyPreset.TESTING:
            self.weight_result, self.weight_quality, self.weight_activity = 0.40, 0.30, 0.30
            self.shops_target_weekly, self.min_processed_daily = 1, 20
            self.min_unique_leads_daily, self.min_active_minutes_daily = 15, 120
        elif self.preset == self.DifficultyPreset.NORMAL:
            self.weight_result, self.weight_quality, self.weight_activity = 0.60, 0.25, 0.15
            self.shops_target_weekly, self.min_processed_daily = 2, 30
            self.min_unique_leads_daily, self.min_active_minutes_daily = 25, 180
        elif self.preset == self.DifficultyPreset.HARDCORE:
            self.weight_result, self.weight_quality, self.weight_activity = 0.80, 0.15, 0.05
            self.shops_target_weekly, self.min_processed_daily = 3, 40
            self.min_unique_leads_daily, self.min_active_minutes_daily = 35, 300
        super().save(*args, **kwargs)
```

### 6.2 Presets визуально (ОТКАЛИБРОВАНЫ для B2B cold-calling)

```
          TESTING              NORMAL              HARDCORE
      ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
      │ Results  40% │    │ Results  60% │    │ Results  80% │
      │ Quality  30% │    │ Quality  25% │    │ Quality  15% │
      │ Activity 30% │    │ Activity 15% │    │ Activity  5% │
      ├──────────────┤    ├──────────────┤    ├──────────────┤
      │ 1 shop/week  │    │ 2 shops/week │    │ 3 shops/week │
      │ 20 proc/day  │    │ 30 proc/day  │    │ 40 proc/day  │
      │ 15 leads/day │    │ 25 leads/day │    │ 35 leads/day │
      │ 120 min/day  │    │ 180 min/day  │    │ 300 min/day  │
      │ 3 no-ans max │    │ 3 no-ans max │    │ 3 no-ans max │
      │ 3d cb penalty│    │ 3d cb penalty│    │ 3d cb penalty│
      └──────────────┘    └──────────────┘    └──────────────┘
      Новые менеджеры      Стандарт            Опытные
      (тестовый период)    (после 2-4 нед.)    (2+ мес.)

  Контексты (B2B cold-calling wholesale clothing):
  - 50-70% no-answer rate → нужно 50 звонков → 15-25 разговоров
  - Конверсия холодный → сделка: 1-3%
  - Для 2 shops/week нужно ~100-200 контактов/неделю
  - Если из парсинг-базы: min_processed_daily можно повысить до 50
```

### 6.3 Admin UI (в Django Admin)

```python
@admin.register(ManagementEfficiencyConfig)
class EfficiencyConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "preset", "is_active", "manager_override",
                    "weight_result", "weight_quality", "weight_activity", "updated_at")
    list_filter = ("preset", "is_active")
    fieldsets = (
        ("Основные", {
            "fields": ("name", "preset", "is_active", "manager_override"),
        }),
        ("Веса (сумма = 1.0)", {
            "fields": ("weight_result", "weight_quality", "weight_activity"),
            "description": "Выберите preset для авто-заполнения, или Custom для ручной настройки"
        }),
        ("KPI Targets", {
            "fields": ("shops_target_weekly", "revenue_target_monthly",
                       "min_processed_daily", "min_unique_leads_daily",
                       "min_active_minutes_daily", "conversion_baseline"),
        }),
        ("Anti-Gaming", {
            "fields": ("velocity_cap_per_hour", "trust_ratio_alert_threshold",
                       "provisional_confirm_window_days", "max_no_answer_before_close",
                       "messenger_activity_multiplier", "reason_diversity_min"),
            "classes": ("collapse",),
        }),
    )
```

---

## 7. Trust Ratio — Детектор аномалий

### 7.1 Формула

```python
def calculate_trust_ratio(manager, period):
    """
    Trust Ratio = Result_Score / max(1, Activity_Score)

    Интерпретация:
    > 1.5 — Отличный: мало активности, много результатов (суперэффективный)
    > 0.8 — Хороший: нормальное соотношение
    > 0.3 — Подозрительный: много активности, мало результатов
    < 0.3 — 🚨 ALERT: возможный гейминг или некомпетентность
    """
    result = calculate_result_score(manager, period, config)
    activity = calculate_activity_score(manager, period, config)

    ratio = result / max(1, activity)

    if ratio < config.trust_ratio_alert_threshold:
        # Генерируем alert для админа
        TrustRatioAlert.objects.create(
            manager=manager,
            period_start=period.start,
            period_end=period.end,
            result_score=result,
            activity_score=activity,
            ratio=ratio,
            message=f"Trust Ratio {ratio:.2f} < {config.trust_ratio_alert_threshold}"
        )

    return ratio
```

### 7.2 Визуализация для админа

```
┌──────────────── Trust Ratio Dashboard ────────────────┐
│                                                       │
│  Manager A: ████████████████████░░░░░ 1.4  ✅ Efficient│
│  Manager B: ████████████████░░░░░░░░░ 0.9  ✅ Normal   │
│  Manager C: ████████░░░░░░░░░░░░░░░░░ 0.4  ⚠️ Low     │
│  Manager D: ███░░░░░░░░░░░░░░░░░░░░░░ 0.15 🚨 ALERT!  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## 8. Интеграция с Heatmap

### 8.1 Ежедневный расчёт HES → Heatmap

```python
# Cron: 00:05 каждый день
def calculate_daily_heatmap():
    yesterday = date.today() - timedelta(days=1)
    config = get_active_efficiency_config()

    for manager in get_active_managers():
        # Per-manager override
        mgr_config = get_manager_config(manager) or config

        period = DayPeriod(yesterday)

        # Если не было активности — серый
        if not has_any_activity(manager, yesterday):
            color = "gray"
            score = 0
        else:
            result = calculate_result_score(manager, period, mgr_config)
            quality = calculate_quality_score(manager, period, mgr_config)
            activity = calculate_activity_score(manager, period, mgr_config)
            trust = calculate_trust_ratio(manager, period)

            hes = (
                result * float(mgr_config.weight_result) +
                quality * float(mgr_config.weight_quality) +
                activity * float(mgr_config.weight_activity)
            )

            score = hes
            color = score_to_color(hes)

        ManagerDailyHeatmap.objects.update_or_create(
            manager=manager, date=yesterday,
            defaults={
                "efficiency_score": score,
                "color": color,
                "result_score": result if score > 0 else 0,
                "quality_score": quality if score > 0 else 0,
                "activity_score": activity if score > 0 else 0,
                "trust_ratio": trust if score > 0 else None,
                "config_preset": mgr_config.preset,
                "breakdown_json": {
                    "result": {"shops": shops, "revenue": revenue, ...},
                    "quality": {"reason_rate": ..., "callback_rate": ...},
                    "activity": {"processed": ..., "cp_sent": ..., "time": ...},
                    "anti_gaming": {"velocity_penalty": ..., "diversity": ...},
                }
            }
        )

def score_to_color(score):
    if score <= 0:
        return "gray"
    elif score < 25:
        return "red"       # #FF4444
    elif score < 50:
        return "orange"    # #FF8844
    elif score < 75:
        return "yellow"    # #FFCC00
    elif score <= 100:
        return "green"     # #44CC44
    else:
        return "dark_green"  # #22AA22 (>100% перевыполнение)
```

### 8.2 Расширенная модель Heatmap

```python
class ManagerDailyHeatmap(models.Model):
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()

    # HES scores
    efficiency_score = models.FloatField(default=0)  # итоговый HES
    result_score = models.FloatField(default=0)
    quality_score = models.FloatField(default=0)
    activity_score = models.FloatField(default=0)
    trust_ratio = models.FloatField(null=True, blank=True)

    color = models.CharField(max_length=20)  # gray/red/orange/yellow/green/dark_green
    config_preset = models.CharField(max_length=20, blank=True)  # какой preset использовался
    breakdown_json = models.JSONField(default=dict)  # детальная разбивка

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("manager", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["manager", "-date"]),
            models.Index(fields=["color", "-date"]),
        ]
```

---

## 9. Полный список моделей данных

| Модель | Назначение | Связи |
|--------|------------|-------|
| `ManagementEfficiencyConfig` | Admin-настройки HES | manager_override → User |
| `CallAttempt` | Каждая попытка звонка | client, manager |
| `ProvisionalPoint` | Отложенные баллы | manager, client, call_attempt |
| `ManagerDailyHeatmap` | Ежедневный HES результат | manager |
| `TrustRatioAlert` | Алерты при низком Trust Ratio | manager |
| `NotInterestedReason` | Enum причин отказа | в CallAttempt |
| `ClientCPLink` | Привязка КП к клиенту | client, cp_log |

---

## 10. Roadmap внедрения

```
Фаза 0: Подготовка (1 неделя)
├─ Создать ManagementEfficiencyConfig модель
├─ Создать CallAttempt модель
├─ Создать ProvisionalPoint модель
└─ Миграции + Admin регистрация

Фаза 1: Базовый HES (2 недели)
├─ Имплементация calculate_result_score()
├─ Имплементация calculate_quality_score()
├─ Имплементация calculate_activity_score()
├─ Cron для daily heatmap
└─ UI: heatmap полоска в профиле менеджера

Фаза 2: Anti-Gaming (1 неделя)
├─ Velocity cap
├─ Channel penalty
├─ Diversity check
├─ Trust Ratio + alerts
└─ Provisional points cron

Фаза 3: Admin Panel (1 неделя)
├─ UI для ManagementEfficiencyConfig
├─ Presets (Testing/Normal/Hardcore)
├─ Per-manager overrides
├─ Trust Ratio dashboard
└─ Historical comparison ("what-if" mode)

Фаза 4: Тонкая настройка (ongoing)
├─ A/B тестирование разных весов
├─ Калибровка conversion_baseline
├─ Настройка velocity_cap по реальным данным
└─ Feedback loop: анализ корреляции HES ↔ реальной прибыльности
```

> [!CAUTION]
> **Начинать с preset=TESTING** (40/30/30). Только после 2-4 недель данных переключать на NORMAL. На HARDCORE — только для проверенных менеджеров после 2+ месяцев работы.

---

## 11. Аудит Telegram-уведомлений

> [!WARNING]
> **Результат аудита**: Текущие уведомления слишком сухие, без структуры, без контекста и последствий. Ниже — редизайн.

### 11.1 Текущие проблемы

| Уведомление | Проблема | Решение |
|-------------|----------|---------|
| `send_telegram_report()` | Нет KPD/HES/shops/target%, только «бали за сьогодні» | Добавить HES + target + цвет дня |
| `_send_manager_bot_notifications()` | Сухое «Нагадування» без why/what/consequences | Добавить контекст + urgency + action |
| `notify_test_shops` | Лучший формат (emoji, action), но нет escalation | Добавить 2-ю reminder за 4 часа |
| Callback reminders | НЕТ НАПОМИНАНИЙ при просроченном callback! | **Новый механизм** (§5.5) |
| No-answer reminders | Нет напоминаний после 1-2 попыток | **Новый механизм** (§5.6) |

### 11.2 Новый формат уведомлений

#### Ежедневный отчёт (менеджеру + админу):
```
📊 Звіт за 03.03.2026
👤 Петро Менеджер

🏆 HES: 67.4% (🟡 жовтий)
├─ 📈 Результати: 45/100 (0 нових магазинів)
├─ ⭐ Якість: 78/100 (причини: 92%)
└─ 🔄 Активність: 62/100 (28 контактів)

🎯 Ціль тижня: 0/2 магазинів
📞 Контактів сьогодні: 28/30
📧 КП email: 5 | 💬 КП месенджер: 3
🔔 Перезвони на завтра: 4

⚠️ 2 прострочені перезвони!
```

#### Напоминание о перезвоне (escalating):
```
--- ДЕНЬ 1 ---
⚠️ Нагадування: перезвон
📞 Клієнт: ФОП "Стиль", Олена Петренко
📱 +380 67 123 4567
📅 Мав/ла перезвоніти: вчора о 15:00
👉 Перезвоніть сьогодні, або бали не будуть зараховані.

--- ДЕНЬ 2 ---
🔴 УВАГА: Прострочений перезвон!
📞 ФОП "Стиль" — Олена Петренко
📱 +380 67 123 4567
⏰ Прострочено: 2 дні
❗ Бали будуть знято через 24 години!
👉 Перезвоніть ЗАРАЗ.

--- ДЕНЬ 3 ---
❌ Перезвон прострочено 3+ дні
📞 ФОП "Стиль" — Олена Петренко
📊 Бали за цей контакт: ЗНЯТО
📋 Статус: автоматично закрито як "не перезвонив"
```

#### Напоминание "Не взял трубку" (1-2 попытки):
```
📞 Не відповів: перезвоніть!
👤 Олена Петренко (ФОП "Стиль")
📱 +380 67 123 4567
🔄 Спроба: 1/3 (людина може бути зайнята)
📅 Перезвоніть: завтра після 10:00
💡 Порада: спробуйте в інший час дня
```

#### Тестовый магазин (улучшенный):
```
⏳ Тестовий магазин: УВАГА!
🏪 Магазин: ФОП "Стиль"
👤 Контакт: Олена Петренко, +380 67 123 4567
⏰ Залишилось: 18 годин

📋 Що робити:
1. Зателефонуйте клієнту
2. Уточніть: продовжують чи повертають товар?
3. Якщо продовжують → оформіть накладну
4. Якщо повертають → організуйте повернення

⚠️ Якщо не зв'яжетесь — магазин автоматично буде закрито!
```

### 11.3 Система уведомлений для админа

```
🚨 ALERT: Trust Ratio
👤 Менеджер: Петро Менеджер
📊 Trust Ratio: 0.18 (поріг: 0.30)
📈 Activity: 85/100 (багато дій)
📉 Results: 15/100 (мало результатів)

⚠️ Можливе імітування роботи.
👉 Рекомендація: перевірити звіти за тиждень.
```
