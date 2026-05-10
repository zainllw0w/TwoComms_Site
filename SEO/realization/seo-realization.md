# SEO Realization — TwoComms

> Документ имплементации улучшений SEO. Ведётся пошагово. После каждой фазы —
> коммит и деплой на сервер. Если работа продолжается другим агентом — читать
> этот файл целиком, смотреть раздел **Status** и продолжать с первой
> незавершённой фазы.

---

## Контекст и инфраструктура

- **Хостинг:** shared cPanel (qlknpodo@195.191.24.169), Python 3.14, virtualenv
  по пути `/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14`. Код по
  пути `/home/qlknpodo/TWC/TwoComms_Site/twocomms`.
- **Доступ:** `sshpass -p '***REMOVED_SSH_PASSWORD***' ssh -o StrictHostKeyChecking=no
  qlknpodo@195.191.24.169 "bash -lc '...'"`. Все миграции и команды выполняем
  на сервере (БД и медиа там).
- **Redis / Celery:** ОТСУТСТВУЮТ. Никакого нового кода с `@shared_task`,
  `.delay()`, `apply_async`. Async-работу выполняем:
  - синхронно в `transaction.on_commit` (для лёгких задач — IndexNow);
  - через cron + management-команды (фиды, пакетная AI-генерация).
- **Cron уже настроен** для `generate_prom_feed` (00:00, 12:00) и др.

## Архитектурные решения (зафиксированы пользователем)

1. **URL-формат вариантов:** path-сегменты + canonical.
   `/<slug>/<color-slug>/<size>/<fit>/`. Базовый URL `/<slug>/` — каноничен.
   Варианты имеют `rel=canonical` либо на себя (если индексируем), либо на
   базовый. Стратегия canonical уточняется в Phase 7.

2. **AI — строго по галочке.** По умолчанию AI выключен. Чекбокс
   `ai_generation_enabled` у Product и Category. Метатеги/Schema всегда отдают
   приоритет ручным `seo_*` полям; `ai_*` используется только если флаг
   включён И `seo_*` пусты; иначе fallback на `short_description`/категорию.

3. **Переключение варианта без перезагрузки страницы:** History API
   (`pushState`) + точечное обновление DOM (галерея, цена, кнопки, title,
   meta description, JSON-LD, Open Graph). Никакого full reload. Поведение —
   как новая страница для SEO, но мгновенное для пользователя.

4. **Per-product fit-toggle:** на товаре поле `fit_selector_enabled`
   (default=True). Если выключено — в шаблоне кнопок «класика/оверсайз» нет.

---

## Список фаз

| #  | Фаза                                                       | Status   |
|----|------------------------------------------------------------|----------|
| 0  | Подготовка плана и инфраструктуры                          | DONE     |
| 1  | AI opt-in: галочка у Product и Category, fallback chain    | DONE     |
| 2  | Отказ от Celery, перенос на cron + sync on_commit          | DONE     |
| 3  | IndexNow polish (sync, retry, manual reindex в админке)    | DONE     |
| 4  | Sitemap: image-sitemap, sitemap-index, lastmod из БД       | DONE     |
| 5  | Schema.org: Organization, WebSite, shipping/return policy   | DONE     |
| 6  | robots.txt — дедупликация, UTM-noise, AdsBot+AI блоки       | DONE     |
| 7  | Path-URL для вариантов товара (size / color / fit)         | DONE     |
| 8  | AJAX-переключение вариантов без перезагрузки               | DONE     |
| 9  | Цветовой фильтр в каталоге и на главной                    | TODO     |
| 10 | SEO-блоки в категориях (топ-фильтры, топ-запросы и т. п.)  | TODO     |
| 11 | Раздел SEO в админ-панели (категории + блоки + настройки)  | TODO     |
| 12 | Финальная вычитка: тестовые прогоны, валидация Schema       | TODO     |

Каждая фаза = отдельный коммит + деплой. Если фаза большая — несколько
подкоммитов внутри неё.

---

## Phase 0 — Подготовка (DONE)

- [x] Проверен SSH-доступ.
- [x] Подтверждено отсутствие Redis/Celery на сервере.
- [x] Зафиксированы архитектурные решения по URL и AI.
- [x] Создан этот документ.

---

## Phase 1 — AI opt-in

**Цель.** Полный контроль над тем, что и когда генерирует AI. По умолчанию
AI выключен. Метатеги и Schema всегда предпочитают ручные SEO-поля.

### Изменения в моделях

`storefront/models.py`:
- `Product.ai_generation_enabled = BooleanField(default=False)` — новое поле.
- `Category.ai_generation_enabled = BooleanField(default=False)` — новое поле.

> `ai_content_generated` оставляем — это маркер «AI был вызван и заполнил
> поля», полезен для отчётности.

### Изменения в SEO-utils (`storefront/seo_utils.py`)

**Новый порядок приоритета для description:**

1. `product.seo_description` (ручной).
2. Если `product.ai_generation_enabled` И `product.ai_description` —
   использовать AI-описание.
3. Каскад: `short_description` → `full_description` → `description` →
   шаблонный fallback по категории.

**Новый порядок для keywords:**

1. `product.seo_keywords` (ручной).
2. Если `product.ai_generation_enabled` И `product.ai_keywords` — AI.
3. Каскад на основе категории/цвета/размера/тегов.

Аналогично для Category.

### Изменения в management-командах

`generate_ai_content.py`:
- По умолчанию обходит только товары/категории с `ai_generation_enabled=True`.
- Флаг `--all` оставляет старое поведение (для разовых миграций).
- `--force` — перезаписывает `ai_*` даже если они уже заполнены.

### Изменения в `tasks.py` (Celery)

- Помечаем как deprecated; реальная логика остаётся в `seo_utils` /
  management-командах (Phase 2 убирает `@shared_task` совсем).

### Изменения в админке (Django admin + кастомный «Адмін Панель»)

В Django admin (`storefront/admin.py`):
- В `ProductAdmin` добавить fieldsets с группой «SEO», полями
  `seo_title, seo_description, seo_keywords, ai_generation_enabled,
  ai_keywords, ai_description, ai_content_generated`.
- В `CategoryAdmin` — аналогично.

В кастомной админке (`twocomms_django_theme/templates/admin_panel/...`):
- Найти форму редактирования товара/категории, добавить чекбокс
  «Генерувати SEO через AI» рядом с SEO-полями.
- В `views/admin/...` сохранять флаг.

### Тесты

Юнит-тест на `seo_utils.SEOMetaGenerator.generate_meta_description`:
- Если `seo_description` заполнен → возвращает его.
- Если `ai_generation_enabled=False` И `ai_description` есть → НЕ
  возвращает AI, идёт на fallback.
- Если `ai_generation_enabled=True` И `ai_description` есть И
  `seo_description` пуст → возвращает AI.

### Миграция БД

`makemigrations storefront` → `migrate` на сервере. Для существующих товаров
с `ai_content_generated=True` имеет смысл перенести флаг в
`ai_generation_enabled=True`, чтобы их поведение не изменилось.
**RunPython data-migration:**

```python
def forward(apps, schema_editor):
    Product = apps.get_model('storefront', 'Product')
    Category = apps.get_model('storefront', 'Category')
    Product.objects.filter(ai_content_generated=True).update(ai_generation_enabled=True)
    Category.objects.filter(ai_content_generated=True).update(ai_generation_enabled=True)
```

### Чек-лист Phase 1

- [x] Поле `ai_generation_enabled` добавлено в обе модели.
- [x] Поле `fit_selector_enabled` добавлено в Product (бонус из ТЗ).
- [x] Миграция `0050_seo_ai_optin_and_fit_toggle` создана и применена на сервере.
- [x] Data-migration перенесла опт-ин для 52 товаров и 2 категорий,
      у которых был выставлен `ai_content_generated=True`.
- [x] `seo_utils._ai_enabled()` + новые каскады в
      `_pick_product_description_source`, `generate_meta_description`,
      `generate_product_keywords`, `generate_category_keywords`,
      `generate_category_meta`.
- [x] `services/marketplace_feeds._source_description` тоже уважает флаг.
- [x] `generate_ai_content.py` по умолчанию фильтрует по флагу; `--all`
      сохраняет старое поведение.
- [x] Django admin: новые fieldsets «SEO (ручне керування)» +
      «AI-генерація SEO» для Product и Category, плюс list-filters.
- [x] `_resolve_fit_options()` короткозамыкает при `fit_selector_enabled=False`.
- [x] Юнит-тесты `AiOptInBehaviorTests` (6 шт.) написаны. На shared hosting
      нет доступа к созданию тестовой БД, но ручной smoke через
      `manage.py shell` подтвердил поведение на живых данных.
- [x] Smoke: главная `/` → 200, `/product/clasic-tshort/` → 200, meta
      description присутствует.
- [x] Commit `c83ef65a`, push на GitHub, pull на сервере, migrate, restart
      через `tmp/restart.txt`.

### Кастомная админка (custom "Адмін Панель")

Кастомная форма товара/категории пока НЕ обновлена. Этим занимается Phase 11
(большой SEO-раздел в админ-панели). До тех пор флаг можно редактировать
через стандартный Django admin `/admin/storefront/product/<id>/change/`.

---

## Phase 2 — Отказ от Celery, перенос на cron

**Цель.** Убрать зависимость от Celery, потому что её нет на сервере.

### Что найдено сейчас

- `storefront/tasks.py` — задачи: `generate_google_merchant_feed_task`,
  `submit_indexnow_urls_task`, `generate_ai_content_for_product_task`.
- `storefront/signals.py` — два сигнала вызывают `.apply_async`/`.delay`.

### План

1. **IndexNow** — переводим на синхронный `submit_indexnow_urls()` внутри
   `transaction.on_commit`. Запрос лёгкий (1 HTTP). Если вдруг таймаут —
   логируем и не падаем. Для надёжности — добавить retry-обёртку с
   `requests.adapters.HTTPAdapter(max_retries=...)`.

2. **Marketplace feeds.** Сигналы больше не запускают задачу. Вместо этого:
   - `storefront/signals.py` пишет timestamp последнего изменения в
     БД-флаг или файл (`feeds_dirty.flag`).
   - Новая management-команда `regenerate_feeds_if_dirty` запускается из
     cron каждые 10 минут. Если флаг новее последнего билда — пересобирает
     все фиды. Иначе ничего не делает.
   - Это и есть «дебаунс через cron + флаг».

3. **AI-генерация** — только через management-команду
   `generate_ai_content` (запускается вручную или из cron еженедельно).

4. **`tasks.py`** — оставляем файл, но превращаем все `@shared_task` в
   обычные функции; добавляем алиасы `*_task = function` чтобы старый
   импорт не сломался.

### Cron-задачи, которые добавим

```
*/10 * * * * cd /home/.../twocomms && .../python manage.py regenerate_feeds_if_dirty >> .../logs/feeds_cron.log 2>&1
0 4 * * 0   cd /home/.../twocomms && .../python manage.py generate_ai_content --only-missing >> .../logs/ai_seo_cron.log 2>&1
```

### Чек-лист Phase 2

- [x] `tasks.py` — Celery опционален (shim), `bind=True` убран там, где
      нужны sync-вызовы.
- [x] `signals.py` без Celery вызовов; `_schedule_marketplace_feed_update`
      использует `transaction.on_commit` + `mark_feeds_dirty`.
- [x] `services/feeds_queue.py` — flag-файл API (mark_feeds_dirty,
      are_feeds_dirty, mark_feeds_clean, dirty_since_seconds).
- [x] Команда `regenerate_feeds_if_dirty` с debounce (`--min-age-sec=120`),
      `--force`, `--only=...` для точечных пересборок.
- [x] Cron на сервере: `*/10 * * * * flock ... regenerate_feeds_if_dirty`,
      лог `logs/feeds_cron.log`.
- [x] `services/indexnow.enqueue_indexnow_urls` теперь синхронный — без
      попытки `.delay()`. Вызовы из сигналов уже обёрнуты в
      `transaction.on_commit`.
- [x] `tasks.py`: Celery-shim (`shared_task` подменяется при отсутствии
      Celery; `.delay()`, `.apply_async()`, `.run()`, `.apply()` мапятся в
      sync). Убран `bind=True` у `optimize_image_field_task` и
      `submit_indexnow_urls_task` — сигнатуры теперь корректны для
      sync-вызовов из сигналов.
- [x] `signals._enqueue_image_optimization` обёрнут в
      `transaction.on_commit`.
- [x] Smoke на сервере: после save() товара `are_feeds_dirty()` → True;
      `--force --only=generate_prom_feed` корректно генерирует фид;
      главная сайта 200.
- [x] Commit `9d2d5d19`, push, pull, restart.

### Что осталось НЕ тронутым (намеренно)

- `tasks.py` всё ещё содержит функции `generate_ai_content_for_*_task` и
  `send_survey_report_task` под `@shared_task`. Они под shim просто
  выполняются sync. Удалять не стал — могут пригодиться, если когда-то
  появится воркер.
- `orders/telegram_notifications.py` и `orders/signals.py` тоже используют
  `send_telegram_notification_task.delay(...)` через тот же shim — работает
  sync.

---

## Phase 3 — IndexNow polish

### Что сделано

- **Ключ проверен:** `https://twocomms.shop/fda0e47b6c894bcab3f42a5ddc4eb049.txt` → 200,
  `is_indexnow_configured()` → True.
- **`services/indexnow.submit_indexnow_urls`** теперь:
  - батчит по 100 URL/запрос (`INDEXNOW_BATCH_SIZE`),
  - таймаут поднят с 2.5 до 5 сек (`INDEXNOW_DEFAULT_TIMEOUT`),
  - 2 ретрая на 5xx и сетевые таймауты (`INDEXNOW_DEFAULT_RETRIES`),
  - возвращает `False` если хоть один батч не прошёл,
  - 4xx — немедленно фатальная (нет смысла ретраить).
- **`management/commands/reindex_indexnow.py`** — bulk-команда с флагами:
  `--all`, `--core`, `--products`, `--categories`, `--since-days=N`,
  `--limit=N`, `--batch-size=N`, `--retries=N`, `--dry-run`.
  Smoke на сервере: `--core` → 18 URL → IndexNow accepted.
- **Django admin actions:** `Надіслати в IndexNow (поточні URL)` для
  Product и Category. Фильтрует неопубликованные/неактивные, дедуп,
  выводит результат через `messages`.
- **Кастомна `Адмін-панель` (`/admin-panel/?section=catalogs`):** основная
  админка проекта, не Django admin. Добавлено:
  - Endpoint `POST /admin-panel/indexnow/submit/` (`admin_indexnow_submit`)
    принимает `{type: product|category|core|all, ids: [...]}`.
  - Кнопка `IndexNow` на каждой картке категории (рядом з «Видалити»).
  - Кнопка `IndexNow` на каждой картке товара.
  - Глобальная кнопка `IndexNow: усе` в шапке секції каталогів — с `confirm`,
    шлёт core + все опубликованные товары + все активные категории.
  - JS-обработчик в `admin_panel.html`: loading-state, тост через
    существующий `showNotification`.

### Команды для регулярного использования

```bash
# Раз в неделю — переподтверждение всего каталога
python manage.py reindex_indexnow --all

# Ежедневно — только то, что менялось
python manage.py reindex_indexnow --all --since-days=1
```

### Чек-лист Phase 3

- [x] Ключ IndexNow доступен по своему URL.
- [x] Sync через `on_commit`, таймаут 5 с (раньше было 2.5 с).
- [x] Retry на 5xx и сетевые ошибки.
- [x] Batching при больших списках.
- [x] Команда `reindex_indexnow` написана и протестирована на проде.
- [x] Admin-actions для Product и Category (Django admin).
- [x] Кнопки IndexNow в кастомній «Адмін-панелі» (categories / products / global).
- [x] Commits `1b898845`, `c85525a7`, push, pull, restart, smoke OK.

---

## Phase 4 — Sitemap

### Что сделано

- **`/sitemap.xml` теперь sitemap-INDEX** (`storefront.views.static_pages.custom_sitemap`).
  Search Console ничего не нужно перенастраивать — он сам распознаёт
  формат `<sitemapindex>`. Index несёт `<lastmod>` для каждой секции,
  взятый из последнего `updated_at` соответствующей таблицы.
- **Дочерние sitemap-ы:**
  - `/sitemap-static.xml` — `StaticViewSitemap` (curated landing).
  - `/sitemap-products.xml` — `ProductSitemap`, `lastmod=updated_at`.
  - `/sitemap-categories.xml` — `CategorySitemap`, `lastmod=updated_at`.
  - `/sitemap-images.xml` — Google Image Sitemap с `xmlns:image`,
    одна запись на товар (`main_image`).
- **Headers:** `Content-Type: application/xml; charset=utf-8`,
  `Cache-Control: public, max-age=3600`. Никаких `X-Robots-Tag`,
  никаких analytics-cookie (явное отсутствие проверено тестом).
- **Канонический origin:** все sitemap-ы используют `SITE_BASE_URL`,
  не `django.contrib.sites.domain` (тест регрессии переподтверждён).
- **Sitemap для path-URL вариантов** (`sitemap-product-variants.xml`)
  отложен — добавим вместе с Phase 7 (path-URL).

### Smoke на проде

```
GET /sitemap.xml            → 200, sitemapindex с 4 children и lastmod.
GET /sitemap-static.xml     → 200, 2166 байт, 18 <loc>.
GET /sitemap-products.xml   → 200, 10141 байт, 65 <loc>.
GET /sitemap-categories.xml → 200, 592 байт, 3 <loc>.
GET /sitemap-images.xml     → 200, 15590 байт, 64 <loc> + image: namespace.
```

Все четыре дают `application/xml` + `Cache-Control: public, max-age=3600`.

### Чек-лист Phase 4

- [x] `/sitemap.xml` — sitemap-INDEX с lastmod детей.
- [x] `/sitemap-static.xml`, `/sitemap-products.xml`, `/sitemap-categories.xml`.
- [x] `/sitemap-images.xml` (Google Image Sitemap).
- [x] `lastmod` из `updated_at` (`ProductSitemap`, `CategorySitemap`).
- [x] HTTP-кеш через `Cache-Control: public, max-age=3600`.
- [x] Тесты: `<sitemapindex>`, `pro-brand` в static, `xmlns:image` в images.
- [ ] `sitemap-product-variants.xml` — отложено до Phase 7.
- [x] Commit `4fb795c6`, push, pull, restart, smoke OK.

---

## Phase 5 — Schema.org

### Что сделано

- **`storefront/services/policy.py`** — новый модуль, single source of
  truth для тарифов Нова Пошти (UAH, weight-based: 85 / 180 / 220) и
  правил повернення (14 днів, `MerchantReturnFiniteReturnWindow`,
  `ReturnByMail`, `ReturnShippingFees`). Значення збігаються з реальними
  сторінками `/delivery/` і `/returns/`.
- **`StructuredDataGenerator.SHIPPING_OPTIONS`** тепер береться з
  policy-модуля через `shipping_tiers_as_dicts()` (обратная
  совместимость для зовнішнього коду).
- **`generate_product_schema`** — `shippingDetails` /
  `hasMerchantReturnPolicy` тепер на константах `CURRENCY`,
  `APPLICABLE_COUNTRY`, `RETURN_POLICY` замість inline-літералів.
  `priceValidUntil` дина­мічний (today + 90 днів).
- **`generate_organization_schema()`** — стабільний `@id`
  `https://twocomms.shop/#organization`, `sameAs`, `contactPoint`,
  логотип. Ту саму payload раніше дублював `pro_brand.html` inline.
- **`generate_website_schema()`** — `@id` `…/#website`, `SearchAction`
  з `target=EntryPoint`, `urlTemplate` веде на реальний `/search/`.
- **Шаблонні теги** `{% organization_schema %}` і `{% website_schema %}`
  у `seo_tags.py`.
- **`pages/index.html`** використовує нові теги (4 окремі
  `<script type="application/ld+json">`: Organization, WebSite,
  WebPage+ItemList, фрагменти від base-шаблону).
- **`Product.aggregateRating`** — поки відкладено (модель `Product`
  ще не має полів rating/review_count). Додамо разом із системою
  відгуків.
- **Variant schema** (color/size/fit additionalProperty) — увійде у
  Phase 7 разом із path-URL.

### Smoke на проді

```
GET / → 4 <script type="application/ld+json">:
  Organization (@id …/#organization, sameAs, contactPoint)
  WebSite      (@id …/#website, SearchAction → EntryPoint /search/)
  WebPage + ItemList (top-8 categories)
  base-template fragments
GET /product/clasic-tshort/ → присутні priceValidUntil,
  merchantReturnDays, OfferShippingDetails, shippingDetails,
  shippingRate.
```

### Чек-лист Phase 5

- [x] `services/policy.py` — single source для shipping & return.
- [x] `Offer.priceValidUntil` (today + 90 днів).
- [x] `Offer.shippingDetails` weight-based (3 tiers Нової Пошти).
- [x] `Offer.hasMerchantReturnPolicy` (14 днів, ReturnByMail).
- [x] Organization schema на `/` (стабільний `@id`).
- [x] WebSite schema на `/` з SearchAction → `/search/`.
- [x] Тести: `StructuredDataPhase5Tests` (4 нових кейси).
- [ ] `Product.aggregateRating` — після появи відгуків.
- [ ] Variant schema (color/size/fit) — увійде в Phase 7.
- [x] Commit `a31bc808`, push, pull, restart, smoke OK.

---

## Phase 6 — robots.txt

### Что сделано

- **Дедупликация.** Было 375 строк (блоки Googlebot /
  Googlebot-Image / bingbot / Applebot / DuckDuckBot / YandexBot / Slurp
  дублировали `User-agent: *`). Стало ровно **195 строк**.
  Их правила полностью покрываются `*` по спеке.
- **Специфичные блоки ОСТАВЛЕНЫ** только там, где это
  технически обязательно или важно как сигнал:
  - `AdsBot-Google`, `AdsBot-Google-Mobile`, `AdsBot-Google-Mobile-Apps`
    — по спеке Google эти боты НЕ слушают `*`. Без явных
    блоков Shopping/PMax превью перестают работать.
  - `OAI-SearchBot`, `ChatGPT-User`, `Claude-SearchBot`, `Claude-User`,
    `PerplexityBot`, `Perplexity-User`, `Google-Extended`, `GPTBot`,
    `CCBot`, `ClaudeBot`, `anthropic-ai` — явный opt-in в AI
    discovery (в паре с `llms.txt`).
- **Disallow внутри каждого блока повторяются.** По спеке
  robots.txt конкретный user-agent блок НЕ наследует правила
  из `*` — иначе AdsBot и AI-боты разрешили бы себе `/admin/`,
  `/cart/` и т. п. Обязательно повторяем.
- **Query-noise блокировки** в `*` блоке: `?utm_*`, `&utm_*`,
  `?gclid=`, `?fbclid=`, `?yclid=`, `?msclkid=`, `?ref=`, `?ref_=`,
  `?sort=`, `?order=`. Это устраняет размывание canonical от рекламных
  параметров и экономит crawl budget.
- **`/search/` ОСТАЛСЯ доступным** для роботов. Страница
  выдаёт `<meta name="robots" content="noindex, follow">`,
  их нужно пустить внутрь, чтобы они увидели директиву.
- **`Cache-Control: public, max-age=3600`** — robots.txt почти не
  меняется, кэшируем агрессивно.
- **Sitemap-index в конце** — `Sitemap: https://twocomms.shop/sitemap.xml`
  (это именно индекс из Phase 4, а не плоский sitemap).

### Smoke на проде

```
GET /robots.txt → 200, text/plain, 195 строк.
User-agent блоков: 1×*, 3×AdsBot, 11×AI = 15.
Disallow ноиса: utm_, gclid, fbclid, sort= — все присутствуют.
Sitemap: https://twocomms.shop/sitemap.xml.
```

### Чек-лист Phase 6

- [x] Удалены дубли (375 → 195 строк).
- [x] Чёткие `Allow: /` + Disallow в `*`-блоке.
- [x] AdsBot и AI-блоки с полным набором disallow.
- [x] `Disallow: /*?utm_*` и родственники (gclid/fbclid/sort/...).
- [x] Sitemap-index в конце.
- [x] `Cache-Control: public, max-age=3600`.
- [x] Тесты: AI bots, AdsBot, query-noise, crawlable `/search/`.
- [x] Commit `532947b3`, push, pull, restart, smoke OK.

---

## Phase 7 — Path-URL для вариантов

**Цель.** Каждая комбинация (size × color × fit) — уникальный URL,
индексируемый отдельно с собственным title/description, но
`rel=canonical` указывает на самого себя (то есть индексируемая
вариант-страница) — а на базовом URL `rel=canonical` указывает на базовый.

> Альтернатива canonical — отметить вариант как «non-canonical» и сослаться
> на базовый. Это безопаснее, но не даёт SEO-bumps. Решение: первичные
> комбинации (популярные размеры — M, L, XL и базовые цвета) индексируем,
> экзотические — canonical на базовый. Конкретный список первичных
> комбинаций — настраиваем в админке (см. Phase 11).

### URL-структура

```
/product/<slug>/                                              # base, canonical
/product/<slug>/<size>/                                       # size variant
/product/<slug>/<color-slug>/                                 # color variant
/product/<slug>/<color-slug>/<size>/                          # color+size
/product/<slug>/<color-slug>/<size>/<fit-slug>/               # all three
```

Допустимые значения:
- `size`: из `Product.available_sizes` (нижний регистр, slug-safe).
- `color-slug`: новое поле `ColorVariant.slug` (миграция).
- `fit-slug`: `'classic'` или `'oversize'` (определяем из `ProductFitOption.code`).

### Изменения в роутинге

`storefront/urls.py`:
```python
path('product/<slug:slug>/', views.product_detail, name='product'),
path('product/<slug:slug>/<slug:variant1>/', views.product_detail_variant, name='product_variant_1'),
path('product/<slug:slug>/<slug:variant1>/<slug:variant2>/', ...),
path('product/<slug:slug>/<slug:variant1>/<slug:variant2>/<slug:variant3>/', ...),
```

Парсер вариантов в view определяет, что есть что (size — короткий
буквенный код, color/fit — slug). Если непарсится → 404.

### Динамические meta

Title-формула (Ukrainian):
> «Купити {category_singular} {product_title} {color}{size}{fit} — TwoComms»

Например:
> «Купити футболку Pivnich, чорна, розмір M, оверсайз — TwoComms»

Meta-description тоже параметризуем по варианту.

### Canonical-стратегия

- Базовый `/product/<slug>/`: canonical → self.
- Вариант с одним сегментом: canonical → self.
- Вариант с 2-3 сегментами: canonical → self ТОЛЬКО если эта комбинация
  есть в списке «значимых вариаций» (размеры M/L/XL, базовые цвета). Иначе
  → базовый.

Список «значимых» хранится в админ-настройках (Phase 11).

### Sitemap

`sitemap-product-variants.xml` — все индексируемые варианты.

### Backward-compatibility

Старые URL `/product/<slug>/?size=M&color=123` — 301-redirect на новый
path-формат.

---

## Phase 8 — AJAX-переключение варианта

**Цель.** Никакой полной перезагрузки. Пользователь кликает размер/цвет/крой —
страница за 50-100ms обновляет всё что нужно, URL меняется через
`history.pushState`.

### Что обновляем динамически

- URL (pushState).
- `<title>`.
- `<meta name="description">`, `og:title`, `og:description`, `og:url`,
  `og:image`, `twitter:*`.
- `rel=canonical`.
- JSON-LD (`<script type="application/ld+json">`) — заменяем содержимое.
- Хлебные крошки (последняя крошка).
- Главное изображение, галерея.
- Цена, скидка, наличие, кнопка «купить» (offer_id).
- Текстовая «формулировка варианта» (например «Розмір M, чорний, оверсайз»).

### Реализация

1. **Endpoint** `GET /api/product/<slug>/variant/?size=M&color=123&fit=oversize`
   возвращает JSON с тем же набором полей (title/description/canonical/
   schema/image_urls/price/offer_id/breadcrumb_last/og/...).
2. **Серверный рендер при прямом заходе на path-URL Phase 7** даёт
   корректный SEO-snapshot — для краулеров.
3. **Клиентский JS** (`product-detail.js`) при клике на размер/цвет/крой:
   - вызывает endpoint;
   - применяет ответ к DOM;
   - делает `history.pushState(state, title, newUrl)`.
4. **`popstate`** — откат к предыдущему варианту.

### Прогрессивное улучшение

Если JS не работает (краулер, выключен) — клик по варианту работает как
обычная ссылка `<a href="/product/slug/m/">`, открывается полноценная
страница. JS перехватывает клик и заменяет на AJAX. Это нативный SEO-friendly
паттерн.

### Чек-лист Phase 8

- [x] Клиент синхронизирует path-URL через `history.replaceState`
      на изменение размера/цвета/кроя без перезагрузки
      (`product-variant-history.js`, коммит `958efc91`).
- [x] `document.title` и `<link rel=canonical>` обновляются по той
      же стратегии Phase 7.3 (1-сегмент → self, 2+ → base).
- [x] Шаблон карточки отдаёт `data-product-slug`,
      `data-product-base-path`, `data-product-title-base` +
      `data-variant-slug` на каждом swatch.
- [x] Прогрессивное улучшение: ссылки `<a href>` остаются рабочими
      без JS — клиент перехватывает клик и заменяет на pushState.
- [x] Prod smoke: атрибуты доступны (`black`, `coyote`),
      минифицированный JS отдаётся CDN.
- [x] Коммит + деплой (`958efc91`, `def37265`).
- [ ] Полный AJAX-эндпойнт `/api/product/<slug>/variant/`
      (опциональное расширение: подмена цены/изображения/JSON-LD
      без перехода). Не реализован — текущий path-вариант рендерит
      сервер при прямом заходе, а клиент только синхронизирует URL.

---

## Phase 9 — Цветовой фильтр в каталоге

- Каталог: добавить цветной фильтр (chip-список цветов из ColorVariant).
- URL: `/catalog/<cat>/?color=black,red`.
- На карточке товара — мини-цветные точки (если есть варианты).
- На главной странице рядом с категориями — chip фильтр по цветам.

### Реализация (2026-05-09)

**Backend.** `storefront/services/color_filter.py`:
- `parse_color_filter(request)` — принимает и `?color=black,red`, и
  повторённые `?color=black&color=red`; нормализует слаги
  (`[a-z0-9-]+`), дедуплицирует, ограничивает 10 значениями.
- `apply_color_filter(qs, slugs)` — `qs.filter(color_variants__slug__in=slugs).distinct()`,
  то есть OR-match. Использует уникальный per-product `ProductColorVariant.slug`
  (Phase 7.1) — ключ `black` стабильно соответствует одному «чорному» по всему каталогу.
- `build_available_colors(base_qs, request, selected)` — агрегирует чипы по slug
  с количеством товаров, наиболее частой парой hex и человеческим лейблом;
  каждая чипа несёт `url`, тогглящий свой slug в `?color=` (другие GET-параметры
  сохраняются, `page` сбрасывается).
- `build_reset_url(request)` — путь без `color=`.
- `build_home_color_chips(qs, target_path, limit=12)` — топ-12 цветов с прямыми
  ссылками на `/catalog/?color=<slug>` для главной.

**Views.** `storefront/views/catalog.py`:
- `catalog()` строит `base_product_qs` ДО фильтра (для чипов), затем применяет
  цвет; при активном фильтре скрывает showcase-cards на корневом `/catalog/`,
  чтобы пользователь видел отфильтрованную сетку.
- `search()` — те же шаги поверх результатов поиска.
- `home()` строит `home_color_chips` через `build_home_color_chips`.
- Кэш `cache_page_for_anon` уже включает querystring → `?color=` даёт собственный
  ключ (см. `_build_anon_cache_key`).

**Templates.**
- `partials/color_filter_chips.html` — общий chip-strip с reset-ссылкой
  (`rel="nofollow"`).
- `pages/catalog.html` — включает партиал после `.catalog-filter-rail` и
  возвращает `noindex, follow` для отфильтрованных URL (canonical при этом
  ведёт на чистый путь — оставлен прежний блок `{% block canonical %}`).
- `pages/index.html` — `home-color-filter` секция между блоком категорий и
  «Новинки».
- `static/css/color-filter.css` — единый стиль chip-strip + домашний вариант.

**SEO.**
- Robots: при любом `?color=` → `noindex, follow` (фильтрованные комбинации не
  индексируем).
- Canonical: всегда указывает на чистый путь (без `color=`); перенаправлений
  нет — фильтр доступен напрямую.
- Поиск (`is_search_page`) уже был `noindex` — поведение не изменилось.

**Тесты.** `storefront/tests/test_phase9_color_filter.py` — 14 кейсов:
парсинг (`comma`, `multi-param`, нормализация, дедуп), OR-фильтр,
toggle-URL, reset-URL, домашние чипы; интеграционные — каталог
(`?color=coyote` → правильные товары, `noindex`, скрытые showcase-cards),
комбинированный `?color=black,coyote`, `?q=tee&color=coyote` в поиске,
наличие чипов в `pages/catalog.html`, `home_color_chips` в контексте home.
Команда: `python manage.py test storefront.tests.test_phase9_color_filter --settings=test_settings` → 14 passed. Регрессия: `storefront.tests.test_catalog` → 15 passed.

**Файлы.**
- `twocomms/storefront/services/color_filter.py` (new).
- `twocomms/storefront/views/catalog.py` (catalog/search/home).
- `twocomms/twocomms_django_theme/templates/partials/color_filter_chips.html` (new).
- `twocomms/twocomms_django_theme/templates/pages/catalog.html` (chips + robots).
- `twocomms/twocomms_django_theme/templates/pages/index.html` (home strip + CSS).
- `twocomms/twocomms_django_theme/static/css/color-filter.css` (new).
- `twocomms/storefront/tests/test_phase9_color_filter.py` (new).

---

## Phase 10 — SEO-блоки в категории

**Что добавляем (по образцу retromagaz / aac):**

1. **Текст-описание категории** (внизу страницы, после товаров): rich-text
   с правом ссылок, выделения, заголовков. До 800-1500 символов.
2. **Top-Filters** — блок «Популярні фільтри» (chip-ссылки на отфильтрованные
   списки).
3. **Top-Queries** — блок «Популярні запити» (текстовые ссылки).
4. **Top-Cards** — блок «Найкращі товари в категорії» (вручную выбранные
   карточки).
5. **Top-Menu** — блок «Розділи категорії» (подкатегории / связанные).
6. **Bottom Price-block** — «Найкращі ціни на ...» (динамический список топ-N).

### Модели

Новый файл `storefront/models_seo.py`:

```python
class CategorySeoBlock(models.Model):
    BLOCK_TYPES = [
        ('top_filters', 'Топ фільтри'),
        ('top_queries', 'Топ запити'),
        ('top_cards', 'Топ карточки'),
        ('top_menu', 'Топ меню'),
        ('bottom_text', 'SEO текст'),
        ('best_prices', 'Найкращі ціни'),
    ]
    category = models.ForeignKey(Category, on_delete=CASCADE, related_name='seo_blocks')
    block_type = CharField(choices=BLOCK_TYPES)
    title = CharField(max_length=200, blank=True)
    is_active = BooleanField(default=True)
    order = PositiveIntegerField(default=0)

class CategorySeoBlockItem(models.Model):
    block = ForeignKey(CategorySeoBlock, related_name='items')
    label = CharField(max_length=200)
    url = CharField(max_length=500, blank=True)  # абсолютный или относительный
    extra = JSONField(default=dict, blank=True)  # для top_cards: product_id и т.п.
    order = PositiveIntegerField(default=0)

class CategorySeoText(models.Model):
    category = OneToOneField(Category, related_name='seo_text')
    title = CharField(max_length=200, blank=True)  # H2
    body_html = TextField(blank=True)  # rich-text (CKEditor / TinyMCE)
    show_on_listing = BooleanField(default=True)
```

### Шаблоны

В `pages/catalog.html` — после списка товаров рендерить блоки в порядке
`order`. Каждый тип — свой include-шаблон с собственной разметкой и стилем.

### Стиль

Используем уже существующую glass/neon-эстетику сайта. Никаких новых CSS
библиотек.

### Реализация (2026-05-09)

**Модели.** Прагматичная подгонка под существующую схему вместо буквального
повторения трёх моделей из спека:

- `Category.seo_text_title` — новый `CharField(blank=True)` для H2 над
  длинным SEO-текстом. Если пусто — используется `category.name`.
  Тело текста по-прежнему хранится в существующем `Category.description`
  (rich-text как был, никаких миграций данных).
- `CategorySeoBlock(category, block_type, title, is_active, order)` —
  одна «рейка» на странице категории. `block_type` ∈ {`top_filters`,
  `top_queries`, `top_cards`, `top_menu`, `best_prices`}. Индексы:
  `(category, is_active, order)` + `(block_type)`.
- `CategorySeoBlockItem(block, label, url, extra: JSONField, order)` —
  элемент рейки. `extra` хранит, например, `{"product_id": 42}` для
  `top_cards` или `{"price": 599}` для `best_prices`. Индекс
  `(block, order)`.

Миграция: `storefront/migrations/0051_phase10_category_seo_blocks.py`
(+ 1 поле, + 2 модели, + 3 индекса).

**Сервис.** `storefront/services/category_seo_blocks.py`:
`get_category_seo_blocks(category)` загружает активные блоки с
`prefetch_related('items')`, гидратирует `extra.product_id` живыми
`Product`'ами (только `status='published'`), отбрасывает пустые
блоки кроме `best_prices` (он может быть динамическим в будущем).

**Views.** `catalog()` пробрасывает `category_seo_blocks` в контекст
только для страниц с конкретной категорией; на корневом `/catalog/`
передаётся пустой список. Поиск/главная блоки не получают.

**Шаблоны.**
- `partials/category_seo_blocks.html` — единый партиал с ветками по
  `block_type`: `top_filters`/`top_menu` → chip-ссылки, `top_queries`
  → текстовые ссылки, `top_cards` → используем существующий
  `partials/product_card.html`, `best_prices` → строки `label / price`.
- `pages/catalog.html` — секция `catalog-category-seo-blocks` между
  гридом товаров и старым описанием категории. H2 описания теперь
  использует `category.seo_text_title|default:category.name`.
- `static/css/category-seo-blocks.css` — стиль рейок и chip-ссылок,
  совместим с `color-filter.css` (тот же glass/neon).

**Админка.** `CategoryAdmin` — добавлено поле `seo_text_title` в
fieldset «Основне». `CategorySeoBlockAdmin` зарегистрирован с inline
`CategorySeoBlockItemInline` (`extra=1`, ordering по `order, id`),
`list_editable` для `is_active` и `order`, фильтры по типу/статусу/
категории. Редактирование `extra` — через стандартный JSON-виджет
Django (rich-text WYSIWYG отложен до Phase 11).

**Тесты.** `storefront/tests/test_phase10_category_seo_blocks.py` —
10 кейсов: возврат для `None`, пустого кэта, сортировка `order`,
`is_active=False` отбрасывается, пустые блоки кроме `best_prices`
скрываются, `top_cards` гидратирует только `published`-товары,
изоляция per-category; интеграционные — `category_seo_blocks` в
контексте `catalog_by_cat`, отсутствие на корневом `/catalog/`,
`seo_text_title` → H2, fallback на `category.name`. Команда:
`python manage.py test storefront.tests.test_phase10_category_seo_blocks --settings=test_settings` → 10 passed. Регрессия — `test_catalog` 15/15 + Phase 9 14/14.

**Файлы.**
- `twocomms/storefront/models.py` (Category.seo_text_title +
  CategorySeoBlock + CategorySeoBlockItem).
- `twocomms/storefront/migrations/0051_phase10_category_seo_blocks.py` (new).
- `twocomms/storefront/services/category_seo_blocks.py` (new).
- `twocomms/storefront/views/catalog.py` (catalog context).
- `twocomms/storefront/admin.py` (CategoryAdmin + CategorySeoBlockAdmin).
- `twocomms/twocomms_django_theme/templates/partials/category_seo_blocks.html` (new).
- `twocomms/twocomms_django_theme/templates/pages/catalog.html` (section + H2).
- `twocomms/twocomms_django_theme/static/css/category-seo-blocks.css` (new).
- `twocomms/storefront/tests/test_phase10_category_seo_blocks.py` (new).

**Отложено в Phase 11.**
- WYSIWYG для `Category.description` (CKEditor / TinyMCE) — сейчас
  Textarea + `|safe` рендер. Контент-менеджер пишет HTML вручную.
- Автоматический `top_filters` (на основе самых популярных
  `?color=`/`?size=`/`?fit=`-комбинаций) — пока ручное наполнение.

### Доделка Phase 10b — табы / pricing-таблица / intro / seed (2026-05-09)

После Phase 10 пользователь прислал референс с AAC.com.ua: блоки реализованы
не вертикальными «рейками», а в виде **одного компонента-табов**
(`ТОП меню / ТОП фільтри / ТОП запити / ТОП карточки`); pricing — настоящий
`<table>`; над сеткой товаров — короткий intro с `<details>`-розворотом.
Phase 10b догоняет паттерн.

**Schema.**
- `Category.seo_intro_html` — `TextField`, рендерится `|safe` над сеткой
  товаров. Поддерживает `<details>/<summary>` для «Що таке X?»-блока.
- Миграция `0052_phase10b_category_seo_intro.py`.

**Service.** `services/category_seo_blocks.get_category_seo_layout(category)`
возвращает `{tab_blocks, best_prices, has_any}`:
- `tab_blocks` — блоки в каноническом порядке `TAB_BLOCK_TYPES =
  (top_menu, top_filters, top_queries, top_cards)`, по одному на тип
  (первый активный); пустые отброшены.
- `best_prices` — отдельный блок (или `None`, если нет items), рендерится
  как `<table>` независимо от табов.

**View.** `views/catalog.py.catalog()` пробрасывает `category_seo_layout`
в контекст; legacy `category_seo_blocks` остаётся для тестов/обратной
совместимости.

**Templates.**
- `pages/catalog.html` — добавлена секция `.catalog-category-intro`
  (между hero и products-grid), отображает `category.seo_intro_html|safe`.
  Гейт SEO-блоков переключён на `category_seo_layout.has_any`.
- `partials/category_seo_blocks.html` полностью переписан:
  pricing-`<table>` сверху → tabs-component (`button[role=tab]` +
  `div[role=tabpanel]`) с inline-JS-переключателем (idempotent
  `data-seo-tabs-bound`), `top_cards` рендерится через `product_card.html`.

**CSS.** `static/css/category-seo-blocks.css`:
- `.catalog-intro-panel` (glass, кастомный `<details>` с
  оранжевой стрелкой ▾, ротация при `[open]`).
- `.seo-pricing__table` (sticky шапка, моноширинная цена справа,
  `overflow-x:auto` для мобайла).
- `.seo-tabs__nav` + `.seo-tab.is-active` — pill-кнопки, активная
  заливается neon-orange-градиентом (`#ff7e29 → #ff5a32` + glow).
- `.seo-tab-panel__links--columns` — `columns: 1/2/3/4` через
  `@media`-брейкпоинты (mobile → desktop), как у AAC.
- `.catalog-description-panel` — стилизованы `h2/h3/p/a/ul/ol` для
  длинного SEO-текста снизу (без `|safe` html-bleed).

**Admin.** `seo_intro_html` добавлен в `CategoryAdmin.fieldsets[0]`.

**Seed (`0053_phase10b_seed_category_seo.py`).** Идемпотентная миграция
заполняет SEO-копию для трёх живых категорий:
- `hoodie` (Худі) / `tshirts` (Футболки) / `long-sleeve` (Лонгсліви).
- `seo_intro_html` — короткий параграф с HF-ключами + `<details>` с
  «Що таке X?»; внутренние ссылки на колор-фильтры и сестринские
  категории.
- `description` — длинная HTML-копия с H3-секциями (`Як обрати`, `Силуети`,
  `Доставка та оплата`, `Чому TwoComms`), внутренней перелинковкой на
  `/rozmirna-sitka/`, `/doglyad-za-odyagom/`, `/delivery/`, `/pro-brand/`.
- `seo_text_title` — H2 над длинным текстом
  (`«Худі TwoComms — патріотичний streetwear...»` и т.д.).
- Tab-blocks: `top_menu` (5–6 ссылок), `top_filters` (9–10 цвет/размер/fit),
  `top_queries` (14–16 LF/MF-фраз: «Купити худі ЗСУ», «Худі з тризубом»,
  «Тактичне худі», «Худі oversize Україна», `Худі Київ/Львів`,
  «Стрітвір худі» и т.д., каждая ссылается на осмысленный URL).
- `best_prices` — динамически из реальных `Product.objects` (топ-8 по
  `priority`, опубликованные); если категория пустая — блок не создаётся.
- Идемпотентность: пропускает категорию, если у неё уже есть `description`,
  и пропускает блоки, если для типа уже есть активный блок. Reverse —
  no-op (не разрушает редакторский контент при rollback).

**Tests.** `storefront/tests/test_phase10b_seo_layout.py` — 11 кейсов:
- `get_category_seo_layout` — каноническая сортировка табов независимо
  от `block.order`, `best_prices` отдельно от `tab_blocks`, отбрасывание
  пустых, `None`-категория.
- Catalog — intro-секция рендерится только при наличии `seo_intro_html`,
  табы-компонент с тремя триггерами, pricing `<table>` с ценой+«грн»,
  `category_seo_layout` в контексте.
- Seed-смоук — функция `seed_seo_copy(apps, schema_editor)`
  заполняет 3 категории; повторный запуск идемпотентен (не дублирует
  блоки и не перезаписывает ручные правки).

Tests Phase 10b → 11/11 passed; регрессия Phase 9+10+11+catalog → 61/61
passed.

**Файлы.**
- `twocomms/storefront/models.py` (`Category.seo_intro_html`).
- `twocomms/storefront/migrations/0052_phase10b_category_seo_intro.py` (new).
- `twocomms/storefront/migrations/0053_phase10b_seed_category_seo.py` (new, RunPython).
- `twocomms/storefront/services/category_seo_blocks.py`
  (`TAB_BLOCK_TYPES`, `get_category_seo_layout`).
- `twocomms/storefront/views/catalog.py` (`category_seo_layout` в контексте).
- `twocomms/storefront/admin.py` (`seo_intro_html` в `CategoryAdmin`).
- `twocomms/twocomms_django_theme/templates/pages/catalog.html`
  (`catalog-category-intro` + новый гейт SEO-блоков).
- `twocomms/twocomms_django_theme/templates/partials/category_seo_blocks.html`
  (полностью переписан под табы/таблицу).
- `twocomms/twocomms_django_theme/static/css/category-seo-blocks.css`
  (полностью переписан под Phase 10b).
- `twocomms/storefront/tests/test_phase10b_seo_layout.py` (new, 11 tests).
- `twocomms/storefront/tests/test_phase10_category_seo_blocks.py`
  (один ассерт обновлён под новые tab-data-атрибуты).

**Ручной шаг при деплое.** На проде нужно `manage.py migrate storefront 0053`,
после чего проверить контент в админке (`Категорії` → `Худі/Футболки/Лонгсліви`):
поля `seo_intro_html`, `seo_text_title`, `description` заполнятся; каждая
категория получит 3–4 активных `CategorySeoBlock`. Если контент-менеджер
переписал `description` ДО миграции — она его сохранит.

---

## Phase 11 — Админ-раздел SEO

В кастомной админ-панели (sidebar):

- **SEO → Категорії**
  - Список категорий → редактирование SEO-полей (title, description,
    keywords, AI-флаг), описательного текста (`CategorySeoText`),
    блоков (`CategorySeoBlock` + items). Rich-text редактор с возможностью
    вставлять ссылки, выделять теги.
- **SEO → Глобальні налаштування**
  - Default meta для статических страниц.
  - Шаблоны title для вариантов товара (Phase 7).
  - Список «значимих вариантов» (path-URL для индексации).
  - robots.txt — превью + редактор (опционально).
  - IndexNow ключ + статус последних submission.
- **SEO → Sitemap**
  - Превью количества URL в каждом sitemap.
  - Кнопка «Прогреть кеш».
- **SEO → AI**
  - Список товаров/категорий с включённым AI и статусом генерации.
  - Кнопка «Сгенерировать сейчас» для одного товара (вызывает
    `generate_ai_content` через subprocess или прямой вызов функции).

### Реализация (2026-05-09)

Кастомна адмін-панель (`/admin-panel/?section=...`), не Django-admin.
Розкладено на сервіс + один частковий шаблон + AJAX-ендпоінт.

**Сервіс.** `storefront/services/seo_dashboard.py`:
- `build_sitemap_summary()` — повертає 5 під-sitemap-секцій + рядок
  «Всього URL»: `static` (через `StaticViewSitemap().items()`),
  `products`/`categories` (через `count()` ORM), `variants` (через
  `ProductVariantSitemap().items()`), `images` (count товарів з
  `main_image`).
- `build_ai_panel()` — топ-50 товарів і категорій з
  `ai_generation_enabled=True`, агрегати (`*_total`/`*_generated`),
  стан фічa-флагів (`USE_AI_KEYWORDS`, `USE_AI_DESCRIPTIONS`,
  `OPENAI_API_KEY`, `AUTO_GENERATE_AI_CONTENT_ON_CREATE`).
- `build_seo_blocks_summary(limit=20)` — анотація `Count('seo_blocks',
  filter=Q(seo_blocks__is_active=True))` для активних категорій.
- `build_seo_dashboard_context()` — об'єднує три блоки в один dict.

**Views.** `storefront/views/admin.py`:
- `admin_panel(?section=seo)` — пробрасывает `build_seo_dashboard_context()`
  в існуючий шаблон.
- Новий `admin_seo_ai_generate(request)` — `@staff_member_required`,
  POST JSON `{"target": "product"|"category", "id": <int>}`. Виклик
  `generate_ai_content_for_*_task(obj.id)` напряму (sync, бо без Celery
  на проді — Phase 2). Повертає `{success, ai_content_generated,
  ai_keywords, ai_description}`. Помилки: 405/400/404/503/500.

**URL.** `admin-panel/seo/ai/generate/` → `admin_seo_ai_generate`
(`name='admin_seo_ai_generate'`).

**Шаблон.** `partials/admin_seo_dashboard.html` — три картки:
- **Sitemap** — grid тайлів з кількістю URL і прямими лінками.
- **AI** — лічильники + дві таблиці (товари/категорії) з кнопками
  «Згенерувати», `data-action="seo-ai-generate"`. Inline JS викликає
  endpoint, оновлює пілку статусу in-place через `[data-seo-flag]`.
- **Phase 10 SEO-блоки** — таблиця активних категорій з лічильниками
  active/total та кнопкою «Редагувати» (Django-admin за filter
  `category__id__exact=<id>`). Внизу — quick-links на `/sitemap.xml`,
  `/robots.txt`, Django-admin Category/CategorySeoBlock.

Бічна панель адмінки (`templates/pages/admin_panel.html`) отримала
новий пункт «SEO» (іконка лупа+плюс) одразу після «Диспетчер».

**Тести.** `storefront/tests/test_phase11_seo_admin.py` — 11 кейсів:
- Сервіс — `sitemap_summary` (5+total, count ≥ фікстур),
  `ai_panel.ai_counts`, `seo_blocks_summary` (active vs total).
- View — staff бачить дашборд (sitemap/AI/SEO-блоки), не-staff
  редіректиться на home.
- Endpoint — 405 на GET, 503 без API-ключа, 503 з вимкнутими
  фічa-флагами, 400 на невідомий target, 400 на не-opt-in товар,
  200 + JSON-snapshot на happy-path (з замоканим
  `generate_ai_content_for_product_task`).

Команда: `python manage.py test storefront.tests.test_phase11_seo_admin --settings=test_settings` → 11 passed. Регрессія —
Phase 9 + Phase 10 + `test_catalog` сумарно 50/50 passed.

**Файли.**
- `twocomms/storefront/services/seo_dashboard.py` (new).
- `twocomms/storefront/views/admin.py` (`admin_seo_ai_generate` +
  `?section=seo` бранч у `admin_panel`).
- `twocomms/storefront/urls.py` (новий path).
- `twocomms/twocomms_django_theme/templates/pages/admin_panel.html`
  (sidebar + `{% elif section == 'seo' %}` бранч).
- `twocomms/twocomms_django_theme/templates/partials/admin_seo_dashboard.html` (new).
- `twocomms/storefront/tests/test_phase11_seo_admin.py` (new).

**Відкладено в Phase 12 / окрема ітерація.**
- WYSIWYG для `Category.description` (CKEditor / TinyMCE) — поки
  стандартний Textarea + `|safe` рендер у каталозі.
- Окремі сторінки «Глобальні SEO-налаштування» (variant title-templates,
  список «значимих варіантів» для індексації, robots.txt-редактор) —
  поки керується через `settings.py` + Django-admin для AI-полів.
- Inline-редактор шаблонів variant-title (Phase 7.3 рендерить динамічно
  з фіксованих рядків у view) — потребує окремої моделі
  `SeoVariantTemplate`.

---

## Phase 12 — Финальная вычитка

- Прогон [Schema Markup Validator](https://validator.schema.org/) на главной,
  категории, товаре, варианте.
- Прогон [Rich Results Test](https://search.google.com/test/rich-results).
- Lighthouse SEO для топ-10 страниц (должно быть 100).
- Проверка sitemap.xml в Google Search Console.
- Проверка IndexNow в Bing Webmaster Tools.
- Финальный коммит «SEO overhaul complete».

---

## Журнал изменений

| Дата | Фаза | Коммит | Заметки |
|------|------|--------|---------|
| 2026-05-08 | 0 | — | План создан, инфраструктура изучена. |
| 2026-05-09 | 1 | `c83ef65a` | AI opt-in + fit toggle. Migrate applied on server; data-migration перенесла 52 товара. Smoke HTTP OK. |
| 2026-05-09 | 2 | `9d2d5d19` | Celery-less сигналы: dirty-flag + cron `regenerate_feeds_if_dirty`. IndexNow и image-opt — sync через `on_commit`. Cron `*/10 *` добавлен. Smoke: `dirty=True` после save, `--force` фид сгенерирован за 0.8s, главная 200. |
| 2026-05-09 | 3 | `1b898845` | IndexNow polish: batching/retries в `submit_indexnow_urls`, команда `reindex_indexnow`, admin-actions для Product/Category. Smoke: `--core` → 18 URL accepted. |
| 2026-05-09 | 3 | `c85525a7` | IndexNow controls в кастомній «Адмін-панелі» (`/admin-panel/?section=catalogs`): endpoint, кнопки на картках товарів/категорій, глобальна `IndexNow: усе`. URL резолвиться, шаблон містить контролі. |
| 2026-05-09 | 4 | `4fb795c6` | Sitemap-INDEX `/sitemap.xml` + 4 дочірні (static / products / categories / images). lastmod з `updated_at`, image: namespace, `Cache-Control: public, max-age=3600`. Smoke: 4 секції, 18+65+3+64 `<loc>`. |
| 2026-05-09 | 5 | `a31bc808` | Schema.org: `services/policy.py` (Нова Пошта 85/180/220 UAH, 14d return). Organization+WebSite+SearchAction на `/` через нові теги, стабільні `@id`. Smoke: 4 ld+json блоки, EntryPoint → `/search/`. |
| 2026-05-09 | 6 | `532947b3` | robots.txt: 375→195 строк. Удалены дубли (Googlebot/bing/Applebot/DDG/Yandex — следуют `*`). Оставлены AdsBot ×3 (спека) и AI ×11 (opt-in). UTM/gclid/fbclid/sort noise. Cache-Control 1ч. |
| 2026-05-09 | 7.1 | `528654b4` → `b5b110a8` | `ProductColorVariant.slug` + точный EN-перевод (`чорний→black`, `кайот→coyote`, compound `біло-бордовий→white-burgundy`). 4 миграции: AddField → backfill translit → reslug to EN → normalize (size-reserved set). 121 вариантов на проде — чистые slug'и. |
| 2026-05-09 | 7.2 | `24b2e9d9` | Path-URL роутинг: `/product/<slug>/[<v1>/[<v2>/[<v3>]]]/`. Content-addressable parser (order-insensitive), path overrides query, unknown-segment → 404. Smoke: 5 сценариев 200/200/200/200/404. |
| 2026-05-09 | 7.3 | `35654d6c` | Variant-aware canonical + meta: base/1-segment → self, 2+ → base URL. Динамические title/description (`Купити X — кайот, розмір M — TwoComms`). Prod smoke: canonical на 3 URL'ах точно по стратегии. |
| 2026-05-09 | 7.4 | `26310db5` → `a9001e15` | `sitemap-product-variants.xml`: 416 URL в виде 1-сегмент вариаций (65×L/M/XL/S/XXL, 24×XS, 22×oversize/classic, 12×black, 7×coyote...). Multi-segment омитнуты (канонизируются на base). Добавлен в sitemap-index. |
| 2026-05-09 | 7.5 | `7327c354` | 301 redirect: legacy `?size=M&color=<id>&fit=<code>` → `/<color>/<size>/<fit>/`. Каноничный порядок (color → size → fit). UTM/gclid/fbclid/ref preserved. Invalid query → 200 fallback. Path-URL не редиректится повторно. Prod smoke: 4 сценария (3×301, 1×200). |
| 2026-05-09 | 8   | `958efc91` | Phase 8 — `product-variant-history.js`: при изменении color/size/fit на странице товара клиент через `history.replaceState` синхронизирует path-URL без перезагрузки, обновляет `document.title` и `<link rel=canonical>` по той же стратегии (1-сегмент → self, 2+ → base). Шаблон отдаёт `data-product-slug`, `data-product-base-path`, `data-product-title-base` + `data-variant-slug` на swatch. Prod smoke: атрибуты доступны (`black`, `coyote`), минифицированный JS отдаётся CDN. |
| 2026-05-09 | 9   | _pending_  | Phase 9 — colour filter. `storefront/services/color_filter.py`: `parse_color_filter` (comma + repeated `?color=`), `apply_color_filter` (OR-match по `ProductColorVariant.slug`), `build_available_colors` / `build_reset_url` (toggle-URL, сохраняет UTM/прочие GET, сбрасывает `page`), `build_home_color_chips` (топ-12 цветов → `/catalog/?color=<slug>`). Catalog/search: фильтр + `noindex, follow` на отфильтрованных URL, скрытие showcase-cards на корневом `/catalog/?color=…`. Home: chip-strip между блоком категорий и «Новинки». Партиал `partials/color_filter_chips.html`, `static/css/color-filter.css`. Tests: 14 кейсов (`storefront.tests.test_phase9_color_filter`) → all passed; регрессия `test_catalog` 15/15. |
| 2026-05-10 | 12  | `fea9a8eb` | Phase 12 — production validation. JSON-LD smoke (`/`, `/catalog/{hoodie,tshirts,long-sleeve}/`, `/product/HD-twocomms-reality-bends-future-2026/`): all blocks parse OK; home → Organization+WebSite+WebPage (4), category → Organization+BreadcrumbList+CollectionPage (3), product → Organization+Product(price=1912, sku=TC-102, brand=TwoComms)+BreadcrumbList. Sitemap-index sanity: 5 sub-maps healthy (18+3+65+416+64 = **566 URL**). IndexNow batch via `manage.py submit_indexnow_urls --categories --url sitemap.xml --url sitemap-categories.xml` → "IndexNow accepted 5 URL(s)" (Bing/Yandex notified). Color filter prod check: `/catalog/hoodie/?color=black` → 200 + `meta robots: noindex, follow` ✅. Все Phase 9–11 секции (intro/pricing/tabs/long-text/color-chips) рендерятся на проде. Manual: GSC/Bing Webmaster fetch + Rich Results test пользователь сделает в дашбордах (нужны логины). |
| 2026-05-09 | 10b | _pending_  | Phase 10b — догон под AAC-паттерн. `Category.seo_intro_html` + миграция `0052`. `services.category_seo_blocks.get_category_seo_layout` (`TAB_BLOCK_TYPES`, splits tabs vs `best_prices`). Полная переборка партиала: pricing `<table>` сверху + tabs-component (4 триггера, inline-JS, idempotent), CSS `.catalog-intro-panel`/`.seo-pricing__table`/`.seo-tabs__nav` с neon-orange-active-табой и `columns:1/2/3/4` на брейкпоинтах, `<details>`-розворот. Admin: `seo_intro_html` в `CategoryAdmin`. Seed-миграция `0053` (RunPython, idempotent, reverse=noop) — заполняет `seo_intro_html`/`seo_text_title`/`description` + 3–4 SEO-блока для `hoodie`/`tshirts`/`long-sleeve`: `top_menu` (5–6 ссылок), `top_filters` (9–10 цвет/размер/fit), `top_queries` (14–16 LF/MF: «купити худі ЗСУ», «тризуб футболка», «тактичний лонгслів» …), `best_prices` динамически из топ-8 опубликованных продуктов. Tests: 11 (`storefront.tests.test_phase10b_seo_layout`) → all passed; регрессия 9+10+11+catalog 61/61. Деплой: `migrate storefront 0053`. |
| 2026-05-09 | 10  | _pending_  | Phase 10 — SEO-блоки в категории. Модели `CategorySeoBlock` + `CategorySeoBlockItem` (миграция `0051`), поле `Category.seo_text_title`. Сервис `category_seo_blocks.get_category_seo_blocks` (prefetch items, гидратация `extra.product_id`→Product, фильтр пустых кроме `best_prices`). Партиал `partials/category_seo_blocks.html` с ветками `top_filters`/`top_queries`/`top_cards`/`top_menu`/`best_prices`. Секция в `pages/catalog.html` между гридом и описанием; H2 описания → `seo_text_title|default:category.name`. CSS `category-seo-blocks.css` (glass/neon). Admin: `CategorySeoBlockAdmin` + inline + `list_editable`. Tests: 10 (`storefront.tests.test_phase10_category_seo_blocks`) → all passed; регрессия Phase 9 + test_catalog 29/29. |
| 2026-05-09 | 11  | _pending_  | Phase 11 — SEO admin section. `?section=seo` у кастомній адмін-панелі: sitemap-counts (5 sub + total), AI-панель (opt-in товари/категорії з in-place "Згенерувати"), Phase-10 SEO-блоки (active/total + лінк на Django-admin). Сервіс `services/seo_dashboard.py`, шаблон `partials/admin_seo_dashboard.html`, AJAX-ендпоінт `admin_seo_ai_generate` (sync виклик `generate_ai_content_for_*_task` без Celery — Phase 2). Tests: 11 (`storefront.tests.test_phase11_seo_admin`) → all passed; регрессія Phase 9+10+catalog 50/50. Відкладено в окрему ітерацію: WYSIWYG для `Category.description`, редактор variant-title-шаблонів, robots.txt-редактор. |
| 2026-05-10 | 14  | `5b8cf30d` | Phase 14 — UX-фиксы карточек: CTA "Переглянути" → "Купити" в `partials/product_card.html`. Color-filter-aware preview: `enrich_color_preview_with_slugs(products, color_slugs)` + `attach_preferred_card_image(products, color_slugs)` в `services/color_filter.py`; view'ы `catalog`/`search` ставят `preferred_card_image_url`/`preferred_card_image_alt` на каждый product; шаблон `home_card` показывает variant-image. Tests: 13 (`test_phase14_card_preview`). Регрессия Phase 9 + catalog 19/19. |
| 2026-05-10 | 15  | `00403022` | Phase 15 — per-product SEO landing block. `services/product_seo_landing.py`: `build_landing(product, fit_code=None)` → `{landing_html, top_queries, h2}`; theme-aware H2 + 4–5 параграфов (color / fit / city-Київ-Харків-Львів / brand-DTF-ZSU). `build_top_queries(product)`: ≤14 chips с приоритетом color × fit × city + custom-print + alternate-fit + категория. `Product.seo_bottom_html` (миграция `0058`) — admin override. Партиал `partials/product_seo_landing.html` (header + tabs + фолбэк pricing-table + длинный SEO-текст), CSS `product-seo-landing.css`. Reuse `top_filters`/`top_menu` из категории через `get_category_seo_layout`. Tests: 16 (`test_phase15_product_seo_landing`). |
| 2026-05-10 | fix | `79ad7f25` | Bugfix: многострочные `{# ... #}` в Django **не работают** (рендерятся как текст). Тексты Phase 14 утекали в HTML под "Новинки" и над каждой карточкой. Свернул на 1 строку (`product_card.html:6`) или перевёл на `{% comment %}...{% endcomment %}` (`product_detail.html` × 2). Сбросил `fragments` + `default` Redis-кэш на проде (рекомендации товара кэшируются 1 ч). |
| 2026-05-10 | 16  | `55968ca8` | Phase 16 — fit-aware variant meta + unique fit SEO paragraph. `build_variant_meta`: для 1-segment fit URL fit вынесен **в начало** title/description ("Оверсайз X — купити в TwoComms"); page_keywords заполняется только для fit-only (отсутствует на color-only/multi-segment). `FIT_SEO_COPY` (oversize/classic/regular): уникальный H3 + body параграф (плечи +4–6 см, бавовна 280–320 г/м², use-cases) — рендерится только при path-fit и обеспечивает не-дубль content между oversize и classic страницами. Tests: 11 (`test_phase16_fit_seo`). Регрессия 57/57. |
| 2026-05-10 | 17  | `679b60ab` | Phase 17 — simple fit-toggle UI в кастомній адмін-панели + auto-bootstrap legacy tshirts. `ProductFitToggleForm`: 2 BooleanField (Класична/Оверсайз) + RadioSelect (default). `save(product)` лениво создаёт/активирует/деактивирует canonical pair, **не трогает** custom-codes (regular). `ensure_default_fit_options_for_tshirt()` лечит legacy tshirt-товары без rows: вызов из `views/product._resolve_fit_options` (heal at first PDP view) + admin save flow. UI: 2 toggle-карточки (`admin-fit-toggle.css`, oranges accent), inline-JS sync radio↔switch, legacy formset спрятан в `<details>`. Toggle save runs ONLY when `fit_toggle-` префикс в POST (не ломает legacy admin scripts). Tests: 12 (`test_phase17_fit_toggle`). Регрессия 76/76 (Phase 7 / 14 / 15 / 16 / 17 + admin builder). |
| 2026-05-10 | 18  | `3d65988d` → `caedb45a` | Phase 18 — PDP perf optimization (no visual change). **18a** (`3d65988d`): LCP preload hint. Новый `{% block preload_hints %}` в `base.html` `<head>` + `responsive_images.preload_image` simple_tag, генерит `<link rel=preload as=image imagesrcset='...avif' imagesizes='...' type=image/avif fetchpriority=high>` из существующих `optimized/<slug>_<W>w.avif` файлов. Возвращает "" если AVIF вариантов нет. Tests: 6 (`test_phase18_preload`). Mobile baseline LCP **5000ms → 4115ms** (median 3 runs, **−885ms / −17.7%**); desktop 1500→1300 ms. **18b** (`c61af0dd`): `body main.container-xxl` (специфичность ↑) для inline padding-rule, чтобы Bootstrap async-load `.py-4 !important` не переопределял. CLS desktop 0.131 → 0.129 — **не помогло**, shift был не от этого. **18c** (`034990a7`): block-load Bootstrap CSS на PDP/catalog/search через `<link rel=preload as=style>` + sync `<link rel=stylesheet>`. Mobile CLS 0.019→0.000 ✅, **mobile LCP 4115ms→6760ms ❌ (+2.5 s)** — block-load CSS блокировал discovery LCP-картинки. ROI отрицательный. **18d** (`caedb45a`): откат block-load, оставлен `preload as=style` hint (high-priority discovery без блокировки рендера). Mobile final: LCP 4102 ms (−18% от baseline сохранено), CLS 0.048 (< 0.1 порог CWV), TBT 82 ms — **mobile CWV passing**. Desktop CLS=0.129 остался — shifting element ещё не идентифицирован, отложено до Phase 19. |

> Каждый раз после `git push` + деплоя — добавлять строку.

---

## Phase 13 — Автозаполнение SEO товаров (DONE)

Команда `manage.py autofill_product_seo` + сервис `services/product_seo_autofill.py`.
Заполняет пустые поля `seo_title`, `seo_description`, `seo_keywords`, `main_image_alt`,
`short_description`, `full_description`, `care_instructions`, `target_audience` и создаёт
5 стандартных FAQ. Идемпотентна. Прогон на проде: 64/65 товаров заполнено, 320 FAQ
создано. Коммит: `db9a7b7f`.

---

## Phase 13.5 — Recraft в plain-text + theme-aware copy (DONE)

**Проблема Phase 13**: HTML-теги (`<p>`, `<h3>`, `<ul>`) попадали в поля, рендерящиеся
через `|linebreaksbr` — на странице товара отображались как сырой текст.

**Фикс**:
- `services/product_copy_v2.py` — plain-text генератор (paragraphs через `\n\n`).
- `services/_product_themes.py` — **26 уникальных тем-карт** на 65 товаров (`classic`,
  `my_little_baby`, `where_my_present`, `in_shee`, `business_money`, `last_breath`,
  `kharkiv_district`, `pokrovsk_girl`, `death_grabs_ass`, `dvoznachni_summy`,
  `lord_lending`, `red_leaves`, `na_toy_svit`, `kha_edition`, `kha_style`, `pojuy`,
  `bentejne`, `limited_edition`, `t225`, `pokrovsk_v2`, `drones`, `silent_winter`,
  `glory_ukraine`, `hool`, `idea_hd`, `reality_bends_pink`, `reality_dark_neon`,
  `reality_mentol`, `beliveidea`). Каждая тема — уникальный intro, keywords, audience,
  первый FAQ.
- Безопасная перезапись по сигнатуре Phase 13.
- `manage.py recraft_product_seo --dry-run/--slug/--include-drafts/--force`.
- 12 тестов `storefront.tests.test_phase13b_recraft`.

Прогон на проде: 64 товара пересозданы, 320 FAQ заменены. Коммит: `9a8cf591`.

---

## Phase 14 — UX-фиксы карточек товаров (PLAN)

1. **CTA-кнопка** «Переглянути» → «Купити» в `partials/product_card.html`.
2. **Color-filter-aware preview**: при `?color=<slug>` каждая карточка показывает
   изображение варианта, чей slug совпадает с фильтром (фикс бага «выбрал чёрный, а
   карточка кайот»). Ставим `product.preferred_card_image_url` в view'ах
   `catalog`/`search`, и используем в `partials/product_card.html` ветке `home_card`.

Тесты: расширение `test_phase9_color_filter` — 2 кейса на preview-mapping. Деплой:
`collectstatic` + `restart`. Smoke: `/catalog/hoodie/?color=black` карточки чёрные.

---

## Phase 15 — Per-product SEO landing + dynamic top queries (PLAN)

**Цель**: на каждой странице товара перед футером — блок такой же структуры, как
в категории (top_filters / top_queries / top_menu + длинный текст), но с уникальным
контентом per-product.

**Архитектура**:

- `services/product_seo_landing.py`:
  - `build_landing(product, fit_code=None)` → генерит `landing_html` из темы Phase 13.5
    + 2–3 параграфа с city-keys (Київ/Харків/Львів/Україна) + параграф про fit-варианты.
    Уникальность гарантирована: используется title + theme + colors + fit_options.
  - `build_top_queries(product)` → 10–14 chip'ов: категория+цвет, текущий товар в
    другом цвете/посадке, `/custom-print/`, категория целиком, city-keyword chip'ы.
- Опциональный admin override: `Product.seo_bottom_html` (TextField, blank=True),
  миграция `0054`.
- `top_filters` и `top_menu` блоки переиспользуем из `product.category` через
  `get_category_seo_layout`.
- Партиал `partials/product_seo_landing.html`. Внедрение в `pages/product_detail.html`
  перед `recommended_products`.

Тесты: 8–10 кейсов: уникальность, ключи, валидные href'ы, fallback, admin override.
Деплой: `migrate storefront 0054`, `collectstatic`, `restart`.

---

## Phase 16 — Fit-aware SEO (PLAN)

**Цель**: при выборе посадки meta description / H1 / landing адаптируются.

- Используем существующий `preselected_fit_code` из `views/product.py`.
- Передаём в `build_landing(product, fit_code=...)`.
- Сервис вставляет «оверсайз»/«класична» в meta description, в H1/H2 landing, в
  параграф про посадку, в top-queries chip про другую посадку.
- **Canonical** остаётся базовым (Phase 7.3 уже так делает) — без дублей в индексе.

Тесты: 5–7 кейсов. Деплой: `restart`.

---

> Phase 17+ (i18n RU/EN — бывшая Phase 14) — отложено в отдельную итерацию.
