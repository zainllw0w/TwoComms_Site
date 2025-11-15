# 📊 GTM Data Layer: Анализ и руководство по реализации

**Дата обновления:** 2025-10-24  
**Цель:** синхронизировать фронтовые события (GA4 ecommerce + Meta Pixel) с товарным фидом Google Merchant v3 и обеспечить правильную дедупликацию с CAPI.  
**GTM Container ID:** `GTM-PRLLBF9H`  
**Meta Pixel ID:** `823958313630148`  
**Google Merchant Feed v3:** `https://twocomms.shop/media/google-merchant-v3.xml`

---

## 🧾 TL;DR — критические тезисы

- Все события должны пушиться **только через `dataLayer.push({...})`** и содержать _два уровня данных_: `ecommerce` (GA4) и `eventModel` (Meta Pixel). Названия полей должны полностью совпадать с эталонным примером.
- `event_id`, `fbp`, `fbc`, `user_data` теперь обязательны внутри `dataLayer` — GTM будет передавать их в Meta Pixel для дедупликации с `facebook_conversions_service.py` (CAPI).
- `item_id`/`content_ids` обязаны совпадать с `g:id` из Merchant Feed (формат `TC-{product_id}-{variant_key}-{SIZE}`) — пока feed и `get_offer_id()` генерируют **разные** ID.
- `purchase` и `lead` события уже генерируются на `order_success.html`, но их `ecommerce`/`eventModel` неполные (нет brand/category/tax/shipping/coupon). Мы должны дополнить структуру.
- `view_item`, `add_to_cart`, `begin_checkout` пока не отправляются в `dataLayer` (есть только `trackEvent`). Нужно дословно повторить структуру эталона.
- В GTM необходимо настроить отдельные теги Meta Pixel и GA4, которые берут данные из `eventModel` и `ecommerce` соответственно. Именование триггеров/переменных должно совпадать.

---

## 🛠️ План работ и статус

| # | Что делаем | Где правим | Детали | Статус |
|---|------------|------------|--------|--------|
| 1 | Унифицировать ID между фидом и событиями | `twocomms/storefront/management/commands/generate_google_merchant_feed.py:177`, `twocomms/storefront/utils/analytics_helpers.py:1-110`, `order_success.html`, `main.js` | Фид сейчас генерирует `TC-123-cv456-M`, а фронт использует `TC-0123-CHERNYI-M`. Нужно либо использовать `get_offer_id()` внутри генератора фида, либо изменить фронт. Предпочтительно — фид. | ⚠️ Требует фикса |
| 2 | Добавить `dataLayer` события для `view_item`, `add_to_cart`, `begin_checkout` | `product_detail.html`, `twocomms/twocomms_django_theme/static/js/main.js` | После `trackEvent()` вставляем `dataLayer.push()` с `ecommerce` и `eventModel` (идентичные названиям из еталона). | ⚠️ Нет реализации |
| 3 | Дополнить `purchase` / `lead` payload | `order_success.html:1783-2100` | Добавляем `affiliation`, `tax`, `shipping`, `coupon`, `item_brand`, `item_category`, `eventModel` + `event_id`, `fbp`, `fbc`. | ⚠️ Частично |
| 4 | Пробросить `event_id` + `fbp` + `fbc` в `dataLayer` повсеместно | `analytics-loader.js:86-360`, места `trackEvent` вызовов | Используем `window.generateEventId()` и `window.getTrackingContext()` и пушим значения в `dataLayer`. | ⚠️ Нет |
| 5 | Настройка GTM (переменные, триггеры, теги) | GTM UI | GA4 event tag читает `ecommerce`, Meta Pixel tag — `eventModel`. `event_id` передаем и в Pixel, и в CAPI для дедупликации. | ⚠️ ToDo |
| 6 | QA и мониторинг | GTM Preview, Meta Pixel Helper, feed checker | Проверка всех событий, сравнение ID с фидом, контроль EMQ в Meta Events Manager. | 🟡 В процесcе |

---

## 1. Архитектура и исходники

| Компонент | Файл/сервис | Назначение |
|-----------|-------------|------------|
| `trackEvent` мост | `twocomms/twocomms_django_theme/static/js/analytics-loader.js:86-360` | Генерация event_id, сбор `fbp`/`fbc`, отправка в Meta Pixel/TikTok/GA4 (`dataLayer.push({event, eventParameters})`). Сейчас payload для GTM недостаточен. |
| Data Layer события | `product_detail.html`, `main.js`, `order_success.html` | Непосредственные точки генерации `view_item`, `add_to_cart`, `begin_checkout`, `purchase`, `lead`. |
| Offer ID генератор | `twocomms/storefront/utils/analytics_helpers.py:1-110` | Функция `get_offer_id()` возвращает формат `TC-{product_id:04d}-{COLOR}-{SIZE}`. Используется `OrderItem.get_offer_id()` и CAPI. |
| Google Merchant Feed | `twocomms/storefront/management/commands/generate_google_merchant_feed.py:150-230` + `update_google_merchant_feed.sh` | Сейчас ID = `TC-{product.id}-{variant_key}-{size}`. Нужно синхронизировать с фронтом. |
| Conversions API | `twocomms/orders/facebook_conversions_service.py` | Серверная отправка Lead/Purchase. Берёт `event_id` из `Order.get_purchase_event_id()` и `get_lead_event_id()`. Критично, чтобы эти ID совпадали с браузерными событиями. |
| Cart Summary API | `twocomms/storefront/views/cart.py:748-950` (`/cart/summary/`) | Предоставляет `items[]`, `total`, `currency`. Используем для заполнения `ecomm_prodid` и `ecomm_totalvalue` в add_to_cart/begin_checkout. |
| Checkout payload в шаблоне | `twocomms/twocomms_django_theme/templates/pages/cart.html:603` | Скрытый `div#checkout-payload` содержит JSON со всеми товарами. `main.js:getCheckoutAnalyticsPayload()` читает его для InitiateCheckout. |
| Purchase payload | `twocomms/twocomms_django_theme/templates/pages/order_success.html:1783-2100` | Формирует `contents`, `user_data`, `lead_data`. Здесь проще всего обогатить `ecommerce` и `eventModel`. |

---

## 2. Синхронизация с Google Merchant Feed

### 2.1 Формат ID

- **Фид (сейчас):** `TC-{product.id}-{variant_key}-{size}` (пример: `TC-123-cv456-M`). См. `generate_google_merchant_feed.py:177`.
- **Фронт/Pixel/CAPI:** `get_offer_id()` → `TC-{product_id:04d}-{COLOR}-{SIZE}` (пример: `TC-0123-CHERNYI-M`). См. `analytics_helpers.py:31-75` и `OrderItem.get_offer_id()`.

🔧 **Решение:** внутри генератора фида вызвать `get_offer_id(product.id, color_variant_id, size)` и записывать его в `<g:id>`. Тогда:

```python
from storefront.utils.analytics_helpers import get_offer_id
...
g_id.text = get_offer_id(product_id=product.id,
                           color_variant_id=variant_id,
                           size=size)
```

После правки запустить `./update_google_merchant_feed.sh` и убедиться, что `https://twocomms.shop/media/google-merchant-v3.xml` содержит новые ID.

### 2.2 Поля, которые должны совпадать

| Feed (`g:*`) | Событие (`ecommerce`/`eventModel`) | Где взять |
|--------------|------------------------------------|-----------|
| `g:id` | `item_id`, `content_ids`, `eventModel.ecomm_prodid[]` | `get_offer_id()` / payloadы корзины и заказа |
| `g:brand` = `"TwoComms"` | `item_brand` | Константа — добавляем при формировании `items[]` |
| `g:product_type` | `item_category` / `eventModel.category` | `product.category.name` (см. `OrderItem.product.category`) |
| `g:price` | `price`, `value`, `eventModel.ecomm_totalvalue` | Уже доступно в payload (цена товара / сумма заказа) |
| `g:title` | `item_name` | Берём `product.title` (не нужно добавлять размер — он уже в ID) |

### 2.3 Проверка соответствия

```bash
# 1. Проверяем первые 10 ID из фида
curl -s https://twocomms.shop/media/google-merchant-v3.xml \
  | rg -o "TC-[0-9]{4}-[A-Z]+-[A-Z]+" | head -10

# 2. Сравниваем с событиями на реальном сайте (DevTools → Console)
window.dataLayer.filter(evt => evt.ecommerce && evt.ecommerce.items).map(evt => evt.ecommerce.items);
```

При расхождениях — блокировать деплой.

---

## 3. Базовые требования к `dataLayer`

1. **Единая структура:** каждый push содержит `event`, `event_id`, `fbp`, `fbc`, `user_data` (если есть PII), `ecommerce`, `eventModel`.
2. **`event_id`:**
   - Для динамических событий используем `window.generateEventId()` (`analytics-loader.js:86`).
   - Для `purchase`/`lead` используем `{{ order.get_purchase_event_id }}` / `{{ order.get_lead_event_id }}` (чтобы совпасть с CAPI).
   - Обязательно дублируем `event_id` в Meta Pixel payloadе (`trackEvent`) и в `eventModel`.
3. **`fbp`/`fbc`:** берём через `window.getTrackingContext()` (`analytics-loader.js:126`). Если `fbc` отсутствует — передаем `null`, а GTM/Pixel работает только с `fbp`.
4. **`user_data`:**
   - На этапе `purchase`/`lead` берём из формы (см. `order_success.html`).
   - Значения для Enhanced Conversions (GA4) можно передавать **нехешированными**, но для Meta Pixel `trackEvent` мы уже хешируем (`buildMetaUserData`).
5. **`ecommerce.items[]`:** должно соответствовать [GA4](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce#items). Минимум: `item_id`, `item_name`, `item_brand`, `item_category`, `item_variant` (цвет/размер), `price`, `quantity`, `currency`.
6. **`eventModel`:** используется для Meta Pixel (как в эталоне). Всегда включает `items[]`, `ecomm_prodid`, `ecomm_pagetype`, `ecomm_totalvalue`, `event_id`, `value`, `currency`, `content_name`. Названия **не изменяем**.
7. **Валюта:** `UAH` по умолчанию, uppercase. На уровне транзакции (`ecommerce.currency`). На уровне item допускается дублирование.
8. **`affiliation`, `tax`, `shipping`, `coupon`:** обязательны в `purchase`. Если значение 0 — передаем `0`/пустую строку.

---

## 4. GA4 ecommerce + Meta Pixel events

### 4.0 Карта соответствий

| dataLayer event | Meta Pixel event (`trackEvent`) | Описание |
|-----------------|-------------------------------|----------|
| `view_item` | `ViewContent` | Просмотр карточки товара |
| `add_to_cart` | `AddToCart` | Добавление в корзину |
| `begin_checkout` | `InitiateCheckout` | Нажатие «Оформити замовлення» / Monobank |
| `purchase` | `Purchase` | Успешная оплата (или подтверждение заказа) |
| `lead` | `Lead` | Предоплата 200 грн (pay_type `prepay_200`) |

Дальше — детальные спецификации. Все примеры используют **реальные** данные (TwoComms ID `TC-0123-CHERNYI-M`).

---

### 4.1 ViewContent ↔ view_item

**Где внедряем:** `twocomms/twocomms_django_theme/templates/pages/product_detail.html:814-860` (после `window.trackEvent('ViewContent', ...)`).

**Когда срабатывает:** через 200 мс после загрузки карточки товара (после вычисления `selection = getCurrentSelection()`).

**dataLayer push:**

```javascript
const selection = getCurrentSelection();
const ctx = window.getTrackingContext ? window.getTrackingContext() : {};
const viewEventId = window.generateEventId ? window.generateEventId() : Date.now();

window.dataLayer.push({
  event: 'view_item',
  event_id: viewEventId,
  fbp: ctx.fbp || null,
  fbc: ctx.fbc || null,
  ecommerce: {
    currency: 'UAH',
    value: price,
    items: [{
      item_id: selection.offerId,      // TC-0123-CHERNYI-M (совпадает с g:id)
      item_name: title,                // product.title
      item_brand: 'TwoComms',
      item_category: pe.dataset.category || '',
      item_variant: selection.size,
      price: price,
      quantity: 1
    }]
  },
  eventModel: {
    event_id: viewEventId,
    value: price,
    currency: 'UAH',
    content_name: title,
    items: [{ id: selection.offerId, name: title, price: price, quantity: 1 }],
    ecomm_prodid: selection.offerId,
    ecomm_pagetype: 'product',
    ecomm_totalvalue: price
  }
});
```

**Meta Pixel payload (уже есть, дополняем `event_id`):**

```javascript
window.trackEvent('ViewContent', {
  event_id: viewEventId,
  content_ids: [selection.offerId],
  content_type: 'product',
  content_name: title,
  content_category: pe.dataset.category || '',
  currency: 'UAH',
  value: price,
  contents: [{ id: selection.offerId, quantity: 1, item_price: price, item_name: title }]
});
```

**Примечания:**
- `selection.offerId` должен поступать из `data-current-offer-id`, который уже обновляется при смене размера/цвета.
- Если нет категории — передаем пустую строку, но лучше добавить `data-category` на `#product-analytics-payload` (он уже есть).
- QA: GTM Preview должен показать `event: view_item`, а Meta Pixel Helper — `ViewContent` с тем же `event_id`.

---

### 4.2 AddToCart ↔ add_to_cart

**Где внедряем:** `twocomms/twocomms_django_theme/static/js/main.js:1434-1595` (`trackAddToCartAnalytics`).

**Когда срабатывает:** после успешного ответа `/cart/add/` (уже вызывается `trackAddToCartAnalytics`).

**Данные:**
- `offerId`, `contentName`, `contentCategory`, `itemPrice`, `quantity` — уже есть в функции.
- `cart summary` для `ecomm_prodid` / `ecomm_totalvalue` получаем через `fetch('/cart/summary/')` (JSON содержит `items` с `offer_id`).

**dataLayer push:**

```javascript
const ctx = window.getTrackingContext ? window.getTrackingContext() : {};
const dlEventId = window.generateEventId ? window.generateEventId() : Date.now();

fetch('/cart/summary/')
  .then(res => res.json())
  .then(cart => {
    const cartItems = Array.isArray(cart.items) ? cart.items : [];
    const allIds = cartItems.length ? cartItems.map(item => item.offer_id) : [offerId];
    const totalValue = Number(cart.total) || value;

    window.dataLayer.push({
      event: 'add_to_cart',
      event_id: dlEventId,
      fbp: ctx.fbp || null,
      fbc: ctx.fbc || null,
      ecommerce: {
        currency: currency,
        value: value,
        items: [{
          item_id: offerId,
          item_name: contentName || '',
          item_brand: 'TwoComms',
          item_category: contentCategory || '',
          item_variant: triggerButton?.getAttribute('data-size') || '',
          price: itemPrice,
          quantity: quantity
        }]
      },
      eventModel: {
        event_id: dlEventId,
        value: value,
        currency: currency,
        content_name: contentName || '',
        items: [{ id: offerId, name: contentName || '', price: itemPrice, quantity: quantity }],
        ecomm_prodid: allIds,
        ecomm_pagetype: 'cart',
        ecomm_totalvalue: totalValue
      }
    });
  })
  .catch(() => {
    window.dataLayer.push({ ...fallback без cart summary... });
  });
```

**Meta Pixel payload:** дополняем существующий `trackEvent('AddToCart', payload)` полями `event_id`, `content_category`, `content_name`, `contents[].item_name` (уже есть). Важно: `payload.contents[0].brand = 'TwoComms'` уже реализовано — оставляем.

**QA:**
- `eventModel.ecomm_prodid` должен содержать **все** позиции из корзины.
- Проверяем `cart/summary/` в DevTools → Network, убеждаемся, что `offer_id` совпадает с фидом.

---

### 4.3 InitiateCheckout ↔ begin_checkout

**Где внедряем:** `main.js:612-840` в `bindMonoCheckout` и других местах, где вызывается `trackEvent('InitiateCheckout', ...)`.

**Источник данных:** `const analytics = getCheckoutAnalyticsPayload();` (читает `#checkout-payload` из `cart.html:603`). Там уже есть `analytics.contents`, `analytics.content_ids`, `analytics.value`, `analytics.num_items`.

**dataLayer push:**

```javascript
if (analytics) {
  const ctx = window.getTrackingContext ? window.getTrackingContext() : {};
  const checkoutEventId = window.generateEventId ? window.generateEventId() : Date.now();

  const ecommerceItems = analytics.contents.map(item => ({
    item_id: item.id,
    item_name: item.item_name || item.name || '',
    item_brand: 'TwoComms',
    item_category: item.item_category || '',
    price: item.item_price || item.price || 0,
    quantity: item.quantity || 1,
    currency: analytics.currency || 'UAH'
  }));

  window.dataLayer.push({
    event: 'begin_checkout',
    event_id: checkoutEventId,
    fbp: ctx.fbp || null,
    fbc: ctx.fbc || null,
    ecommerce: {
      currency: analytics.currency || 'UAH',
      value: analytics.value || 0,
      items: ecommerceItems
    },
    eventModel: {
      event_id: checkoutEventId,
      value: analytics.value || 0,
      currency: analytics.currency || 'UAH',
      items: ecommerceItems.map(item => ({
        id: item.item_id,
        name: item.item_name,
        price: item.price,
        quantity: item.quantity
      })),
      ecomm_prodid: analytics.content_ids || [],
      ecomm_pagetype: 'cart',
      ecomm_totalvalue: analytics.value || 0
    }
  });
}
```

**Meta Pixel payload:**

```javascript
window.trackEvent('InitiateCheckout', {
  event_id: checkoutEventId,
  value: analytics.value,
  currency: analytics.currency,
  num_items: analytics.num_items,
  payment_method: 'monobank',
  content_ids: analytics.content_ids,
  contents: analytics.contents
});
```

**QA:**
- Проверить, что `#checkout-payload` существует на странице (DevTools → `document.getElementById('checkout-payload')`).
- В GTM Preview после кнопки Monobank должно появиться событие `begin_checkout`.

---

### 4.4 Purchase ↔ purchase

**Где внедряем:** `order_success.html:1783-2100` (в блоке `shouldSendPurchase`).

**Данные:**
- `orderNumber`, `purchaseValue`, `currency`, `contents` (`[{id, quantity, price, name}]`).
- `user_data` (нехешированные), `fbUserData` (хешированные — для Meta Pixel).
- `event_id = {{ order.get_purchase_event_id }}` — совпадает с CAPI.

**dataLayer push:**

```javascript
const ctx = window.getTrackingContext ? window.getTrackingContext() : {};
const purchaseEventId = '{{ order.get_purchase_event_id }}';
const affiliation = 'TwoComms';
const taxValue = parseFloat(el.dataset.tax || '0') || 0;
const shippingValue = parseFloat(el.dataset.shipping || '0') || 0;
const couponCode = el.dataset.coupon || '';

const ecommerceItems = contents.map(item => ({
  item_id: item.id,
  item_name: item.name || 'Product ' + item.id,
  item_brand: 'TwoComms',
  item_category: item.category || '',
  item_variant: item.variant || '',
  price: item.price || 0,
  quantity: item.quantity,
  currency: currency
}));

const purchaseData = {
  event: 'purchase',
  event_id: purchaseEventId,
  fbp: ctx.fbp || window.readCookieValue?.('_fbp') || null,
  fbc: ctx.fbc || window.readCookieValue?.('_fbc') || null,
  user_data: userData,               // GA4 Enhanced Conversions (нехешированное)
  ecommerce: {
    transaction_id: orderNumber,
    affiliation: affiliation,
    value: purchaseValue,
    currency: currency,
    tax: taxValue,
    shipping: shippingValue,
    coupon: couponCode,
    items: ecommerceItems
  },
  eventModel: {
    event_id: purchaseEventId,
    transaction_id: orderNumber,
    affiliation: affiliation,
    value: purchaseValue,
    currency: currency,
    tax: taxValue,
    shipping: shippingValue,
    coupon: couponCode,
    content_name: 'Order ' + orderNumber,
    items: ecommerceItems.map(item => ({
      id: item.item_id,
      name: item.item_name,
      price: item.price,
      quantity: item.quantity
    })),
    ecomm_prodid: contents.map(item => item.id),
    ecomm_pagetype: 'purchase',
    ecomm_totalvalue: purchaseValue
  }
};

window.dataLayer.push(purchaseData);
```

**Meta Pixel payload:** (добавляем `fbp`/`fbc`/`user_data` в `__meta`)

```javascript
const purchaseMeta = {
  event_id: purchaseEventId,
  user_data: fbUserData,
  external_id: externalHash || null,
  fbp: purchaseData.fbp,
  fbc: purchaseData.fbc
};

window.trackEvent('Purchase', {
  event_id: purchaseEventId,
  value: purchaseValue,
  currency: currency,
  content_type: 'product',
  content_ids: contents.map(item => item.id),
  content_name: 'Order ' + orderNumber,
  contents: contents.map(item => ({
    id: item.id,
    quantity: item.quantity,
    item_price: item.price || 0,
    item_name: item.name || ''
  })),
  __meta: purchaseMeta
});
```

**QA:**
- Проверить GTM Preview → `purchase` event содержит все поля.
- В Events Manager Meta EMQ ≥ 8/10 (при наличии `fbp`, `fbc`, hashed user data).
- CAPI и Pixel события объединяются по `event_id = {{ order.get_purchase_event_id }}` (проверяем в Meta Events Manager → Diagnostics → Deduplication).

---

### 4.5 Lead ↔ lead

**Где внедряем:** `order_success.html:2050-2100` (блок `shouldSendLead`).

**Сценарий:** заказы с `pay_type = prepay_200` (предоплата 200 грн). Здесь важно отправлять `Lead` и в Pixel, и в GA4 (кастомное событие `lead`).

**dataLayer push:**

```javascript
const leadEventId = '{{ order.get_lead_event_id }}';
const ctx = window.getTrackingContext ? window.getTrackingContext() : {};

const leadPayload = {
  event: 'lead',
  event_id: leadEventId,
  fbp: ctx.fbp || purchaseData.fbp || null,
  fbc: ctx.fbc || purchaseData.fbc || null,
  user_data: userData,
  lead_data: {
    order_id: orderNumber,
    value: leadValue,
    currency: currency,
    payment_status: paymentStatus
  },
  eventModel: {
    event_id: leadEventId,
    value: leadValue,
    currency: currency,
    content_name: 'Lead ' + orderNumber,
    ecomm_prodid: contents.map(item => item.id),
    ecomm_pagetype: 'lead',
    ecomm_totalvalue: leadValue
  }
};

window.dataLayer.push(leadPayload);
```

**Meta Pixel payload:**

```javascript
window.trackEvent('Lead', {
  event_id: leadEventId,
  value: leadValue,
  currency: currency,
  content_ids: contents.map(item => item.id),
  content_type: 'product',
  __meta: {
    event_id: leadEventId,
    user_data: fbUserData,
    external_id: externalHash || null,
    fbp: leadPayload.fbp,
    fbc: leadPayload.fbc
  }
});
```

**QA:**
- Проверить, что события `lead` и `purchase` не дублируются (используем `sessionStorage` как сейчас).
- В Meta Pixel Helper должны одновременно появиться `Lead` (на сумму 200) и, если полная оплата, `Purchase`.

---

## 5. Конфигурация GTM

### 5.1 Data Layer variables (все тип — Data Layer Variable)

| Имя в GTM | Путь | Примечание |
|-----------|------|------------|
| `dl.event` | `event` | Стандарт |
| `dl.event_id` | `event_id` | Используем в Meta Pixel шаблоне |
| `dl.ecommerce` | `ecommerce` | Объект; используем в GA4 Event Tag |
| `dl.eventModel` | `eventModel` | Объект для Meta Pixel |
| `dl.fbp` | `fbp` | Для передачи в Pixel |
| `dl.fbc` | `fbc` | Для передачи в Pixel |
| `dl.user_data` | `user_data` | Для Enhanced Conversions |
| `dl.lead_data` | `lead_data` | Только для lead |

### 5.2 Triggers

- `event equals view_item`
- `event equals add_to_cart`
- `event equals begin_checkout`
- `event equals purchase`
- `event equals lead`

### 5.3 Tags

1. **GA4 Event Tag** (тип GA4 → Event):
   - Event Name: `{{dl.event}}`
   - Items: `{{dl.ecommerce.items}}`
   - Value: `{{dl.ecommerce.value}}`
   - Currency: `{{dl.ecommerce.currency}}`
   - Для purchase: заполнить Transaction ID, Tax, Shipping, Coupon.

2. **Meta Pixel Tag** (Custom HTML или Template):
   - Event Name: мапим `view_item → ViewContent`, `add_to_cart → AddToCart`, и т.д.
   - Payload: `{{dl.eventModel}}`
   - Event ID: `{{dl.event_id}}`
   - `fbp`/`fbc`: брать из Data Layer переменных.
   - user_data: для purchase/lead брать `{{dl.user_data}}` (GTM макрос JSON → объект).

3. **TikTok/другие пиксели** — при необходимости можно также читать `eventModel`.

### 5.4 Дедупликация с CAPI

- `facebook_conversions_service.py` уже использует `order.get_purchase_event_id()` / `get_lead_event_id()`.
- В GTM Meta Pixel Tag обязательно вставляем `event_id = {{dl.event_id}}`.
- В Meta Events Manager → Diagnostics нужно убедиться, что события приходят один раз.

---

## 6. QA и мониторинг

1. **GTM Preview Mode:**
   - Проверить каждое событие на реальном сайте / staging.
   - Убедиться, что в `Data Layer` → `ecommerce.items` присутствует весь массив товаров.
2. **Meta Pixel Helper / TikTok Pixel Helper:**
   - Отслеживать `event_id` (должен совпадать с `dataLayer.event_id`).
3. **Google Tag Assistant (GA4):**
   - Проверить, что `purchase` содержит `transaction_id`, `items`, `tax`, `shipping`.
4. **Feed Checker:**
   - После синхронизации ID прогнать ручной скрипт (см. раздел 2.3) или `python manage.py generate_google_merchant_feed` локально и сравнить ID с `curl`.
5. **Meta Events Manager → Test Events:**
   - Включить Test ID в `analytics-loader.js` (если нужно) и убедиться, что `event_id` корректен.
6. **Логи CAPI:**
   - `twocomms/orders/facebook_conversions_service.py` логирует `Generated Purchase event_id...`. Сопоставить с браузерным `event_id`.

---

## 7. Будущее: GTM Server-Side (sGTM)

- Планируется перенос CAPI в sGTM. Пока оставляем генерацию `event_id` на фронте/сервере.
- После внедрения sGTM можно использовать `{{Event ID}}` (gtm.uniqueEventId). Пока важно просто передавать `event_id` в Data Layer.
- sGTM позволит автоматически подставлять `fbp/fbc` и управлять задержками. Но без корректного `dataLayer` переход невозможен.

---

## 8. Документация и полезные ссылки

- [GA4 Ecommerce Events](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce)
- [GA4 Items Object](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce#items)
- [Meta Pixel Standard Events](https://developers.facebook.com/docs/facebook-pixel/reference)
- [Meta Pixel Server-Side Deduplication](https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events/)
- [Google Merchant Center Feed Specs](https://support.google.com/merchants/answer/7052112)
- [GTM Data Layer Guide](https://developers.google.com/tag-manager/devguide)

---

## 9. Next steps (чтобы не забыть)

1. [ ] Синхронизировать ID фида с `get_offer_id()` и перегенерировать feed.
2. [ ] Дописать `view_item` / `add_to_cart` / `begin_checkout` `dataLayer.push()` в `main.js` и `product_detail.html`.
3. [ ] Дополнить `purchase`/`lead` в `order_success.html` (brand/category/affiliation/tax/shipping/coupon + eventModel).
4. [ ] Протянуть `event_id`/`fbp`/`fbc` в каждый push.
5. [ ] Настроить GTM теги и проверить дублирование.
6. [ ] Пройтись по чек-листу QA и зафиксировать результат в `META_PIXEL_VALIDATION_AND_QA_2025.md`.

После выполнения всех шагов можно запускать загрузку на сервер и мониторить EMQ/ROAS в Meta.
