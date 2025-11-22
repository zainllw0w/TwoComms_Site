# 🔧 Fix & Harden: Meta/TikTok tracking w/ CAPI, no duplicates, deposits vs full payments, catalogs in sync

**Заголовок:** Fix & Harden: Meta/TikTok tracking w/ CAPI, no duplicates, deposits vs full payments, catalogs in sync

**Цель:** Исправить все найденные проблемы в системе трекинга, обеспечить корректную дедупликацию, правильную логику событий для предоплаты и полной оплаты, синхронизацию каталогов.

---

## СЕКЦИЯ A — ПРАВКИ ПО ФАЙЛАМ

### 1. `twocomms/twocomms_django_theme/templates/pages/order_success.html`

**Проблема:** Неправильная логика отправки событий - Lead отправляется для prepaid И paid, должно быть только для prepaid.

**Правка (строки 1807-1814):**

```javascript
// БЫЛО (НЕПРАВИЛЬНО):
var shouldSendLead = paymentStatus === 'prepaid' || paymentStatus === 'paid';
var shouldSendPurchase = paymentStatus === 'paid';

// ДОЛЖНО БЫТЬ:
var shouldSendLead = paymentStatus === 'prepaid';  // ТОЛЬКО для предоплаты
var shouldSendPurchase = paymentStatus === 'paid';  // ТОЛЬКО для полной оплаты
```

**Код-патч:**

```javascript
// НОВАЯ ЛОГИКА (по требованиям):
// 1. Lead - ТОЛЬКО для prepaid (предоплата)
// 2. Purchase - ТОЛЬКО для paid (полная оплата)
// 3. Для unpaid - никаких событий
var shouldSendLead = paymentStatus === 'prepaid';
var shouldSendPurchase = paymentStatus === 'paid';
```

**Проверка:** После правки проверить, что:
- При `payment_status='prepaid'` отправляется только Lead
- При `payment_status='paid'` отправляется только Purchase
- При `payment_status='unpaid'` события не отправляются

---

### 2. `twocomms/storefront/views/checkout.py` (или где создается заказ)

**Проблема:** Нужно убедиться, что fbp/fbc/ttclid передаются с клиента на сервер при создании заказа.

**Правка:** Добавить передачу cookies в `payment_payload.tracking` при создании заказа.

**Код-патч (пример):**

```python
# В функции create_order или аналогичной
def create_order(request):
    # ... существующий код ...
    
    # Получаем tracking cookies с клиента
    tracking_data = {}
    
    # Facebook Pixel cookies
    fbp = request.COOKIES.get('_fbp', '')
    fbc = request.COOKIES.get('_fbc', '')
    
    # TikTok Pixel cookie
    ttclid = request.COOKIES.get('ttclid', '')
    
    # External ID (user_id или session_key)
    if request.user.is_authenticated:
        external_id = f"user:{request.user.id}"
    else:
        session_key = request.session.session_key or ''
        external_id = f"session:{session_key}" if session_key else ''
    
    if fbp:
        tracking_data['fbp'] = fbp
    if fbc:
        tracking_data['fbc'] = fbc
    if ttclid:
        tracking_data['ttclid'] = ttclid
    if external_id:
        tracking_data['external_id'] = external_id
    
    # Client IP и User Agent
    tracking_data['client_ip_address'] = request.META.get('REMOTE_ADDR', '')
    tracking_data['client_user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    # Сохраняем в payment_payload
    if not order.payment_payload:
        order.payment_payload = {}
    order.payment_payload['tracking'] = tracking_data
    order.save(update_fields=['payment_payload'])
```

**Проверка:** После правки проверить в логах, что `payment_payload.tracking` содержит fbp, fbc, ttclid.

---

### 3. `twocomms/twocomms_django_theme/templates/pages/order_success.html` (передача cookies)

**Проблема:** Нужно передать cookies с клиента на сервер при создании заказа (если еще не сделано).

**Правка:** Добавить JavaScript код для передачи cookies через AJAX при создании заказа (если заказ создается через AJAX).

**Код-патч (если заказ создается через AJAX):**

```javascript
// В функции создания заказа (если используется AJAX)
function createOrderAjax(formData) {
    // Получаем tracking cookies
    var trackingData = {
        fbp: getCookie('_fbp') || '',
        fbc: getCookie('_fbc') || '',
        ttclid: getCookie('ttclid') || ''
    };
    
    // Добавляем к formData
    formData.append('tracking_fbp', trackingData.fbp);
    formData.append('tracking_fbc', trackingData.fbc);
    formData.append('tracking_ttclid', trackingData.ttclid);
    
    // ... остальной код отправки ...
}

function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return '';
}
```

**Проверка:** После правки проверить в Network tab, что cookies передаются при создании заказа.

---

### 4. `twocomms/orders/facebook_conversions_service.py`

**Проблема:** Нужно убедиться, что event_id точно совпадает с клиентским.

**Правка:** Проверить, что используется `order.get_facebook_event_id()` везде.

**Код-патч (проверка):**

```python
# В методе send_purchase_event и send_lead_event
def send_purchase_event(self, order, ...):
    # Убедиться, что event_id генерируется так же, как на клиенте
    event_id = order.get_facebook_event_id()  # ✅ Правильно
    
    # Добавить логирование для проверки
    logger.info(f"Facebook CAPI Purchase: order={order.order_number}, event_id={event_id}")
    
    # ... остальной код ...
```

**Проверка:** После правки проверить в логах, что event_id совпадает с клиентским.

---

### 5. `twocomms/orders/tiktok_events_service.py`

**Проблема:** Нужно убедиться, что event_id точно совпадает с клиентским.

**Правка:** Проверить, что используется `order.get_facebook_event_id()` (тот же метод, что для Meta).

**Код-патч (проверка):**

```python
# В методе send_purchase_event и send_lead_event
def send_purchase_event(self, order, ...):
    # Убедиться, что event_id генерируется так же, как на клиенте
    event_id = order.get_facebook_event_id()  # ✅ Правильно
    
    # Добавить логирование для проверки
    logger.info(f"TikTok Events API Purchase: order={order.order_number}, event_id={event_id}")
    
    # ... остальной код ...
```

**Проверка:** После правки проверить в логах, что event_id совпадает с клиентским.

---

### 6. `twocomms/twocomms_django_theme/static/js/analytics-loader.js`

**Проблема:** Нужно убедиться, что event_id передается корректно в Meta Pixel и TikTok Pixel.

**Правка:** Проверить, что event_id извлекается из payload и передается в пиксели.

**Код-патч (проверка, строки 84-170):**

```javascript
// Убедиться, что event_id извлекается правильно
var metaConfig = (payload.__meta && typeof payload.__meta === 'object') ? payload.__meta : {};
var eventId = metaConfig.event_id || payload.event_id || null;

// Для Meta Pixel
if (eventId) {
    metaOptions.eventID = String(eventId);  // ✅ Правильно
}

// Для TikTok Pixel
if (eventId) {
    ttqPayload.event_id = String(eventId);  // ✅ Правильно
}
```

**Проверка:** После правки проверить в консоли браузера, что event_id передается в пиксели.

---

### 7. Добавить обработку ретраев для CAPI/Events API

**Проблема:** Нет обработки ретраев при ошибках отправки событий.

**Правка:** Добавить retry логику в серверные сервисы.

**Код-патч (пример для facebook_conversions_service.py):**

```python
import time
from typing import Optional

def send_purchase_event(self, order, ..., max_retries=3):
    """Отправляет Purchase событие с retry логикой"""
    if not self.enabled:
        return False
    
    for attempt in range(max_retries):
        try:
            # ... существующий код отправки ...
            
            logger.info(f"✅ Purchase event sent successfully on attempt {attempt + 1}")
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"⚠️ Purchase event failed on attempt {attempt + 1}, "
                    f"retrying in {wait_time}s: {e}"
                )
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Purchase event failed after {max_retries} attempts: {e}")
                return False
    
    return False
```

**Проверка:** После правки проверить, что события повторно отправляются при ошибках.

---

## СЕКЦИЯ B — СОБЫТИЙНЫЙ КОНТРАКТ

### Таблица событий

| Событие | Когда стрелять | Параметры | Источник | event_id политика | Проверка/тест |
|---------|----------------|-----------|----------|-------------------|---------------|
| **Purchase (Meta)** | `payment_status == 'paid'` | `content_ids`, `value`, `currency`, `event_id`, `user_data` | Browser + Server | Одинаковый на клиенте и сервере | Meta Events Manager → Test Events |
| **CompletePayment (TikTok)** | `payment_status == 'paid'` | `content_id`, `value`, `currency`, `event_id`, `user_context` | Browser + Server | Одинаковый на клиенте и сервере | TikTok Events Manager → Test Events |
| **Lead (Meta)** | `payment_status == 'prepaid'` | `value`, `currency`, `event_id`, `user_data` | Browser + Server | Одинаковый на клиенте и сервере | Meta Events Manager → Test Events |
| **Lead (TikTok)** | `payment_status == 'prepaid'` | `value`, `currency`, `event_id`, `user_context` | Browser + Server | Одинаковый на клиенте и сервере | TikTok Events Manager → Test Events |
| **ViewContent** | Просмотр товара | `content_ids`, `value`, `currency` | Browser | Генерируется на клиенте | Meta/TikTok Pixel Helper |
| **AddToCart** | Добавление в корзину | `content_ids`, `value`, `currency` | Browser | Генерируется на клиенте | Meta/TikTok Pixel Helper |
| **InitiateCheckout** | Начало оформления | `content_ids`, `value`, `currency` | Browser | Генерируется на клиенте | Meta/TikTok Pixel Helper |

### Критически важно

1. **Purchase/CompletePayment** отправляется ТОЛЬКО при `payment_status == 'paid'`
2. **Lead** отправляется ТОЛЬКО при `payment_status == 'prepaid'`
3. **event_id** должен быть одинаковым на клиенте и сервере для дедупликации
4. **content_ids** должен совпадать с ID в каталогах (Google Merchant, Meta Catalog)

---

## СЕКЦИЯ C — GTM

### Матрица тегов

| Тег | Статус | Условие | Комментарий |
|-----|--------|---------|------------|
| **GTM Container** | ✅ Активен | Все страницы | Инициализация в base.html |
| **Meta Pixel Tag** | ⚠️ Проверить | Если настроен | Отключить, если дублирует trackEvent() |
| **TikTok Pixel Tag** | ⚠️ Проверить | Если настроен | Отключить, если дублирует trackEvent() |
| **Purchase Event** | ✅ Активен | `event: 'purchase'` | Триггер на событие purchase |
| **Lead Event** | ✅ Активен | `event: 'lead'` | Триггер на событие lead |

### Рекомендации

1. **Отключить теги Meta/TikTok Pixel в GTM**, если они дублируют события из `trackEvent()`
2. **Использовать только события через dataLayer** для GTM
3. **Проверить триггеры** - должны срабатывать на `event: 'purchase'` и `event: 'lead'`

### Логика работы sGTM (если используется)

**Текущий статус:** Не найдена явная реализация sGTM.

**Рекомендация:** Если используется sGTM, убедиться, что:
- События отправляются через sGTM endpoint
- event_id передается корректно
- Дедупликация настроена правильно

---

## СЕКЦИЯ D — КАТАЛОГИ/ФИД

### Google Merchant Center

**Формат:** XML v3  
**URL:** `https://twocomms.shop/media/google-merchant-v3.xml`  
**Обновление:** Автоматически при изменении товаров  
**ID формат:** `TC-{product_id}-{color_variant_id}-{SIZE}`

**Проверка согласованности:**

1. **Проверить, что content_ids в событиях совпадает с g:id в фиде:**
   ```bash
   # Проверить формат ID в фиде
   grep -o "TC-[0-9]*-[A-Z]*-[A-Z]*" media/google-merchant-v3.xml | head -10
   
   # Проверить, что используется тот же формат в событиях
   # (проверить в логах или консоли браузера)
   ```

2. **Убедиться, что get_offer_id() используется везде:**
   - В `generate_google_merchant_feed.py` ✅
   - В `facebook_conversions_service.py` ✅
   - В `tiktok_events_service.py` ✅
   - В `analytics-loader.js` (для клиентских событий) ⚠️ Проверить

### Meta Catalog

**Статус:** Не найдена явная интеграция с Meta Catalog API.

**Рекомендация:**
1. Проверить, есть ли каталог в Meta Business Manager
2. Если есть, убедиться, что ID товаров совпадает с content_ids в событиях
3. Если нет, настроить каталог через фид или Content API

### Обеспечение консистентности

**Правило:** Всегда использовать `get_offer_id(product_id, color_variant_id, size)` для генерации ID товара.

**Формат:** `TC-{product_id}-{color_variant_id}-{SIZE}`

**Пример:**
- Product ID: 123
- Color Variant ID: 456
- Size: XL
- Offer ID: `TC-123-456-XL`

---

## СЕКЦИЯ E — QA/ВАЛИДАЦИЯ

### Чеклист тестов

#### 1. Meta Test Events / Diagnostics

**Тест 1: Purchase событие (полная оплата)**
- [ ] Создать заказ с `pay_type='online_full'`
- [ ] Дождаться `payment_status='paid'`
- [ ] Проверить в Meta Events Manager → Test Events:
  - [ ] Событие Purchase отправлено
  - [ ] event_id присутствует
  - [ ] fbp/fbc присутствуют
  - [ ] content_ids совпадает с ID в каталоге
  - [ ] value и currency корректны
- [ ] Проверить Event Match Quality (EMQ)
- [ ] Проверить Deduplication (должно быть 1 событие, не 2)

**Тест 2: Lead событие (предоплата)**
- [ ] Создать заказ с `pay_type='prepay_200'`
- [ ] Дождаться `payment_status='prepaid'`
- [ ] Проверить в Meta Events Manager → Test Events:
  - [ ] Событие Lead отправлено (НЕ Purchase!)
  - [ ] event_id присутствует
  - [ ] value = сумма предоплаты (200 грн)
  - [ ] value НЕ равна полной сумме заказа

**Тест 3: Дедупликация**
- [ ] Создать заказ с полной оплатой
- [ ] Проверить в Meta Events Manager → Deduplication:
  - [ ] Одно событие Purchase (не два)
  - [ ] event_id одинаковый в браузере и сервере

#### 2. TikTok Test Events

**Тест 1: Purchase событие (полная оплата)**
- [ ] Создать заказ с `pay_type='online_full'`
- [ ] Дождаться `payment_status='paid'`
- [ ] Проверить в TikTok Events Manager → Test Events:
  - [ ] Событие Purchase отправлено
  - [ ] event_id присутствует
  - [ ] content_id совпадает с ID в каталоге
  - [ ] value и currency корректны

**Тест 2: Lead событие (предоплата)**
- [ ] Создать заказ с `pay_type='prepay_200'`
- [ ] Дождаться `payment_status='prepaid'`
- [ ] Проверить в TikTok Events Manager → Test Events:
  - [ ] Событие Lead отправлено (НЕ Purchase!)
  - [ ] event_id присутствует
  - [ ] value = сумма предоплаты (200 грн)

**Тест 3: Дедупликация**
- [ ] Создать заказ с полной оплатой
- [ ] Проверить в TikTok Events Manager → Deduplication:
  - [ ] Одно событие Purchase (не два)
  - [ ] event_id одинаковый в браузере и сервере

#### 3. GTM Preview

**Тест 1: Purchase событие**
- [ ] Открыть GTM → Preview
- [ ] Создать заказ с полной оплатой
- [ ] Проверить в GTM Preview:
  - [ ] Событие `purchase` отправлено
  - [ ] Данные корректны (transaction_id, value, currency)
  - [ ] user_data присутствует (если есть)

**Тест 2: Lead событие**
- [ ] Открыть GTM → Preview
- [ ] Создать заказ с предоплатой
- [ ] Проверить в GTM Preview:
  - [ ] Событие `lead` отправлено
  - [ ] Данные корректны (order_id, value, currency)

#### 4. E2E сценарии

**Сценарий 1: Гость, полная оплата**
- [ ] Создать заказ как гость
- [ ] Оплатить полную сумму
- [ ] Проверить:
  - [ ] Purchase отправлен в Meta (Pixel + CAPI)
  - [ ] Purchase отправлен в TikTok (Pixel + Events API)
  - [ ] event_id одинаковый
  - [ ] Нет дублей

**Сценарий 2: Авторизованный, предоплата**
- [ ] Создать заказ как авторизованный пользователь
- [ ] Оплатить предоплату (200 грн)
- [ ] Проверить:
  - [ ] Lead отправлен в Meta (Pixel + CAPI)
  - [ ] Lead отправлен в TikTok (Pixel + Events API)
  - [ ] Purchase НЕ отправлен
  - [ ] value = 200 грн (не полная сумма)

**Сценарий 3: Мини-корзина, изменение варианта**
- [ ] Добавить товар в корзину
- [ ] Изменить цвет/размер
- [ ] Проверить:
  - [ ] AddToCart отправлен с правильным content_id
  - [ ] content_id отражает выбранный вариант

---

### Метрики успеха

**Первая неделя после релиза:**

1. **Event Match Quality (Meta):**
   - Цель: > 70% для событий Purchase/Lead
   - Проверка: Meta Events Manager → Diagnostics

2. **Deduplication Rate (Meta):**
   - Цель: 100% дедупликация (1 событие, не 2)
   - Проверка: Meta Events Manager → Deduplication

3. **Match Keys (TikTok):**
   - Цель: > 60% для событий Purchase/Lead
   - Проверка: TikTok Events Manager → Match Keys

4. **Отсутствие дублей:**
   - Цель: 0 дублей в отчетах
   - Проверка: Сравнить количество событий в Pixel и API

5. **Правильная логика событий:**
   - Цель: 0 Purchase для предоплаты, 0 Lead для полной оплаты
   - Проверка: Проверить события для всех заказов

---

## СЕКЦИЯ F — ИСТОЧНИКИ/ССЫЛКИ

### Meta Conversions API

- **Дедупликация:** https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/event-id
- **fbp/fbc консистентность:** https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event#fbc-and-fbp
- **User Data нормализация:** https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters
- **sGTM подход:** https://developers.facebook.com/docs/marketing-api/conversions-api/guides/using-server-side-tag-managers

### TikTok Events API

- **Дедупликация:** https://ads.tiktok.com/help/article?aid=10028
- **Match Keys:** https://ads.tiktok.com/help/article?aid=10028
- **Стандартные события:** https://ads.tiktok.com/help/article?aid=10028

### Google Merchant Center

- **Спецификация:** https://support.google.com/merchants/answer/7052112
- **Content API v2.1:** https://developers.google.com/merchant/api/guides/overview

### GTM Server-Side

- **Обзор:** https://support.google.com/tagmanager/answer/9263294
- **Гайд 2025:** https://support.google.com/tagmanager/topic/7679384

---

## КРИТИЧЕСКИ ВАЖНО

1. **НЕ отправлять Purchase для предоплаты** - только Lead
2. **НЕ отправлять Lead для полной оплаты** - только Purchase
3. **event_id должен быть одинаковым** на клиенте и сервере
4. **content_ids должен совпадать** с ID в каталогах
5. **Проверить GTM конфигурацию** - отключить дублирующие теги

---

## ПЛАН ДЕЙСТВИЙ

1. ✅ Исправить логику событий в `order_success.html`
2. ✅ Добавить передачу cookies при создании заказа
3. ✅ Проверить GTM конфигурацию
4. ✅ Добавить обработку ретраев
5. ✅ Провести тестирование
6. ✅ Мониторинг первой недели

---

**Готово к реализации!** 🚀
















