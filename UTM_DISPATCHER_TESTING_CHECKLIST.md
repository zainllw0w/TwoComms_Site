# ✅ Чек-лист тестирования "Диспетчер" (UTM Analytics)

**Дата:** 2025-01-30  
**Версия:** 1.0  
**Назначение:** Проверка работоспособности всех компонентов UTM-аналитики

---

## 🔍 Pre-Deploy тестирование

### 1. Проверка файлов

#### 1.1 Модели
```bash
# Проверяем что файлы существуют и компилируются
cd /home/engine/project/twocomms
python -c "from storefront.models import UTMSession, UserAction; print('Models OK')"
python -c "from orders.models import Order; print('Order OK')"
```

- [ ] `storefront/models.py` содержит UTMSession
- [ ] `storefront/models.py` содержит UserAction
- [ ] `orders/models.py` содержит UTM поля
- [ ] Нет синтаксических ошибок

#### 1.2 Middleware
```bash
python -c "from storefront.utm_middleware import UTMTrackingMiddleware; print('Middleware OK')"
```

- [ ] `storefront/utm_middleware.py` существует
- [ ] Нет синтаксических ошибок
- [ ] Импорты работают

#### 1.3 Утилиты
```bash
python -c "from storefront.utm_utils import get_client_ip, parse_user_agent; print('Utils OK')"
python -c "from storefront.utm_tracking import record_user_action; print('Tracking OK')"
python -c "from storefront.utm_analytics import get_general_stats; print('Analytics OK')"
```

- [ ] `utm_utils.py` работает
- [ ] `utm_tracking.py` работает
- [ ] `utm_analytics.py` работает

#### 1.4 Views
```bash
python -c "from storefront.views.admin import _build_dispatcher_context; print('Admin View OK')"
```

- [ ] `_build_dispatcher_context` существует в admin.py

#### 1.5 Шаблоны
```bash
ls -la twocomms_django_theme/templates/partials/admin_dispatcher_section.html
```

- [ ] Шаблон `admin_dispatcher_section.html` существует

---

## 🚀 Post-Deploy тестирование

### 2. Проверка миграций

```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate

# Проверяем статус миграций
python manage.py showmigrations storefront | grep "0033"
python manage.py showmigrations orders | grep "0037"

# Должны быть отмечены [X]
```

- [ ] Миграция `storefront/0033` применена
- [ ] Миграция `orders/0037` применена
- [ ] Нет ошибок при применении

### 3. Проверка таблиц БД

```bash
python manage.py dbshell
```

```sql
-- Проверяем что таблицы созданы
SHOW TABLES LIKE 'storefront_utmsession';
SHOW TABLES LIKE 'storefront_useraction';

-- Проверяем структуру UTMSession
DESCRIBE storefront_utmsession;

-- Проверяем структуру UserAction
DESCRIBE storefront_useraction;

-- Проверяем что Order расширен
DESCRIBE orders_order;
-- Должны быть поля: utm_session_id, utm_source, utm_medium, utm_campaign, utm_content, utm_term

-- Проверяем индексы
SHOW INDEX FROM storefront_utmsession;

EXIT;
```

- [ ] Таблица `storefront_utmsession` существует
- [ ] Таблица `storefront_useraction` существует
- [ ] Таблица `orders_order` содержит UTM поля
- [ ] Индексы созданы

### 4. Проверка middleware

```bash
# В Django shell
python manage.py shell
```

```python
from django.test import RequestFactory
from storefront.utm_middleware import UTMTrackingMiddleware

# Создаем тестовый request с UTM
factory = RequestFactory()
request = factory.get('/?utm_source=test&utm_medium=cpc&utm_campaign=test_campaign&fbclid=test123')

# Создаем фейковую сессию
from django.contrib.sessions.backends.db import SessionStore
request.session = SessionStore()
request.session.create()

# Применяем middleware
middleware = UTMTrackingMiddleware(lambda r: None)
middleware.process_request(request)

# Проверяем что UTM сохранились в сессию
print("UTM Data:", request.session.get('utm_data'))
print("Platform Data:", request.session.get('platform_data'))

# Проверяем что UTMSession создалась
from storefront.models import UTMSession
session_key = request.session.session_key
utm_session = UTMSession.objects.filter(session_key=session_key).first()
print("UTM Session created:", utm_session is not None)
if utm_session:
    print("UTM Source:", utm_session.utm_source)
    print("UTM Medium:", utm_session.utm_medium)
    print("UTM Campaign:", utm_session.utm_campaign)
    print("FBCLID:", utm_session.fbclid)

exit()
```

- [ ] Middleware успешно захватывает UTM
- [ ] UTM сохраняются в session
- [ ] UTMSession создается в БД
- [ ] Платформенные ID захватываются

### 5. Проверка функций tracking

```bash
python manage.py shell
```

```python
from django.test import RequestFactory
from django.contrib.auth.models import User
from storefront.utm_tracking import record_add_to_cart, record_initiate_checkout
from storefront.models import UTMSession, UserAction

# Создаем тестовый request
factory = RequestFactory()
request = factory.get('/')

# Создаем сессию
from django.contrib.sessions.backends.db import SessionStore
request.session = SessionStore()
request.session.create()

# Создаем UTMSession
utm_session = UTMSession.objects.create(
    session_key=request.session.session_key,
    utm_source='test',
    utm_medium='cpc',
    utm_campaign='test_campaign'
)

# Тестируем record_add_to_cart
record_add_to_cart(request, product_id=1, product_name='Test Product', cart_value=100.0)

# Проверяем что действие записалось
actions = UserAction.objects.filter(utm_session=utm_session, action_type='add_to_cart')
print("Add to cart recorded:", actions.exists())

# Тестируем record_initiate_checkout
record_initiate_checkout(request, cart_value=200.0)

# Проверяем
checkout_actions = UserAction.objects.filter(utm_session=utm_session, action_type='initiate_checkout')
print("Initiate checkout recorded:", checkout_actions.exists())

exit()
```

- [ ] `record_add_to_cart` работает
- [ ] `record_initiate_checkout` работает
- [ ] Действия сохраняются в БД
- [ ] Баллы рассчитываются правильно

### 6. Проверка аналитики

```bash
python manage.py shell
```

```python
from storefront.utm_analytics import (
    get_general_stats,
    get_sources_stats,
    get_campaigns_stats,
    get_funnel_stats
)

# Общая статистика
stats = get_general_stats('all_time')
print("General Stats:", stats)

# По источникам
sources = get_sources_stats('all_time')
print("Sources Stats:", sources)

# По кампаниям
campaigns = get_campaigns_stats('all_time')
print("Campaigns Stats:", campaigns)

# Воронка
funnel = get_funnel_stats('all_time')
print("Funnel Stats:", funnel)

exit()
```

- [ ] `get_general_stats` возвращает данные
- [ ] `get_sources_stats` работает
- [ ] `get_campaigns_stats` работает
- [ ] `get_funnel_stats` работает
- [ ] Нет ошибок при расчете метрик

---

## 🌐 Тестирование в браузере

### 7. Проверка админ-панели

**URL:** `https://twocomms.shop/admin-panel?section=dispatcher`

#### 7.1 Доступность
- [ ] Секция "Диспетчер" появилась в навигации
- [ ] Кнопка "Диспетчер" кликабельна
- [ ] При клике открывается страница с аналитикой
- [ ] Нет ошибок 500/404

#### 7.2 UI элементы
- [ ] Заголовок "Диспетчер UTM-аналітики" отображается
- [ ] Фильтр периодов работает (4 кнопки)
- [ ] Карточки общей статистики отображаются (4 штуки)
- [ ] Воронка конверсий отображается (6 этапов)
- [ ] Таблица источников отображается
- [ ] Таблица кампаний отображается
- [ ] Блок устройств отображается
- [ ] Блок географии отображается
- [ ] Таблица последних сессий отображается

#### 7.3 Данные
- [ ] Метрики отображают корректные числа
- [ ] CR% рассчитывается правильно
- [ ] Доход в гривнах
- [ ] Даты в правильном формате
- [ ] Нет "undefined" или "null"

#### 7.4 Интерактивность
- [ ] Клик по периоду переключает данные
- [ ] Hover на таблицы работает (фон меняется)
- [ ] Hover на карточки работает (поднимаются)
- [ ] Нет лагов при переключении

### 8. Тестирование захвата UTM

#### 8.1 Создание тестовой UTM-сессии

1. Откройте в браузере:
```
https://twocomms.shop/?utm_source=facebook&utm_medium=cpc&utm_campaign=test_campaign&utm_content=ad123&fbclid=test_fbclid_123
```

2. Проверьте в БД:
```bash
python manage.py shell
```

```python
from storefront.models import UTMSession

# Ищем последнюю сессию
last_session = UTMSession.objects.order_by('-first_seen').first()
print("Last session:")
print(f"  Source: {last_session.utm_source}")
print(f"  Medium: {last_session.utm_medium}")
print(f"  Campaign: {last_session.utm_campaign}")
print(f"  Content: {last_session.utm_content}")
print(f"  FBCLID: {last_session.fbclid}")
print(f"  IP: {last_session.ip_address}")
print(f"  Device: {last_session.device_type}")
print(f"  City: {last_session.city}")
print(f"  Country: {last_session.country_name}")

exit()
```

- [ ] UTMSession создалась
- [ ] UTM-параметры сохранились корректно
- [ ] FBCLID захватился
- [ ] IP определился
- [ ] Device type определился
- [ ] Геолокация определилась (если настроена GeoIP2)

#### 8.2 Тестирование действий

1. Добавьте товар в корзину (с той же сессии)
2. Проверьте в БД:

```python
from storefront.models import UserAction, UTMSession

# Последняя сессия
last_session = UTMSession.objects.order_by('-first_seen').first()

# Действия этой сессии
actions = UserAction.objects.filter(utm_session=last_session)
print(f"Actions count: {actions.count()}")
for action in actions:
    print(f"  {action.action_type} - {action.timestamp}")

exit()
```

- [ ] Действие `add_to_cart` записалось
- [ ] utm_session связан правильно
- [ ] product_id и product_name заполнены
- [ ] cart_value указан
- [ ] Баллы начислены

#### 8.3 Тестирование создания заказа

1. Оформите заказ (с той же сессии)
2. Проверьте в БД:

```python
from orders.models import Order
from storefront.models import UTMSession

# Последний заказ
last_order = Order.objects.order_by('-created').first()

print(f"Order: {last_order.order_number}")
print(f"  UTM Source: {last_order.utm_source}")
print(f"  UTM Medium: {last_order.utm_medium}")
print(f"  UTM Campaign: {last_order.utm_campaign}")
print(f"  UTM Session ID: {last_order.utm_session_id}")

# Проверяем связь
if last_order.utm_session:
    print(f"  Linked to session: {last_order.utm_session.utm_string}")

# Проверяем что UTMSession отмечена как конверсия
utm_session = last_order.utm_session
if utm_session:
    print(f"  Is converted: {utm_session.is_converted}")
    print(f"  Conversion type: {utm_session.conversion_type}")

exit()
```

- [ ] Order связан с UTMSession
- [ ] UTM-параметры скопировались в Order
- [ ] UTMSession отмечена как конверсионная
- [ ] conversion_type правильный (lead/purchase)

---

## 📊 Проверка аналитики в админке

### 9. Проверка метрик

После создания тестовых данных (несколько визитов с разными UTM):

1. Откройте: `https://twocomms.shop/admin-panel?section=dispatcher&period=all_time`

#### 9.1 Общая статистика
- [ ] Всего сессий > 0
- [ ] Уникальные посетители показаны
- [ ] Конверсии показаны (если были заказы)
- [ ] CR% рассчитан корректно
- [ ] Доход показан (если были оплаты)
- [ ] Средний чек рассчитан

#### 9.2 Воронка конверсий
- [ ] Всего сессий = количество UTMSession
- [ ] Просмотры товаров показаны (если были)
- [ ] В корзину показаны (если были)
- [ ] Оформление показано (если было)
- [ ] Лиды показаны (если были)
- [ ] Покупки показаны (если были)
- [ ] Проценты рассчитаны правильно

#### 9.3 Таблица источников
- [ ] Показаны все источники (facebook, google, etc.)
- [ ] Сессии подсчитаны правильно
- [ ] Конверсии подсчитаны правильно
- [ ] CR% рассчитан
- [ ] Доход показан
- [ ] Средний чек рассчитан

#### 9.4 Таблица кампаний
- [ ] Показаны все кампании
- [ ] Группировка по источникам работает
- [ ] Метрики правильные

#### 9.5 Устройства и география
- [ ] Desktop/Mobile/Tablet показаны
- [ ] Проценты рассчитаны
- [ ] Страны показаны
- [ ] Progress bars работают

#### 9.6 Последние сессии
- [ ] Показаны последние 30 сессий
- [ ] Даты правильные
- [ ] Источники правильные
- [ ] Локация показана
- [ ] Конверсии отмечены

### 10. Проверка фильтров

#### 10.1 Фильтр по периодам
- [ ] Клик на "Сьогодні" - показывает только сегодняшние
- [ ] Клик на "Тиждень" - показывает за последние 7 дней
- [ ] Клик на "Місяць" - показывает за последние 30 дней
- [ ] Клик на "Весь час" - показывает все данные

---

## 🐛 Тестирование граничных случаев

### 11. Edge Cases

#### 11.1 Без UTM
1. Откройте: `https://twocomms.shop/` (без UTM)
2. Проверьте:
- [ ] Сайт работает нормально
- [ ] Нет ошибок в консоли
- [ ] Middleware не ломает запрос

#### 11.2 Неполные UTM
1. Откройте: `https://twocomms.shop/?utm_source=test` (только source)
2. Проверьте:
- [ ] UTMSession создается
- [ ] utm_source заполнен
- [ ] utm_medium = null (нормально)
- [ ] utm_campaign = null (нормально)

#### 11.3 Некорректные UTM
1. Откройте: `https://twocomms.shop/?utm_source=test%20test&utm_campaign=<script>alert(1)</script>`
2. Проверьте:
- [ ] XSS не выполняется
- [ ] Данные санитизированы
- [ ] В БД сохранились безопасные значения

#### 11.4 Очень длинные UTM
1. Откройте с utm_source длиной 500+ символов
2. Проверьте:
- [ ] Данные обрезаются до 255 символов
- [ ] Нет ошибок БД

#### 11.5 Повторные визиты
1. Откройте с UTM
2. Закройте и откройте снова (без UTM)
3. Проверьте:
- [ ] UTM сохранились в сессии
- [ ] visit_count увеличился
- [ ] is_returning_visitor = True

#### 11.6 Регистрация
1. Зарегистрируйте нового пользователя (с UTM-сессией)
2. Проверьте:
- [ ] user_registered = True
- [ ] user_registered_at заполнен

---

## 📈 Performance тестирование

### 12. Производительность

#### 12.1 Время загрузки админки
```bash
# Измеряем время загрузки
curl -w "@-" -o /dev/null -s https://twocomms.shop/admin-panel?section=dispatcher <<'EOF'
time_namelookup:  %{time_namelookup}\n
time_connect:  %{time_connect}\n
time_appconnect:  %{time_appconnect}\n
time_pretransfer:  %{time_pretransfer}\n
time_redirect:  %{time_redirect}\n
time_starttransfer:  %{time_starttransfer}\n
time_total:  %{time_total}\n
EOF
```

- [ ] time_total < 2 секунды
- [ ] Нет тайм-аутов

#### 12.2 Запросы к БД
```bash
python manage.py shell
```

```python
from django.db import connection
from django.test.utils import override_settings

# Включаем debug для подсчета запросов
from django.conf import settings
settings.DEBUG = True

from storefront.utm_analytics import get_general_stats

# Замеряем количество запросов
from django.test.utils import CaptureQueriesContext
with CaptureQueriesContext(connection) as context:
    stats = get_general_stats('all_time')
    print(f"Queries count: {len(context.captured_queries)}")

exit()
```

- [ ] Количество запросов < 20 (оптимально < 10)
- [ ] Нет N+1 проблем

---

## ✅ Финальный чек-лист

### Критические проверки:

- [ ] Миграции применены без ошибок
- [ ] Middleware работает и захватывает UTM
- [ ] Действия пользователей записываются
- [ ] Заказы связываются с UTM
- [ ] Админка показывает корректные данные
- [ ] Нет ошибок 500 в логах
- [ ] Нет ошибок JS в консоли браузера
- [ ] Производительность приемлемая

### Некритические:

- [ ] GeoIP2 настроен (опционально)
- [ ] Кэширование настроено (опционально)
- [ ] Экспорт в CSV добавлен (опционально)
- [ ] Chart.js графики добавлены (опционально)

---

## 📝 Отчет о тестировании

После завершения тестирования заполните:

**Дата тестирования:** _________________  
**Протестировано:** ________ из ________ пунктов  
**Критические ошибки:** _____ (список ниже)  
**Некритические ошибки:** _____ (список ниже)  

**Критические ошибки:**
1. _________________________________
2. _________________________________

**Некритические ошибки:**
1. _________________________________
2. _________________________________

**Статус:** 
- [ ] ✅ Готово к production
- [ ] ⚠️ Требуются исправления
- [ ] ❌ Не готово

**Подпись:** _________________

---

**Успешного тестирования! 🚀**
