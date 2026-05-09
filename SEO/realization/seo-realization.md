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
| 5  | Schema.org: точные shipping/return из реальных страниц     | TODO     |
| 6  | robots.txt — финальная вычитка и нормализация              | TODO     |
| 7  | Path-URL для вариантов товара (size / color / fit)         | TODO     |
| 8  | AJAX-переключение вариантов без перезагрузки               | TODO     |
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

## Phase 5 — Schema.org Product

- `Offer.priceValidUntil` — добавить.
- `Offer.shippingDetails` — генерация из реальной страницы доставки
  (Нова Пошта, тарифы по весу).
- `Offer.hasMerchantReturnPolicy` — из реальной страницы возврата.
- `Product.aggregateRating` — если есть отзывы.
- На страницах вариантов: `Product` с конкретными `color`, `size`,
  `additionalProperty` для крой (классика / оверсайз).
- Добавить `Organization` schema на главной (есть ли — проверить),
  `WebSite` с `SearchAction`.
- BreadcrumbList — уже есть, проверить корректность.

---

## Phase 6 — robots.txt

- Удалить дубли.
- Чёткие `Allow: /` + `Disallow:` для админки/корзины/профиля.
- Sitemap-index в конце.
- Добавить `Disallow: /*?utm_*=` через мета-canonical.

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

- [ ] Endpoint `/api/product/<slug>/variant/` возвращает все нужные поля.
- [ ] JS перехватывает клики по `<a data-variant-link>`.
- [ ] pushState + popstate работают.
- [ ] Все meta/og/canonical обновляются.
- [ ] JSON-LD обновляется.
- [ ] Lighthouse / без-JS проверка: страница отдаётся целиком и без AJAX.
- [ ] Коммит + деплой.

---

## Phase 9 — Цветовой фильтр в каталоге

- Каталог: добавить цветной фильтр (chip-список цветов из ColorVariant).
- URL: `/catalog/<cat>/?color=black,red`.
- На карточке товара — мини-цветные точки (если есть варианты).
- На главной странице рядом с категориями — chip фильтр по цветам.

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

> Каждый раз после `git push` + деплоя — добавлять строку.
