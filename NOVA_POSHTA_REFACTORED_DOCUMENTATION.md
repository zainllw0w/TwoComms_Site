# 🚀 Nova Poshta Integration - Refactored & Improved

## 📋 Обзор изменений

Проведен полный рефакторинг интеграции с Nova Poshta API для автоматического отслеживания и обновления статусов посылок.

### Основные улучшения:

1. ✅ **Использование StatusCode** - приоритет StatusCode == 9 для определения получения посылки
2. ✅ **Proper Logging** - замена `print()` на структурированное логирование
3. ✅ **API Error Handling** - проверка поля `errors` в ответе API
4. ✅ **Retry Logic** - автоматические повторные попытки при сетевых ошибках
5. ✅ **Rate Limiting** - защита от превышения лимитов API
6. ✅ **Fallback Mechanism** - резервное обновление если cron не работает
7. ✅ **Fixed DropshipperOrder** - исправлен вызов несуществующего метода
8. ✅ **StatusCode Normalization** - нормализация StatusCode (может приходить как строка)

---

## 📁 Измененные файлы

### 1. `/twocomms/orders/nova_poshta_service.py`

**Что изменилось:**

#### A. Добавлены константы статусов
```python
# Коды статусов Nova Poshta (StatusCode)
STATUS_ACCEPTED = 1  # Прийнято
STATUS_SENT = 2  # Відправлено
STATUS_ARRIVED_CITY = 3  # Прибуло в місто
STATUS_ARRIVED_WAREHOUSE = 4  # Прибуло в відділення
STATUS_RECEIVED_OLD = 5  # Отримано (старый формат)
STATUS_REFUSED = 6  # Відмова
STATUS_SENT_ALT = 7  # Відправлено (альтернативный)
STATUS_UNKNOWN = 8  # Невідомо
STATUS_RECEIVED = 9  # Отримано одержувачем (ОСНОВНОЙ КОД ДЛЯ ПОЛУЧЕНИЯ)
STATUS_RETURNED = 10  # Повернено відправнику
STATUS_REFUSED_ALT = 11  # Відмова (альтернативный)
```

#### B. Добавлен rate limiting
```python
def _check_rate_limit(self):
    """Проверяет и применяет rate limiting для API запросов"""
    current_calls = cache.get(self.RATE_LIMIT_KEY, 0)
    
    if current_calls >= self.RATE_LIMIT_MAX_CALLS:
        logger.warning(f"Rate limit exceeded")
        return False
    
    cache.set(self.RATE_LIMIT_KEY, current_calls + 1, self.RATE_LIMIT_PERIOD)
    return True
```

#### C. Улучшен метод `get_tracking_info()`

**До:**
```python
data = response.json()

if data.get('success') and data.get('data'):
    return data['data'][0] if data['data'] else None
```

**После:**
```python
data = response.json()

# Проверяем наличие ошибок в ответе API
if data.get('errors') and len(data.get('errors', [])) > 0:
    errors = data.get('errors', [])
    error_msg = ', '.join(str(e) for e in errors)
    logger.error(f"Nova Poshta API errors for TTN {ttn_number}: {error_msg}")
    return None

# Проверяем успешность запроса
if not data.get('success'):
    logger.warning(f"API returned success=false for TTN {ttn_number}")
    return None

# Проверяем наличие данных
if not data.get('data'):
    logger.warning(f"No data in API response for TTN {ttn_number}")
    return None

# Обрабатываем данные (может быть массив или объект)
tracking_data = None
if isinstance(data['data'], list):
    if len(data['data']) == 0:
        logger.warning(f"Empty data array for TTN {ttn_number}")
        return None
    tracking_data = data['data'][0]
elif isinstance(data['data'], dict):
    tracking_data = data['data']
else:
    logger.error(f"Unexpected data type: {type(data['data'])}")
    return None
```

#### D. Добавлены повторные попытки при ошибках

```python
last_error = None
for attempt in range(self.MAX_RETRIES):
    try:
        response = requests.post(...)
        # обработка ответа
        return tracking_data
        
    except requests.exceptions.Timeout as e:
        last_error = e
        logger.warning(f"Timeout error (attempt {attempt + 1}/{self.MAX_RETRIES})")
        if attempt < self.MAX_RETRIES - 1:
            time.sleep(self.RETRY_DELAY * (attempt + 1))
            
    except requests.exceptions.RequestException as e:
        # обработка других ошибок сети
```

#### E. Использование StatusCode для определения получения

**До:**
```python
def _update_order_status_if_delivered(self, order, status, status_description):
    delivered_keywords = ['отримано', 'получено', ...]
    is_delivered = any(keyword in status_lower for keyword in delivered_keywords)
```

**После:**
```python
def _update_order_status_if_delivered(self, order, status, status_description, status_code=None):
    # МЕТОД 1: Проверка по коду статуса (НАДЕЖНО)
    is_delivered_by_code = status_code == self.STATUS_RECEIVED
    
    # МЕТОД 2: Проверка по ключевым словам (РЕЗЕРВНЫЙ)
    is_delivered_by_keywords = any(...)
    
    # Объединяем результаты (приоритет StatusCode)
    is_delivered = is_delivered_by_code or is_delivered_by_keywords
    
    logger.debug(
        f"Order {order.order_number} delivery check: "
        f"StatusCode={status_code}, is_delivered_by_code={is_delivered_by_code}, "
        f"is_delivered_by_keywords={is_delivered_by_keywords}"
    )
```

#### F. Улучшена обработка статусов

**Изменение:**
- Метод `update_order_tracking_status` теперь проверяет `if order.status != 'done'` перед изменением статуса
- Это позволяет избежать лишних обновлений уже завершенных заказов
- Сервис обрабатывает все заказы с ТТН, но пропускает обновление если статус уже 'done'

#### G. Добавлены методы для fallback механизма

```python
@staticmethod
def get_last_update_time():
    """Получает время последнего успешного обновления статусов"""
    return cache.get('nova_poshta_last_update')

@staticmethod
def should_trigger_fallback_update():
    """
    Проверяет нужно ли запустить резервное обновление
    
    Если с момента последнего обновления прошло больше 15 минут,
    возвращает True (значит cron не работает)
    """
    last_update = NovaPoshtaService.get_last_update_time()
    
    if last_update is None:
        return True
    
    time_since_update = timezone.now() - last_update
    threshold = timedelta(minutes=15)
    
    return time_since_update > threshold
```

#### H. Логирование вместо print()

**До:**
```python
print(f"Ошибка при получении статуса посылки {ttn_number}: {e}")
print(f"✅ Заказ {order.order_number}: статус изменен")
```

**После:**
```python
logger.error(f"Failed to get tracking info for TTN {ttn_number}: {e}")
logger.info(f"✅ Order {order.order_number}: status changed to 'done'")
```

---

### 2. `/twocomms/orders/models.py` (DropshipperOrder)

**Что исправлено:**

**До:**
```python
status_info = np_service.track_parcel(self.tracking_number)  # ❌ Метод не существует
```

**После:**
```python
status_info = np_service.get_tracking_info(self.tracking_number)  # ✅ Правильный метод
```

---

### 3. `/twocomms/orders/management/commands/update_tracking_statuses.py`

**Улучшения:**
- Добавлено структурированное логирование
- Добавлен флаг `--verbose` для детального вывода
- Улучшена обработка ошибок
- Добавлена статистика `processed` в дополнение к `updated` и `errors`

---

### 4. `/twocomms/orders/nova_poshta_middleware.py` (НОВЫЙ ФАЙЛ)

**Назначение:** Fallback механизм для обновления статусов если cron не работает

**Как работает:**

1. При каждом запросе проверяет время последнего обновления
2. Если прошло больше 15 минут → запускает обновление
3. Использует блокировку через кеш чтобы избежать дублирования
4. Обновление выполняется в фоновом потоке (не блокирует запрос)

**Два варианта middleware:**

#### A. `NovaPoshtaFallbackMiddleware` (рекомендуется)
- Запускает обновление в отдельном потоке
- Не блокирует текущий запрос
- Подходит для большинства серверов

#### B. `NovaPoshtaFallbackSimpleMiddleware` (для ограниченных серверов)
- Запускает обновление синхронно
- Только каждый N-й запрос (по умолчанию каждый 100-й)
- Для серверов без поддержки threading

**Настройки:**

```python
# В settings.py
NOVA_POSHTA_FALLBACK_ENABLED = True  # Включить/выключить
```

---

### 5. `/twocomms/twocomms/settings.py`

**Добавлено:**

```python
# Middleware для fallback обновления
MIDDLEWARE = [
    # ... другие middleware ...
    "orders.nova_poshta_middleware.NovaPoshtaFallbackMiddleware",  # Резервное обновление
]

# Настройки Nova Poshta
NOVA_POSHTA_API_KEY = os.environ.get('NOVA_POSHTA_API_KEY', '')
NOVA_POSHTA_API_URL = os.environ.get('NOVA_POSHTA_API_URL', 'https://api.novaposhta.ua/v2.0/json/')
NOVA_POSHTA_UPDATE_INTERVAL = _env_int('NOVA_POSHTA_UPDATE_INTERVAL', 5)
NOVA_POSHTA_FALLBACK_ENABLED = _env_bool('NOVA_POSHTA_FALLBACK_ENABLED', True)

# Логирование Nova Poshta
LOGGING = {
    'loggers': {
        'orders.nova_poshta_service': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'orders.nova_poshta_middleware': {
            'handlers': ['console', 'app_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

---

## 🔧 Как использовать

### 1. Ручное обновление статусов

```bash
# Обновить все заказы
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
python manage.py update_tracking_statuses

# Обновить конкретный заказ
python manage.py update_tracking_statuses --order-number TWC01012025N01

# Dry-run (показать что будет обновлено)
python manage.py update_tracking_statuses --dry-run

# Подробный вывод
python manage.py update_tracking_statuses --verbose
```

### 2. Cron Job (автоматическое обновление каждые 5 минут)

```bash
# Настроить cron
bash setup_nova_poshta_cron.sh

# Проверить cron задачи
crontab -l

# Просмотреть логи
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log
```

### 3. Fallback Middleware (резервное обновление)

Middleware автоматически активируется если:
- Прошло больше 15 минут с последнего обновления
- Cron job не сработал

**Включить/выключить:**

```bash
# В .env файле
NOVA_POSHTA_FALLBACK_ENABLED=True  # включить
NOVA_POSHTA_FALLBACK_ENABLED=False  # выключить
```

### 4. Проверка статуса интеграции

```python
# В Django shell
from orders.nova_poshta_service import NovaPoshtaService
from django.utils import timezone

# Проверить время последнего обновления
last_update = NovaPoshtaService.get_last_update_time()
if last_update:
    print(f"Last update: {last_update}")
    time_since = timezone.now() - last_update
    print(f"Time since last update: {time_since}")
else:
    print("No updates yet")

# Проверить нужно ли запустить fallback
if NovaPoshtaService.should_trigger_fallback_update():
    print("Fallback update needed!")
else:
    print("Updates are running normally")
```

---

## 📊 Структура логирования

### Уровни логирования:

- **DEBUG**: Детальная информация о каждом запросе API, проверке статуса
- **INFO**: Обновления статусов, успешные операции
- **WARNING**: Предупреждения API, ошибки получения данных
- **ERROR**: Ошибки API, сетевые ошибки
- **CRITICAL**: Критические ошибки интеграции

### Примеры логов:

```
[INFO] Starting update of all tracking statuses
[INFO] Found 15 orders with TTN to process
[INFO] Updating tracking status for order TWC01012025N01
[DEBUG] Requesting tracking info for TTN: 20450012345678
[DEBUG] API request attempt 1/3
[DEBUG] API response for TTN 20450012345678: {"success": true, "data": [...]}
[INFO] Tracking info for TTN 20450012345678: Status='Отримано', StatusCode=9
[INFO] Order TWC01012025N01: shipment_status changed from 'Відправлено' to 'Отримано одержувачем'
[DEBUG] Order TWC01012025N01 delivery check: StatusCode=9, is_delivered_by_code=True
[INFO] ✅ Order TWC01012025N01: status changed from 'ship' to 'done' (parcel received, StatusCode=9)
[INFO] 💰 Order TWC01012025N01: payment_status changed from 'unpaid' to 'paid'
[INFO] 📊 Facebook Purchase event sent for order TWC01012025N01
[INFO] Finished updating tracking statuses: 3/15 updated, 0 errors
```

---

## 🔍 Диагностика проблем

### Проблема: Статусы не обновляются

**Проверки:**

1. **API ключ настроен?**
   ```bash
   grep NOVA_POSHTA_API_KEY .env
   ```

2. **Cron job работает?**
   ```bash
   crontab -l | grep nova
   tail -f logs/nova_poshta_cron.log
   ```

3. **Fallback middleware активен?**
   ```bash
   grep NOVA_POSHTA_FALLBACK_ENABLED .env
   # Проверить логи Django
   tail -f django.log | grep nova_poshta
   ```

4. **API доступен?**
   ```bash
   curl -X POST https://api.novaposhta.ua/v2.0/json/ \
     -H "Content-Type: application/json" \
     -d '{"apiKey":"YOUR_KEY","modelName":"TrackingDocument","calledMethod":"getStatusDocuments"}'
   ```

### Проблема: Статус посылки обновляется, но статус заказа не меняется на 'done'

**Причины:**

1. StatusCode != 9 в ответе API
2. Текст статуса не содержит ключевых слов

**Решение:**
- Проверить логи на уровне DEBUG
- Убедиться что API возвращает StatusCode=9 для полученных посылок

```bash
python manage.py update_tracking_statuses --order-number TWC... --verbose
```

### Проблема: Rate limit exceeded

**Причина:** Слишком много запросов к API

**Решение:**
- Увеличить интервал cron (с 5 до 10 минут)
- Уменьшить лимит в коде (по умолчанию 60 запросов/минуту)

```python
# В nova_poshta_service.py
RATE_LIMIT_MAX_CALLS = 30  # Уменьшить если нужно
```

---

## 🎯 Рекомендации

### 1. Мониторинг

Настройте мониторинг времени последнего обновления:

```python
# Создайте Django management команду
from orders.nova_poshta_service import NovaPoshtaService
from django.utils import timezone

last_update = NovaPoshtaService.get_last_update_time()
if last_update:
    time_since = timezone.now() - last_update
    if time_since.total_seconds() > 1800:  # 30 минут
        # Отправить уведомление админу
        send_alert("Nova Poshta updates not running!")
```

### 2. Логи

Регулярно проверяйте логи на ошибки:

```bash
# Проверить ошибки за последние 24 часа
grep -i error logs/nova_poshta_cron.log | tail -100

# Проверить предупреждения
grep -i warning logs/nova_poshta_cron.log | tail -100
```

### 3. Тестирование

Периодически тестируйте интеграцию:

```bash
# Dry-run для проверки
python manage.py update_tracking_statuses --dry-run --verbose

# Тест конкретного заказа
python manage.py update_tracking_statuses --order-number TWC... --verbose
```

### 4. Обновление API ключа

API ключи Nova Poshta имеют срок действия 3 месяца. Настройте напоминание для обновления:

```bash
# Добавить в календарь напоминание каждые 3 месяца
# Получить новый ключ: https://my.novaposhta.ua/settings/index#apikeys
# Обновить в .env файле
```

---

## 📚 Полезные ссылки

- **Документация Nova Poshta API**: https://api.novapost.com/developers/index.html
- **Метод отслеживания**: https://api.novapost.com/developers/index.html#tracking
- **Статусы посылок**: https://api.novapost.com/developers/index.html#statuses
- **Личный кабинет Nova Poshta**: https://my.novaposhta.ua/

---

## ✅ Чек-лист после установки

- [ ] API ключ настроен в `.env`
- [ ] Cron job настроен (`bash setup_nova_poshta_cron.sh`)
- [ ] Fallback middleware добавлен в `MIDDLEWARE`
- [ ] Логирование настроено в `LOGGING`
- [ ] Проверен ручной запуск (`python manage.py update_tracking_statuses`)
- [ ] Проверены логи cron (`tail -f logs/nova_poshta_cron.log`)
- [ ] Настроен мониторинг времени последнего обновления
- [ ] Добавлено напоминание об обновлении API ключа

---

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте логи: `logs/nova_poshta_cron.log` и `django.log`
2. Запустите с флагом `--verbose` для детальной диагностики
3. Проверьте документацию Nova Poshta API
4. Убедитесь что API ключ актуален (не истек)

---

**Версия документации:** 1.0  
**Дата:** 2025-01-30  
**Статус:** ✅ Реализовано и протестировано
