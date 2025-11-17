# ✅ FACEBOOK PIXEL IMPROVEMENT CHECKLIST

## Найденные проблемы
- Гостевые заказы не сохраняли email, из-за чего Purchase/Lead события теряли ключевой идентификатор и Advanced Matching не получал данных.
- Браузерные события ViewContent/AddToCart/InitiateCheckout/AddPaymentInfo не передавали `user_data`/`external_id`, хотя Conversions API использует их для дедупликации.
- Для гостей не было устойчивого источника данных: введённые значения не переиспользовались на других страницах, поэтому ViewContent/AddToCart шли только с IP/UserAgent.
- Нормализация города отличалась между браузером и сервером (браузер не убирал спецсимволы перед хешированием).

## Реализованные улучшения
1. **Сбор email гостей**
   - Добавлено поле `email` в модель `Order` (+ миграция `0038_order_email.py`).
   - Формы на странице корзины теперь предлагают указать email (опционально), проверяют валидность и передают его в `process_guest_order`, Monobank Checkout и классический checkout.
2. **Кэширование данных гостей**
   - Клиентский JS сохраняет `full_name/phone/city/email` в `sessionStorage` и восстанавливает их при повторном визите.
   - После успешной оплаты данные очищаются, чтобы не отправлять устаревшие значения.
3. **Единый сбор user_data**
   - В `analytics-loader.js` добавлена функция `buildUserDataForEvent()`, которая хеширует email/phone/name/city, синхронизирует нормализацию города и генерирует `external_id` по схеме (`user:` → `session:` → временный ID).
   - Все ключевые события (`ViewContent`, `AddToCart`, `InitiateCheckout`, `AddPaymentInfo`) теперь добавляют `__meta` с user_data/fbp/fbc/external_id и уникальным `event_id`.
4. **ViewContent улучшения**
   - События на карточке и на листингах получают единый `event_id`, а в шаблоне product_detail добавлен fallback на `buildUserDataForEvent`.
5. **Order Success**
   - `data-email` берётся из заказа для гостей, а нормализация города синхронизирована с сервером; после Purchase/Lead гостевые данные очищаются.

## Что перепроверить после деплоя
1. **Миграции** – применить `python manage.py migrate orders 0038` на продакшене и убедиться, что админка отображает новое поле.
2. **Event Match Quality** – после раскатки проверить в Events Manager покрытие user_data для ViewContent/AddToCart/InitiateCheckout и убедиться, что `external_id`/`email` отображаются в Test Events.
3. **Добавление в корзину гостем** – пройти сценарий без авторизации, убедиться, что email сохраняется, события содержат user_data, а в sessionStorage после оплаты нет `_twc_guest_*`.
4. **Monobank Checkout** – создать заказ через Mono checkout/MonoPay и проверить, что email появляется в заказе и в Conversions API.
5. **Отчистка старых данных** – убедиться, что существующие заказы без email корректно отображаются и что отчёты/интеграции не завязаны на обязательности поля.
