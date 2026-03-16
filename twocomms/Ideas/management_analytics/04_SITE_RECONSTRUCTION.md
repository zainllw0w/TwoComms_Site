# 🏗️ Реконструкция менеджмент-сайта: UI/UX и функциональный рефакторинг

## Оглавление
1. [Текущее состояние сайта](#1-текущее-состояние-сайта)
2. [Функциональный анализ](#2-функциональный-анализ)
3. [Предложения по UI/UX](#3-предложения-по-uiux)
4. [Автоматизация процессов](#4-автоматизация-процессов)
5. [Система напоминаний](#5-система-напоминаний)
6. [Дорожная карта реализации](#6-дорожная-карта)

---

## 1. Текущее состояние сайта

### 1.1 Структура навигации (83 URL маршрута)

| Раздел | Кол-во маршрутов | Описание |
|--------|-----------------|----------|
| Auth | 2 | Login / Logout |
| Home (CRM) | 1 | Главная с формой добавления клиента |
| Admin Panel | 8 | Обзор, пользователи, инвойсы, выплаты |
| Reports | 2 | Просмотр и отправка отчётов |
| Reminders | 2 | Чтение и лента напоминаний |
| Profile | 2 | Обновление профиля, привязка кода |
| Invoices | 6 | CRUD накладных, оплата |
| Contracts | 5 | Генерация, просмотр, отправка договоров |
| Commercial Offers | 9 | Email КП: preview, send, settings, gallery |
| Shops | 8 | CRUD магазинов, инвентарь, ТТН, контракты |
| Stats | 5 | Личная статистика, admin, activity pulse |
| Info | 1 | Информационная страница |
| Payouts | 2 | Запрос на выплату |
| Leads | 3 | Создание, детали, обработка лидов |
| Parsing | 6 | Dashboard парсера, start/pause/resume/stop/status |
| Telegram Bot | 1 | Webhook |

### 1.2 Функциональная матрица ролей

| Функция | Менеджер | Админ |
|---------|----------|-------|
| Добавление клиентов | ✅ | ✅ |
| Просмотр своей статистики | ✅ | ✅ |
| Просмотр статистики всех | ❌ | ✅ |
| Создание магазинов | ✅ | ✅ |
| Генерация накладных | ✅ | ✅ |
| Одобрение накладных | ❌ | ✅ |
| Генерация договоров | ✅ | ✅ |
| Отправка КП | ✅ | ✅ |
| Парсинг лидов | ✅ | ✅ |
| Модерация лидов | ❌ | ✅ |
| Управление выплатами | ❌ | ✅ |
| Просмотр выплат | ✅ | ✅ |

---

## 2. Функциональный анализ

### 2.1 Существующие CRM-функции (что уже есть)

#### ✅ Хорошо реализовано:
1. **Pipeline: Lead → Client → Shop** — полная воронка
2. **Commercial Offer via Email** — настраиваемые шаблоны (LIGHT/VISUAL, NEUTRAL/EDGY)
3. **Invoice generation** — автогенерация с review workflow
4. **Contract generation** — с автонумерацией по году
5. **Shop management** — типы (test/full), ТТН, инвентарь
6. **Telegram bot integration** — уведомления и привязка аккаунта
7. **Lead parsing** — автоматический парсинг Google Maps
8. **Commission system** — начисления с frozen period
9. **Payout management** — запрос → одобрение → выплата
10. **Activity tracking** — pulse-based daily activity

#### ❌ Отсутствует или требует доработки:
1. **Drag & drop Kanban** — для статусов лидов/клиентов
2. **Calendar view** — для перезвонов и контактов с магазинами
3. **Dashboard с графиками** — только цифры, нет визуализации
4. **Mobile-responsive design** — не оптимизировано под мобильные
5. **Real-time updates** — нет WebSocket, только polling
6. **Search** — нет глобального поиска по контактам/магазинам
7. **Bulk operations** — нет массовых действий
8. **Export / Import** — нет выгрузки данных
9. **Notification center** — только Telegram, нет in-app
10. **Audit log** — нет истории изменений

### 2.2 Оценка UX по разделам

| Раздел | UX Score | Проблемы |
|--------|----------|----------|
| Home (CRM) | 5/10 | Перегружен, форма добавления + список на одной странице |
| Stats | 6/10 | Данные есть, визуализации нет |
| Shops | 7/10 | Хорошая модель, но нет calendar view |
| Invoices | 7/10 | Workflow есть, но UI basic |
| КП Email | 8/10 | Лучший раздел — preview, gallery, settings |
| Admin Panel | 4/10 | Перегружен, нет drill-down |
| Leads | 5/10 | Нет Kanban, нет фильтров |
| Parsing | 6/10 | Функционально, но UX linear |

---

## 3. Предложения по UI/UX

### 3.1 Новый макет главной страницы

```
╔═══════════════════════════════════════════════════════════════╗
║  🏠 TwoComms Management           [🔔 3] [👤 Олена К.] [⚙️] ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  ╭──────────────╮  ╭──────────────╮  ╭──────────────╮        ║
║  │  КПД сьогодні │  │  Дзвінки     │  │  ELO рейтинг │        ║
║  │     72/100    │  │    34/50     │  │     1280     │        ║
║  │  🟢 Сильна    │  │  ████░░ 68%│  │  🥇 Gold     │        ║
║  │  ↑ +8 від вч. │  │              │  │  ↑ +12       │        ║
║  ╰──────────────╯  ╰──────────────╯  ╰──────────────╯        ║
║                                                               ║
║  ╭─ 🔔 Перезвони сьогодні (4) ───────────────────────╮       ║
║  │ ⏰ 10:00  Магазин "Сонячний"    📞 +380991234567  │       ║
║  │ ⏰ 12:30  Магазин "Style Store"  📞 +380997654321  │       ║
║  │ 🔴 Прострочено: "ФОП Петренко"  📞 +380995551234  │       ║
║  │ ⏰ 16:00  "New Fashion"          📞 +380991112233  │       ║
║  ╰────────────────────────────────────────────────────╯       ║
║                                                               ║
║  ╭─ 📋 Швидке додавання клієнта ──────────────────────╮      ║
║  │ Назва: [____________]  Телефон: [____________]     │      ║
║  │ ПІБ:   [____________]  Результат: [▼ Оберіть  ]   │      ║
║  │ Джерело: [____________] [📞 Додати клієнта]        │      ║
║  ╰────────────────────────────────────────────────────╯       ║
║                                                               ║
║  ╭─ 📊 Сьогоднішні контакти (34) ─────────────────────╮      ║
║  │ Замовлення: 2  │ КП відправ.: 5  │ Подумає: 8     │      ║
║  │ Не відпов.: 12 │ Не цікавить: 4  │ Інше: 3        │      ║
║  ╰────────────────────────────────────────────────────╯       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### 3.2 Sidebar навигация

```
╭─────────────────────╮
│ 🏠 Головна          │ ← Dashboard + quick add
│ 📞 Клієнти          │ ← Полный список + фильтры
│ 📋 Ліди             │ ← Kanban board + parsing
│ 🏪 Магазини         │ ← Grid/List + calendar
│ 📊 Статистика       │ ← Спидометр + графики
│ 🏆 Рейтинг          │ ← ELO + TOP-10
│ 📧 КП               │ ← Коммерческие предложения
│ 📄 Накладні          │ ← Invoice management
│ 📝 Договори         │ ← Contract management
│ 💰 Виплати          │ ← Payouts + earnings
│ 📈 Звітність        │ ← Reports
│ ──────────────────  │
│ ⚙️ Налаштування     │
│ 🔔 Нагадування      │
│ ℹ️ Допомога          │
╰─────────────────────╯
```

### 3.3 Дизайн-система

#### Цветовая палитра:
```css
:root {
    --primary:    #6366f1;  /* Indigo-500 — основной */
    --success:    #10b981;  /* Emerald-500 — успех */
    --warning:    #f59e0b;  /* Amber-500 — предупреждение */
    --danger:     #ef4444;  /* Red-500 — ошибка */
    --info:       #3b82f6;  /* Blue-500 — информация */
    
    --bg-primary: #0f172a;  /* Slate-900 — основной фон (dark) */
    --bg-card:    #1e293b;  /* Slate-800 — карточки */
    --bg-hover:   #334155;  /* Slate-700 — hover */
    --text-main:  #f8fafc;  /* Slate-50 — основной текст */
    --text-muted: #94a3b8;  /* Slate-400 — вторичный текст */
    
    --radius:     12px;     /* Скруглённые углы */
    --shadow:     0 4px 12px rgba(0,0,0,0.3);  /* Тень карточек */
}
```

#### Компоненты:
- **KPI Cards** — карточки с анимацией числа (countUp.js)
- **Gauge Chart** — спидометр КПД (Chart.js или D3.js)
- **Trend Sparkline** — мини-график тренда рядом с числом
- **Progress Ring** — кольцо прогресса (клиенты: 34/50)
- **Toast Notifications** — «+45 балів за замовлення!» (Sonner)
- **Modal Drawer** — боковая панель для деталей (вместо full-page)
- **Calendar Widget** — для перезвонов и контактов магазинов
- **Kanban Board** — для лидов (moderation → base → converted → rejected)

---

## 4. Автоматизация процессов

### 4.1 Автоматические действия

| Триггер | Действие | Реализация |
|---------|---------|------------|
| Client saved с `call_result` ∈ {thinking, sent_*} | Создать follow-up | post_save signal |
| Follow-up просрочен > 4 часов | Пометить как missed | Celery beat (каждые 30 мин) |
| Shop без контакта > 4 дней | Telegram reminder | Celery beat (ежедневно 9:00) |
| КПД < 30 три дня подряд | Alert админу | Celery beat (ежедневно 18:00) |
| Тестовый период закончился | Reminder менеджеру | Celery beat (ежедневно) |
| Накладная оплачена | Начислить комиссию | post_save signal / webhook |
| 5 `no_answer` подряд | Предложить сменить источник | Realtime advice |
| Отчёт не отправлен до 19:00 | Telegram warning | Celery beat (19:00) |
| ELO изменился | Telegram notification | post_save signal |
| Новый лид прошёл модерацию | Notify available managers | post_save signal |

### 4.2 Telegram Bot расширения

Текущий бот:
- Привязка аккаунта (bind code)
- Напоминания о перезвонах
- Уведомления о накладных

**Новые функции бота:**
```
/stats — Мій КПД сьогодні
/elo — Мій ELO рейтинг
/top — ТОП-5 менеджерів
/followups — Перезвони на сьогодні
/shops — Магазини, що потребують контакту
/report — Відправити звіт
/streak — Скільки днів поспіль
/help — Допомога
```

---

## 5. Система напоминаний

### 5.1 Приоритизация напоминаний

```python
REMINDER_PRIORITY = {
    'followup_overdue':    1,  # 🔴 Прострочений перезвон
    'report_missing':      2,  # 🔴 Не відправлений звіт
    'shop_test_expired':   3,  # 🟠 Тестовий період закінчився
    'shop_stale':          4,  # 🟡 Магазин потребує контакту
    'followup_upcoming':   5,  # 🟢 Перезвон через 15 хв
    'kpd_low':             6,  # 🟡 КПД нижче норми
    'elo_drop':            7,  # 🟡 ELO впав
    'achievement_unlocked': 8, # 🎉 Досягнення розблоковано
}
```

### 5.2 In-App Notification Center

```
╭─ 🔔 Сповіщення ──────────────────────────╮
│                                            │
│ 🔴 10:15  Прострочений перезвон:          │
│          "Магазин Сонячний"               │
│          [📞 Зателефонувати] [🔄 Перенести]│
│                                            │
│ 🟠 09:00  Тестовий період закінчився:     │
│          "New Fashion Store"              │
│          [📋 Переглянути]                 │
│                                            │
│ 🟡 Вчора  Ваш КПД впав до 42.           │
│          Зробіть ще 10 дзвінків!          │
│                                            │
│ 🎉 Вчора  🔥 Streak! 5 днів поспіль      │
│          КПД > 60!                        │
│                                            │
╰────────────────────────────────────────────╯
```

### 5.3 Правила напоминаний о магазинах (каждые 4 дня)

```python
SHOP_REMINDER_RULES = {
    'full_active': {
        'interval': timedelta(days=4),
        'channel': ['in_app', 'telegram'],
        'message': "Магазин {name} потребує контакту (останній: {days} днів тому)",
    },
    'test_active': {
        'interval': timedelta(days=2),  # Чаще для тестовых!
        'channel': ['in_app', 'telegram'],
        'message': "Тестовий магазин {name}: {days_left} днів до кінця тесту",
    },
    'test_expired': {
        'interval': timedelta(days=1),
        'channel': ['in_app', 'telegram', 'admin_alert'],
        'message': "⚠️ Тест для {name} закінчився! Конвертувати чи закрити?",
        'escalate_after': timedelta(days=3),  # Через 3 дня → админ
    },
}
```

---

## 6. Дорожная карта реализации

### Фаза 1: Критические исправления (1-2 недели)
- [ ] Дедупликация контактов (проверка при добавлении)
- [ ] Нормализация КПД на шкалу 0-100
- [ ] Автоматический missed для просроченных follow-up
- [ ] Исправить баллы (снизить `no_answer`, `invalid_number`)

### Фаза 2: Визуализация (2-3 недели)
- [ ] Спидометр КПД на главной странице
- [ ] Прогресс-бары для дневных целей
- [ ] Тренд-графики (30 дней)
- [ ] Toast-уведомления при начислении баллов

### Фаза 3: ELO и геймификация (3-4 недели)
- [ ] ELO-система (модель, расчёт, UI)
- [ ] TOP-10 лидерборд
- [ ] Система достижений (badges)
- [ ] Streak counter

### Фаза 4: Автоматизация (2-3 недели)
- [ ] Автоматические follow-up при определённых результатах
- [ ] Telegram bot расширения
- [ ] In-app notification center
- [ ] Напоминания о магазинах (каждые 4 дня)

### Фаза 5: Расширенный UX (3-4 недели)
- [ ] Новый sidebar + navigation
- [ ] Kanban для лидов
- [ ] Calendar view для перезвонов
- [ ] Mobile-responsive redesign
- [ ] Dark mode

### Фаза 6: Аналитика и зарплата (2-3 недели)
- [ ] Revenue tracking per manager
- [ ] Автоматический расчёт зарплаты
- [ ] Export to Excel
- [ ] Admin comparison dashboard

---

## 7. Углублённый анализ — дополнения v2

### 7.1 Stats Page — Frontend уже продвинут (повышение UX оценки)

Ранее Stats оценён как 6/10. После анализа `stats.html` + `management-stats.js` (318 строк):

**Обнаруженные визуальные компоненты:**

| Компонент | Реализация | Качество |
|-----------|-----------|----------|
| SVG Donut chart (call_result) | `renderSpiral()` — custom SVG с glow-фильтром | ⬆️ 8/10 |
| Followup Gauge | `renderGauge()` — SVG arc для missed rate | 7/10 |
| Sparklines (3 шт.) | `renderSparkline()` — Canvas 2D (points, KPD, active) | 7/10 |
| Source Comparison | `renderSources()` — horizontal bars | 7/10 |
| Report Timeline | `renderReportTimeline()` — dot timeline | 6/10 |
| KPI Cards (7 шт.) | HTML grid с подзаголовками | 6/10 |
| Advice Cards | Тонированные карточки с CTA | 8/10 |

**Обновлённая UX оценка Stats: 7.5/10** (было 6/10)

> [!TIP]
> Frontend статистики **значительно лучше**, чем ожидалось. Приоритет реконструкции Stats — **НИЗКИЙ**. Основной фокус — CRM (home), Admin, и Leads.

### 7.2 home() — CRM экран. Критические UX проблемы

Из анализа `home()` (views.py:453-629, 176 строк):

1. **Нет пагинации**: Все Client записи загружаются на одну страницу — при 5000 контактов DOM будет перегружен
2. **400 базовых лидов**: `ManagementLead.objects.filter(status='base')[:400]` — тоже на одной странице
3. **Добавление + список на одной странице**: Перегружает UX, нет разделения режимов
4. **AJAX создание**: При POST создаёт Client без перезагрузки — хорошо, но нет duplicate check

**Рекомендация для фазы 1:**
- Добавить пагинацию (50 клиентов на страницу)
- Вынести "Швидке додавання" в floating action button + modal
- Добавить duplicate check на blur event поля "Телефон"

### 7.3 views.py — план декомпозиции монолита

Текущий `views.py` = **5959 строк, 133+ функций**. Предлагаемая декомпозиция:

| Новый файл | Функции | ~Строк |
|-----------|---------|--------|
| `home_views.py` | `home()`, `_sync_client_followup()`, `get_user_stats()`, `get_reminders()` | ~400 |
| `admin_views.py` | `admin_overview()`, `admin_user_detail()` | ~500 |
| `report_views.py` | `reports_list()`, `reports_submit()`, `_close_followups_for_report()` | ~300 |
| `invoice_views.py` | 6 функций CRUD + review + payment | ~500 |
| `contract_views.py` | 5 функций генерации/просмотра/отправки | ~400 |
| `cp_views.py` | 9 функций КП email (preview, send, settings, gallery) | ~800 |
| `telegram_views.py` | webhook, bind, `_send_telegram_message()` | ~300 |
| `profile_views.py` | `profile_update()`, photo upload | ~200 |
| `payout_views.py` | payout request, admin approval | ~200 |
| `lead_views.py` | create, detail, process leads | ~300 |
| `utils.py` | `_load_env_tokens()`, `normalize_phone()`, helpers | ~200 |

### 7.4 shop_views.py — 938 строк требуют рефакторинга

`shops_save_api()` = **195 строк** в одной функции. Обрабатывает:
- Создание нового магазина
- Обновление существующего
- Добавление/обновление телефонов (ShopPhone)
- Добавление контактных лиц (ShopContactPerson)
- Обновление инвентаря
- Установка типа (test/full)
- Привязка менеджера

**Рекомендация**: Разбить на:
- `_create_shop()` — только создание
- `_update_shop()` — только обновление
- `_sync_shop_phones()` — синхронизация телефонов
- `_sync_contacts()` — контактные лица
- Или переписать на DRF Serializers (предпочтительно)

### 7.5 Обновлённые UX Score после deep-dive

| Раздел | Было | Стало | Комментарий |
|--------|------|-------|-------------|
| Home (CRM) | 5/10 | **4/10** ↓ | Нет пагинации, нет duplicate check |
| Stats | 6/10 | **7.5/10** ↑ | Обнаружены SVG spiral, gauge, sparklines |
| Admin Panel | 4/10 | **3.5/10** ↓ | N+1 запросы, 398 строк в одной функции |
| КП Email | 8/10 | **8/10** = | По-прежнему лучший раздел |
| Shops | 7/10 | **6/10** ↓ | 195-строчный save, нет rate limiting |

### 7.6 Обновлённые приоритеты фаз

На основе deep-dive, обновлённый порядок фаз:

1. **Фаза 0 (НОВАЯ, 3-5 дней)**: Критические баг-фиксы
   - Duplicate check в home()
   - _close_followups_for_report баг-фикс
   - Пагинация в home()
   - Расширение reminder window (5 мин → 30 мин)

2. **Фаза 1**: Визуализация (2-3 недели) — как было, но Stats уже хороший

3. **Фаза 1.5 (НОВАЯ)**: Рефакторинг кода
   - views.py декомпозиция
   - DRY normalize_phone
   - Admin.py: регистрация всех 23 моделей
   - Rate limiting на API

---

## Deep Dive v3 — Молекулярный анализ реконструкции

### Анализ `home.html` — 967 строк монолитного шаблона

Полный breakdown:

| Секция | Строки | Описание |
|--------|--------|----------|
| Processing pane (clients table) | 1-125 | Таблица клиентов с date-groups |
| Lead base pane | 127-179 | Таблица лидов |
| Modal: Add Client | 182-279 | 14 полей, conditional fields |
| Modal: Add Lead | 281-351 | 12 полей |
| Modal: Process Lead | 353-450 | 14 полей |
| Inline JavaScript | 453-967 | **514 строк JS в `<script>`!** |

**Критические проблемы шаблона:**

1. **514 строк inline JS** — должно быть в отдельном `.js` файле
2. **3 модальных окна** — DRY violation: select options для `role`, `source`, `call_result` **скопированы 3 раза** (строки 214-253, 312-331, 385-423)
3. **Нет lazy loading** для lead-base-pane — оба пейна загружаются сразу
4. **XSS потенциал** в `buildClientRowHtml()` (строка 644) — строковая интерполяция `${client.shop}` без escaping
5. **Нет client-side validation** — только server-side
6. **Report countdown** (строка 20) — hardcoded "19:00" в HTML, не связан с `report_deadline_hour` из config

### DRY violation: Select options дублирование

Каждый select `role`, `source`, `call_result` повторяется 2-3 раза:

```html
<!-- Modal 1: Add Client (строки 214-253) -->
<select id="role" name="role">
    <option value="owner">Власник</option>
    <option value="supervisor">Управляючий</option>
    ...
</select>

<!-- Modal 3: Process Lead (строки 385-423) — ИДЕНТИЧНАЯ КОПИЯ! -->
<select id="process_role" name="role">
    <option value="owner">Власник</option>
    <option value="supervisor">Управляючий</option>
    ...
</select>
```

**Решение**: Template include или JavaScript-генерация из словаря.

### Models.py — Enum дублирование (130 строк waste)

`CommercialOfferEmailLog` дублирует 6 enum-классов из `CommercialOfferEmailSettings`:
- `CpMode` (2 опции × 2 = 4 строки waste)
- `CpSegmentMode` (2 × 2 = 4)
- `CpSubjectPreset` (4 × 2 = 8)
- `CpCtaType` (6 × 2 = 12)
- `PricingMode` (2 × 2 = 4)
- `OptTier` (5 × 2 = 10)

**Итого ~130 строк** дублированного кода в models.py.

### Обновлённый план реконструкции v3

```
Фаза 0:  Критические фиксы (1-2 дня)
  - Dedup check в home() POST
  - Исправить _close_followups_for_report
  - Вынести inline JS из home.html в home.js

Фаза 0.5: DRY cleanup (2-3 дня)
  - Enum consolidation в models.py (-130 строк)
  - Select options → template include или JS dict
  - normalize_phone() → utils.py

Фаза 1:  Component extraction (1 неделя)
  - home.html → base template + modal components
  - views.py → home_views, stats_views, admin_views, api_views
  - forms.py → unified validation layer

Фаза 2:  Frontend modernization (2-3 недели)
  - Alpine.js или htmx для reactivity
  - CSS design system
  - Mobile responsive layout

Фаза 3:  Performance (1 неделя)
  - Pagination для client list
  - Optimized queries (select_related)
  - Lazy loading для lead pane
```

> [!TIP]
> **Ключевой инсайт v3**: Ядро системы (stats_service.py) **не нуждается в реконструкции**. Фокус реконструкции — исключительно на presentation layer (views.py, templates, frontend).

---

## Обновление от владельца (новые требования к навигации)

> [!IMPORTANT]
> **Трёхвкладочная навигация** — обязательное требование к реконструкции сайта.

### Структура вкладок верхнего уровня

```
[Бренд 👔]  [DTF 🎨]  [Склад 🏭]

Бренд:   Главная | Статистика | Парсинг | ...  (текущий функционал)
DTF:     Заявки | Заказы | Семплы | Dashboard   (см. 06_DTF_INTEGRATION.md)
Склад:   (заглушка — модуль в разработке)       (см. 07_MANAGER_WORKFLOW.md §9)
```

### Система доступов

Доступ к вкладкам назначается администратором через `ManagerProfileExtras`:
- `can_access_brand` (default: True)
- `can_access_dtf` (default: False)
- `can_access_warehouse` (default: False)

Подробности: [07_MANAGER_WORKFLOW.md §10](./07_MANAGER_WORKFLOW.md)

### Связанные документы
- **[06_DTF_INTEGRATION.md](./06_DTF_INTEGRATION.md)** — DTF вкладка: модели, views, admin
- **[07_MANAGER_WORKFLOW.md](./07_MANAGER_WORKFLOW.md)** — Workflow + склад заглушка + навигация
- **[08_EFFICIENCY_SYSTEM.md](./08_EFFICIENCY_SYSTEM.md)** — HES вместо KPD (влияет на статистику в Бренд вкладке)
