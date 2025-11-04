# 🚀 Рекомендации по внедрению новых возможностей Nova Poshta API

**Дата создания:** 2025-01-30  
**Версия:** 1.0  
**Цель:** Рекомендации по расширению функциональности интеграции с Nova Poshta API

---

## 📋 Содержание

1. [Приоритетные улучшения](#приоритетные-улучшения)
2. [Расширенная функциональность](#расширенная-функциональность)
3. [Оптимизация и производительность](#оптимизация-и-производительность)
4. [Мониторинг и алертинг](#мониторинг-и-алертинг)
5. [План внедрения](#план-внедрения)

---

## 🔴 Приоритетные улучшения

### 1. Исправление текущих проблем (КРИТИЧНО)

#### 1.1. Использование StatusCode для определения доставки
**Проблема:** Текущий код определяет "получено" только по тексту, что ненадежно.

**Решение:**
```python
def _update_order_status_if_delivered(self, order, status, status_description, status_code=None):
    # Проверка по коду статуса (надежнее)
    is_delivered_by_code = status_code == 9
    
    # Проверка по ключевым словам (резервный вариант)
    is_delivered_by_keywords = any(...)
    
    is_delivered = is_delivered_by_code or is_delivered_by_keywords
```

**Приоритет:** 🔴 КРИТИЧНО  
**Время:** 1-2 часа  
**Сложность:** Низкая

#### 1.2. Обработка ошибок API
**Проблема:** Игнорируются ошибки API в поле `errors`.

**Решение:**
```python
if data.get('errors') and len(data.get('errors', [])) > 0:
    error_msg = ', '.join(data.get('errors', []))
    logger.error(f"API errors: {error_msg}")
    return None
```

**Приоритет:** 🔴 КРИТИЧНО  
**Время:** 1 час  
**Сложность:** Низкая

#### 1.3. Добавление логирования
**Проблема:** Нет логирования для отладки.

**Решение:**
- Использовать стандартный `logging` модуль Python
- Логировать все запросы и ответы API
- Логировать изменения статусов
- Логировать ошибки

**Приоритет:** 🟡 ВАЖНО  
**Время:** 2-3 часа  
**Сложность:** Низкая

#### 1.4. Исправление метода track_parcel
**Проблема:** В `DropshipperOrder` используется несуществующий метод.

**Решение:**
```python
# Было:
status_info = np_service.track_parcel(self.tracking_number)

# Должно быть:
status_info = np_service.get_tracking_info(self.tracking_number)
```

**Приоритет:** 🟡 ВАЖНО  
**Время:** 15 минут  
**Сложность:** Очень низкая

---

## 🟢 Расширенная функциональность

### 2. Получение городов и отделений (Address API)

#### 2.1. Получение списка городов
**Зачем:** Для выбора города при оформлении заказа.

**Метод API:** `Address.getCities`

**Реализация:**
```python
def get_cities(self, search_string=None, limit=100):
    """
    Получает список городов Nova Poshta
    
    Args:
        search_string (str): Поисковый запрос (название города)
        limit (int): Максимальное количество результатов
        
    Returns:
        list: Список городов с полями:
        - Ref (идентификатор города)
        - Description (название города)
        - DescriptionRu (название на русском)
        - Area (область)
    """
    payload = {
        "apiKey": self.api_key,
        "modelName": "Address",
        "calledMethod": "getCities",
        "methodProperties": {
            "FindByString": search_string or "",
            "Limit": limit
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        return data['data']
    return []
```

**Кеширование:**
- Список городов редко меняется
- Можно кешировать на 24-48 часов
- Использовать Django cache или Redis

**Приоритет:** 🟡 ВАЖНО  
**Время:** 4-6 часов  
**Сложность:** Средняя

#### 2.2. Получение отделений в городе
**Зачем:** Для выбора отделения при оформлении заказа.

**Метод API:** `Address.getWarehouses`

**Реализация:**
```python
def get_warehouses(self, city_ref, warehouse_type=None):
    """
    Получает список отделений в городе
    
    Args:
        city_ref (str): Ref города (из get_cities)
        warehouse_type (str, optional): Тип отделения
        
    Returns:
        list: Список отделений с полями:
        - Ref (идентификатор отделения)
        - Description (название отделения)
        - DescriptionRu (название на русском)
        - Number (номер отделения)
        - CityRef (Ref города)
    """
    payload = {
        "apiKey": self.api_key,
        "modelName": "Address",
        "calledMethod": "getWarehouses",
        "methodProperties": {
            "CityRef": city_ref,
            "TypeOfWarehouseRef": warehouse_type or ""
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        return data['data']
    return []
```

**Кеширование:**
- Отделения меняются редко
- Кешировать на 12-24 часа

**Приоритет:** 🟡 ВАЖНО  
**Время:** 4-6 часов  
**Сложность:** Средняя

#### 2.3. Поиск населенных пунктов
**Зачем:** Для поиска городов по частичному совпадению.

**Метод API:** `Address.searchSettlements`

**Реализация:**
```python
def search_settlements(self, search_string, limit=50):
    """
    Поиск населенных пунктов
    
    Args:
        search_string (str): Поисковый запрос
        limit (int): Максимальное количество результатов
        
    Returns:
        list: Список населенных пунктов
    """
    payload = {
        "apiKey": self.api_key,
        "modelName": "Address",
        "calledMethod": "searchSettlements",
        "methodProperties": {
            "CityName": search_string,
            "Limit": limit
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        return data['data']
    return []
```

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 3-4 часа  
**Сложность:** Средняя

---

### 3. Расчет стоимости доставки

#### 3.1. Расчет стоимости доставки
**Зачем:** Показывать реальную стоимость доставки при оформлении заказа.

**Метод API:** `InternetDocument.getDocumentPrice`

**Текущая реализация:** `calculate_shipping()` всегда возвращает 0 (TODO)

**Реализация:**
```python
def calculate_delivery_cost(self, city_ref, weight, service_type="WarehouseWarehouse", 
                          cost=0, cargo_type="Cargo", seats_amount=1):
    """
    Рассчитывает стоимость доставки
    
    Args:
        city_ref (str): Ref города получателя
        weight (float): Вес посылки в кг
        service_type (str): Тип услуги:
            - "WarehouseWarehouse" - склад-склад
            - "WarehouseDoors" - склад-двери
            - "DoorsWarehouse" - двери-склад
            - "DoorsDoors" - двери-двери
        cost (float): Оценочная стоимость посылки
        cargo_type (str): Тип груза (Cargo, Parcel, etc.)
        seats_amount (int): Количество мест
        
    Returns:
        dict: {
            "Cost": стоимость доставки,
            "AssessedCost": оценочная стоимость,
            "CostRedelivery": стоимость обратной доставки,
            "TZone": тарифная зона
        } или None при ошибке
    """
    # Ref города отправителя (Киев)
    sender_city_ref = "8d5a980d-391c-11dd-90d9-001a92567626"
    
    payload = {
        "apiKey": self.api_key,
        "modelName": "InternetDocument",
        "calledMethod": "getDocumentPrice",
        "methodProperties": {
            "CitySender": sender_city_ref,
            "CityRecipient": city_ref,
            "Weight": str(weight),
            "ServiceType": service_type,
            "Cost": str(cost),
            "CargoType": cargo_type,
            "SeatsAmount": seats_amount,
            "DateTime": datetime.now().strftime("%d.%m.%Y")
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        return data['data'][0] if isinstance(data['data'], list) else data['data']
    return None
```

**Использование в views:**
```python
def calculate_shipping(request):
    """Расчет стоимости доставки (AJAX)"""
    city_ref = request.POST.get('city_ref')
    weight = float(request.POST.get('weight', 1.0))
    
    np_service = NovaPoshtaService()
    cost_info = np_service.calculate_delivery_cost(
        city_ref=city_ref,
        weight=weight,
        service_type="WarehouseWarehouse"
    )
    
    if cost_info:
        shipping_cost = float(cost_info.get('Cost', 0))
        return JsonResponse({
            'success': True,
            'shipping_cost': shipping_cost,
            'message': f'Вартість доставки: {shipping_cost} грн'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Не вдалося розрахувати вартість доставки'
        })
```

**Приоритет:** 🟡 ВАЖНО  
**Время:** 6-8 часов  
**Сложность:** Средняя

---

### 4. Создание накладной (InternetDocument API)

#### 4.1. Создание экспресс-накладной
**Зачем:** Автоматическое создание накладной при оформлении заказа.

**Метод API:** `InternetDocument.save`

**Реализация:**
```python
def create_shipment(self, order):
    """
    Создает экспресс-накладную для заказа
    
    Args:
        order (Order): Заказ для создания накладной
        
    Returns:
        dict: {
            "Ref": Ref накладной,
            "CostOnSite": стоимость наложенного платежа,
            "EstimatedDeliveryDate": дата доставки,
            "IntDocNumber": номер накладной (ТТН),
            // ... другие поля
        } или None при ошибке
    """
    # Получаем данные отправителя (из настроек)
    sender_city_ref = settings.NOVA_POSHTA_SENDER_CITY_REF
    sender_ref = settings.NOVA_POSHTA_SENDER_REF
    sender_address_ref = settings.NOVA_POSHTA_SENDER_ADDRESS_REF
    
    # Получаем Ref города получателя
    recipient_city = self._get_city_ref_by_name(order.city)
    if not recipient_city:
        logger.error(f"City not found: {order.city}")
        return None
    
    # Получаем Ref отделения получателя
    recipient_warehouse = self._get_warehouse_ref_by_name(
        order.city, 
        order.np_office
    )
    if not recipient_warehouse:
        logger.error(f"Warehouse not found: {order.np_office}")
        return None
    
    # Рассчитываем вес заказа
    weight = self._calculate_order_weight(order)
    
    # Определяем тип оплаты
    payer_type = "Recipient" if order.pay_type == "cod" else "Sender"
    payment_method = "Cash" if order.pay_type == "cod" else "NonCash"
    
    payload = {
        "apiKey": self.api_key,
        "modelName": "InternetDocument",
        "calledMethod": "save",
        "methodProperties": {
            "SenderWarehouseIndex": sender_address_ref,
            "RecipientWarehouseIndex": recipient_warehouse,
            "PayerType": payer_type,
            "PaymentMethod": payment_method,
            "DateTime": datetime.now().strftime("%d.%m.%Y"),
            "CargoType": "Cargo",
            "Weight": str(weight),
            "ServiceType": "WarehouseWarehouse",
            "SeatsAmount": "1",
            "Description": f"Замовлення {order.order_number}",
            "Cost": str(order.total_sum),
            "CitySender": sender_city_ref,
            "Sender": sender_ref,
            "SenderAddress": sender_address_ref,
            "ContactSender": settings.NOVA_POSHTA_SENDER_CONTACT,
            "SendersPhone": settings.NOVA_POSHTA_SENDER_PHONE,
            "CityRecipient": recipient_city,
            "Recipient": order.full_name,
            "RecipientAddress": recipient_warehouse,
            "ContactRecipient": order.full_name,
            "RecipientsPhone": order.phone,
            "RecipientContactName": order.full_name,
            "RecipientContactPhone": order.phone
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        shipment_data = data['data'][0] if isinstance(data['data'], list) else data['data']
        
        # Сохраняем ТТН в заказ
        order.tracking_number = shipment_data.get('IntDocNumber')
        order.save(update_fields=['tracking_number'])
        
        logger.info(f"Created shipment for order {order.order_number}: TTN={order.tracking_number}")
        return shipment_data
    
    logger.error(f"Failed to create shipment for order {order.order_number}: {data.get('errors')}")
    return None
```

**Настройки (settings.py):**
```python
# Nova Poshta Sender Info
NOVA_POSHTA_SENDER_CITY_REF = os.environ.get('NOVA_POSHTA_SENDER_CITY_REF', '')
NOVA_POSHTA_SENDER_REF = os.environ.get('NOVA_POSHTA_SENDER_REF', '')
NOVA_POSHTA_SENDER_ADDRESS_REF = os.environ.get('NOVA_POSHTA_SENDER_ADDRESS_REF', '')
NOVA_POSHTA_SENDER_CONTACT = os.environ.get('NOVA_POSHTA_SENDER_CONTACT', '')
NOVA_POSHTA_SENDER_PHONE = os.environ.get('NOVA_POSHTA_SENDER_PHONE', '')
```

**Приоритет:** 🟡 ВАЖНО  
**Время:** 12-16 часов  
**Сложность:** Высокая

#### 4.2. Обновление накладной
**Зачем:** Изменение данных накладной (например, изменение адреса).

**Метод API:** `InternetDocument.update`

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 6-8 часов  
**Сложность:** Средняя

#### 4.3. Удаление накладной
**Зачем:** Отмена накладной при отмене заказа.

**Метод API:** `InternetDocument.delete`

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 4-6 часов  
**Сложность:** Средняя

---

### 5. Дополнительные методы

#### 5.1. Получение истории движения посылки
**Зачем:** Показывать полную историю движения посылки пользователю.

**Метод API:** `TrackingDocument.getStatusDocuments` (уже используется, но можно расширить)

**Реализация:**
```python
def get_tracking_history(self, ttn_number):
    """
    Получает полную историю движения посылки
    
    Returns:
        list: Список событий с полями:
        - Status (статус)
        - StatusCode (код статуса)
        - DateCreated (дата события)
        - Warehouse (склад)
        - City (город)
    """
    # Используем тот же метод, но получаем полную историю
    tracking_info = self.get_tracking_info(ttn_number)
    if tracking_info:
        # API может вернуть историю в поле History или в отдельном запросе
        return tracking_info.get('History', [])
    return []
```

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 4-6 часов  
**Сложность:** Средняя

#### 5.2. Получение типов груза и услуг
**Зачем:** Для правильного выбора типа услуги при создании накладной.

**Методы API:** `Common.getCargoTypes`, `Common.getServiceTypes`

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 2-3 часа  
**Сложность:** Низкая

---

## ⚡ Оптимизация и производительность

### 6. Кеширование данных

#### 6.1. Кеширование списка городов
- Кешировать на 24-48 часов
- Использовать Django cache или Redis
- Обновлять кеш при изменении

**Реализация:**
```python
from django.core.cache import cache

def get_cities_cached(self, search_string=None):
    cache_key = f"nova_poshta_cities_{search_string or 'all'}"
    cities = cache.get(cache_key)
    
    if cities is None:
        cities = self.get_cities(search_string)
        cache.set(cache_key, cities, 86400)  # 24 часа
    
    return cities
```

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 2-3 часа  
**Сложность:** Низкая

#### 6.2. Кеширование отделений
- Кешировать на 12-24 часа
- По ключу `city_ref`

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 2-3 часа  
**Сложность:** Низкая

### 7. Rate Limiting

**Проблема:** При обновлении множества заказов может быть слишком много запросов к API.

**Решение:**
```python
import time
from functools import wraps

def rate_limit(calls_per_second=2):
    """Декоратор для ограничения частоты запросов"""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

# Использование:
@rate_limit(calls_per_second=2)
def get_tracking_info(self, ttn_number):
    # ... код ...
```

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 1-2 часа  
**Сложность:** Низкая

### 8. Batch запросы

**Проблема:** Текущая реализация делает отдельный запрос для каждого заказа.

**Решение:** API позволяет передавать несколько ТТН в одном запросе.

**Реализация:**
```python
def get_tracking_info_batch(self, ttn_numbers):
    """
    Получает статусы для нескольких ТТН в одном запросе
    
    Args:
        ttn_numbers (list): Список номеров ТТН
        
    Returns:
        dict: {ttn_number: tracking_info, ...}
    """
    documents = [
        {"DocumentNumber": ttn, "Phone": ""}
        for ttn in ttn_numbers
    ]
    
    payload = {
        "apiKey": self.api_key,
        "modelName": "TrackingDocument",
        "calledMethod": "getStatusDocuments",
        "methodProperties": {
            "Documents": documents
        }
    }
    
    response = requests.post(self.API_URL, json=payload, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if data.get('success') and data.get('data'):
        # Создаем словарь для быстрого поиска
        result = {}
        for item in data['data']:
            result[item.get('Number')] = item
        return result
    
    return {}
```

**Использование в update_all_tracking_statuses:**
```python
def update_all_tracking_statuses(self):
    orders_with_ttn = Order.objects.filter(
        tracking_number__isnull=False
    ).exclude(tracking_number='')
    
    # Группируем по 10 заказов (лимит API)
    batch_size = 10
    ttn_list = list(orders_with_ttn.values_list('tracking_number', flat=True))
    
    for i in range(0, len(ttn_list), batch_size):
        batch = ttn_list[i:i+batch_size]
        tracking_data = self.get_tracking_info_batch(batch)
        
        # Обновляем заказы
        for ttn in batch:
            order = orders_with_ttn.get(tracking_number=ttn)
            if ttn in tracking_data:
                self._update_order_from_tracking_info(order, tracking_data[ttn])
```

**Приоритет:** 🟡 ВАЖНО  
**Время:** 6-8 часов  
**Сложность:** Средняя

---

## 📊 Мониторинг и алертинг

### 9. Мониторинг работы API

#### 9.1. Метрики
- Количество запросов к API
- Количество успешных/неуспешных запросов
- Среднее время ответа API
- Количество обновленных статусов
- Количество ошибок API

**Реализация:**
```python
from django.core.cache import cache
from datetime import datetime

def track_api_metrics(self, method_name, success, response_time):
    """Отслеживание метрик API"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Общие метрики
    cache_key = f"nova_poshta_metrics_{today}"
    metrics = cache.get(cache_key, {
        'total_requests': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'total_response_time': 0,
        'methods': {}
    })
    
    metrics['total_requests'] += 1
    if success:
        metrics['successful_requests'] += 1
    else:
        metrics['failed_requests'] += 1
    
    metrics['total_response_time'] += response_time
    
    # Метрики по методам
    if method_name not in metrics['methods']:
        metrics['methods'][method_name] = {
            'count': 0,
            'success': 0,
            'failed': 0
        }
    
    metrics['methods'][method_name]['count'] += 1
    if success:
        metrics['methods'][method_name]['success'] += 1
    else:
        metrics['methods'][method_name]['failed'] += 1
    
    cache.set(cache_key, metrics, 86400)  # 24 часа
```

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 4-6 часов  
**Сложность:** Средняя

#### 9.2. Алерты
- Уведомление при высокой частоте ошибок API
- Уведомление при истечении API ключа
- Уведомление при отсутствии обновлений статусов

**Приоритет:** 🟢 ЖЕЛАТЕЛЬНО  
**Время:** 6-8 часов  
**Сложность:** Средняя

---

## 📅 План внедрения

### Фаза 1: Критические исправления (1-2 недели)

1. **Неделя 1:**
   - Исправить использование StatusCode для определения доставки
   - Добавить обработку ошибок API
   - Исправить метод track_parcel
   - Добавить базовое логирование

2. **Неделя 2:**
   - Тестирование исправлений
   - Мониторинг работы
   - Документирование изменений

### Фаза 2: Важные улучшения (2-4 недели)

3. **Неделя 3-4:**
   - Реализация получения городов и отделений
   - Реализация расчета стоимости доставки
   - Интеграция в формы заказа

4. **Неделя 5-6:**
   - Реализация создания накладных
   - Тестирование
   - Документирование

### Фаза 3: Оптимизация (2-3 недели)

5. **Неделя 7-8:**
   - Кеширование данных
   - Batch запросы
   - Rate limiting

6. **Неделя 9:**
   - Мониторинг и метрики
   - Финальное тестирование

### Фаза 4: Дополнительные возможности (по необходимости)

7. **По требованию:**
   - История движения посылки
   - Обновление/удаление накладных
   - Дополнительные методы API

---

## 💡 Рекомендации по реализации

### Приоритеты:
1. 🔴 **КРИТИЧНО:** Исправить текущие проблемы (StatusCode, ошибки API)
2. 🟡 **ВАЖНО:** Расчет стоимости доставки
3. 🟡 **ВАЖНО:** Получение городов и отделений
4. 🟡 **ВАЖНО:** Создание накладных
5. 🟢 **ЖЕЛАТЕЛЬНО:** Оптимизация и кеширование
6. 🟢 **ЖЕЛАТЕЛЬНО:** Мониторинг и алертинг

### Технические рекомендации:
- Использовать Django cache для кеширования
- Использовать Celery для фоновых задач (создание накладных)
- Использовать Redis для rate limiting
- Логировать все запросы к API
- Добавить unit тесты для всех методов
- Добавить integration тесты для реальных запросов к API

### Безопасность:
- Хранить API ключ в переменных окружения
- Не логировать API ключ
- Валидировать все входные данные
- Использовать HTTPS для всех запросов

---

**Конец рекомендаций**

