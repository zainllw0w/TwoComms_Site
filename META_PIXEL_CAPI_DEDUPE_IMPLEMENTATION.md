# Meta Pixel + CAPI Дедупликация - Реализация

## Обзор

Полная реализация дедупликации Meta Pixel ↔ Conversions API для e-commerce проекта TwoComms.

### Цели и KPI

1. ✅ **Дедупликация подтверждена** - Одно пользовательское действие = одна связка browser+server
2. 📊 **Покрытие ≥ 75%** - "pixel events covered by CAPI" по ключевым событиям
3. 🎯 **EMQ ≥ 9/10** - Event Match Quality на AddToCart, InitiateCheckout, Lead, Purchase
4. 📈 **Сходимость ≤ ±3%** - Разница Lead/Purchase с БД за 7 дней
5. ✓ **Нет предупреждений** - В Diagnostics (Missing user data / Low coverage)

## Архитектура

### Клиент (JavaScript)

**Файл**: `twocomms_django_theme/static/js/analytics-loader.js`

#### Новые функции:

1. **generateEventId()** - Генерирует уникальный event_id для дедупликации
   ```javascript
   // Format: timestamp_random
   var eventId = timestamp + '_' + random;
   ```

2. **ensureFbpCookie()** - Создает/проверяет _fbp cookie (Meta Pixel Browser ID)
   ```javascript
   // Format: fb.1.timestamp.random
   setCookieValue('_fbp', fbp, 90); // 90 дней
   ```

3. **ensureFbcCookie()** - Парсит fbclid из URL и создает _fbc cookie (Click ID)
   ```javascript
   // Format: fb.1.timestamp.fbclid
   // Парсит из URL: ?fbclid=...
   setCookieValue('_fbc', fbc, 90);
   ```

4. **getTrackingContext()** - Экспортирует tracking контекст
   ```javascript
   window.getTrackingContext() // => { fbp, fbc, event_id }
   ```

#### Логика trackEvent():

```javascript
win.trackEvent = function(eventName, payload) {
  // 1. Генерируем event_id автоматически
  var eventId = payload.event_id || generateEventId();
  
  // 2. Обновляем fbp/fbc cookies
  var fbpValue = ensureFbpCookie();
  var fbcValue = ensureFbcCookie();
  
  // 3. Обогащаем payload
  payload.__meta = {
    event_id: eventId,
    fbp: fbpValue,
    fbc: fbcValue,
    external_id: ...
  };
  
  // 4. Отправляем в Meta Pixel с eventID
  fbq('track', eventName, fbPayload, {
    eventID: eventId,
    fbp: fbpValue,
    fbc: fbcValue
  });
}
```

### Сервер (Django)

#### 1. Monobank Create Invoice

**Файл**: `storefront/views/monobank.py`

```python
@require_POST
def monobank_create_invoice(request):
    # Получаем tracking данные от клиента
    client_tracking = body.get('tracking', {})  # {event_id, fbp, fbc}
    
    # Собираем tracking_context
    tracking_context = {
        'fbp': request.COOKIES.get('_fbp'),
        'fbc': request.COOKIES.get('_fbc'),
        'external_id': f"user:{user.id}" or f"session:{session_key}",
        'client_ip_address': request.META.get('HTTP_X_FORWARDED_FOR'),
        'client_user_agent': request.META.get('HTTP_USER_AGENT'),
        **client_tracking  # Добавляем event_id от клиента
    }
    
    # Сохраняем в payment_payload
    order.payment_payload = {
        'tracking': tracking_context
    }
```

#### 2. Facebook Conversions API

**Файл**: `orders/facebook_conversions_service.py`

**Основные изменения:**

1. **Использование event_id из tracking_data**:
```python
def send_purchase_event(self, order):
    # Приоритет - event_id от клиента
    tracking_data = order.payment_payload.get('tracking') or {}
    event_id = tracking_data.get('event_id')
    
    # Fallback - генерируем
    if not event_id:
        event_id = order.get_facebook_event_id()
```

2. **Улучшенный _prepare_user_data()**:
```python
def _prepare_user_data(self, order):
    user_data = UserData()
    
    # EMQ Critical Fields:
    user_data.email = self._hash_data(order.user.email)  # SHA-256
    user_data.phone = self._hash_data(phone_digits)      # SHA-256
    user_data.fbp = tracking_data.get('fbp')
    user_data.fbc = tracking_data.get('fbc')
    user_data.external_id = self._hash_data(external_source)
    user_data.client_ip_address = tracking_data.get('client_ip_address')
    user_data.client_user_agent = tracking_data.get('client_user_agent')
    
    return user_data
```

#### 3. Order Model

**Файл**: `orders/models.py`

```python
def get_facebook_event_id(self, event_type='purchase'):
    """
    Генерирует уникальный event_id для дедупликации.
    
    Args:
        event_type: 'purchase' или 'lead'
    
    Format: {order_number}_{timestamp}_{event_type}
    Example: TWC30102025N01_1730304000_purchase
    """
    timestamp = int(self.created.timestamp())
    return f"{self.order_number}_{timestamp}_{event_type}"
```

### Поток событий

#### 1. PageView
- **Клиент**: `fbq('track', 'PageView', {}, {eventID: generated_id})`
- **Сервер**: Нет (только browser event)
- **event_id**: Генерируется на клиенте

#### 2. ViewContent
- **Клиент**: `trackEvent('ViewContent', {content_ids, value})`
- **Сервер**: Нет (только browser event)
- **event_id**: Генерируется на клиенте

#### 3. AddToCart
- **Клиент**: `trackEvent('AddToCart', {content_ids, value})`
- **Сервер**: Нет (только browser event)
- **event_id**: Генерируется на клиенте

#### 4. InitiateCheckout
- **Клиент**: `trackEvent('InitiateCheckout', {value, content_ids})`
  - Генерирует event_id
  - Отправляет на сервер в tracking: {event_id, fbp, fbc}
- **Сервер**: Сохраняет tracking_data в order.payment_payload
- **event_id**: Один и тот же клиент→сервер

#### 5. Lead (Предоплата 200 грн)
- **Клиент**: Отправляет `trackEvent('Lead')` на странице успеха
- **Сервер**: Отправляет через CAPI из webhook Monobank
  - Использует event_id из tracking_data
  - Или генерирует: `{order_number}_{timestamp}_lead`
- **Триггер**: ТОЛЬКО webhook Monobank с payment_status='prepaid'

#### 6. Purchase (Полная оплата)
- **Клиент**: Отправляет `trackEvent('Purchase')` на странице успеха
- **Сервер**: Отправляет через CAPI из webhook Monobank
  - Использует event_id из tracking_data
  - Или генерирует: `{order_number}_{timestamp}_purchase`
- **Триггер**: ТОЛЬКО webhook Monobank с payment_status='paid'

## Моноbank Webhooks

### Обработка статусов

**Файл**: `storefront/views/utils.py`

```python
def _record_monobank_status(order, payload, source='webhook'):
    status = payload.get('status')
    
    if status == 'success':
        # Определяем тип оплаты
        if order.pay_type == 'prepay_200':
            order.payment_status = 'prepaid'
            # Отправляем Lead событие
            fb_service.send_lead_event(order)
        else:
            order.payment_status = 'paid'
            # Отправляем Purchase событие
            fb_service.send_purchase_event(order)
```

### Проверка подписи

```python
def _verify_monobank_signature(request):
    """
    Проверяет X-Sign заголовок webhook.
    Использует публичный ключ Monobank для верификации.
    """
    signature = request.headers.get('X-Sign')
    public_key = _get_monobank_public_key()  # Кешируется
    # RSA PKCS1v15 + SHA256 verification
```

## Тестирование

### 1. Test Events (Meta Events Manager)

**Проверка дедупликации:**
1. Откройте Events Manager → Test Events
2. Выполните действие (например, AddToCart)
3. Проверьте что событие приходит с:
   - Source: browser (Meta Pixel)
   - Event ID: `{timestamp}_{random}`
   - Параметры: fbp, fbc, external_id

### 2. Diagnostics

**Проверьте метрики:**
- "Pixel events covered by CAPI" ≥ 75%
- EMQ (Event Match Quality) ≥ 9/10
- Нет предупреждений "Duplicate event"
- Нет ошибок "Missing user data"

### 3. Monobank Webhook Testing

```bash
# Симуляция webhook предоплаты
curl -X POST https://twocomms.com/payments/monobank/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Sign: {signature}" \
  -d '{
    "invoiceId": "test_invoice",
    "status": "success",
    ...
  }'
```

### 4. Сверка с БД

```python
# Проверка сходимости Lead/Purchase
from orders.models import Order
from datetime import timedelta

# За последние 7 дней
start_date = timezone.now() - timedelta(days=7)

# Lead события (prepaid)
lead_orders = Order.objects.filter(
    payment_status='prepaid',
    created__gte=start_date
).count()

# Purchase события (paid)
purchase_orders = Order.objects.filter(
    payment_status='paid',
    created__gte=start_date
).count()

# Сравнить с Events Manager
print(f"DB Lead: {lead_orders}, DB Purchase: {purchase_orders}")
```

## EMQ (Event Match Quality) - Оптимизация

### Критичные параметры для EMQ 9+/10:

1. ✅ **fbp** (Browser ID) - Создается автоматически
2. ✅ **fbc** (Click ID) - Парсится из fbclid URL
3. ✅ **external_id** - user_id или session_id (хеш SHA-256)
4. ✅ **client_ip_address** - Реальный IP (X-Forwarded-For)
5. ✅ **client_user_agent** - User-Agent браузера
6. ✅ **em** (email) - SHA-256 хеш email
7. ✅ **ph** (phone) - SHA-256 хеш телефона (только цифры)

### Advanced Matching (Meta Pixel)

```javascript
// При инициализации Pixel
fbq('init', PIXEL_ID, {
  em: 'user@example.com',  // lowercase
  ph: '380XXXXXXXXX',       // только цифры
  fn: 'ivan',               // lowercase first name
  ln: 'petrov',             // lowercase last name
  ct: 'kyiv',               // lowercase city
  external_id: 'user:123'
});
```

## Content IDs - Синхронизация с каталогом

### Формат Offer ID:

```python
def get_offer_id(product_id, color_variant_id, size):
    """
    Format: TC-{product_id}-{variant_id}-{SIZE}
    Example: TC-123-45-M
    """
    return f"TC-{product_id}-{color_variant_id or 0}-{size.upper()}"
```

### Проверка каталога:

1. Commerce Manager → Catalog
2. Проверить что `id` товара = offer_id в событиях
3. Обязательные поля:
   - id (offer_id)
   - title
   - price
   - availability (in stock / out of stock)
   - image_link
   - link (URL товара)

## GTM Партнер - Временное отключение

### Отключение в Meta Business Manager:

1. Business Settings → Data Sources → Partner Integrations
2. Найти "Google Tag Manager"
3. Отключить интеграцию временно
4. Это исключит "пустой" источник и улучшит метрики

### Повторное включение после стабилизации:

- После достижения покрытия ≥ 75%
- После подтверждения EMQ ≥ 9/10
- Настройка Server-Side GTM (SSGTM) - отдельная задача

## Мониторинг и логи

### Django логи:

```python
# Facebook Conversions API
logger.info(f"📊 Using event_id from tracking_data: {event_id}")
logger.info(f"✅ Purchase event sent: Order {order.order_number}")

# Monobank
monobank_logger.info(f"📊 Client tracking data received: {client_tracking}")
monobank_logger.info(f"✅ Order {order.order_number} updated with tracking")
```

### JavaScript консоль:

```javascript
console.log('[Analytics] Event sent:', eventName, {
  event_id: eventId,
  fbp: fbpValue,
  fbc: fbcValue
});
```

## Чек-лист деплоя

- [ ] GTM партнер отключен в Business Manager
- [ ] analytics-loader.js обновлен (event_id, fbp, fbc)
- [ ] main.js передает tracking в payload
- [ ] monobank.py сохраняет client_tracking
- [ ] facebook_conversions_service.py использует event_id
- [ ] Monobank webhook проверяет подпись
- [ ] Test Events показывает дедупликацию
- [ ] Diagnostics без ошибок
- [ ] Покрытие ≥ 75%
- [ ] EMQ ≥ 9/10
- [ ] Сверка с БД ≤ ±3%

## Известные проблемы и решения

### 1. Дубли событий

**Проблема**: Событие приходит 2 раза (browser + server)

**Решение**: 
- Проверить что event_id идентичен
- Проверить event_name (должен совпадать)
- Проверить event_time (разница < 60 сек допустима)

### 2. Низкий EMQ

**Проблема**: EMQ < 9/10

**Решение**:
- Проверить наличие fbp/fbc cookies
- Убедиться что em/ph хешируются правильно (SHA-256)
- Добавить external_id во все события

### 3. Отсутствие _fbc

**Проблема**: _fbc cookie не создается

**Решение**:
- Проверить что fbclid присутствует в URL
- Убедиться что ensureFbcCookie() вызывается
- Проверить что cookie не блокируется браузером

## Контакты и поддержка

**Документация Meta:**
- [Conversions API](https://developers.facebook.com/docs/marketing-api/conversions-api)
- [Event Deduplication](https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events)
- [Event Match Quality](https://www.facebook.com/business/help/765081237991954)

**Monobank API:**
- [Acquiring Docs](https://api.monobank.ua/docs/acquiring.html)
- [Webhook Signature](https://api.monobank.ua/docs/acquiring.html#webhook)
