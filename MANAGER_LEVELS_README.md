# Система рівнів менеджерів - Швидкий старт

## Що це?

Багаторівнева система менеджерів з 6 рівнями, автоматичним розрахунком KPI, тижневими виплатами та контролем доступу.

## Швидкий старт

### 1. Запустити міграції

```bash
cd /Users/zainllw0w/TwoComms/site/twocomms
python manage.py migrate management
```

Це створить таблиці та автоматично мігрує всіх існуючих менеджерів на рівень "Менеджер 1-го рівня".

### 2. Перевірити роботу

Увійти в management-субдомен та перейти на `/profile/` - має відобразитись профіль з рівнем.

### 3. Призначити рівень менеджеру (через Django shell)

```python
python manage.py shell

from django.contrib.auth import get_user_model
from management.services.manager_levels import promote_manager
from decimal import Decimal
from datetime import date

User = get_user_model()

# Знайти користувача
user = User.objects.get(username='manager_username')

# Призначити рівень
promote_manager(
    user=user,
    new_level='level_1',  # candidate, level_1, level_2, top_manager, project_manager, admin
    promoted_by=User.objects.get(is_staff=True).first(),
    weekly_salary=5000,  # грн/тиждень
    commission_percent=Decimal('5.5'),  # %
    start_date=date.today(),
    comment='Призначення рівня'
)
```

### 4. Перевірити API

```bash
# Прогрес до наступного рівня
curl -X GET http://management.twocomms.shop/api/levels/progression/ \
  -H "Cookie: sessionid=YOUR_SESSION"

# Поточний тижневий KPI
curl -X GET http://management.twocomms.shop/api/levels/weekly-kpi/ \
  -H "Cookie: sessionid=YOUR_SESSION"
```

## Рівні менеджерів

1. **Candidate** - стартовий рівень, без виплат
2. **Level 1** - з виплатами та KPI
3. **Level 2** - + обробка баз
4. **Top Manager** - + парсинг та контроль
5. **Project Manager** - + системні налаштування
6. **Admin** - повний доступ

## Тижневий KPI

- **2+ конверсії** = 100% ставки
- **1 конверсія** = 50% ставки
- **0 конверсій** = 0% ставки

Конверсія = замовлення (ORDER) або тестова партія (TEST_BATCH)

## Файли

- `management/models.py` - моделі
- `management/services/manager_levels.py` - логіка рівнів
- `management/services/weekly_kpi.py` - розрахунок KPI
- `management/views_levels.py` - views
- `management/templates/management/profile.html` - шаблон профілю

## Документація

- `MANAGER_LEVELS_DEPLOYMENT.md` - повна інструкція
- `MANAGER_LEVELS_IMPLEMENTATION_STATUS.md` - статус реалізації
- `.claude/plans/manager-levels-system.md` - архітектурний план
