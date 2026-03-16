# 📊 Аудит текущей реализации статистики менеджеров

## Оглавление
1. [Архитектура системы](#1-архитектура-системы)
2. [Система баллов (POINTS)](#2-система-баллов)
3. [Формула КПД](#3-формула-кпд)
4. [Система советов (Advice)](#4-система-советов)
5. [Отслеживание активности](#5-отслеживание-активности)
6. [Магазины и конверсии](#6-магазины-и-конверсии)
7. [Выявленные проблемы и недочёты](#7-выявленные-проблемы-и-недочёты)
8. [Оценка правильности реализации](#8-оценка-правильности-реализации)

---

## 1. Архитектура системы

### 1.1 Модели данных (23 модели)

Система менеджмента построена на Django и включает следующие ключевые сущности:

| Модель | Назначение | Ключевые поля |
|--------|-----------|---------------|
| `Client` | Контакт менеджера (обзвоненный клиент) | `shop_name`, `phone`, `phone_normalized`, `call_result` (13 вариантов), `owner`, `next_call_at`, `points_override` |
| `ManagementLead` | Лид (из парсера или ручной) | `status` (4 варианта), `lead_source`, `niche_status`, `phone_normalized`, `google_place_id` |
| `Shop` | Подключённый магазин | `shop_type` (test/full), `test_connected_at`, `test_period_days`, `next_contact_at` |
| `ShopCommunication` | Запись коммуникации с магазином | `contacted_at`, `contact_person`, `phone`, `note` |
| `ShopShipment` | Отправка (ТТН) | `ttn_number`, `shipped_at`, `invoice_total_amount` |
| `ShopInventoryMovement` | Движение товара (склад) | `kind` (receipt/sale/adjust), `product_name`, `delta_qty` |
| `Report` | Ежедневный отчёт менеджера | `points`, `processed`, `file` |
| `ClientFollowUp` | Перезвон (follow-up) | `due_at`, `due_date`, `status` (5 вариантов: open/done/rescheduled/cancelled/missed) |
| `ManagementDailyActivity` | Активность за день | `active_seconds`, `last_seen_at` |
| `ManagementStatsConfig` | Настройки КПД (singleton) | `kpd_weights`, `advice_thresholds` |
| `ManagementStatsAdviceDismissal` | Скрытие совета | `key`, `expires_at` |
| `CommercialOfferEmailSettings` | Настройки КП email | Много полей: `mode`, `segment_mode`, `pricing_mode`, CTA, галерея |
| `CommercialOfferEmailLog` | Лог отправленных КП | `status` (sent/failed), `recipient_email`, `mode`, `segment_mode` |
| `ManagerCommissionAccrual` | Начисление комиссии | `base_amount`, `percent`, `amount`, `frozen_until` |
| `ManagerPayoutRequest` | Запрос на выплату | `status` (processing/approved/rejected/paid), `amount` |
| `ManagementContract` | Договор | `contract_number`, `review_status`, `payload` |
| `LeadParsingJob` | Сессия парсинга (Google Maps) | `keywords`, `cities`, `request_limit`, `duplicate_skipped` |
| `LeadParsingResult` | Результат парсинга | `status` (added/duplicate/no_phone/rejected/error) |

### 1.2 Ключевые файлы

| Файл | Размер | Назначение |
|------|--------|-----------|
| `stats_service.py` | 1259 строк | Основная логика: КПД, советы, метрики, агрегация |
| `stats_views.py` | 223 строки | 5 представлений: stats, admin_list, admin_user, activity_pulse, advice_dismiss |
| `views.py` | 5959 строк | Главный контроллер: home, admin_overview, reports, invoices, contracts, commercial offers, telegram bot |
| `models.py` | 1160 строк | Все 23 модели |
| `constants.py` | 24 строки | POINTS dict, TARGET_CLIENTS_DAY=20, TARGET_POINTS_DAY=100 |
| `lead_services.py` | 58 строк | Расчёт бонусов за лиды (LEAD_ADD_POINTS=2) |
| `urls.py` | 85 строк | 83 маршрута |
| `shop_views.py` | 37KB | Управление магазинами |

### 1.3 URL Структура

Статистика доступна по маршрутам:
- `/stats/` — личная статистика менеджера
- `/stats/admin/` — список менеджеров (для админа)
- `/stats/admin/<user_id>/` — статистика конкретного менеджера (для админа)
- `/stats/advice/dismiss/` — скрытие совета
- `/activity/pulse/` — heartbeat активности (фронтенд отправляет каждые ~30сек)

---

## 2. Система баллов

### 2.1 Текущая таблица баллов

```
POINTS = {
    "order":              45  ← Оформил заказ
    "test_batch":         25  ← Тестовая партия
    "waiting_payment":    20  ← Ожидается оплата
    "waiting_prepayment": 18  ← Ожидается предоплата
    "xml_connected":      15  ← Подключил XML (Prom)
    "sent_email":         15  ← Отправил КП по email
    "sent_messenger":     15  ← Отправил КП в мессенджер
    "wrote_ig":           15  ← Написал в Instagram
    "thinking":           10  ← Подумает
    "other":               8  ← Другое
    "no_answer":           5  ← Не отвечает
    "invalid_number":      5  ← Номер недоступен
    "not_interested":      5  ← Не интересует
    "expensive":           5  ← Дорого
}

LEAD_ADD_POINTS = 2  ← За ручное добавление лида
LEAD_BASE_PROCESSING_PENALTY = 2
TARGET_CLIENTS_DAY = 20
TARGET_POINTS_DAY = 100
```

### 2.2 Анализ баллов — выявленные проблемы

> [!WARNING]
> **Критические проблемы в системе баллов:**

1. **Несоответствие таргетов**: `TARGET_CLIENTS_DAY=20`, но в формуле КПД `points_norm=180`. При 20 клиентах с средним 10 баллов → 200 баллов. Но пользователь говорит нормой должно быть 50 звонков/день.

2. **Нет отрицательных баллов**: Менеджер НЕ теряет баллы за бездействие или плохую работу. Только penalty в КПД уменьшает множитель, но сам показатель баллов только растёт.

3. **Одинаковые баллы для разных действий**: `sent_email`, `sent_messenger`, `wrote_ig` все дают 15 баллов, хотя email с КП = существенно больше усилий, чем сообщение в Instagram.

4. **`no_answer` и `invalid_number` дают по 5 баллов**: Создаёт мотивацию добавлять несуществующие контакты → абуз системы.

5. **Нет весов по качеству**: Контакт, который привёл к продаже через 2 дня, ценится так же, как контакт, который «подумает» и больше никогда не ответит.

6. **`points_override`**: Позволяет менеджеру задать кастомные баллы, но нет ограничения на максимальное значение и нет аудит-лога.

### 2.3 Веса успешности (success_weight)

Используется в расчёте качества:
```python
ORDER:            1.0
TEST_BATCH:       0.8
WAITING_PAYMENT:  0.6
WAITING_PREPAYMENT: 0.5
XML_CONNECTED:    0.4
Всё остальное:    0.0
```

> [!NOTE]
> Формула `success_rate = (success_weighted + 1.0) / (processed + 5.0)` — это Bayesian smoothing (сглаживание), что корректно для малых выборок. При 0 клиентов rate = 1/5 = 0.2 (нейтральный стартовый рейтинг).

---

## 3. Формула КПД

### 3.1 Полная формула

```
КПД = (Effort + Quality + Ops) × (1 - Penalty)
```

#### Effort (Усилие) — max 2.2:
```python
effort_active = min(1.0, (active_minutes / 240) ^ 0.6)   # Время на сайте
effort_points = min(1.2, (points / 180) ^ 0.55 * 1.2)     # Заработанные баллы
effort = min(2.2, effort_active + effort_points)
```

#### Quality (Качество) — max 1.6:
```python
quality_smoothed = (success_weighted + 1.0) / (processed + 5.0)
quality = min(1.6, quality_smoothed * 2.0)
```

#### Ops (Операции) — max 1.2:
```python
cp = min(0.4, cp_sent / 5 * 0.4)           # КП отправлено
shops = min(0.4, shops_created / 2 * 0.4)  # Магазинов создано
invoices = min(0.4, invoices / 2 * 0.4)    # Накладных
ops = min(1.2, cp + shops + invoices)
```

#### Penalty (Штраф) — max 0.6:
```python
penalty = min(0.6,
    missed_rate * 0.8                          # Пропущенные перезвоны
  + report_late_rate * 0.25                    # Опоздавшие отчёты
  + report_missing_rate * 0.5                  # Отсутствующие отчёты
  + followup_plan_missing_penalty              # Без плана перезвона (max 0.2)
)
```

### 3.2 Теоретические границы

| Компонент | Минимум | Максимум | Норма |
|-----------|---------|----------|-------|
| Effort | 0.0 | 2.2 | ~1.5 при 4ч + 180 баллов |
| Quality | 0.0 | 1.6 | ~0.4 при среднем смешении |
| Ops | 0.0 | 1.2 | ~0.4 при 3 КП + 1 магазин |
| Penalty | 0.0 | 0.6 | ~0.1 при хорошей дисциплине |
| **ИТОГО КПД** | **0.0** | **5.0** | **~2.0 при средней работе** |

### 3.3 Проблемы формулы КПД

> [!CAUTION]
> **Основные дефекты формулы:**

1. **Шкала 0-5 неинтуитивна**: Менеджер не может быстро понять, хорошо он работает или нет. Шкала 0-100 была бы более понятной.

2. **Нелинейные кривые скрывают лень**: `(active_minutes / 240) ^ 0.6` — при 2 часах (120 мин) из 4-часовой нормы менеджер уже получает `(120/240)^0.6 = 0.66` из 1.0 — 66%! Это слишком щедро.

3. **Low-volume protection слишком агрессивная**: `min(1.0, followups_total / 5.0)` означает, что при 1-2 перезвонах penalty практически обнуляется, даже если все пропущены.

4. **Нет учёта дней без активности**: Если менеджер не работал 3 дня, КПД за эти дни просто отсутствует, но это не влияет на рейтинг.

5. **Отсутствует revenue-компонент**: Самая важная метрика — сколько денег принёс менеджер — полностью отсутствует в формуле.

6. **Нет сравнения между менеджерами**: КПД считается только для одного менеджера. Нет нормализации относительно лучших/худших.

7. **Кэширование 60 секунд** может быть причиной «устаревших» данных при интенсивной работе.

---

## 4. Система советов (Advice)

### 4.1 Категории советов

Система генерирует до 8 советов, отсортированных по серьёзности:

| # | Категория | Тон | Условие |
|---|-----------|-----|---------|
| 1 | Тренд продуктивности | good/bad | Сравнение бал/час с предыдущим периодом (±20%) |
| 2 | Дисциплина перезвонов | bad/good | Процент пропущенных > 8% / все выполнены |
| 3 | Тестирование источников | neutral | Google Maps/форумы < 5 лидов |
| 4 | Активность vs результат (3 дня) | neutral | Мало часов + 0 конверсий за 3 дня |
| 5 | Дисциплина отчётов | bad/neutral/good | Пропущенные/опоздавшие/стабильные отчёты |
| 6 | План перезвонов после КП | neutral | ≥3 клиента без назначенного next_call |
| 7 | Устаревшие магазины | neutral/bad | Магазины без контакта > 14 дней / просроченные контакты |
| 8 | Сравнение источников | neutral | Разница в success_rate ≥ 25% между источниками |

### 4.2 Оценка

> [!TIP]
> Система советов хорошо реализована: Bayesian подход, низковолумная защита, expire через 1-2 дня, возможность dismiss (скрытия). Это одна из **лучших** частей текущей реализации.

**Недостатки:**
- Нет совета о дублях контактов
- Нет совета о слишком высоком проценте `no_answer` / `invalid_number`
- Нет совета о конверсии лидов → контакты → магазины (воронка)
- Советы приходят максимум 8 — если все плохие, хорошие советы не отобразятся

---

## 5. Отслеживание активности

### 5.1 Activity Pulse

Фронтенд отправляет POST `/activity/pulse/` каждые ~30 секунд с `active_seconds` (clamped to 0-60).

```python
# Защита от абуза
active_seconds = max(0, min(active_seconds, 60))
```

Данные сохраняются в `ManagementDailyActivity` (unique per user + date).

### 5.2 Оценка

**✅ Правильно:**
- Clamping в 60 секунд — защита от инъекции больших значений
- Atomic F-expression update (`F("active_seconds") + active_seconds`)
- Привязка к локальному дню (Europe/Kiev)

**❌ Проблемы:**
- Нет проверки на focus/idle: менеджер может оставить открытую вкладку и пульс продолжает считать
- Нет проверки window.hidden (Page Visibility API) — только серверная сторона
- Отсутствует фингерпринтинг сессий: нельзя понять, 4 часа непрерывной работы или 8 раз по 30 минут
- Нет корреляции с действиями: можно «сидеть» 8 часов и добавить 2 контакта

---

## 6. Магазины и конверсии

### 6.1 Pipeline: Lead → Client → Shop

```
ManagementLead (parser/manual)
    ↓ processed_by → converted_client
Client (call_result → order/test_batch)
    ↓ manual creation
Shop (test/full)
    ↓ shipments, inventory, communications
```

### 6.2 Отслеживание магазинов

- **Тестовые магазины**: `test_connected_at` + `test_period_days` (дефолт 14 дней)
- **Stale shops**: > 14 дней без коммуникации
- **Next contact due**: просроченные запланированные контакты
- **Overdue tests**: тестовый период закончился, но магазин всё ещё "test"
- **Inventory tracking**: приход, продажа, корректировка

### 6.3 Оценка

**✅ Хорошо:**
- Полная модель данных для магазинов
- Отслеживание stale shops и overdue tests
- Communications log с date/person/note
- Inventory movement tracking

**❌ Проблемы:**
- Нет автоматического начисления баллов за активность с магазинами
- Нет метрики retention (% магазинов, которые продолжают покупать)
- Нет отслеживания revenue per shop
- `next_contact_at` — ручная установка, нет автоматической генерации (например, каждые 4 дня)

---

## 7. Выявленные проблемы и недочёты

### 7.1 Критические

| # | Проблема | Влияние | Файл |
|---|---------|---------|------|
| 1 | Дубли контактов: один и тот же клиент может добавляться многократно разными менеджерами | Раздутые баллы, ложная статистика | `models.py` — нет unique на `phone_normalized` в Client |
| 2 | Нет верификации XML подключений | Менеджер получает 15 баллов без проверки | `constants.py`, `views.py` |
| 3 | Система не отличает повторный контакт от нового | Менеджер добавляет 10 контактов, на следующий день переносит 7 → считает 17 | `views.py` → home() |
| 4 | `points_override` без ограничений | Потенциальный абуз | `models.py`, `lead_services.py` |
| 5 | Несоответствие таргетов (20 vs 50 клиентов/день) | Нормы КПД неактуальны | `constants.py` vs бизнес-требования |

### 7.2 Средние

| # | Проблема | Влияние |
|---|---------|---------|
| 6 | Отсутствие ELO/рейтинговой системы | Нет конкуренции и мотивации |
| 7 | Нет ТОП-10 и сравнения менеджеров | Менеджер не видит, где он относительно других |
| 8 | Шкала КПД 0-5 неинтуитивна | Менеджер не понимает «хорошо» или «плохо» |
| 9 | Нет привязки КПД к зарплате в системе | Ручной контроль |
| 10 | Кривая effort_active слишком щедрая (x^0.6) | 50% времени = 66% баллов |

### 7.3 Минорные

| # | Проблема |
|---|---------|
| 11 | Нет dark/light theme toggle |
| 12 | Кэширование 60 сек может мешать при интенсивной работе |
| 13 | Нет пуш-уведомлений о падении КПД |
| 14 | Нет мобильной адаптации для менеджера «в полях» |
| 15 | Нет голосовых напоминаний о перезвонах |

---

## 8. Оценка правильности реализации

### 8.1 Общая оценка: 6.5/10

| Аспект | Оценка | Коммент |
|--------|--------|---------|
| Архитектура данных | 8/10 | Хорошо продуманные модели, правильные индексы |
| Формула КПД | 5/10 | Работает, но неинтуитивна, слишком щедра, нет revenue |
| Система баллов | 4/10 | Статичные баллы, нет отрицательных, возможен абуз |
| Советы (Advice) | 8/10 | Отлично — Bayesian, expire, dismiss, 8 категорий |
| Activity tracking | 5/10 | Базовый пульс без проверки реальной активности |
| Магазины | 7/10 | Хорошая модель, но нет автоматизации контактов |
| Дедупликация | 2/10 | Практически отсутствует |
| UI/UX статистики | 6/10 | Функциональный, но не мотивирующий |
| Сравнение менеджеров | 1/10 | Только admin list, нет ranking/comparison |
| Привязка к зарплате | 3/10 | Есть commission model, но не автоматическая |

### 8.2 Что реализовано хорошо

1. ✅ **Bayesian smoothing** в расчёте качества — корректный статистический подход
2. ✅ **Low-volume protection** — защита от выводов на малых выборках
3. ✅ **Period comparison** — сравнение с предыдущим периодом
4. ✅ **Configurable weights** через ManagementStatsConfig — можно тюнить без деплоя
5. ✅ **Advice system** — 8 категорий автоматических советов
6. ✅ **Report discipline tracking** — on_time / late / missing
7. ✅ **Follow-up pipeline** — open → done / missed / rescheduled
8. ✅ **Shop communications log** — фиксация каждого контакта
9. ✅ **Activity pulse** — атомарное обновление через F-expression
10. ✅ **Commission system** — frozen_until для отложенных выплат

### 8.3 Что необходимо переработать

1. ❌ Полностью переделать систему баллов (progressive, decay, anti-abuse)
2. ❌ Добавить ELO-систему рейтинга
3. ❌ Нормализовать КПД на шкалу 0-100
4. ❌ Реализовать дедупликацию контактов
5. ❌ Добавить revenue-метрики в КПД
6. ❌ Создать ТОП-10 сравнение менеджеров
7. ❌ Интегрировать IP-телефонию
8. ❌ Автоматизировать напоминания по магазинам
9. ❌ Добавить визуализацию эффективности (спидометр)
10. ❌ Привязать КПД к автоматическому расчёту зарплаты

---

## 9. Углублённый анализ — найденные дополнительные детали (Deep Dive v2)

### 9.1 Frontend: SVG Spiral + JS визуализация (stats.html + management-stats.js)

Страница статистики **значительно более продвинута**, чем простая таблица. Она содержит:

#### Визуальные компоненты:
1. **SVG Spiral (donut chart)**: Кастомный donut chart из call_result сегментов с hover-tooltips
   - Отрисовка через `renderSpiral()` — 105 строк custom JS
   - Каждый сегмент — arc path через `describeDonutArc()`
   - При hover: tooltip с количеством, процентом и описанием
   - Glow-фильтр через SVG `feGaussianBlur`
   - Central KPD value с delta ("+5 до попереднього періоду")

2. **Followup Gauge (полукруглый спидометр)**: SVG arc для missed rate
   - `renderGauge()` — анимирует arc-path по проценту пропусков
   - Порог > 8% показывает badge-warn

3. **Trend Sparklines**: Три мини-графика (`renderSparkline()`):
   - Баллы/день (`chart-points`) — оранжевый
   - КПД/день (`chart-kpd`) — синий
   - Активный час/день (`chart-active`) — зелёный
   - Рендеринг через Canvas 2D API (не Chart.js!)

4. **Source Comparison** (`renderSources()`): Горизонтальные бары по источникам лидов
   - Процент конверсии по каждому источнику
   - Визуальное сравнение Instagram vs Google Maps vs Prom.ua

5. **Report Timeline** (`renderReportTimeline()`): Временная шкала отчётов
   - Цветные dot: зелёный (вовремя), жёлтый (поздно), красный (пропущено)

6. **KPI Cards Grid** (7 карточек):
   - Бали / Клієнти / Активний час / Передзвони / КП email / Накладні / Перший клієнт
   - С подзаголовками (бал/клієнт, бал/год, % пропусків)

7. **Advice System UI**: Карточки с тоном (good/bad/neutral), dismiss кнопкой, CTA кнопкой

#### Пропущенная находка:
> [!IMPORTANT]
> Stats page передаёт ВЕСЬ payload как JSON через `{{ stats_payload|json_script:"mgmt-stats-data" }}`.
> Это значит **клиентский JS имеет полный доступ ко всей статистике менеджера** (включая kpd_delta, daily breakdowns, source stats).
> Потенциальная проблема: если admin_view=1, данные другого менеджера отправляются в clear text.

#### Оценка frontend: **7.5/10**
- ✅ Custom SVG визуализации — профессионально
- ✅ Canvas sparklines — лёгкие (не тянем Chart.js)
- ✅ Advice dismiss через AJAX с CSRF
- ❌ Нет Chart.js/D3 — ограниченные возможности интерактивности
- ❌ Нет WebSocket — sparklines не обновляются в real-time
- ❌ Нет mobile breakpoints — responsive не проверен
- ❌ Palette жёстко задана (10 цветов), нет dark/light theme

### 9.2 home() — главная страница (views.py:453-629, 176 строк)

Функция `home()` — основной CRM-экран менеджера:

**GET-запрос**:
- Загружает **ВСЕ** Client записи пользователя: `Client.objects.filter(owner=user)` — **без пагинации!**
- Группирует по дням (Сьогодні / Вчора / дата)
- Загружает **400 базовых лидов**: `ManagementLead.objects.filter(status='base')[:400]`
- Считает stats, reminders, progress bars

> [!CAUTION]
> **Performance issue**: Если менеджер обработал 5000 клиентов за год, `home()` загружает ВСЕ 5000 на одну страницу. Нет пагинации.

**POST-запрос (AJAX)**:
- Создаёт/обновляет Client
- **НОЛЬ проверок на дубли** — `client = Client.objects.create(...)` без любой проверки `phone_normalized`
- Синхронизирует follow-up через `_sync_client_followup()`
- Возвращает JSON с обновлёнными points/progress

**Критическая уязвимость**:
```python
# views.py:527 — НЕТ проверки дублей перед созданием
client = Client.objects.create(
    shop_name=shop_name, phone=phone, ...
)
```

### 9.3 parser_service.py — ЧАСТИЧНО существующая дедупликация

> [!NOTE]
> **Ранее упущено:** Парсер **ИМЕЕТ** дедупликацию, и она довольно качественная!

```python
def _duplicate_state(phone_normalized, place_id):
    // Проверяет дубли в ManagementLead И Client:
    # 1. phone_normalized совпадает ИЛИ google_place_id совпадает
    # 2. Если найден rejected лид → "rejected" (пропускаем)
    # 3. Если найден любой лид/клиент → "duplicate" (пропускаем)
    # 4. Иначе → None (добавляем)
```

**Что проверяется**:
- ✅ Дубли по `phone_normalized` в ManagementLead
- ✅ Дубли по `google_place_id` в ManagementLead 
- ✅ Дубли по `phone_normalized` в Client (кросс-модельная проверка!)
- ✅ Rejected-статус → пропуск (не добавлять повторно отклонённых)

**Что НЕ проверяется**:
- ❌ Парсер проверяет, но **ручное добавление через home()** — нет
- ❌ Обновление Client (edit) — нет
- ❌ Кросс-менеджерная проверка (разные менеджеры — один номер)

### 9.4 Follow-up автоматика (_sync_client_followup + _close_followups_for_report)

Обнаружена **двухфазная система**:

**Фаза 1: Создание follow-up** (`_sync_client_followup`):
```
Client.next_call_at изменён → автоматически создаётся ClientFollowUp(status=OPEN)
Client.next_call_at очищен → все open follow-ups → CANCELLED
Client.next_call_at перенесён → open → RESCHEDULED (если ещё не due) или DONE (если уже due)
```

**Фаза 2: Закрытие при отчёте** (`_close_followups_for_report`):
```
Менеджер отправляет daily report → все сегодняшние OPEN follow-ups → MISSED
```

> [!WARNING]
> **Проблема дизайна**: При отправке отчёта ВСЕ незакрытые follow-ups автоматически помечаются как missed.
> Если менеджер запланировал перезвон на 17:00, но отправил отчёт в 16:30 — follow-up пометится как missed, хотя он ещё не был due.

### 9.5 Reminder System — работает только в окне ±5 минут

```python
# views.py:259-260
if status == 'soon' and eta_raw > 300:
    continue  # Пропускаем будущие дзвінки > 5 хвилин
```

Менеджер видит напоминание **ТОЛЬКО за 5 минут до перезвона**.
- Нет утреннего briefing с планом на день
- Нет email/push напоминаний за 30 минут
- Нет timeline с будущими перезвонами
- Shop reminders тоже ограничены 5 минутами — бесполезно для магазинов

### 9.6 admin.py — покрытие только 6 из 23 моделей

**Зарегистрировано в Django Admin:**
1. ManagementStatsConfig
2. ManagementDailyActivity
3. ClientFollowUp
4. ManagementStatsAdviceDismissal
5. ManagementLead
6. LeadParsingJob + LeadParsingResult

**НЕ зарегистрировано (17 моделей!)**:
- Client ❌ — основная модель!
- Shop ❌ — управление только через shop_views
- ShopCommunication, ShopShipment, ShopInventoryMovement ❌
- Report ❌
- CommercialOfferEmailSettings, CommercialOfferEmailLog ❌
- ManagerCommissionAccrual, ManagerPayoutRequest ❌
- ManagementContract, ContractSequence ❌
- ShopPhone ❌
- ReminderRead, ReminderSent ❌
- InvoiceRejectionReasonRequest, ContractRejectionReasonRequest ❌

> [!IMPORTANT]
> Отсутствие Client и Shop в Django Admin означает, что администратор не может:
> - Массово просматривать/редактировать клиентов
> - Фильтровать/искать по phone_normalized
> - Проводить аудит данных
> - Экспортировать записи

### 9.7 views.py — монолит на 5959 строк

**Антипаттерн**: `views.py` содержит 133 функции/класса в одном файле:
- home (176 строк)
- admin_overview (398 строк!)
- profile_update (167 строк)
- reports, invoices, contracts, commercial offers, telegram
- Все в одном файле без разделения по модулям

**Рекомендация**: Разделить на:
- `home_views.py` — главная CRM
- `admin_views.py` — администрирование
- `report_views.py` — отчёты
- `invoice_views.py` — накладные
- `contract_views.py` — договоры
- `cp_views.py` — коммерческие предложения
- `telegram_views.py` — бот
- `profile_views.py` — профиль

### 9.8 Commercial Offer Email — продвинутая система (forms.py)

Ранее **не проанализирована** детально. `CommercialOfferEmailForm` содержит **47 полей**:

- **Режимы**: LIGHT/VISUAL
- **Сегменты**: NEUTRAL/EDGY
- **Subject presets**: 4 варианта (3 пресета + кастомный)
- **Pricing**: OPT (5 тиров: 8-15/16-31/32-63/64-99/100+) и DROP
- **CTA типы**: 6 вариантов (Telegram/WhatsApp/Email/Reply/Custom URL)
- **Менеджер контакты**: Phone/Viber/WhatsApp/Telegram с валидацией
- **Галерея**: 2 набора (neutral/edgy), до 6 изображений каждый
- **Duplicate phone normalization**: `normalize_ua_phone()` — дублирует логику из `models.py`

> [!WARNING]
> **DRY violation**: Функция `normalize_ua_phone()` из forms.py дублирует `normalize_phone()` из models.py. Это два разных места с одной и той же логикой — ошибка в одном не затронет другой.

### 9.9 Обновлённая итоговая оценка: 6.0/10 (снижена с 6.5)

| Аспект | Было | Стало | Почему изменилось |
|--------|------|-------|-------------------|
| Архитектура данных | 8/10 | **7/10** | 17 моделей не в admin, views.py монолит |
| Frontend визуализация | 6/10 | **7.5/10** | Обнаружены custom SVG spiral, sparklines, gauge |
| Performance | — | **4/10** | home() загружает ВСЕ записи без пагинации |
| DRY/Code Quality | — | **5/10** | Дублирование normalize_phone, 6000-строк views.py |
| Reminder System | — | **3/10** | 5-минутное окно, нет push/email, нет briefing |
| Дедупликация | 2/10 | **3/10** | Парсер имеет частичную дедупликацию, но home() — нет |
| **Общая** | **6.5** | **6.0** | Добавлены performance и DRY проблемы |

---

## 10. Молекулярный анализ v3 — ядро системы

### 10.1 `compute_kpd()` — полная декомпозиция формулы (stats_service.py:182-251)

**Формула:** `KPD = (Effort + Quality + Ops) × (1 - Penalty)`

#### Компонент 1: Effort (0..2.2)
```python
effort_active = min(1.0, (active_minutes / 240) ^ 0.6)  # Субквадратный рост!
effort_points = min(1.2, (points / 180) ^ 0.55 * 1.2)   # Ещё более мягкий рост
effort = min(2.2, effort_active + effort_points)
```

> [!IMPORTANT]
> **Математический анализ**: Степень 0.6 означает, что первые 60 минут дают effort_active = 0.46, а полные 240 мин = 1.0. Это **субквадратная кривая** — быстрый рост на старте, замедление к нормативу. Аналогично для points: первые 45 баллов дают 0.58, а 180 = 1.2.

#### Компонент 2: Quality (0..1.6)
```python
quality_smoothed = (success_weighted + 1.0) / (processed + 5.0)  # Laplace smoothing!
quality = min(1.6, quality_smoothed * 2.0)
```

> [!NOTE]
> **Bayesian smoothing**: Формула `(SW + 1) / (N + 5)` — это вариант Laplace smoothing. Защищает от нулевого деления и от чрезмерного влияния малых выборок. При 0 обработанных = 0.2, при 5 успешных из 5 = 0.6.

#### Компонент 3: Ops (0..1.2)
```python
ops = min(0.4, cp_sent/5 * 0.4) + min(0.4, shops_created/2 * 0.4) + min(0.4, invoices/2 * 0.4)
```
Три равноценных sub-компонента, каждый макс 0.4: КП, магазины, накладные.

#### Компонент 4: Penalty (0..0.6)
```python
penalty = missed_rate * 0.8 + report_late * 0.25 + report_missing * 0.5 + followup_plan_penalty
# Каждый rate защищён low-volume protection: rate *= min(1.0, N / 3..5)
```

**Теоретический максимум KPD**: (2.2 + 1.6 + 1.2) × 1.0 = **5.0**
**Практический максимум**: ~4.0 (невозможно набрать все максимумы одновременно)
**Средний КПД хорошего менеджера**: ~2.0-3.0

### 10.2 `generate_advice()` — AI-подобный движок рекомендаций (260-532, 272 строки)

Обнаружена **8-категорийная** система персональных рекомендаций:

| # | Категория | Тон | Условие срабатывания |
|---|-----------|-----|---------------------|
| 1 | Продуктивность (бал/час) | good/bad | Δ ≥ ±20% vs prev period, min 20 контактов |
| 2 | Дисциплина follow-ups | good/bad | missed_rate > 8% при total ≥ 20 |
| 3 | Тестирование источников | neutral | count < min_n_sources/3 для google_maps/forums |
| 4 | Active time vs results | neutral | 3 дня с low activity + zero success |
| 5 | Дисциплина отчётов | good/bad/neutral | late_days ≥ 1 или missing_days ≥ 1 |
| 6 | Follow-up planning | neutral | plan_missing ≥ 3 при processed ≥ min/2 |
| 7 | Stale shops / next contact | bad/neutral | stale ≥ 2 или next_due ≥ 2 или overdue_tests ≥ 1 |
| 8 | Сравнение источников | neutral | ≥ 2 источника по 25+ контактов, diff ≥ 25% |

**Ключевые архитектурные решения:**
- Все пороги **конфигурируемы через БД** (`ManagementStatsConfig`)
- Каждый совет имеет `key` для **dismiss** (пользователь может скрыть)
- `expires_at` — советы автоматически исчезают через 1-2 дня
- `assumption: true` — честная маркировка, что это предположение, не факт
- `cta` — actionable кнопки (пример: «Підключити Telegram-нагадування»)
- Максимум 8 советов одновременно, сортировка: bad → neutral → good

### 10.3 `get_stats_payload()` — 607-строчный data engine

Функция генерирует **единый JSON payload** с 25+ метриками для frontend. Карта данных:

```
payload = {
  range:     { period, label, from, to, days }
  summary: {
    first_activity_date, days_working,
    processed, points, points_per_client,
    active_seconds, active_hhmm, points_per_active_hour,
    kpd:       { value, raw, effort, quality, ops, penalty, breakdown:{...} }
    kpd_prev:  { ... }
    kpd_delta, kpd_insight,
    success_weighted, success_rate, success_rate_pct,
    followups: { total, missed, overdue_open, missed_effective, done, rescheduled, cancelled, open, missed_rate, problem_list[10] }
    pipeline:  { followup_plan_missing, by[], examples[8] }
    reports:   { required, late, missing, on_time }
    cp:        { total, sent, failed, modes[], segments[] }
    invoices:  { created, amount, approved, paid, review[], payment[] }
    shops:     { created, test, full, test_overdue_total, test_overdue_list[10],
                 tests_converted_total, stale_shops_count, stale_shops_list[10],
                 next_contact_due_count, next_contact_due_list[10],
                 shipments_count, shipments_amount,
                 inventory_sales_delta, inventory_receipts_delta, inventory_adjust_count,
                 communications_count }
  }
  segments:  [{ code, label, count, pct, success_weight, subtypes[] }]
  roles:     [{ code, label, count, pct }]
  sources:   [{ code, label, count, pct, success_weighted, success_rate, raw[] }][:12]
  series:    [{ date, clients, points, active_seconds, active_hhmm,
                success_weighted, report_status, kpd }]  // per day!
  advice:    [{ key, tone, title, text, evidence, assumption, cta, expires_at }][:8]
  meta:      { report_deadline_hour, report_late_grace_minutes }
}
```

**~15 отдельных DB запросов** в одном вызове — потенциальная bottleneck.
**Caching**: 60 секунд (cache.set), + 600 секунд для config.

### 10.4 `ManagementStatsConfig` — конфигурация через БД

> [!TIP]
> **Ранее упущено**: Все веса и пороги КПД **настраиваемы без деплоя!** Через модель `ManagementStatsConfig(pk=1)` с двумя JSONField: `kpd_weights` и `advice_thresholds`. Это **значительно лучше** hard-coded.

Конфигурируемые параметры:

| Группа | Параметр | Дефолт | Описание |
|--------|----------|--------|----------|
| KPD | `active_norm_minutes` | 240 | Норматив активных минут |
| KPD | `points_norm` | 180 | Норматив баллов |
| KPD | `max_effort` | 2.2 | Потолок Effort |
| KPD | `max_quality` | 1.6 | Потолок Quality |
| KPD | `max_ops` | 1.2 | Потолок Ops |
| KPD | `max_penalty` | 0.6 | Потолок Penalty |
| Advice | `min_n_strong` | 20 | Минимум контактов для вывода совета |
| Advice | `missed_followups_warn_pct` | 8.0% | Порог missed для warning |
| Advice | `report_deadline_hour` | 19 | Дедлайн отчёта |
| Advice | `stale_shop_days` | 14 | Дней без контакта = stale |

### 10.5 Дублирование enum-классов — DRY violation в models.py

`CommercialOfferEmailLog` **полностью дублирует** enum-классы из `CommercialOfferEmailSettings`:

```python
# CommercialOfferEmailSettings (строки 352-476):
class CpMode, CpSegmentMode, CpSubjectPreset, CpCtaType, PricingMode, OptTier

# CommercialOfferEmailLog (строки 479-613):
class CpMode, CpSegmentMode, CpSubjectPreset, CpCtaType, PricingMode, OptTier
# ← ПОЛНАЯ КОПИЯ! ~130 строк дублирования!
```

**Решение**: Вынести в отдельный `enums.py` или использовать общие Choice-классы.

### 10.6 Несоответствие дедупликации: lead_create_api vs home()

**КРИТИЧЕСКОЕ ОТКРЫТИЕ**: `lead_create_api()` (lead_views.py:101-105) **ИМЕЕТ** проверку:
```python
# lead_views.py:101-105
has_duplicate = (
    Client.objects.filter(phone_normalized=phone_normalized).exists()
    or ManagementLead.objects.filter(phone_normalized=phone_normalized).exists()
)
if has_duplicate:
    return JsonResponse({"error": "Такий номер вже є у базі."}, status=409)
```

Но `home()` (views.py:527-539) при POST создания Client — **НЕ ИМЕЕТ** такой проверки.

**Вывод**: Два пути добавления контактов → один защищён, другой нет. **Инконсистентность**.

### 10.7 LEAD_BASE_PROCESSING_PENALTY — скрытая механика баллов

`lead_process_api()` применяет штраф при конвертации лида в клиента:
```python
adjusted_points = max(0, base_points - LEAD_BASE_PROCESSING_PENALTY)
client = Client.objects.create(..., points_override=adjusted_points)
```

Это означает, что обработка лида из базы даёт **меньше баллов**, чем ручное добавление клиента. Стимулирует самостоятельный поиск, но может демотивировать обработку базы.

### 10.8 Обновлённая общая оценка v3

| Аспект | v1 | v2 | **v3** | Причина v3 |
|--------|----|----|--------|------------|
| КПД формула | 8/10 | — | **9/10** ↑ | DB-конфигурация, Bayesian smoothing, low-volume protection |
| Advice система | 7/10 | — | **9/10** ↑ | 8 категорий, dismiss, expiry, CTA, configurable thresholds |
| Stats payload | — | — | **8/10** | 25+ метрик, per-day series, shop stale detection, inventory |
| Frontend | 6/10 | 7.5/10 | **7.5/10** = | Custom SVG, Canvas sparklines |
| Дедупликация | 2/10 | 3/10 | **3/10** = | lead_create protected, home() not |
| Performance | — | 4/10 | **4/10** = | Всё ещё нет пагинации |
| Code Quality | — | 5/10 | **4.5/10** ↓ | +130 строк enum duplication обнаружено |
| **ОБЩАЯ** | **6.5** | **6.0** | **6.5** ↑ | Advice engine и KPD formula значительно лучше, чем оценивалось |

> [!IMPORTANT]
> **Вывод v3**: Ядро статистической системы (compute_kpd + generate_advice + get_stats_payload) **технически зрелое и хорошо спроектированное**. Проблемы сконцентрированы в **периферии** (home(), admin, DRY, performance). Приоритет рефакторинга — периферийный код, ядро трогать не нужно.

---

## 11. Обновление приоритетов (от владельца бизнеса)

> [!CAUTION]
> **Все пункты ниже имеют ВЫСШИЙ ПРИОРИТЕТ** — они идут от владельца бизнеса и должны быть реализованы ДО технических улучшений.

### Ссылки на новые документы:
- **[07_MANAGER_WORKFLOW.md](./07_MANAGER_WORKFLOW.md)** — Полная спецификация workflow: зарплата (15k + 2.5%/5%), тестовый период, anti-abuse баллов, monthly heatmap, расширенная обработка клиента, CP sync
- **[06_DTF_INTEGRATION.md](./06_DTF_INTEGRATION.md)** — DTF блок в менеджменте: заявки, заказы, семплы (отдельная от бренда статистика)

### Пересмотр системы баллов (важно!)

Текущая система `POINTS_MAP` **НЕ соответствует** бизнес-требованиям:
- **"Не интересно" без причины → 0 баллов** (а не 0.5 как сейчас)
- **"Не берёт трубку"** → 0 до 3+ попыток, потом 0.3
- **`NotInterestedReason`** — обязательный enum причин отказа
- **`CallAttempt`** — новая модель для учёта каждой попытки звонка
- **Quality modifier** в KPD формуле: `(reason_rate * 0.15 + callback_rate * 0.15)`

### Новый порядок реализации

```
1. 🔴 Monthly Heatmap (ManagerDailyHeatmap модель + cron)
2. 🔴 Anti-Abuse scoring (CallAttempt + NotInterestedReason)
3. 🔴 Enhanced processing modal (новые поля)
4. 🟡 Improved dedup (показ кто обработал + когда + результат)
5. 🟡 CP-email sync (ClientCPLink)
6. 🟢 DTF Integration (вкладка + bridge)
7. 🟢 Warehouse stub (заглушка)
8. 🔵 KPD quality modifier (compute_kpd расширение)
```
