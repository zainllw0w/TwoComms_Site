# 👨‍💼 Workflow менеджера — Полная спецификация

## Оглавление
1. [Специфика работы (от владельца)](#1-специфика-работы)
2. [Система оплаты и мотивации](#2-система-оплаты)
3. [Тестовый период и KPI](#3-тестовый-период-и-kpi)
4. [Monthly Heatmap Report (ПРИОРИТЕТ)](#4-monthly-heatmap-report)
5. [Anti-Abuse система баллов](#5-anti-abuse-система-баллов)
6. [Расширенное поле обработки клиента](#6-расширенное-поле-обработки)
7. [Система дублей (улучшенная)](#7-система-дублей-улучшенная)
8. [Синхронизация КП и email](#8-синхронизация-кп-и-email)
9. [Вкладка "Склад" (заглушка)](#9-вкладка-склад)
10. [Навигация и доступы](#10-навигация-и-доступы)
11. [Пересмотр формул KPD/ELO](#11-пересмотр-формул)

---

## 1. Специфика работы (от владельца)

> [!IMPORTANT]
> **Эта информация — прямой input от владельца бизнеса. Все решения по системе баллов, KPI и мотивации должны строиться на этой основе.**

### 1.1 Процесс работы менеджера

```
1. Менеджер находит контакты (сам или из базы парсинга Google Maps)
2. Связывается по ЛЮБОМУ каналу:
   - Звонок с личного телефона
   - Мессенджер (Telegram, WhatsApp, Viber, Instagram)
   - Email
3. Отправляет КП ЧЕРЕЗ ЛЮБОЙ КАНАЛ:
   - Через сайт на email (CommercialOfferEmailLog — верифицируемо)
   - Через мессенджер (скриншот/ссылка — НЕ верифицируемо автоматически)
   - По телефону (устная презентация — НЕ верифицируемо)
4. Договаривается о тестовой ростовке (4 единицы S-XL, бесплатно, возврат/выкуп 2 нед)
   ИЛИ сразу заказ по накладной (от 8 единиц)
5. Создаёт накладную → отправляет на проверку владельцу
6. Владелец подтверждает/отклоняет (проверка наличия товара)
7. Менеджер коммуницирует результат клиенту
8. Клиент оплачивает → МАГАЗИН ДОБАВЛЕН = УЖЕ ОПЛАТИЛ (подключён)
9. Менеджер ведёт клиента → повторные заказы → процент выше
```

> [!WARNING]
> **Уточнение от владельца**: На данный момент система статусов магазинов не особо реализована. **Если магазин добавлен — значит он уже оплатил.** Пока что считается именно так. Отдельных промежуточных статусов нет.

### 1.2 Каналы связи

- **Телефон**: Личный (нет корпоративной телефонии пока)
- **Мессенджер**: Любой удобный для клиента (Telegram, WhatsApp, Viber, Instagram)
- **Email**: КП через сайт (система `CommercialOfferEmailLog`) — но КП можно отправить и через мессенджер / по телефону
- **Язык**: Украинский или язык клиента

> [!NOTE]
> **КП через мессенджер**: Менеджер может отправить КП через любой канал, не только email. Однако **только email-КП верифицируемы** системой (логируются в `CommercialOfferEmailLog`). КП через мессенджеры учитываются как **неверифицированные** и получают **50% от Activity баллов** в формуле HES (см. [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md)).

### 1.3 Штрафные ситуации

| Нарушение | 1-й раз | 2-й раз | 3-й раз |
|-----------|---------|---------|---------|
| Хамство клиенту | Штраф (по тяжести) | Минус ставка | Рассмотрение увольнения |
| Жалоба от клиента | Штраф (по тяжести) | Минус ставка | Рассмотрение увольнения |
| Попытка обмана | Штраф (по тяжести) | Минус ставка | Рассмотрение увольнения |

## 2. Система оплаты и мотивации

### 2.1 Финансовая модель

```
СТАВКА (после тестового):     15 000 грн/мес
ПРОЦЕНТ (первый заказ):        2.5% от накладной
ПРОЦЕНТ (повторные заказы):    5.0% от накладной  ← мотивация вести клиента!
```

> [!TIP]
> **Ключевой инсайт**: Двойной процент за повторные заказы — прямая мотивация для follow-ups и relationship management. Это должно отражаться в KPI как **retention rate** и frequency of repeat orders.

### 2.2 Расчёт зарплаты (предложение)

```python
class ManagerPayroll:
    BASE_SALARY = 15000  # грн
    FIRST_ORDER_PCT = 0.025  # 2.5%
    REPEAT_ORDER_PCT = 0.05  # 5.0%

    def calculate_monthly(self, manager, month):
        first_orders = WholesaleInvoice.objects.filter(
            manager=manager, created_at__month=month,
            shop__first_invoice_manager=manager,  # первый заказ
            status="paid"
        )
        repeat_orders = WholesaleInvoice.objects.filter(
            manager=manager, created_at__month=month,
            status="paid"
        ).exclude(pk__in=first_orders)

        commission_first = sum(inv.total for inv in first_orders) * self.FIRST_ORDER_PCT
        commission_repeat = sum(inv.total for inv in repeat_orders) * self.REPEAT_ORDER_PCT

        return {
            "base": self.BASE_SALARY,
            "commission_first": commission_first,
            "commission_repeat": commission_repeat,
            "total": self.BASE_SALARY + commission_first + commission_repeat,
            "first_orders_count": first_orders.count(),
            "repeat_orders_count": repeat_orders.count(),
        }
```

## 3. Тестовый период и KPI

### 3.1 Тестовый период (5+3 дней)

```
День 1-5:  Тестовый период
  ЦЕЛЬ: Подключить минимум 1 магазин (накладная от 8 единиц, оплачено)
  ЕСЛИ не выполнено:
    → Разбор ошибок, корректировка
    → Дополнительные 3 дня

День 6-8:  Второй шанс
  ЕСЛИ не выполнено:
    → Вариант 1: Только за процент (обговаривается)
    → Вариант 2: Пересмотр при росте KPI
```

### 3.2 KPI нормативы

| Неделя | Новых магазинов/неделю | Описание |
|--------|----------------------|----------|
| 1-2 | ≥ 1 | Начальный этап, адаптация |
| 3+ | ≥ 2 | Стандартная норма |

### 3.3 Логика подключения магазина

> [!IMPORTANT]
> **Упрощённая логика (текущая)**: Магазин добавлен = уже оплатил. Никаких промежуточных статусов. Система статусов магазинов пока не реализована полноценно.

```
Магазин считается "подключённым" когда:
→ Он ДОБАВЛЕН в систему (Shop.objects.create(...))
→ Факт добавления означает, что оплата уже прошла
→ Не нужна отдельная проверка status="paid"

ТЕСТОВАЯ ростовка (4 единицы S-XL):
- Отправляется бесплатно по договору
- 14 дней на решение: вернуть или выкупить
- НЕ считается подключением!
- В системе отображается КАК ОПЦИЯ внутри подключённого магазина:
  → В карточке магазина есть поле "Тип" = "Тестова ростовка"
  → Это НЕ отдельное поле в модальном окне обработки клиента!
  → А один из вариантов при добавлении магазина
```

## 4. Monthly Heatmap Report (ПРИОРИТЕТ)

> [!IMPORTANT]
> **Идея пользователя (ОБЯЗАТЕЛЬНАЯ РЕАЛИЗАЦИЯ)**: Визуальный отчёт за месяц в стиле uptime-мониторинга. Серый = ничего не было, красный → зелёный = эффективность дня.

### 4.1 Дизайн (по скриншоту пользователя)

```
┌──────────────────────────────────────────────────────┐
│ Эффективность менеджера          Среднее: 76.4%      │
│                                                      │
│ ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌                     │
│ (каждая полоска = 1 день,                            │
│  цвет = от красного к зелёному)                      │
│                                                      │
│ 30 дней назад                              Сегодня   │
└──────────────────────────────────────────────────────┘

Цвета:
  #808080 (серый)   = нет данных / выходной / отсутствие
  #FF4444 (красный) = 0-25% эффективности
  #FF8844 (оранж)   = 25-50% эффективности
  #FFCC00 (жёлтый)  = 50-75% эффективности
  #44CC44 (зелёный) = 75-100% эффективности
  #22AA22 (тёмно-зелёный) = >100% перевыполнение
```

### 4.2 Расчёт эффективности дня (00:00 автоматический)

> [!IMPORTANT]
> **Ответ на вопрос**: Ни ELO, ни KPD, ни KPI отдельно. Используется **HES (Hybrid Efficiency System)** — мульти-компонентная формула с admin-настраиваемыми весами.
>
> **Полная спецификация**: См. [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md) — документ на 500+ строк с 5 уровнями защиты от гейминга, 4-tier таксономией метрик, provisional points, и admin-tunable preset'ами.
>
> **Краткая суть**: HES = Results(60%) + Quality(25%) + Activity(15%), где Results нельзя подделать (магазин добавлен = оплатил), Quality детектирует копипаст причин, Activity имеет логарифмическую шкалу и velocity cap:

```python
def calculate_daily_efficiency(manager, date):
    """Рассчитывается автоматически в 00:00 за прошедший день"""

    # 1. Был ли менеджер активен? (60+ минут активности)
    activity = ManagementDailyActivity.objects.filter(
        user=manager, date=date
    ).first()
    if not activity or activity.active_seconds < 3600:  # < 1 час
        return {"score": 0, "color": "gray", "reason": "no_activity"}

    # 2. Компоненты эффективности
    clients_processed = Client.objects.filter(
        owner=manager, processed_at__date=date
    ).count()

    shops_connected = Shop.objects.filter(
        created_by=manager, created_at__date=date,
        # shop_type="full" — полное подключение
    ).count()

    followups_done = FollowUp.objects.filter(
        client__owner=manager, completed_at__date=date
    ).count()

    followups_missed = FollowUp.objects.filter(
        client__owner=manager, due_date=date,
        status="missed"
    ).count()

    reports_on_time = DailyReport.objects.filter(
        user=manager, date=date, submitted_at__lte=deadline
    ).exists()

    # 3. Формула
    effort_score = min(100, (
        min(30, clients_processed * 3) +          # до 30% за обработку
        min(30, shops_connected * 30) +            # до 30% за подключения
        min(15, followups_done * 3) +              # до 15% за follow-ups
        min(15, (1 - followups_missed / max(1, followups_done + followups_missed)) * 15) +
        (10 if reports_on_time else 0)             # 10% за отчёт вовремя
    ))

    # 4. Штрафы
    if not has_reason_for_not_interested(manager, date):
        effort_score *= 0.8  # -20% если не указывал причины

    return {
        "score": effort_score,
        "color": score_to_color(effort_score),
        "breakdown": {...}
    }
```

### 4.3 Cron job для расчёта

```python
# management command: calculate_daily_efficiency
# Запуск: 00:05 каждый день

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        yesterday = date.today() - timedelta(days=1)
        for manager in get_active_managers():
            result = calculate_daily_efficiency(manager, yesterday)
            ManagerDailyHeatmap.objects.update_or_create(
                manager=manager, date=yesterday,
                defaults={
                    "efficiency_score": result["score"],
                    "color": result["color"],
                    "breakdown_json": result["breakdown"],
                }
            )
```

### 4.4 Модель

```python
class ManagerDailyHeatmap(models.Model):
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    efficiency_score = models.FloatField(default=0)  # 0-100+
    color = models.CharField(max_length=20)  # gray/red/orange/yellow/green/dark_green
    breakdown_json = models.JSONField(default=dict)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("manager", "date")
        ordering = ["-date"]
```

## 5. Anti-Abuse система баллов

> [!IMPORTANT]
> **Идея пользователя (ОБЯЗАТЕЛЬНАЯ)**: Менеджер не должен "филонить" — ставить "не интересно" без причины просто чтобы закрыть контакт. Система должна **наказывать за отсутствие причины** и **вознаграждать за качественную обработку**.

### 5.1 Новые правила начисления баллов

```python
# Текущая система (простая):
POINTS_MAP = {
    CallResult.CONNECTED: 3,        # Подключён
    CallResult.TEST_AGREED: 2,      # Тест согласован
    CallResult.INTERESTED: 1.5,     # Заинтересован
    CallResult.CALLBACK: 1,         # Перезвонить
    CallResult.NOT_INTERESTED: 0.5, # Не интересно
    CallResult.NO_ANSWER: 0.3,      # Не берёт трубку
    CallResult.WRONG_NUMBER: 0,     # Неверный номер
}

# НОВАЯ система (anti-abuse):
def calculate_points(client, call_result, reason=None, callback_count=0):
    base = POINTS_MAP[call_result]

    # === ANTI-ABUSE: Без причины = 0 баллов ===
    if call_result == CallResult.NOT_INTERESTED:
        if not reason or len(reason.strip()) < 10:
            return 0  # НОЛЬ баллов без причины!
        # С причиной: нормальные баллы
        return base

    if call_result == CallResult.NO_ANSWER:
        if callback_count == 0:
            return 0  # Первый раз "не берёт" — ноль
        elif callback_count >= 3:
            return base  # 3+ попытки — баллы начисляются
        else:
            return base * 0.5  # 1-2 попытки — половина

    return base
```

### 5.2 Уведомления менеджеру (превентивные)

```
Перед сохранением:
┌──────────────────────────────────────────────────────┐
│ ⚠️ Внимание!                                        │
│                                                      │
│ Вы выбрали "Не интересно" без указания причины.     │
│ В этом случае:                                       │
│ • Баллы за обработку НЕ будут начислены              │
│ • Рейтинг не изменится                               │
│ • Этот контакт не будет засчитан в KPI               │
│                                                      │
│ Укажите причину отказа для получения баллов:         │
│ ┌────────────────────────────────────────────────┐   │
│ │ [выпадающий список причин]                     │   │
│ │ • Уже работает с конкурентом                   │   │
│ │ • Нет подходящего ассортимента                  │   │
│ │ • Цена не устраивает                            │   │
│ │ • Не наша целевая аудитория                     │   │
│ │ • Бизнес закрыт / не существует                 │   │
│ │ • Другое (обязательный комментарий)             │   │
│ └────────────────────────────────────────────────┘   │
│                                                      │
│ [Сохранить с причиной ✅]  [Сохранить без баллов ❌] │
└──────────────────────────────────────────────────────┘
```

### 5.3 "Не берёт трубку" — отдельная логика

```python
class NoAnswerHandler:
    MAX_ATTEMPTS = 3  # НЕ 5! Владелец: "до 3 раз может быть занят"
    COOLDOWN_HOURS = 24  # Перезвонить не раньше чем через 24ч

    def process(self, client, manager):
        # Считаем попытки
        attempts = CallAttempt.objects.filter(
            client=client, manager=manager,
            result=CallResult.NO_ANSWER
        ).count()

        if attempts >= self.MAX_ATTEMPTS:
            # 3 попытки = можно закрыть с баллами
            return {"allow_close": True, "points": 0.5, "message": "Можна закрити (3 спроби)"}
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
                "message": f"Спроба {attempts + 1}/3. Перезвоніть через 24 години"
            }
```

### 5.4 Новая модель CallAttempt

```python
class CallAttempt(models.Model):
    """Каждая попытка звонка записывается отдельно"""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="call_attempts")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    result = models.CharField(max_length=30, choices=CallResult.choices)
    duration_seconds = models.IntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    not_interested_reason = models.CharField(max_length=100, blank=True)
    not_interested_detail = models.TextField(blank=True)
    points_awarded = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "manager", "-created_at"]),
        ]
```

## 6. Расширенное поле обработки клиента

> [!IMPORTANT]
> **Идея пользователя**: Расширить модальное окно обработки клиента дополнительными полями.

### 6.1 Новые поля в модальном окне

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| Результат звонка | Select | ✅ | Как сейчас (CallResult) |
| Причина отказа | Select + Text | При "не интересно" | Выпадающий список + детали |
| Комментарий менеджера | Textarea | Нет | Свободное поле для заметок |
| Количество попыток дозвона | Auto | — | Автоматически из CallAttempt |
| Отправлено КП | Select | **✅ при выборе "Відправлено КП"** | **ОБЯЗАТЕЛЬНО** выбрать из списка отправленных КП менеджера (CommercialOfferEmailLog) |
| Планируемый перезвон | DateTime | При "перезвонить" | Когда перезвонить |

> [!WARNING]
> **Убрано**: "Статус тестовой ростовки" — это НЕ поле в модальном окне обработки клиента. Тестовая ростовка — это один из типов/опций при **добавлении магазина** (в карточке подключённого магазина). Когда менеджер добавляет магазин, он выбирает: "Тестова ростовка" или "Оптовий замовлення".

> [!IMPORTANT]
> **Поле "Отправлено КП"**: Когда менеджер выбирает этот результат, он **ОБЯЗАН** выбрать конкретное КП из dropdown-списка. Список формируется из `CommercialOfferEmailLog` этого менеджера за последние 30 дней. Если КП было отправлено через мессенджер (не email), менеджер выбирает "КП надіслано через месенджер" (не верифицируемо, 50% Activity points).

### 6.2 Enum причин отказа

```python
class NotInterestedReason(models.TextChoices):
    COMPETITOR = "competitor", "Вже працює з конкурентом"
    NO_ASSORTMENT = "no_assortment", "Немає потрібного асортименту"
    PRICE = "price", "Ціна не влаштовує"
    NOT_TARGET = "not_target", "Не наша ЦА"
    BUSINESS_CLOSED = "business_closed", "Бізнес закрито / не існує"
    SEASONAL = "seasonal", "Сезонність (не зараз)"
    NO_BUDGET = "no_budget", "Обмежений бюджет"
    ALREADY_CONTACTED = "already_contacted", "Вже контактували раніше"
    OTHER = "other", "Інше (обов'язковий коментар)"
```

## 7. Система дублей (улучшенная)

> [!IMPORTANT]
> **Идея пользователя**: При обработке из базы, если номер уже обработан — показать КТО обработал, КОГДА и РЕЗУЛЬТАТ.

### 7.1 Уведомление о существующем контакте

```
При вводе номера телефона (или при нажатии "Обработать" в базе):

┌──────────────────────────────────────────────────────┐
│ ⚠️ Цей номер вже в базі!                            │
│                                                      │
│ 📞 +380 67 123 4567                                  │
│ 👤 ФОП "Стиль", Олена Петренко                       │
│ 🧑‍💼 Обробив: Іван Менеджер                          │
│ 📅 Дата обробки: 15.02.2026                          │
│ 📊 Результат: Не цікаво (конкурент)                  │
│ 💬 Коментар: "Працюють з ТМ Fashion, ціна дешевша"   │
│ 🔄 Спроб дзвінків: 3                                 │
│ 📧 КП відправлено: 12.02.2026 (Preset 2, Visual)     │
│                                                      │
│ [Переглянути детально]  [Скасувати]  [Все одно додати]│
└──────────────────────────────────────────────────────┘
```

### 7.2 Логика для базы лидов

```python
def check_lead_duplicate(phone_normalized, manager):
    """Проверка при нажатии "Обработать" в базе лидов"""

    # Проверить Client
    existing_client = Client.objects.filter(
        phone_normalized=phone_normalized
    ).select_related("owner").first()

    # Проверить ManagementLead
    existing_lead = ManagementLead.objects.filter(
        phone_normalized=phone_normalized,
        status__in=["processed", "in_progress"]
    ).select_related("processed_by").first()

    if existing_client:
        last_attempt = CallAttempt.objects.filter(
            client=existing_client
        ).order_by("-created_at").first()

        last_cp = CommercialOfferEmailLog.objects.filter(
            owner=existing_client.owner,
            recipient_email__icontains=existing_client.email  # или по phone
        ).order_by("-created_at").first()

        return {
            "is_duplicate": True,
            "type": "client",
            "owner": existing_client.owner.get_full_name(),
            "processed_at": existing_client.created_at,
            "result": existing_client.get_call_result_display(),
            "comment": existing_client.notes,
            "call_attempts": CallAttempt.objects.filter(client=existing_client).count(),
            "last_cp": last_cp,
        }

    return {"is_duplicate": False}
```

## 8. Синхронизация КП и каналов связи

> [!IMPORTANT]
> **Уточнение от владельца**: Менеджер может отправить КП не только через email, но и через ЛЮБОЙ мессенджер или по телефону. Однако при выборе "Відправлено КП на email" — он **ОБЯЗАН** выбрать конкретное КП из списка отправленных этим менеджером. Дедупликация email также необходима.

### 8.1 Привязка КП к клиенту

```python
# В модальном окне обработки клиента:
# Новое поле: "Пов'язане КП"

class ClientCPLink(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="cp_links")
    cp_log = models.ForeignKey(CommercialOfferEmailLog, on_delete=models.CASCADE)
    linked_at = models.DateTimeField(auto_now_add=True)
    linked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
```

### 8.2 Dropdown КП в модальном окне

```javascript
// При нажатии "Відправлено КП":
// Загрузить список КП этого менеджера за последние 30 дней
fetch('/api/my-sent-cp/?days=30')
  .then(r => r.json())
  .then(cpList => {
    // Показать dropdown:
    // "12.02.2026 — fashion@store.com — Visual, Neutral"
    // "10.02.2026 — shop@prom.ua — Light, Edgy"
    // + [Нове КП] кнопка для перехода к отправке
  });
```

### 8.3 Email дедупликация

```python
def check_email_duplicate(email, manager):
    """Проверка перед отправкой КП"""
    existing = CommercialOfferEmailLog.objects.filter(
        recipient_email__iexact=email.strip(),
        status="sent",
        created_at__gte=timezone.now() - timedelta(days=30)
    ).select_related("owner").first()

    if existing:
        return {
            "is_duplicate": True,
            "sent_by": existing.owner.get_full_name(),
            "sent_at": existing.created_at,
            "mode": existing.get_mode_display(),
            "segment": existing.get_segment_mode_display(),
        }
    return {"is_duplicate": False}
```

## 9. Вкладка "Склад" (заглушка)

### 9.1 Концепция

```
Навигация: [Бренд] | [DTF] | [Склад]

Склад — будущий модуль для учёта:
- Худі: количество, размеры (S/M/L/XL/XXL), принты
- Футболки: количество, размеры, принты
- Рулоны DTF плёнки
- Тестовые ростовки (отправленные/на складе)
```

### 9.2 Заглушка UI

```html
<div class="warehouse-placeholder">
  <h2>🏭 Склад</h2>
  <p>Модуль в разработке</p>
  <div class="coming-soon-features">
    <div class="feature-card">📦 Худі (по розмірах і принтах)</div>
    <div class="feature-card">👕 Футболки (по розмірах і принтах)</div>
    <div class="feature-card">🎞️ DTF плівка (рулони)</div>
    <div class="feature-card">📋 Тестові ростовки</div>
  </div>
</div>
```

### 9.3 Будущая модель

```python
class WarehouseItem(models.Model):
    class ItemType(models.TextChoices):
        HOODIE = "hoodie", "Худі"
        TSHIRT = "tshirt", "Футболка"
        DTF_FILM = "dtf_film", "DTF плівка"
        TEST_SET = "test_set", "Тестова ростовка"

    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    product = models.ForeignKey("storefront.Product", null=True, blank=True, on_delete=models.SET_NULL)
    size = models.CharField(max_length=10, blank=True)  # S/M/L/XL/XXL
    print_design = models.CharField(max_length=100, blank=True)
    quantity = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)  # Зарезервировано для заказов
    available = models.GeneratedField(...)  # quantity - reserved
    last_counted_at = models.DateTimeField(null=True)
```

## 10. Навигация и доступы

### 10.1 Структура вкладок

```
┌────────────────────────────────────────────────────┐
│ [Бренд 👔]  [DTF 🎨]  [Склад 🏭]                  │
├────────────────────────────────────────────────────┤
│                                                    │
│  Бренд:   Главная | Статистика | Парсинг | ...     │
│  DTF:     Заявки | Заказы | Семплы | Dashboard     │
│  Склад:   (заглушка)                               │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 10.2 Система доступов

```python
# management/models.py — новая модель или расширение User profile

class ManagerProfileExtras(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Доступы к вкладкам (назначает админ)
    can_access_brand = models.BooleanField(default=True)
    can_access_dtf = models.BooleanField(default=False)
    can_access_warehouse = models.BooleanField(default=False)

    # Тестовый период
    test_period_start = models.DateField(null=True, blank=True)
    test_period_end = models.DateField(null=True, blank=True)
    is_on_test_period = models.BooleanField(default=True)
    test_passed = models.BooleanField(default=False)

    # Финансы
    salary_base = models.DecimalField(max_digits=10, decimal_places=2, default=15000)
    commission_first_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.025)
    commission_repeat_pct = models.DecimalField(max_digits=5, decimal_places=3, default=0.050)
    is_commission_only = models.BooleanField(default=False)  # Только за % (без ставки)

    # Штрафы
    penalty_count = models.IntegerField(default=0)
    last_penalty_at = models.DateTimeField(null=True, blank=True)
```

## 11. Пересмотр формул → ЗАМЕНА на HES

> [!CAUTION]
> **Текущая секция устарела**. Вместо модификации существующего KPD, создана полноценная замена — **Hybrid Efficiency System (HES)**.
>
> **Полная документация**: [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md)

### 11.1 Почему HES а не "KPD + modifier"

Простое добавление quality_modifier в compute_kpd() — **недостаточно**, потому что:

| Проблема | KPD + modifier | HES |
|----------|---------------|-----|
| Gaming через КП в мессенджер | Не решает | ✅ Channel penalty (50%) + velocity cap |
| "Не интересно" = 0 баллов | Частично | ✅ + Diversity check on reasons |
| Менеджер за 1 час выполняет KPI | Не решает | ✅ Velocity cap + logarithmic scaling |
| Admin не может настроить сложность | Нет | ✅ 3 preset'а + custom sliders |
| "Заинтересован" но не конвертировал | Не решает | ✅ Provisional points (20%→80%) |
| Обнаружение аномалий | Нет | ✅ Trust Ratio с алертами |

### 11.2 Ключевые компоненты HES

```
HES = Results × 0.60 + Quality × 0.25 + Activity × 0.15
          ↑                 ↑                ↑
    Нельзя подделать   Детектирует         Лог. шкала
    (магазин=оплатил)  копипаст/gaming     + velocity cap
```

Подробности: все формулы, модели, anti-gaming сценарии, и admin-конфигурация описаны в [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md).

### 11.2 Перевыполнение KPI → Повышение

```python
def check_promotion_eligibility(manager, period_days=30):
    stats = get_stats_for_period(manager, period_days)

    criteria = {
        "kpd_above_3": stats["kpd"]["value"] >= 3.0,
        "shops_above_norm": stats["shops"]["created"] >= 8,  # 2/неделю × 4 недели
        "no_penalties": manager.profile.penalty_count == 0,
        "reason_rate_above_90": stats["reason_rate"] >= 0.9,
        "retention_positive": stats["repeat_orders"] >= 2,
    }

    eligible = all(criteria.values())
    return {"eligible": eligible, "criteria": criteria}
```

---

> [!CAUTION]
> **ФИНАЛЬНЫЙ ПРИОРИТЕТ**: Все изменения в этом документе — от владельца бизнеса. Они должны быть реализованы В ПЕРВУЮ ОЧЕРЕДЬ до любых технических улучшений из документов 01-05.
>
> **Порядок**: HES System (08) → Monthly Heatmap → Anti-Abuse → Enhanced Processing → Dedup → CP Sync → DTF Integration → Warehouse.
>
> **Связанные документы**:
> - [08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md) — Hybrid Efficiency System (полная спецификация формулы, anti-gaming, admin-tuning)
> - [06_DTF_INTEGRATION.md](./06_DTF_INTEGRATION.md) — DTF панель в management (отдельная от бренда)
> - [01_CURRENT_STATS_AUDIT.md](./01_CURRENT_STATS_AUDIT.md) — Обновлённые приоритеты
> - [02_IMPROVEMENT_PROPOSALS_ELO.md](./02_IMPROVEMENT_PROPOSALS_ELO.md) — ELO/KPD пересмотр → HES
> - [03_DUPLICATE_MANAGEMENT.md](./03_DUPLICATE_MANAGEMENT.md) — Улучшенная дедупликация с историей менеджера
