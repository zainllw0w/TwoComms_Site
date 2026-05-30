# План реалізації: Система рівнів менеджерів

## Огляд

Реалізація багаторівневої системи менеджерів з 6 рівнями, KPI, виплатами, контролем доступу, профілем та адмін-панеллю для призначення ролей.

## Архітектура

### 1. Моделі даних (management/models.py)

#### 1.1 ManagerLevel - Поточний рівень менеджера
```python
class ManagerLevel(models.Model):
    class Level(models.TextChoices):
        CANDIDATE = 'candidate', 'Менеджер-кандидат'
        LEVEL_1 = 'level_1', 'Менеджер 1-го рівня'
        LEVEL_2 = 'level_2', 'Менеджер 2-го рівня'
        TOP_MANAGER = 'top_manager', 'Топ-менеджер'
        PROJECT_MANAGER = 'project_manager', 'Project-менеджер'
        ADMIN = 'admin', 'Адміністратор'
    
    user = OneToOneField(User, related_name='manager_level')
    level = CharField(choices=Level.choices)
    assigned_at = DateTimeField(auto_now_add=True)
    assigned_by = ForeignKey(User, related_name='assigned_levels')
    
    # Фінансові умови
    weekly_salary_uah = PositiveIntegerField(default=0)  # Тижнева ставка
    commission_percent = DecimalField(max_digits=6, decimal_places=2, default=0)
    salary_start_date = DateField()  # Дата початку нарахувань
    
    # Метадані
    assignment_comment = TextField(blank=True)
    is_active = BooleanField(default=True)
```

#### 1.2 ManagerLevelHistory - Історія змін рівнів
```python
class ManagerLevelHistory(models.Model):
    user = ForeignKey(User, related_name='level_history')
    old_level = CharField(choices=ManagerLevel.Level.choices, null=True)
    new_level = CharField(choices=ManagerLevel.Level.choices)
    changed_at = DateTimeField(auto_now_add=True)
    changed_by = ForeignKey(User, related_name='level_changes_made')
    
    old_weekly_salary = PositiveIntegerField(default=0)
    new_weekly_salary = PositiveIntegerField(default=0)
    old_commission_percent = DecimalField(max_digits=6, decimal_places=2, default=0)
    new_commission_percent = DecimalField(max_digits=6, decimal_places=2, default=0)
    
    reason = TextField(blank=True)
```

#### 1.3 WeeklySalaryAccrual - Тижневі нарахування ставки
```python
class WeeklySalaryAccrual(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Очікує'
        ACCRUED = 'accrued', 'Нараховано'
        CANCELLED = 'cancelled', 'Скасовано'
    
    user = ForeignKey(User, related_name='weekly_salary_accruals')
    week_start = DateField(db_index=True)
    week_end = DateField()
    
    # KPI метрики
    conversions_count = PositiveIntegerField(default=0)
    processed_clients_count = PositiveIntegerField(default=0)
    
    # Розрахунок ставки
    base_weekly_salary = DecimalField(max_digits=12, decimal_places=2)
    kpi_multiplier = DecimalField(max_digits=3, decimal_places=2)  # 0.0, 0.5, 1.0
    accrued_amount = DecimalField(max_digits=12, decimal_places=2)
    
    status = CharField(choices=Status.choices, default=Status.PENDING)
    frozen_until = DateTimeField()
    created_at = DateTimeField(auto_now_add=True)
```

#### 1.4 ManagerContract - Договори (доробка існуючої)
Додати поля:
- `manager_level` - FK до ManagerLevel
- `contract_status` - UNSIGNED / PENDING / SIGNED
- `signed_at` - DateTimeField

### 2. Сервіси (management/services/)

#### 2.1 manager_levels.py - Основна логіка рівнів

**Функції:**
- `get_current_level(user) -> ManagerLevel | None`
- `get_level_display_name(level: str) -> str`
- `get_level_permissions(level: str) -> dict`
- `check_promotion_eligibility(user) -> dict`
- `can_promote_to_level(user, target_level: str) -> tuple[bool, str]`
- `promote_manager(user, new_level, promoted_by, weekly_salary, commission_percent, start_date, comment) -> ManagerLevel`
- `demote_manager(user, reason, demoted_by) -> None`

**Права доступу по рівнях:**
```python
LEVEL_PERMISSIONS = {
    'candidate': {
        'can_view_payouts': False,
        'can_process_bases': False,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': False,
        'can_manage_managers': False,
    },
    'level_1': {
        'can_view_payouts': True,
        'can_process_bases': False,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': False,
        'can_manage_managers': False,
    },
    'level_2': {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': False,
        'can_approve_bases': False,
        'can_view_sensitive_data': True,
        'can_manage_managers': False,
    },
    'top_manager': {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': True,
        'can_approve_bases': True,
        'can_view_sensitive_data': True,
        'can_manage_managers': True,
    },
    'project_manager': {
        'can_view_payouts': True,
        'can_process_bases': True,
        'can_run_parsing': True,
        'can_approve_bases': True,
        'can_view_sensitive_data': True,
        'can_manage_managers': True,
        'can_view_system_settings': True,
    },
    'admin': {
        # Повний доступ
    }
}
```

#### 2.2 weekly_kpi.py - Тижневий KPI та ставка

**Функції:**
- `get_week_boundaries(date=None) -> tuple[date, date]`
- `get_user_week_start(user, date=None) -> date` - з урахуванням salary_start_date
- `calculate_weekly_conversions(user, week_start, week_end) -> int`
- `calculate_weekly_processed_clients(user, week_start, week_end) -> int`
- `calculate_kpi_multiplier(conversions: int) -> Decimal` - 0.0 / 0.5 / 1.0
- `calculate_weekly_salary(user, week_start, week_end) -> dict`
- `accrue_weekly_salary(user, week_start, week_end) -> WeeklySalaryAccrual`
- `get_current_week_kpi_status(user) -> dict`

**Логіка KPI множника:**
```python
def calculate_kpi_multiplier(conversions: int) -> Decimal:
    if conversions >= 2:
        return Decimal('1.0')  # 100%
    elif conversions == 1:
        return Decimal('0.5')  # 50%
    else:
        return Decimal('0.0')  # 0%
```

#### 2.3 level_progression.py - Прогрес до наступного рівня

**Функції:**
- `get_progression_status(user) -> dict`
- `get_next_level_requirements(current_level: str) -> dict`
- `check_auto_promotion_conditions(user) -> tuple[bool, str]`
- `get_unlocked_features(level: str) -> list[dict]`
- `get_locked_features(level: str) -> list[dict]`

**Умови переходу:**
```python
PROMOTION_CONDITIONS = {
    'candidate': {
        'next_level': 'level_1',
        'auto_check': True,
        'conditions': [
            {'type': 'conversions', 'min': 2, 'period': 'all_time'},
            {'type': 'or'},
            {'type': 'processed_clients', 'min': 100, 'period': 'all_time'},
        ],
        'description': '2 конверсії АБО 100 оброблених клієнтів'
    },
    'level_1': {
        'next_level': 'level_2',
        'auto_check': True,
        'conditions': [
            {'type': 'work_duration_days', 'min': 30},
            {'type': 'and'},
            [
                {'type': 'conversions', 'min': 4, 'period': 'all_time'},
                {'type': 'or'},
                {'type': 'processed_clients', 'min': 500, 'period': 'all_time'},
            ]
        ],
        'description': '1 місяць роботи І (4 конверсії АБО 500 оброблених)'
    },
    'level_2': {
        'next_level': 'top_manager',
        'auto_check': False,
        'description': 'Призначається адміністратором вручну'
    },
    'top_manager': {
        'next_level': 'project_manager',
        'auto_check': False,
        'description': 'Призначається адміністратором вручну'
    },
}
```

#### 2.4 Інтеграція з payouts.py

Доробити `get_manager_payout_summary()`:
- Додати weekly_salary_accruals до балансу
- Враховувати WeeklySalaryAccrual.accrued_amount

### 3. Views (management/views.py)

#### 3.1 Нові view функції

**Профіль менеджера:**
```python
@login_required(login_url='management_login')
def manager_profile(request):
    # Показує поточний рівень, прогрес, KPI, історію
```

**API для адміна:**
```python
@login_required(login_url='management_login')
@require_POST
def admin_assign_level_api(request):
    # Призначення рівня менеджеру
    # Доступ: is_staff
```

```python
@login_required(login_url='management_login')
def admin_managers_list_api(request):
    # Список всіх менеджерів з рівнями
    # Доступ: is_staff
```

**API для менеджера:**
```python
@login_required(login_url='management_login')
def manager_progression_api(request):
    # Поточний прогрес до наступного рівня
```

```python
@login_required(login_url='management_login')
def manager_weekly_kpi_api(request):
    # Поточний тижневий KPI статус
```

#### 3.2 Доробка існуючих views

**home()** - додати перевірку рівня для доступу до баз
**payouts()** - locked state для Candidate
**parsing()** - перевірка рівня Top+
**admin_overview()** - додати вкладку "Рівні менеджерів"

### 4. Middleware та декоратори

#### 4.1 Декоратори для перевірки рівня

```python
# management/decorators.py

def require_manager_level(min_level: str):
    """Декоратор для перевірки мінімального рівня менеджера"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not user_is_management(request.user):
                return redirect('management_login')
            
            user_level = get_current_level(request.user)
            if not user_level or not has_required_level(user_level.level, min_level):
                return JsonResponse({
                    'success': False,
                    'error': 'Недостатній рівень доступу'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

**Використання:**
```python
@require_manager_level('level_2')
def process_base_lead(request, lead_id):
    # Обробка ліда з бази
```

### 5. Шаблони (management/templates/management/)

#### 5.1 profile.html - Новий шаблон профілю

**Секції:**
1. Карточка поточного рівня
   - Назва рівня з бейджем
   - Дата призначення
   - Хто призначив
   
2. Фінансові умови (для Level 1+)
   - Тижнева ставка
   - Відсоток від замовлення
   - Дата початку нарахувань
   
3. Поточний тижневий KPI
   - Конверсії за тиждень (X/2)
   - Progress bar
   - Прогноз ставки (0% / 50% / 100%)
   
4. Прогрес до наступного рівня
   - Progress bar з відсотком
   - Список умов з галочками
   - Статус: "Виконується" / "Очікує рішення адміна"
   
5. Доступні функції
   - Список з іконками ✓
   
6. Заблоковані функції
   - Список з іконками 🔒
   - Tooltip з умовами розблокування
   
7. Історія підвищень
   - Таблиця з датами, рівнями, коментарями

#### 5.2 Доробка base.html

Додати вкладку "Профіль" у навігацію:
```html
<a href="{% url 'management_profile' %}" class="tab">Профіль</a>
```

Умовне відображення вкладок:
```html
{% if user_level.level != 'candidate' %}
<a href="{% url 'management_payouts' %}" class="tab">Виплати</a>
{% else %}
<a href="#" class="tab tab-locked" data-tooltip="Виплати доступні з рівня «Менеджер 1-го рівня»">
    Виплати 🔒
</a>
{% endif %}
```

#### 5.3 Доробка payouts.html

Для Candidate показувати locked state:
```html
{% if user_level.level == 'candidate' %}
<div class="locked-state">
    <div class="lock-icon">🔒</div>
    <h2>Виплати доступні з рівня «Менеджер 1-го рівня»</h2>
    <p>Виконайте умови переходу, щоб бачити свої нарахування та виплати.</p>
    <div class="progression-preview">
        <h3>Ваш прогрес:</h3>
        <!-- Progress bar -->
    </div>
</div>
{% else %}
<!-- Існуючий контент виплат -->
{% endif %}
```

#### 5.4 Доробка admin.html

Додати вкладку "Рівні менеджерів":
```html
<div class="tab-pane" id="levels">
    <h2>Управління рівнями менеджерів</h2>
    
    <table class="managers-table">
        <thead>
            <tr>
                <th>Менеджер</th>
                <th>Поточний рівень</th>
                <th>Дата призначення</th>
                <th>Ставка</th>
                <th>Відсоток</th>
                <th>Прогрес</th>
                <th>Дії</th>
            </tr>
        </thead>
        <tbody>
            <!-- Список менеджерів -->
        </tbody>
    </table>
    
    <!-- Модальне вікно призначення рівня -->
    <div class="modal" id="assignLevelModal">
        <form id="assignLevelForm">
            <select name="level">
                <option value="candidate">Менеджер-кандидат</option>
                <option value="level_1">Менеджер 1-го рівня</option>
                <option value="level_2">Менеджер 2-го рівня</option>
                <option value="top_manager">Топ-менеджер</option>
                <option value="project_manager">Project-менеджер</option>
                <option value="admin">Адміністратор</option>
            </select>
            
            <input type="number" name="weekly_salary" placeholder="Тижнева ставка (грн)">
            <input type="number" step="0.01" name="commission_percent" placeholder="Відсоток (%)">
            <input type="date" name="start_date" placeholder="Дата початку">
            <textarea name="comment" placeholder="Коментар (опціонально)"></textarea>
            
            <button type="submit">Призначити</button>
        </form>
    </div>
</div>
```

### 6. Міграції

#### 6.1 Створення нових моделей
```bash
python manage.py makemigrations management --name add_manager_levels
```

#### 6.2 Міграція даних
Створити data migration для існуючих менеджерів:
- Якщо `is_manager=True` → створити ManagerLevel з рівнем 'level_1'
- Перенести `manager_base_salary_uah` → `weekly_salary_uah`
- Перенести `manager_commission_percent` → `commission_percent`
- Перенести `manager_started_at` → `salary_start_date`

### 7. Уведомлення

#### 7.1 Telegram уведомлення

**Події для уведомлень:**
1. Досягнуто умов переходу на наступний рівень
2. Підвищено рівень
3. Не виконано тижневий KPI
4. Місяць без конверсій
5. Перевиконання KPI

**Функція відправки:**
```python
def send_level_notification(user, notification_type, **kwargs):
    # Використати існуючу _tg_send_message()
```

#### 7.2 In-app уведомлення

Доробити `get_reminders()` для додавання:
- Нагадування про умови переходу
- Статус тижневого KPI
- Рекомендації по покращенню

### 8. Celery задачі

#### 8.1 Щотижневе нарахування ставки

```python
# management/tasks.py

@shared_task
def accrue_weekly_salaries():
    """Нараховує тижневі ставки всім менеджерам Level 1+"""
    # Запускається щопонеділка о 00:01
    # Нараховує за попередній тиждень
```

#### 8.2 Перевірка умов автопідвищення

```python
@shared_task
def check_auto_promotions():
    """Перевіряє умови автоматичного підвищення для Candidate та Level 1"""
    # Запускається щодня о 01:00
```

### 9. Тестування

#### 9.1 Unit тести

**Тести для manager_levels.py:**
- `test_get_level_permissions()`
- `test_promote_manager()`
- `test_check_promotion_eligibility()`

**Тести для weekly_kpi.py:**
- `test_calculate_kpi_multiplier()`
- `test_calculate_weekly_salary()`
- `test_get_week_boundaries()`

**Тести для level_progression.py:**
- `test_check_auto_promotion_conditions()`
- `test_get_progression_status()`

#### 9.2 Integration тести

- Тест повного циклу: Candidate → Level 1 → Level 2
- Тест нарахування тижневої ставки з різними KPI
- Тест контролю доступу до баз/парсингу

### 10. Порядок реалізації

**Фаза 1: Моделі та міграції (2-3 дні)**
1. Створити моделі ManagerLevel, ManagerLevelHistory, WeeklySalaryAccrual
2. Створити міграції
3. Створити data migration для існуючих менеджерів

**Фаза 2: Сервіси (3-4 дні)**
1. Реалізувати manager_levels.py
2. Реалізувати weekly_kpi.py
3. Реалізувати level_progression.py
4. Інтегрувати з payouts.py

**Фаза 3: Views та API (2-3 дні)**
1. Створити manager_profile view
2. Створити admin API для призначення рівнів
3. Доробити існуючі views (home, payouts, parsing)
4. Створити декоратори для перевірки рівня

**Фаза 4: UI та шаблони (3-4 дні)**
1. Створити profile.html
2. Доробити base.html (навігація)
3. Доробити payouts.html (locked state)
4. Доробити admin.html (вкладка рівнів)
5. Додати CSS для progression UI

**Фаза 5: Уведомлення та задачі (1-2 дні)**
1. Реалізувати Telegram уведомлення
2. Створити Celery задачі
3. Налаштувати розклад

**Фаза 6: Тестування (2-3 дні)**
1. Написати unit тести
2. Написати integration тести
3. Мануальне тестування всіх сценаріїв

**Загальний час: 13-19 днів**

### 11. Ризики та обмеження

**Ризики:**
1. Складність міграції даних для існуючих менеджерів
2. Конфлікти з існуючою системою виплат
3. Проблеми з тижневими межами для менеджерів, призначених не з понеділка

**Обмеження:**
1. Автопідвищення тільки для Candidate → Level 1 та Level 1 → Level 2
2. Вищі рівні призначаються тільки вручну адміном
3. Договори поки що заглушка без реального ЕЦП

**Мітігація:**
1. Детальне тестування міграцій на копії БД
2. Поступове впровадження з feature flag
3. Документація для адміністраторів

### 12. Майбутні покращення

1. Автоматичне генерування договорів
2. Інтеграція з ЕЦП для підписання
3. Розширена аналітика по менеджерах
4. Система бонусів за перевиконання KPI
5. Gamification елементи (досягнення, бейджі)
6. Експорт звітів по виплатах
7. Мобільний додаток для менеджерів

---

## Висновок

План передбачає повну реалізацію системи рівнів менеджерів з дотриманням існуючої архітектури проекту, переиспользуванням існуючих компонентів та мінімізацією технічного боргу. Всі зміни будуть зворотньо сумісними та не зламають існуючий функціонал.
