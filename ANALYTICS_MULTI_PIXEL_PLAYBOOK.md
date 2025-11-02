# Multi-Platform Pixel & Tag Playbook (Meta, TikTok, Google)

_Версия: 2025-11-02 · Автор: Codex агент_  
_Назначение документа: дать следующему агенту «карту местности» по текущей реализации пикселей TwoComms и описать доработки, необходимые для устойчивого запуска рекламы одновременно в Meta, TikTok и через Google Tag Manager._

---

## 1. Текущее состояние интеграции

- **Общий каркас**: шаблон `twocomms/twocomms_django_theme/templates/base.html` содержит:
  - атрибуты `data-*` на корневом `<html>` для передачи ID-пикселей (`data-meta-pixel-id`, `data-tiktok-pixel-id`, `data-ga-id`, `data-clarity-id`);
  - контейнер `#am` для Advanced Matching (Meta).
- **Ленивая загрузка**: `twocomms/twocomms_django_theme/static/js/analytics-loader.js?v=2` через `window.trackEvent` распределяет события в:
  - Meta Pixel (`fbq`);
  - TikTok Pixel (`ttq`);
  - GA4 / GTM (`dataLayer`/`gtag`);
  - Yandex Metrica (если указан ID).
- **События** приходят из front-end (`main.js`, `product_detail*.html`, `cart.html`, `order_success.html` и др.), которые вызывают `window.trackEvent`.
- **Conversions API (Meta)** подключён на сервере (`twocomms/orders/facebook_conversions_service.py`) с дедупликацией `event_id`.
- **CSP** в `twocomms/twocomms/settings.py` уже whitelists для Meta, TikTok, Google.

### Ключевые проблемы (см. также `META_PIXEL_FINAL_REPORT.md`)
1. **Дублирование AddToCart**: одновременно прямой `fbq` + `trackEvent` → нужно оставить единый путь через `trackEvent`.
2. **ViewContent до инициализации loader**: inline-скрипты карусели вызывают `trackEvent`, когда `analytics-loader.js` ещё не успел создать глобал – требуется defer.
3. **ID товаров**: события используют `product.id`, тогда как фид/каталог — формат `TC-{product.id:04d}-{COLOR}-{SIZE}` → надо унифицировать через сервер или data-атрибуты.
4. **Lead «шумит»**: логин и клики в корзине шлют Lead → для платных аудиторий следует оставить «чистые» лиды (формы/обратная связь).
5. **Поведение при блокировщиках**: метки в `sessionStorage` фиксируют Purchase даже при провале `fbq`/`ttq` → нужно переписать на обработку через буферы и ретраи.

---

## 2. Рекомендации для Meta Pixel

### 2.1 Техническая реализация
- **Базовый код**: оставляем встроенный bootstrap в `<head>` (как сейчас), но запускаем `loadMetaPixel()` без искусственной задержки либо с минимальной (100 мс), чтобы PageView не терялся.
- **Advanced Matching**:
  - Контейнер `#am` уже заполняется; убедиться, что в Twig он есть на всех страницах (в том числе лейауты CMS, промо-страницы).
  - Для серверных заказов синхронизировать поля `fn`, `ln`, `em`, `ph` – они уже передаются, но проверяем escape.
- **Events API**:
  - Дедупликация настроена, важно строго синхронизировать `event_id` между фронтом и CAPI.
  - При добавлении новых кликов на кнопки / CTA всегда указывайте `event_id` и отправляйте тот же ID в CAPI, если событие подтверждается сервером.

### 2.2 Бизнес-логика событий
- **ViewContent**: инициировать через `trackEvent` после того, как карточка полностью готова (вариант: подписаться на `DOMContentLoaded` / IntersectionObserver). Обязательно передавать `content_ids`, `content_name`, `currency`, `value`.
- **AddToCart**: оставить один вызов (через `trackEvent`). В payload передавать массив `contents` (`[{id, quantity, item_price}]`), это упростит ретаргетинг в Advantage+ Catalog Ads.
- **InitiateCheckout**: вызывать на событие «перешёл к оплате». Сейчас 3 места вызывают — согласовать, чтобы не было дублей (использовать `once` флаги).
- **Purchase**: отправка только после подтверждения Monobank (успех оплаты). Следующая итерация — добавить `event_source_url`, `order_id`, `num_items`, `coupon`.
- **Lead**: ограничить реальными лид-формами (подписка, обратная связь). В остальном используйте кастомные события (например, `LoginAttempt`, `CheckoutClick`).

### 2.3 Подготовка к рекламе
- **Каталожные кампании**: строгое совпадение `content_ids` с фидом → используйте server-side функцию, которая генерирует `offer_id` и прокидывает в `data-product-offer-id`.
- **Отслеживание LTV**: добавьте кастомные события для подписки на рассылку, повторной покупки, апселлов. Подготовьте аудитории «Просмотрели X, но не купили».
- **A/B тесты**: для Advantage+ лучше избегать «шумных» событий. Разделите аудитории: ViewContent (теплые), AddToCart/InitiateCheckout (горячие), Purchase (конверсии).

---

## 3. Рекомендации для TikTok Pixel

### 3.1 Техническая реализация
- **Базовый код** уже в `<head>`. Проверить, что `analytics-loader.js` устанавливает флаг `__ttqPixelLoaded`. В случае блокировки планируется console.debug.
- **Events**: используем те же `trackEvent`. TikTok поддерживает стандартные имена событий (см. [TikTok Events API Docs](https://ads.tiktok.com/help/article?aid=10028)).
  - `ttq.track('Browse')` или `ViewContent`? Для синхронизации с TikTok Ads Manager лучше использовать **официальные названия**: `ViewContent`, `AddToCart`, `InitiateCheckout`, `Purchase`, `SubmitForm`, `Subscribe`.
  - Payload: `content_id`, `content_type`, `value`, `currency` (все uppercase), при возможности `contents`.
- **Event ID**: TikTok поддерживает `ttq.track` с опцией `event_id`. Добавьте поле для синхронизации с сервером (понадобится, если подключим TikTok Events API).
- **Consent**: если будет баннер, синхронизируйте вызовы `holdConsent()/grantConsent()` из TikTok SDK (уже подготовлены методы).
- **PII / identify**: TikTok рекомендует передавать хэши PII через `ttq.identify`. В текущем проекте нужно:
  1. Добавить helper (на фронте) для хеширования email/phone/внутреннего ID по SHA-256 (аналоги уже есть для Meta Advanced Matching — можно переиспользовать);
  2. Вызывать `ttq.identify` **после** того как в DOM появляется контейнер `#am` с данными, но **до** любого события (`ViewContent`, `AddToCart` и т.д.);
  3. Хранить/кэшировать подготовленные хэши в data-атрибутах, чтобы не пересчитывать на каждом клике.

### 3.2 Маркетинговые советы
- Цель — оптимизация по `Purchase` / `CompletePayment`. Важно, чтобы хотя бы `ViewContent` и `AddToCart` имели стабильный объём (>50/нед).
- Используйте `ttq.identify` для передачи hashed email/phone, если пользователи авторизованы (по аналогии с Meta Advanced Matching).
- Для Spark Ads и collection ads TikTok требует `content_category` и `content_name` — добавьте эти поля в payload.

### 3.3 Матрица событий TikTok (с учётом официального шаблона)
| Событие TikTok       | Источник данных в проекте | Обязательные поля (TikTok)                                                                                                                      | Комментарии |
|----------------------|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| `ViewContent`        | `trackEvent('ViewContent')` (карточка товара, просмотр модалки) | `contents[0].content_id`, `content_type`, `content_name`, `content_category`, `price`, `brand`, `value`, `currency`, `event_id`                 | `content_id` должен совпадать с оффером. `event_id` можно генерировать через UUID и реиспользовать в CAPI/Events API. |
| `AddToWishlist`      | `trackEvent('AddToWishlist')` | `contents` (с количеством), `value`, `currency`, `event_id`                                                                                     | Сейчас payload проще — нужно расширить объект до требуемого формата. |
| `Search`             | `trackEvent('Search')` (поиск, подсказки) | `search_string`, при наличии `contents` (результаты), `currency`, `value`, `event_id`                                                           | `contents` можно составить из первых N товаров выдачи. |
| `AddPaymentInfo`     | `trackEvent('StartPayment')` / момент выбора оплаты | `contents`, `value`, `currency`, `event_id`                                                                                                      | Важно различать `AddPaymentInfo` и `InitiateCheckout`: первое фиксирует подтверждение платёжного метода. |
| `AddToCart`          | `trackEvent('AddToCart')` | `contents`, `value`, `currency`, `event_id`                                                                                                      | Уже описано — нужно обогащать `contents` объектами `{content_id, content_type, content_name, price, brand, num_items}`. |
| `InitiateCheckout`   | `trackEvent('InitiateCheckout')` | `contents`, `value`, `currency`, `description` (IP), `event_id`                                                                                    | IP можно получить через сервер (или оставить пустым — поле не критично). |
| `PlaceAnOrder`       | `trackEvent('Purchase')` (Monobank успех) | `contents`, `value`, `currency`, `status`, `description`, `event_id`                                                                             | TikTok называет событие `PlaceAnOrder`, но по факту оптимизирует по `Purchase`. Имеет смысл отправлять оба (с одинаковым `event_id`). |
| `CompleteRegistration` | `trackEvent('CompleteRegistration')` | `contents`, `value`, `currency`, `event_id`                                                                                                      | Payload можно минимизировать: `value` = 0, `currency` = "UAH". |

**Заметки:**
- В официальном примере TikTok просит `description` = IP-адрес. Передавать IP из браузера нельзя (GDPR). Вместо этого можно использовать текстовое описание (например, «web_checkout»). При серверной интеграции IP добавляется автоматически.
- `event_id` должен быть одинаковым между фронтом и TikTok Events API, иначе будут задвоения. Логика генерации может совпадать с Meta (`uuidv4()` + order_id).
- В `contents` желательно передавать не более 10 элементов (TikTok ограничивает payload).

### 3.4 Интеграция с общим слоем `trackEvent`
Рекомендуется:
1. Создать mapper `buildTikTokPayload(eventName, payload)` внутри `analytics-loader.js`, который преобразует «голый» `trackEvent`-payload в требуемый TikTok формат (та же идея, что и у Meta).
2. Вынести генерацию `contents` в утилиту, чтобы Meta, TikTok и GA4 использовали один и тот же источник правды.
3. `ttq.identify` вызывать один раз на страницу (при загрузке), хранить флаг `__ttqIdentifySent`, чтобы не спамить повторно.

---

## 4. Google Tag Manager / GA4

### 4.1 Состояние
- GTM контейнер грузится из `analytics-loader.js`. Текущий код создаёт `dataLayer` и push’ит `event`.
- События `trackEvent` дублируются в `gtag('event', eventName, payload)` → в GTM можно ловить по `event`.

### 4.2 Рекомендации
- **Стандартизируйте payload**: использовать `items` (GA4) вместо `content_ids`. Пример:
  ```js
  {
    event: 'add_to_cart',
    ecommerce: {
      currency: 'UAH',
      value: 2199,
      items: [{item_id: 'TC-0007-BLK-M', item_name: 'Худі', quantity: 1, item_category: 'Hoodies'}]
    }
  }
  ```
  Параллельно можно пушить кастомный объект для Meta/TikTok, но важно синхронизировать названия.
- **Consent Mode**: если планируются кампании Google Ads, интегрируйте `gtag('consent', 'default', {...})` + передачу статуса из баннера.
- **Server-Side GTM**: в перспективе перенести Meta/TikTok на серверный контейнер, что облегчит управление блокировками.
- **GAds Remarketing**: убедитесь, что `send_page_view` включён и `dataLayer` имеет ecommerce-события для динамических ремаркетинговых кампаний.

---

## 5. Единая стратегия событий

| User action                        | trackEvent payload (целевое состояние)                                                                                                                                     | Отправка в Meta | TikTok | GA4 / GTM | Примечания |
|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------|--------|-----------|-----------|
| PageView (любая страница)          | `{page_type, page_path}`                                                                                                                                                   | ✅ (авто)        | ✅ (ttq.page) | ✅ (gtag config) | Следить за скоростью загрузки |
| ViewContent (карточка товара)      | `{content_ids: ['TC-0007-BLK-M'], content_type: 'product', content_name, currency: 'UAH', value: 2199, contents: [{id, item_price, quantity}]}`                           | ✅               | ✅      | ✅ (`view_item`) | Триггерить после готовности данных |
| AddToCart                          | `{content_ids: [...], contents: [...], currency, value, num_items}`                                                                                                       | ✅               | ✅      | ✅ (`add_to_cart`) | Убрать прямые вызовы `fbq` |
| InitiateCheckout                   | `{content_ids, value, currency, num_items, checkout_step}`                                                                                                                | ✅               | ✅      | ✅ (`begin_checkout`) | Следить за дублями |
| Purchase (Monobank success)        | `{event_id, transaction_id, contents, value, currency, num_items, payment_method, shipping_method}`                                                                       | ✅ + CAPI        | ✅ (подготовка) | ✅ (`purchase`) | Нужен retry при блокировщиках |
| Lead / SubmitForm (контакты)       | `{lead_type, contact_method}`                                                                                                       | ✅               | ✅ (`SubmitForm`) | ✅ | Использовать только на реальных заявках |
| Search                             | `{search_string}`                                                                                                                                                         | ✅               | ❌ (опц.) | ✅ (`search`) | В TikTok можно опустить либо маппить на `Search` |
| Add/Remove Wishlist                | `{content_ids, content_type}`                                                                                                                                             | ✅               | Опц.    | ✅ (`add_to_wishlist`) | Для TikTok можно использовать `AddToWishlist` |
| CustomizeProduct / Variant select  | `{content_ids, variant_id}`                                                                                                                                                | ✅ (custom)      | Опц. (`SelectProduct`) | ✅ (`view_item`) | Рассмотреть объединение с ViewContent |

---

## 6. Дополнительные проверки и TODO

1. **Синхронизация ID**:
   - Создать helper (Python) для формирования `offer_id` и прокинуть его в шаблоны и JS.
   - Предусмотреть тесты (Django + Cypress) для сопоставления `content_ids` ↔ фид.
2. **Буферизация событий**:
   - `analytics-loader.js` уже буферизует события при отсутствии `ttq`/`fbq`; но нужно очищать буфер только после успешного `track`.
   - Добавить повторную отправку из `sessionStorage`, если страница закрывается до загрузки пикселя.
3. **Документирование**:
   - Обновить `META_PIXEL_FINAL_REPORT.md`, включив раздел о TikTok/Google или сослаться на текущий файл как «общий плейбук».
   - В README проекта добавить ссылку на данный документ и краткий чек-лист релиза.
4. **QA**:
   - Использовать Pixel Helper (Meta), TikTok Pixel Helper и Google Tag Assistant в режиме инкогнито с отключенными блокировщиками.
   - Снять HAR и убедиться, что запросы уходят на `www.facebook.com/tr`, `analytics.tiktok.com`, `www.google-analytics.com`.
   - Провести smoke-тест с реальным заказом в тестовом режиме Monobank → проверить, что CAPI и фронт совпадают по `event_id`.

---

## 7. План улучшений на следующие спринты

1. **Единый слой данных (`dataLayer`)**:
   - Ввести объект `window.analyticsContext` с нормализованными полями → `trackEvent` конвертирует под каждую сеть.
2. **Server-Side расширение**:
   - Подготовить TikTok Events API (аналог CAPI) → потребуется `access_token` и `pixel_code`.
3. **Consent & GDPR**:
   - Добавить баннер согласия и интегрировать с Meta/TikTok (`holdConsent`/`grantConsent`) и Google Consent Mode.
4. **Performance**:
   - Перевести Meta/TikTok загрузчики в `<script type="module">` с динамическим импортом (или оставить текущий inline, но пометить `nonce` для CSP).
5. **Отчётность**:
   - Настроить Looker Studio / Power BI с данными Meta/TikTok/GA4 для мониторинга воронки.

---

## 8. Как пользоваться этим документом

- **Перед правками**: сверка с Live (произвольная страница) → убедиться, что inline скрипты не отличны от репозитория.
- **При внедрении новой акции/лендинга**: копируйте контейнер `#am`, атрибуты `data-*` и подключение `analytics-loader.js?v=2`.
- **При появлении новых событий**:
  1. Описать событие в таблице (раздел 5).
  2. Добавить в `trackEvent` правильный payload.
  3. Проверить отправку в каждой сети.
  4. При необходимости обновить серверную часть (CAPI / Events API).

Если у следующего агента есть вопросы или нужны примеры payload’ов — смотреть исходники `main.js` (фильтр по `trackEvent`) и этот плейбук.

---

_Готово. Если документ нужно расширить, добавьте дату/инициалы в заголовке и опишите изменения кратко в начале._ 
