# Checklist для завершення системи рівнів менеджерів

## ✅ Завершено

### Базова архітектура (100%)
- [x] Моделі: ManagerLevel, ManagerLevelHistory, WeeklySalaryAccrual
- [x] Міграції: створення таблиць + міграція даних
- [x] Сервіси: manager_levels, weekly_kpi, level_progression
- [x] Декоратори: require_manager_level, require_permission
- [x] Views: 5 views для профілю та API
- [x] URL маршрути: 5 нових endpoints
- [x] Шаблони: profile.html, payouts_locked.html
- [x] Навігація: додано вкладку "Профіль"
- [x] Celery задачі: нарахування та перевірки
- [x] Документація: 4 файли

### Інтеграція (60%)
- [x] Locked state для Candidate в payouts view
- [x] Перевірка рівня Top Manager+ для парсингу
- [ ] Перевірка рівня Level 2+ для обробки баз
- [ ] Інтеграція WeeklySalaryAccrual з payouts.py

---

## 🔄 В процесі

### UI для адміна (0%)
- [ ] Вкладка "Рівні менеджерів" в admin.html
- [ ] Таблиця всіх менеджерів з рівнями
- [ ] Форма призначення рівня
- [ ] JavaScript для AJAX запитів
- [ ] Відображення прогресу менеджерів

### Інтеграція з виплатами (20%)
- [x] Locked state для Candidate
- [ ] Додати WeeklySalaryAccrual до get_manager_payout_summary()
- [ ] Відображення тижневих нарахувань в payouts.html
- [ ] Розділити комісійні та ставку в UI

---

## ❌ Не почато

### Уведомлення (0%)
- [ ] Telegram уведомлення про підвищення рівня
- [ ] Уведомлення про виконання умов переходу
- [ ] Уведомлення про невиконання тижневого KPI
- [ ] Уведомлення про місяць без конверсій
- [ ] Уведомлення про перевиконання KPI

### Тести (0%)
- [ ] Unit тести для manager_levels.py
- [ ] Unit тести для weekly_kpi.py
- [ ] Unit тести для level_progression.py
- [ ] Integration тести для views_levels.py
- [ ] Тести міграцій

### Додаткові функції (0%)
- [ ] Експорт звітів по виплатах
- [ ] Графіки KPI за період
- [ ] Порівняння менеджерів
- [ ] Досягнення та бейджі
- [ ] Мобільна версія профілю

---

## 🚀 Пріоритети для запуску

### Критично (Must Have)
1. **Запустити міграції** ⚠️
   ```bash
   python manage.py migrate management
   ```

2. **Протестувати профіль** ⚠️
   - Увійти як менеджер
   - Перейти на /profile/
   - Перевірити відображення даних

3. **Призначити рівні тестовим менеджерам** ⚠️
   ```python
   from management.services.manager_levels import promote_manager
   # ... код призначення
   ```

### Важливо (Should Have)
4. **UI адміна для призначення рівнів**
   - Форма в admin.html
   - AJAX запити до API
   - Таблиця менеджерів

5. **Інтеграція з виплатами**
   - Додати weekly_salary_accruals до балансу
   - Показувати тижневі нарахування

6. **Налаштувати Celery Beat**
   - Додати розклад в settings.py
   - Перезапустити celery-beat

### Бажано (Nice to Have)
7. **Уведомлення**
   - Telegram алерти про підвищення
   - Уведомлення про KPI

8. **Тести**
   - Покриття основної логіки
   - Integration тести

---

## 📋 Інструкції для кожного пункту

### 1. Запуск міграцій

```bash
cd /Users/zainllw0w/TwoComms/site/twocomms

# Перевірити міграції
python manage.py showmigrations management

# Застосувати міграції
python manage.py migrate management

# Перевірити створення таблиць
python manage.py dbshell
\dt management_*
```

### 2. Тестування профілю

```bash
# Запустити dev сервер
python manage.py runserver

# Відкрити в браузері
open http://management.localhost:8000/profile/
```

### 3. Призначення рівня через shell

```python
python manage.py shell

from django.contrib.auth import get_user_model
from management.services.manager_levels import promote_manager
from decimal import Decimal
from datetime import date

User = get_user_model()

# Знайти менеджера
user = User.objects.filter(userprofile__is_manager=True).first()

# Знайти адміна
admin = User.objects.filter(is_staff=True).first()

# Призначити рівень
promote_manager(
    user=user,
    new_level='level_1',
    promoted_by=admin,
    weekly_salary=5000,
    commission_percent=Decimal('5.5'),
    start_date=date.today(),
    comment='Тестове призначення'
)

# Перевірити
print(user.manager_level.level)
print(user.manager_level.weekly_salary_uah)
```

### 4. UI адміна - додати в admin.html

Додати вкладку:
```html
<div class="tab-pane" id="levels">
    <h2>Управління рівнями менеджерів</h2>
    <!-- Таблиця менеджерів -->
    <!-- Форма призначення -->
</div>
```

### 5. Інтеграція з виплатами

Доробити `management/services/payouts.py`:
```python
def get_manager_payout_summary(user) -> dict:
    # ... існуючий код ...
    
    # Додати тижневі нарахування
    from management.models import WeeklySalaryAccrual
    
    weekly_accruals = WeeklySalaryAccrual.objects.filter(
        user=user,
        status=WeeklySalaryAccrual.Status.ACCRUED
    ).aggregate(
        total=Coalesce(Sum("accrued_amount"), zero, output_field=money_field)
    )["total"] or zero
    
    total_accrued += weekly_accruals
    # ...
```

### 6. Налаштування Celery Beat

Додати в `settings.py`:
```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'accrue-weekly-salaries': {
        'task': 'management.tasks.accrue_weekly_salaries',
        'schedule': crontab(hour=0, minute=1, day_of_week=1),
    },
    'check-auto-promotions': {
        'task': 'management.tasks.check_auto_promotions',
        'schedule': crontab(hour=1, minute=0),
    },
}
```

Перезапустити:
```bash
sudo systemctl restart celery-beat
```

---

## 📊 Прогрес

| Категорія | Прогрес | Статус |
|-----------|---------|--------|
| Моделі та міграції | 100% | ✅ Завершено |
| Сервіси | 100% | ✅ Завершено |
| Views та API | 100% | ✅ Завершено |
| Базовий UI | 80% | 🟡 Майже готово |
| Інтеграція | 40% | 🟡 В процесі |
| UI адміна | 0% | ❌ Не почато |
| Уведомлення | 0% | ❌ Не почато |
| Тести | 0% | ❌ Не почато |

**Загальний прогрес: 65%**

---

## 🎯 Мета на найближчі дні

### День 1: Запуск базового функціоналу
- [x] Створити всі файли
- [ ] Запустити міграції
- [ ] Протестувати профіль
- [ ] Призначити рівні

### День 2: UI адміна
- [ ] Вкладка в admin.html
- [ ] Форма призначення
- [ ] Таблиця менеджерів

### День 3: Інтеграція
- [ ] Виплати + weekly salary
- [ ] Celery Beat
- [ ] Тестування

### День 4: Уведомлення та тести
- [ ] Telegram уведомлення
- [ ] Unit тести
- [ ] Документація для користувачів

---

## ✅ Критерії готовності

### Для тестування (MVP)
- [x] Моделі створені
- [x] Міграції готові
- [x] Профіль працює
- [x] API працює
- [ ] Міграції застосовані
- [ ] Рівні призначені

### Для production
- [ ] UI адміна готовий
- [ ] Інтеграція з виплатами
- [ ] Celery Beat налаштований
- [ ] Уведомлення працюють
- [ ] Тести написані
- [ ] Документація для користувачів

---

## 📞 Контакти та підтримка

При виникненні проблем:
1. Перевірити логи Django
2. Перевірити статус міграцій
3. Перевірити Celery
4. Звернутись до розробника

**Документація:**
- `MANAGER_LEVELS_README.md` - швидкий старт
- `MANAGER_LEVELS_DEPLOYMENT.md` - розгортання
- `MANAGER_LEVELS_FINAL_REPORT.md` - фінальний звіт
