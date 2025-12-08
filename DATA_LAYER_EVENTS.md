# Data Layer события (GTM) — краткое руководство

Документ описывает, какие события мы отправляем в `dataLayer` и какие ключи несут значения. Без кода, только структура и логика.

## Базовый формат payload
- `event`: имя события (`view_item`, `add_to_cart`, `begin_checkout`, `purchase`).
- `event_id`: уникальный ID (используется и в Pixel/CAPI для дедупликации).
- `fbp` / `fbc`: считываются из cookie/TrackingContext, нужны для Meta.
- `ecommerce`: объект для GA/GTM e-commerce.
- `eventModel`: дублирует данные в дружелюбном для ремаркетинга виде (`ecomm_*`, `items`).
- `user_data`: добавляется, если есть данные пользователя (email/phone/имя/город); у гостя может быть пустым.

> Значения `items`: всегда массив объектов с `item_id`, `item_name`, `item_brand="TwoComms"`, `item_category`, `item_variant` (размер), `price`, `quantity`, `currency` (UAH).

## События

### 1) `view_item` (карточка товара)
- Когда: загрузка product_detail, после определения выбранного размера/offer_id.
- Значения:
  - `ecommerce.value`: цена текущего SKU.
  - `eventModel.ecomm_pagetype`: `product`.
  - `ecomm_prodid`: `[offer_id]`.
  - `items`: один товар с ценой и выбранным размером.
- Пользователь: если есть `buildUserDataForEvent` → добавляем хеши/данные (для зарегистрированного или если гостевой ввод сохранён).

### 2) `add_to_cart`
- Когда: клик “Добавить в корзину” (в том числе из мини/карточек).
- Значения:
  - `ecommerce.value`: `item_price * quantity` (стоимость добавляемой позиции).
  - `eventModel.ecomm_pagetype`: `cart`.
  - `ecomm_prodid`: offer_id добавляемой позиции + snapshot корзины (если доступен).
  - `ecomm_totalvalue`: сумма корзины из snapshot (`/cart/items/`), fallback — текущая позиция.
  - `items`: только добавляемая позиция (brand/category/variant включены).
- Пользователь: `user_data` если есть (авторизован или данные из формы).

### 3) `begin_checkout`
- Когда: старт Monobank checkout/оплаты (кнопки с `data-mono-checkout-trigger` / `data-monobank-pay-trigger`).
- Значения:
  - Источник данных: hidden `#checkout-payload` на странице (value, currency, num_items, content_ids, contents).
  - `ecommerce.value`: сумма корзины на момент клика.
  - `eventModel.ecomm_pagetype`: `cart`.
  - `ecomm_prodid`: список offer_id из корзины.
  - `items`: все позиции из корзины с ценой/кол-вом.
- Пользователь: `user_data` если есть (auth/guest поля).

### 4) `purchase`
- Когда: страница `order_success` после успешной оплаты (полной или предоплаты).
- Значения:
  - `ecommerce.transaction_id`: `order_number`.
  - `ecommerce.value`: **полная сумма заказа** (даже при предоплате).
  - `tax`, `shipping`, `coupon`: из заказа.
  - `eventModel.ecomm_pagetype`: `purchase`.
  - `ecomm_totalvalue`: полная сумма заказа.
  - `items`: все товары заказа с ценой/размером/категорией.
- Пользователь:
  - Авторизованный: email/phone/имя/город попадают в `user_data`.
  - Гость: берем введённые поля, если доступны; иначе `user_data` может отсутствовать.
- Дедупликация: браузерный push один раз на заказ (sessionStorage `gtm_purchase_{orderId}`), event_id совпадает с CAPI для Meta.

## Общие заметки
- `fbp/fbc` кладём в событие для Meta dedup.
- `event_id` единый для dataLayer и bridge `trackEvent` (Meta/TT), чтобы CAPI и Pixel совпадали.
- Валюта всегда `UAH`.
- Если данных пользователя нет — `user_data` опускаем, структура не ломается.
