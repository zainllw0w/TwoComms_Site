# Інструкція з розгортання системи рівнів менеджерів

## Огляд

Система багаторівневих менеджерів з 6 рівнями, KPI, виплатами, контролем доступу та профілем.

## Що реалізовано

### 1. Моделі даних
- ✅ `ManagerLevel` - поточний рівень менеджера
- ✅ `ManagerLevelHistory` - історія змін рівнів
- ✅ `WeeklySalaryAccrual` - тижневі нарахування ставки

### 2. Сервіси
- ✅ `manager_levels.py` - основна логіка рівнів
- ✅ `weekly_kpi.py` - тижневий KPI та ставка
- ✅ `level_progression.py` - прогрес до наступного рівня

### 3. Views та API
- ✅ `manager_profile` - профіль менеджера
- ✅ `manager_progression_api` - API прогресу
- ✅ `manager_weekly_kpi_api` - API тижневого KPI
- ✅ `admin_assign_level_api` - API призначення рівня
- ✅ `admin_managers_list_api` - API списку менеджерів

### 4. Шаблони
- ✅ `profile.html` - профіль менеджера з прогресією

### 5. Міграції
- ✅ `0034_add_manager_levels.py` - створення моделей
- ✅ `0035_migrate_existing_managers.py` - міграція існуючих менеджерів

### 6. Celery задачі
- ✅ `accrue_weekly_salaries` - нарахування тижневих ставок
- ✅ `check_auto_promotions` - перевірка умов підвищення

## Кроки розгортання

### Крок 1: Встановлення залежностей

Всі необхідні залежності вже є в проекті (Django, Celery, Redis).

### Крок 2: Запуск міграцій

```bash
cd /Users/zainllw0w/TwoComms/site/twocomms
python manage.py migrate management
```

Це створить нові таблиці та мігрує існуючих менеджерів на рівень `level_1`.

### Крок 3: Налаштування Celery Beat

Додати в `settings.py` або `celeryconfig.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'accrue-weekly-salaries': {
        'task': 'management.tasks.accrue_weekly_salaries',
        'schedule': crontab(hour=0, minute=1, day_of_week=1),  # Понеділок 00:01
    },
    'check-auto-promotions': {
        'task': 'management.tasks.check_auto_promotions',
        'schedule': crontab(hour=1, minute=0),  # Щодня о 01:00
    },
}
```

### Крок 4: Перезапуск сервісів

```bash
# Перезапустити Django
sudo systemctl restart twocomms

# Перезапустити Celery worker
sudo systemctl restart celery-worker

# Перезапустити Celery beat
sudo systemctl restart celery-beat
```

### Крок 5: Перевірка

1. Увійти в management-субдомен як менеджер
2. Перейти на `/profile/` - має відобразитись профіль з рівнем
3. Перевірити API endpoints:
   - `/api/levels/progression/`
   - `/api/levels/weekly-kpi/`

## Використання

### Для адміністратора

#### Призначення рівня менеджеру

```javascript
// POST /admin-panel/levels/assign/
{
    "user_id": 123,
    "level": "level_1",
    "weekly_salary": 5000,
    "commission_percent": "5.5",
    "start_date": "2026-05-30",
    "comment": "Підвищення за результатами роботи"
}
```

#### Отримання списку менеджерів

```javascript
// GET /admin-panel/levels/list/
{
    "success": true,
    "managers": [
        {
            "id": 123,
            "username": "manager1",
            "level": "level_1",
            "level_display": "Менеджер 1-го рівня",
            "weekly_salary": 5000,
            "commission_percent": "5.5",
            "progress_pct": 75,
            "requirements_met": false
        }
    ]
}
```

### Для менеджера

#### Перегляд профілю

Перейти на `/profile/` - відобразиться:
- Поточний рівень
- Фінансові умови (ставка, відсоток)
- Тижневий KPI
- Прогрес до наступного рівня
- Доступні/заблоковані функції
- Історія підвищень

#### API прогресу

```javascript
// GET /api/levels/progression/
{
    "success": true,
    "progression": {
        "current_level": "candidate",
        "next_level": "level_1",
        "requirements_met": false,
        "progress_pct": 50,
        "description": "2 конверсії АБО 100 оброблених клієнтів",
        "conditions": [...]
    }
}
```

#### API тижневого KPI

```javascript
// GET /api/levels/weekly-kpi/
{
    "success": true,
    "kpi": {
        "week_start": "2026-05-26",
        "week_end": "2026-06-01",
        "conversions": 1,
        "conversions_target": 2,
        "conversions_progress_pct": 50,
        "processed_clients": 45,
        "kpi_multiplier": "0.5",
        "projected_salary": "2500.00",
        "base_salary": "5000.00",
        "kpi_status": "poor",
        "days_remaining": 2
    }
}
```

## Рівні та права доступу

### Candidate (Менеджер-кандидат)
- ✅ Додавання клієнтів
- ✅ Обробка клієнтів
- ✅ Статистика
- ❌ Виплати
- ❌ Обробка баз
- ❌ Парсинг

**Умови переходу на Level 1:**
- 2 конверсії АБО 100 оброблених клієнтів

### Level 1 (Менеджер 1-го рівня)
- ✅ Всі функції Candidate
- ✅ Виплати
- ✅ Тижнева ставка (з KPI)
- ✅ Відсоток від замовлення
- ❌ Обробка баз
- ❌ Парсинг

**Умови переходу на Level 2:**
- 1 місяць роботи І (4 конверсії АБО 500 оброблених)

### Level 2 (Менеджер 2-го рівня)
- ✅ Всі функції Level 1
- ✅ Обробка одобрених баз
- ✅ Доступ до чутливих даних
- ❌ Парсинг
- ❌ Одобрення баз

**Підвищення:** Вручну адміністратором

### Top Manager (Топ-менеджер)
- ✅ Всі функції Level 2
- ✅ Парсинг
- ✅ Одобрення/відхилення баз
- ✅ Контроль менеджерів 1-2 рівня

**Підвищення:** Вручну адміністратором

### Project Manager
- ✅ Всі функції Top Manager
- ✅ Контроль топ-менеджерів
- ✅ Системні налаштування

**Підвищення:** Вручну адміністратором

### Admin (Адміністратор)
- ✅ Повний доступ до всього

## Логіка тижневої ставки

### Розрахунок KPI множника

```python
if conversions >= 2:
    multiplier = 1.0  # 100% ставки
elif conversions == 1:
    multiplier = 0.5  # 50% ставки
else:
    multiplier = 0.0  # 0% ставки
```

### Приклад

- Базова ставка: 5000 грн/тиждень
- Конверсій за тиждень: 1
- KPI множник: 0.5
- **Нараховано: 2500 грн**

### Заморожування

Нарахування заморожені на 7 днів після кінця тижня для можливості корекції.

## Що потрібно доробити

### 1. UI для адміна
- [ ] Вкладка "Рівні менеджерів" в admin.html
- [ ] Форма призначення рівня
- [ ] Таблиця менеджерів з рівнями

### 2. Доробка існуючих views
- [ ] `payouts()` - locked state для Candidate
- [ ] `parsing_dashboard()` - перевірка рівня Top+
- [ ] `home()` - перевірка рівня для доступу до баз

### 3. Навігація
- [ ] Додати вкладку "Профіль" в base.html
- [ ] Умовне відображення вкладок по рівнях

### 4. Уведомлення
- [ ] Telegram уведомлення про підвищення
- [ ] Уведомлення про виконання умов
- [ ] Уведомлення про невиконання KPI

### 5. Інтеграція з виплатами
- [ ] Додати WeeklySalaryAccrual до `get_manager_payout_summary()`
- [ ] Відображення тижневих нарахувань в payouts.html

### 6. Тести
- [ ] Unit тести для сервісів
- [ ] Integration тести для views
- [ ] Тести міграцій

## Troubleshooting

### Проблема: Міграції не застосовуються

```bash
# Перевірити статус міграцій
python manage.py showmigrations management

# Застосувати конкретну міграцію
python manage.py migrate management 0034
python manage.py migrate management 0035
```

### Проблема: Celery задачі не запускаються

```bash
# Перевірити статус Celery
celery -A twocomms inspect active

# Перевірити розклад Beat
celery -A twocomms inspect scheduled

# Перезапустити Celery
sudo systemctl restart celery-worker celery-beat
```

### Проблема: Користувач не бачить профіль

1. Перевірити, чи є `is_manager=True` в UserProfile
2. Перевірити, чи створено ManagerLevel
3. Перевірити логи Django

```bash
tail -f /var/log/twocomms/django.log
```

## Контакти

При виникненні проблем звертайтесь до розробника або адміністратора системи.
