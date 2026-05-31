# 🎯 План реалізації покращень фінансової системи fin.twocomms.shop

**Дата:** 2026-05-31  
**Автор:** Claude Opus 4.8 (максимальна глибина аналізу)  
**Статус:** Готовий до виконання

---

## 📊 Аналіз поточного стану

### ✅ Що вже працює добре:
- Модель Transaction з полем `is_business` для розділення бізнес/особисте
- Система планових платежів (`status='planned'`)
- Календар з прогнозом балансу на 30 днів
- Інтеграція з warehouse через `warehouse_link.py`
- Monobank синхронізація з `reconcile_internal_transfers`
- Темна тема з консистентною дизайн-системою (fin-* namespace)
- Звіти: Cash Flow, P&L, Дебіторка/Кредиторка, Проекти, Метрики

### ⚠️ Проблеми для вирішення:
1. **Дублювання переказів ФОП→картка** — `reconcile_internal_transfers` працює тільки при точному збігу сум
2. **Відсутність категорії "Вивід на особисте"** — такі перекази рахуються як витрата бізнесу
3. **Немає розхідних матеріалів** — пакети, фарба, клей не відстежуються
4. **Немає автогенерації recurring транзакцій** — RecurrenceRule визначена, але не використовується
5. **Фільтри на ПК** — все в один flex-ряд, незручно
6. **Немає детальної аналітики складу** — динаміка, оборотність, мертвий запас

---

## 🎯 Блоки реалізації (пріоритизовано)

### БЛОК 1: Виправлення дублювання переказів + Owner's Drawings ⚡ КРИТИЧНИЙ

**Проблема:**  
Вивід з ФОП на особисту картку імпортується як дві операції (витрата + дохід), що завищує дохід. Існуючий `reconcile_internal_transfers` працює тільки при точному збігу сум (без комісії).

**Рішення:**

1. **Покращити `reconcile_internal_transfers` у `mono.py`:**
   ```python
   # Додати толерантність по сумі (±2% для комісії)
   # Розширити вікно пошуку з 72 до 168 годин
   # Шукати за counter_iban/counter_name з external_data
   # Не вимагати щоб обидва рахунки були моно
   ```

2. **Створити системну категорію "Вивід на особисте" (Owner's Drawings):**
   - Тип: `both` (може бути на доходах і витратах)
   - `is_system=True` (не можна видалити)
   - Автоматично призначається при злитті внутрішніх переказів
   - Не впливає на бізнес-прибуток (виключається з P&L)

3. **Додати метрику "Виведено власником" в аналітику:**
   - Окрема карточка в дашборді
   - Фільтр по періодах
   - Порівняння з прибутком (% виведення)

**Файли для зміни:**
- `finance/services/mono.py` — функція `reconcile_internal_transfers`
- `finance/migrations/000X_owner_drawings_category.py` — створення категорії
- `finance/views/analytics.py` — нова метрика
- `finance/templates/finance/payments.html` — відображення

**Тести:**
- `finance/tests_mono.py` — тест злиття з комісією
- `finance/tests_reports.py` — тест виключення з P&L

**Час:** ~3-4 години  
**Git commit:** `feat(finance): покращено злиття переказів + Owner's Drawings`

---

### БЛОК 2: Бізнес vs Особисті витрати — детальна аналітика 📊 ВИСОКИЙ

**Мета:**  
Розділити всі транзакції на бізнес/особисті з детальною аналітикою "куди йдуть гроші".

**Рішення:**

1. **Покращити UI для перемикання `is_business`:**
   - Bulk-операція "→ Бізнес" / "→ Особисті" (вже є в `payments.html`)
   - Іконка-індикатор на кожній транзакції (💼 бізнес / 👤 особисте)
   - Швидкий фільтр у панелі (вже є: scope=business/personal)

2. **Створити звіт "Особисті витрати":**
   ```python
   # finance/services/reports.py
   def personal_expenses_report(company, params):
       # Тільки is_business=False, type=expense
       # Групування по категоріях
       # Відсоток від загального доходу
       # Порівняння по місяцях (тренд)
       # Топ-5 категорій
   ```

3. **Розширити дашборд:**
   - Карточка "Бізнес-прибуток" (тільки is_business=True)
   - Карточка "Особисті витрати" (is_business=False)
   - Співвідношення у відсотках
   - Графік динаміки по місяцях

4. **Створити категорії для особистих витрат:**
   - Їжа та продукти
   - Транспорт
   - Розваги
   - Здоров'я
   - Одяг
   - Комунальні послуги
   - Інше особисте

**Файли:**
- `finance/services/reports.py` — функція `personal_expenses_report`
- `finance/views/analytics.py` — view `report(kind='personal_expenses')`
- `finance/templates/finance/reports/personal_expenses.html` — шаблон
- `finance/migrations/000X_personal_categories.py` — категорії

**Час:** ~4-5 годин  
**Git commit:** `feat(finance): детальна аналітика особистих витрат`

---

### БЛОК 3: Регулярні платежі — автогенерація + прогноз 📅 ВИСОКИЙ

**Мета:**  
Автоматично створювати планові транзакції на основі RecurrenceRule та покращити прогноз балансу.

**Рішення:**

1. **Розширити модель `RecurrenceRule`:**
   ```python
   next_occurrence = DateField(null=True)  # Дата наступного спрацювання
   auto_create = BooleanField(default=True)  # Автоматично створювати
   notification_days_before = PositiveIntegerField(default=3)  # Нагадування
   last_generated_at = DateTimeField(null=True)  # Коли останній раз генерували
   ```

2. **Створити сервіс генерації:**
   ```python
   # finance/services/recurring.py
   def generate_planned_transactions(recurrence_rule, from_date, to_date):
       # Розгортає правило у конкретні дати
       # Створює планові транзакції
       # Оновлює next_occurrence
       
   def spawn_next_occurrence(recurrence_rule):
       # Створює одну наступну транзакцію
       # Використовується management командою
   ```

3. **Management команда:**
   ```python
   # finance/management/commands/finance_generate_recurring.py
   # Запускається щодня через cron
   # Генерує планові транзакції на 60 днів вперед
   # Надсилає нагадування за N днів
   ```

4. **Створити довідник "Постійні витрати":**
   - UI для створення recurring правил
   - Шаблони: Оренда (щомісяця), Домен (щороку), Хостинг (кожні 6 міс)
   - Прив'язка до проєктів
   - Розбивка річних витрат на місяці

5. **Покращити звіт "Прогноз балансу":**
   ```python
   # finance/services/reports.py
   def balance_forecast_report(company, months=6):
       # Поточний баланс
       # По кожному місяцю:
       #   - Заплановані надходження
       #   - Заплановані витрати (включно з recurring)
       #   - Прогнозований баланс на кінець місяця
       #   - Попередження якщо < 0
   ```

**Файли:**
- `finance/models_txn.py` — розширення RecurrenceRule
- `finance/migrations/000X_recurring_improvements.py`
- `finance/services/recurring.py` — нова логіка
- `finance/management/commands/finance_generate_recurring.py`
- `finance/views/analytics.py` — звіт forecast
- `finance/templates/finance/reports/forecast.html`

**Cron:**
```bash
# Додати в /home/qlknpodo/crontab
0 6 * * * /home/qlknpodo/recurring_generate.sh >> /home/qlknpodo/recurring.log 2>&1
```

**Час:** ~6-7 годин  
**Git commit:** `feat(finance): автогенерація recurring платежів + прогноз балансу`

---

### БЛОК 4: Розширений склад — розхідні матеріали 📦 ВИСОКИЙ

**Мета:**  
Відстежувати розхідники (пакети, фарба, клей, плівка) з автоматичним списанням при продажу.

**Рішення:**

1. **Створити модель `ConsumableItem` у warehouse:**
   ```python
   class ConsumableItem(models.Model):
       CATEGORY_CHOICES = [
           ('ink', 'Фарба для принтера'),
           ('glue', 'Клей'),
           ('film', 'Плівка (рулони)'),
           ('tags', 'Брендовані бірки'),
           ('patches', 'Шеврони'),
           ('bags_small', 'Пакети малі'),
           ('bags_medium', 'Пакети середні'),
           ('bags_large', 'Пакети великі'),
           ('bags_branded', 'Брендовані пакети'),
           ('cleaner', 'Очисна рідина'),
           ('other', 'Інше'),
       ]
       category = CharField(max_length=32, choices=CATEGORY_CHOICES)
       name = CharField(max_length=255)  # "Фарба чорна Epson T6641"
       quantity = DecimalField(max_digits=10, decimal_places=2)  # Дробова для рідин
       unit = CharField(max_length=16)  # "шт", "мл", "м", "кг"
       cost_per_unit = DecimalField(max_digits=10, decimal_places=2)
       total_cost = DecimalField(max_digits=10, decimal_places=2)  # quantity × cost_per_unit
       supplier = ForeignKey('finance.Counterparty', null=True)
       purchase_date = DateField()
       min_stock_alert = DecimalField(max_digits=10, decimal_places=2, default=0)
       notes = TextField(blank=True)
       created_at = DateTimeField(auto_now_add=True)
       updated_at = DateTimeField(auto_now=True)
   ```

2. **Розширити `StockMovement` для розхідників:**
   ```python
   # Вже є поліморфізм через ContentType
   # Додати MovementReason.CONSUMABLE_USE
   # ConsumableItem буде content_object
   ```

3. **Додати в `WriteOffRequest` поле `packaging_used`:**
   ```python
   packaging_used = JSONField(default=dict)  # {"bags_branded": 1, "tags": 2}
   ```

4. **Автоматичне списання при продажу:**
   - При створенні WriteOffRequest показувати чекбокс "Використано брендоване пакування"
   - Якщо так — автоматично списувати з ConsumableItem
   - Створювати StockMovement з reason=CONSUMABLE_USE

5. **UI для управління розхідниками:**
   - `/warehouse/consumables/` — список всіх розхідників
   - Фільтри: категорія, низькі залишки
   - Додавання нових надходжень
   - Ручне списання
   - Сповіщення про низькі залишки

6. **Інтеграція з фінансами:**
   ```python
   # finance/services/warehouse_link.py
   def frozen_in_warehouse():
       # Додати ConsumableItem.objects.aggregate(...)
       
   def warehouse_breakdown():
       # Додати 'consumables_value', 'consumables_qty'
   ```

**Файли:**
- `warehouse/models.py` — модель ConsumableItem
- `warehouse/migrations/000X_consumables.py`
- `warehouse/views/consumables.py` — CRUD
- `warehouse/templates/warehouse/consumables.html`
- `warehouse/services/inventory.py` — adjust_consumable
- `finance/services/warehouse_link.py` — включити розхідники

**Час:** ~5-6 годин  
**Git commit:** `feat(warehouse): розхідні матеріали з автосписанням`

---

### БЛОК 5: Аналітика складу — динаміка та оборотність 📊 СЕРЕДНІЙ

**Мета:**  
Детальна аналітика руху та вартості складу для прийняття рішень про закупівлі.

**Рішення:**

1. **Звіт "Динаміка складу":**
   ```python
   # finance/services/warehouse_analytics.py
   def warehouse_dynamics(days=90):
       # Графік вартості складу по днях
       # Додано товарів (сума)
       # Продано товарів (сума)
       # Списано товарів (сума)
       # Поточна вартість
       # Використовує StockMovement
   ```

2. **Звіт "Структура складу":**
   ```python
   def warehouse_structure():
       # Топ-10 категорій за вартістю
       # Топ-10 товарів за вартістю
       # Розхідники за категоріями
       # Відсоток від загального капіталу
       # Pie chart розподілу
   ```

3. **Звіт "Оборотність складу":**
   ```python
   def warehouse_turnover():
       # Товари без руху > 90 днів (мертвий запас)
       # Середній час на складі
       # Швидкість обороту по категоріях
       # Рекомендації щодо закупівель
       # ABC-аналіз (20% товарів = 80% обороту)
   ```

4. **Інтеграція з фінансами:**
   - При кліку на "Заморожено у складі" відкривається детальний звіт
   - Зв'язок StockMovement ↔ Transaction (закупівля/продаж)
   - Автоматичне створення транзакції при закупівлі товару

5. **Візуалізація:**
   - Графіки Chart.js з анімацією
   - Heatmap для оборотності
   - Таблиці з сортуванням

**Файли:**
- `finance/services/warehouse_analytics.py` — нова логіка
- `finance/views/analytics.py` — views для звітів
- `finance/templates/finance/reports/warehouse_dynamics.html`
- `finance/templates/finance/reports/warehouse_structure.html`
- `finance/templates/finance/reports/warehouse_turnover.html`

**Час:** ~4-5 годин  
**Git commit:** `feat(finance): детальна аналітика складу`

---

### БЛОК 6: Покращення UI/UX — фільтри та анімації 🎨 СЕРЕДНІЙ

**Мета:**  
Зробити інтерфейс більш естетичним, плавним та зручним.

**Рішення:**

1. **Переверстати панель фільтрів на ПК:**
   ```css
   .fin-filters__row {
       display: grid;
       grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
       gap: 12px;
   }
   ```
   - Групувати фільтри логічно
   - Кнопка "Скинути фільтри"
   - Зберігати стан у localStorage

2. **Додати анімації:**
   ```css
   @keyframes fadeInUp {
       from { opacity: 0; transform: translateY(20px); }
       to { opacity: 1; transform: translateY(0); }
   }
   
   .fin-row {
       animation: fadeInUp 0.3s ease-out;
       animation-fill-mode: both;
   }
   
   .fin-row:nth-child(1) { animation-delay: 0.05s; }
   .fin-row:nth-child(2) { animation-delay: 0.1s; }
   /* ... */
   ```

3. **Skeleton loaders:**
   ```html
   <div class="fin-skeleton">
       <div class="fin-skeleton__line"></div>
       <div class="fin-skeleton__line"></div>
   </div>
   ```

4. **Hover-ефекти:**
   ```css
   .fin-report-card:hover {
       transform: translateY(-4px);
       box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
   }
   ```

5. **Анімація чисел (countUp.js):**
   ```javascript
   // Для великих сум у карточках
   new CountUp('fin-total-balance', targetValue, {
       duration: 1.5,
       separator: ' ',
       decimal: ',',
   }).start();
   ```

6. **Прогрес-бари з анімацією:**
   ```css
   .fin-progress-bar {
       animation: fillProgress 1s ease-out;
   }
   ```

**Файли:**
- `finance/templates/finance/partials/filters.html` — нова панель
- `finance/static/finance/css/animations.css` — анімації
- `finance/static/finance/js/ui-enhancements.js` — інтерактивність
- `finance/templates/finance/base.html` — підключення

**Час:** ~3-4 години  
**Git commit:** `feat(finance): покращення UI/UX з анімаціями`

---

### БЛОК 7: Інтеграція та фінальні штрихи 🔗 НИЗЬКИЙ

**Мета:**  
Зв'язати всі частини системи воєдино.

**Рішення:**

1. **Єдиний дашборд "Фінансове здоров'я":**
   - Поточний баланс (всі рахунки)
   - Прогноз на 3 місяці
   - Бізнес-прибуток за місяць
   - Особисті витрати за місяць
   - Заморожено у складі (з деталізацією)
   - Найближчі регулярні платежі
   - Попередження та рекомендації

2. **AI-інсайти:**
   - Аналіз трендів витрат
   - Рекомендації щодо оптимізації
   - Виявлення аномалій
   - Прогноз майбутніх витрат

3. **Експорт та звіти:**
   - PDF-звіти для всіх розділів
   - Автоматична розсилка щомісячних звітів

4. **Нотифікації:**
   - Push про низькі залишки розхідників
   - Нагадування про майбутні платежі
   - Сповіщення про великі витрати

**Файли:**
- `finance/views/dashboard.py` — новий дашборд
- `finance/templates/finance/dashboard.html`
- `finance/services/ai_advisor.py` — розширення
- `finance/services/notifications.py` — нова логіка

**Час:** ~4-5 годин  
**Git commit:** `feat(finance): єдиний дашборд фінансового здоров'я`

---

## 🚀 Процес виконання

### Для кожного блоку:

1. ✅ **Створити/оновити моделі** + міграції
2. ✅ **Реалізувати бізнес-логіку** (services)
3. ✅ **Створити/оновити views**
4. ✅ **Створити/оновити templates**
5. ✅ **Додати CSS/JS** для UI
6. ✅ **Тестування локально**
7. ✅ **Git commit** з описовим повідомленням
8. ✅ **Git push**
9. ✅ **Deploy** на fin.twocomms.shop
10. ✅ **Перевірка** на продакшені

### Deploy команда:
```bash
./deploy_finance.sh
# Або вручну через SSH:
# ssh qlknpodo@195.191.24.169
# cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
# source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
# git fetch origin main && git reset --hard origin/main
# python manage.py makemigrations --merge --noinput
# python manage.py migrate finance
# python manage.py migrate warehouse
# python manage.py collectstatic --noinput
# touch tmp/restart.txt
```

---

## 📐 Технічні принципи

1. **Чистота коду**: Дотримуватись існуючих патернів проєкту
2. **Безпека**: Всі зміни через `@db_transaction.atomic`, аудит-лог
3. **Продуктивність**: Індекси на нові поля, `select_related`/`prefetch_related`
4. **Тестування**: Покрити новий функціонал тестами
5. **Міграції**: Безпечні міграції з можливістю rollback
6. **UI/UX**: Мобільна адаптація обов'язкова
7. **Документація**: Docstrings у стилі проєкту

---

## 📊 Оцінка часу

| Блок | Пріоритет | Час | Статус |
|------|-----------|-----|--------|
| 1. Виправлення переказів + Owner's Drawings | ⚡ Критичний | 3-4 год | 🔜 Наступний |
| 2. Бізнес vs Особисті витрати | 📊 Високий | 4-5 год | ⏳ Очікує |
| 3. Регулярні платежі + прогноз | 📅 Високий | 6-7 год | ⏳ Очікує |
| 4. Розширений склад з розхідниками | 📦 Високий | 5-6 год | ⏳ Очікує |
| 5. Аналітика складу | 📊 Середній | 4-5 год | ⏳ Очікує |
| 6. Покращення UI/UX | 🎨 Середній | 3-4 год | ⏳ Очікує |
| 7. Інтеграція та фінальні штрихи | 🔗 Низький | 4-5 год | ⏳ Очікує |
| **ВСЬОГО** | | **29-36 год** | |

---

## 🎯 Наступні кроки

1. ✅ Підтвердження плану користувачем
2. 🔜 Початок реалізації БЛОКУ 1
3. ⏳ Послідовне виконання блоків 2-7

---

**Статус:** 📋 План затверджено, готовий до виконання  
**Наступна дія:** Почати з БЛОКУ 1 (виправлення дублювання переказів)
