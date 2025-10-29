# Catalog Redesign Test Playbook

> Цель документа — передать другому агенту максимально подробную инструкцию по проверке всего, что было сделано в рамках редизайна каталога. Все проверки должны выполняться локально и изолированно, предпочтительно на SQLite-тестовой базе, без влияния на боевую среду и основные миграции.

## 1. Обзор и границы тестирования
- Новые доменные сущности: `Catalog`, `CatalogOption`, `CatalogOptionValue`, `SizeGrid`, расширенный `Product`.
- Сервисный слой: `storefront/services/product_builder.py`, `storefront/services/catalog_helpers.py`, интеграции `seo_utils`, `ai_signals`.
- Новые DRF-вьюсеты: `AdminProductBuilderViewSet` и связанные эндпоинты (`/api/admin/product-builder/*`).
- Шаблон и фронтенд: `product_builder.html`, `product-builder.js`, связанные CSS/partials.
- Формы и formset’ы: `ProductForm`, `SizeGridForm`, `ColorVariantFormSet`, `CatalogOptionFormSet`.
- Сторонние взаимодействия: AI генерация (mock), кеширование, права доступа.

Покрытие должно включать unit, integration, API, UI, performance, regression и smoke-проверки.

## 2. Тестовая среда и инструменты
- **Django settings**: `DJANGO_SETTINGS_MODULE=twocomms.settings`.
- **Тестовый раннер**: штатный Django `manage.py test`; допускается `pytest` при наличии.
- **Библиотеки**: `pytest`, `pytest-django`, `factory-boy`, `freezegun`, `responses` (для mock HTTP), `playwright` или `pytest-playwright`.
- **Линтеры и типизация**: `flake8`, `isort`, `mypy` (опционально — фиксация недочетов для последующей передачи).

### 2.1 SQLite тестовая база
Чтобы не затрагивать основную MySQL/PG базу:
1. Создать файл `twocomms/settings_test_sqlite.py` (если отсутствует) со следующим содержимым:
   ```python
   from .settings import *  # noqa

   DATABASES['default'] = {
       'ENGINE': 'django.db.backends.sqlite3',
       'NAME': BASE_DIR / 'var' / 'catalog_test.sqlite3',
       'TEST': {
           'NAME': BASE_DIR / 'var' / 'catalog_test.sqlite3',
       },
   }
   ```
2. Экспортировать переменную окружения:  
   `export DJANGO_SETTINGS_MODULE=twocomms.settings_test_sqlite`
3. Запустить миграции только для тестовой БД:  
   `python manage.py migrate --settings=twocomms.settings_test_sqlite`
4. При запуске тестов Django автоматически создаст и уничтожит временную копию, не затрагивая боевую БД.

### 2.2 Правила запуска тестов
- Обычный прогон: `python manage.py test storefront --settings=twocomms.settings_test_sqlite --verbosity 2`.
- Целевой модуль: `python manage.py test storefront.tests.test_admin_product_builder --verbosity 2`.
- Pytest: `pytest storefront/tests -c pytest.ini --ds=twocomms.settings_test_sqlite`.
- Для Playwright E2E: `npx playwright test --config=playwright.config.ts`.

## 3. Матрица покрытия

| Слой               | Конкретные зоны                               | Типы тестов                          | Инструменты / Комментарии                                  |
|--------------------|-----------------------------------------------|--------------------------------------|------------------------------------------------------------|
| Доменные модели    | Catalog / CatalogOption / SizeGrid / Product  | Unit (модели, сигналы)               | `django.test.TestCase`, фабрики                            |
| Сервисы            | `product_builder`, `catalog_helpers`, SEO/AI  | Unit + интеграция                    | mock, `freezegun`, `responses`                             |
| Формы              | ProductForm + formset’ы                       | Unit                                 | `Client`, `FormTestCase`                                   |
| API (DRF)          | Admin Product Builder endpoints               | API/integration                      | `APITestCase`, ангулярные JSON снапшоты                    |
| UI/JS              | product-builder.js взаимодействия             | E2E (Playwright), unit (Jest)        | Playwright, `vitest`/`jest` (по необходимости)             |
| Миграции и данные  | Связность, обратимость                        | Миграционные, дата-интеграция        | `MigrationExecutor`, кастомные проверки                    |
| Кеши и перф        | get_categories_cached, payload size           | Performance, cache, regression       | custom profiler, `pytest-benchmark`, настройка cache backends |
| Права доступа      | Staff/Non-staff, rate limiting                | Security, negative tests             | `Client`, manual headers                                   |
| Ретросовместимость | Старые views/templates                        | Regression smoke                     | Selenium-lite/Playwright, snapshot CSS проверки            |

## 4. Детализированные тест-кейсы

### 4.1 Доменные модели
- **Catalog CRUD и индексирование**
  - Шаги: создать `Catalog`, обновить `order`, `is_active`, проверить сортировку по `order`, снять/вернуть активность.
  - Ожидание: соблюдаются ограничения уникальности slug, индексы ускоряют выборку (`assertNumQueries`).
- **CatalogOption уникальность**
  - Шаги: создать две опции с одинаковым именем для каталога.
  - Ожидание: `IntegrityError`; отдельный тест проверяет `unique_together`.
- **CatalogOptionValue порядок и флаги**
  - Шаги: создать набор значений, переключить `is_default`, проверить автосортировку по `order`, сериализацию метаданных.
  - Ожидание: один `is_default` на опцию; метаданные не теряются.
- **SizeGrid привязка к каталогу**
  - Шаги: создать сетку, потом удалить каталог.
  - Ожидание: каскадное удаление, тест проверяет `on_delete=models.CASCADE`.
- **Product расширения**
  - Проверить: обязательность slug, автогенерацию при сохранении формой; поля SEO/AI; поведение `priority`, `published_at`, `recommendation_tags`.
  - Негатив: попытка привязать продукт к неактивному каталогу → валидация формы должна провалиться.

### 4.2 Сервисный слой
- **`serialize_catalog`**
  - Проверка: возвращает опции и size grids с корректной сортировкой, без N+1 (`assertNumQueries`).
- **`list_catalog_payloads`**
  - Сравнить активные/неактивные каталоги, убедиться в фильтрации по `active_only`.
- **`serialize_product`**
  - Проверить наличие SEO/AI блоков, order вариантов цвета, корректность fallback для `main_image`.
  - Негатив: продукт без каталога — поле `catalog` должно быть `None`, но `catalog_id` отсутствовать не должно.
- **`get_product_builder_payload`**
  - С продуктом: содержит ключи `product` и `catalogs`.
  - С только каталогом: ключ `catalog`.
  - Без аргументов: только `catalogs`.
- **`catalog_helpers.build_color_preview_map`**
  - Проверка на пустой список, корректная структура, устойчивость к отсутствию `ProductColorVariant`.
  - Протестировать ветку с несуществующей моделью (mock `apps.get_model` чтобы выбросить `LookupError`).

### 4.3 Формы и formset’ы
- **ProductForm**
  - Валидация обязательных полей, автогенерация slug, привязка size grid.
  - Негативные сценарии: slug-коллизия, `price` < 0, `discount_percent` > 100.
- **CatalogOptionFormSet**
  - Добавление/удаление опций, валидация `order`, `is_additional_cost` и `additional_cost`.
- **ColorVariantFormSet + вложенные images formset**
  - Проверить создание варианта с изображениями, reorder, `is_default`.
  - Негатив: два варианта с `is_default=True` → валидация должна упасть.
- **SizeGridForm**
  - Создание новой сетки в рамках POST из конструктора, проверка автопривязки к продукту.

### 4.4 API / DRF
- **`GET /api/admin/product-builder/`**
  - Ожидание: JSON с `catalogs`, каждый содержит опции, size grids.
  - Проверить кеширование (использовать `assertNumQueries` при повторном запросе).
- **`GET /api/admin/product-builder/{id}/`**
  - Ожидание: возвращает продукт со всеми вложенными сущностями, включая seo/ai.
  - Негатив: запрос несуществующего id → `404`.
- **`GET /api/admin/product-builder/catalogs?active=false`**
  - Проверка фильтра по активности.
- **`GET /api/admin/product-builder/catalogs/{id}/`**
  - Проверить сериализацию конкретного каталога, ручку ошибок при неверном id.
- **`GET /api/admin/product-builder/product/new`**
  - Без параметров: каталоги.
  - С `?catalog=<id>`: предзаполненный `catalog`.
- **Права доступа**
  - Неавторизованный → `401`.
  - Пользователь без `is_staff` → `403`.
  - Staff пользователь → `200`.
- **Rate limiting / headers**
  - Подготовить тест с имитацией большого количества запросов (mock throttling класса, если будет добавлен).

### 4.5 Шаблоны и фронтенд
- **Unit (JS)**
  - Использовать `jest`/`vitest` для модулей `product-builder.js`:  
    - Инициализация без формы → вывод предупреждения.  
    - Drag&Drop событийный поток (`start`, `over`, `drop`).  
    - Автосохранение: дебаунс, повторный запрос при ошибке.  
    - Интеграция с AI панелью: события `generateSEO`, обработка статусов.
- **E2E (Playwright)**
  - `scenario_create_basic_product` — создать товар с одной цветовой вариацией и size grid.
  - `scenario_add_multiple_variants` — drag&drop reorder, загрузка фиктивных изображений.
  - `scenario_ai_generation_fallback` — имитация 500 от AI API (mock сервис Worker), проверка UI fallback.
  - `scenario_access_control` — попытка открыть конструктор неавторизованным пользователем.
  - `scenario_responsive_layout` — viewport mobile/desktop, проверка чек-листа прогресса.
- **Accessibility**
  - Проверить наличие aria-атрибутов, фокус-ловушки, клавиатурную навигацию.
  - Использовать `playwright-a11y-snapshot` или `axe-playwright`.

### 4.6 Миграции и данные
- **Проверка применения**
  - Запустить `MigrationExecutor` на SQLite, убедиться что миграции применяются и откатываемы.
- **Data migration dry-run**
  - Если есть кастомные миграции (slug fill, default catalog), протестировать на фикстурах старых данных.
- **Совместимость**
  - Проверить, что старые товары без `catalog_id` корректно сериализуются и отображаются.

### 4.7 AI и SEO
- Использовать `responses` для подмены запросов к AI.
- Тесты позитив/негатив: успешная генерация, таймаут, rate limit.
- Проверить кэширование результатов (`ai_description` не перезаписывается без явного запроса).
- Валидация SEO: длина title/description, уникальность slug (коллизии → предложение нового slug).

### 4.8 Производительность и кеширование
- **Payload size**
  - Измерить размер ответа `/api/admin/product-builder/{id}/`, сравнить с целевым (не более 200 КБ).
- **Кол-во запросов**
  - `assertNumQueries` для основных API (целевой ≤ 5 запросов).
- **Кеш `get_categories_cached`**
  - Прогнать тесты с fake cache backend: первый запрос → SQL, второй → без SQL.
- **Stress**
  - Использовать `pytest-benchmark` для сериализации каталога с 50 опциями и 200 вариантами цвета.

### 4.9 Безопасность и права
- Проверить CSRF для HTML формы конструктора.
- Убедиться, что API возвращает только необходимые поля (нет утечек внутренних идентификаторов).
- Проверить rate-limit (когда будет добавлен) и поведение при истекшей сессии.

### 4.10 Регрессия и обратная совместимость
- Smoke по старым страницам каталога (`/catalog`, `/product/<slug>`).
- Тесты корзины/дропшип витрины на предмет использования новых полей (`catalog` не должен ломать сериализаторы).
- Проверка, что RSS/feeds (если есть) отрабатывают c новыми полями.

## 5. Организация тестовых данных
- Использовать фабрики или фикстуры:
  - `CatalogFactory`, `CatalogOptionFactory`, `ProductFactory`, `ProductColorVariantFactory`.
  - Предусмотреть JSON-фикстуры для Playwright (example: `fixtures/catalog_base.json`).
- Для изображений применять `SimpleUploadedFile` и временные директории (`override_settings(MEDIA_ROOT=tempdir)`).
- В тестах, требующих миграций, использовать транзакционные кейсы (`TransactionTestCase`) и `setUpClass`.
- Все вспомогательные данные (например, результаты AI mock) хранить в `tests/fixtures/ai_responses/`.

## 6. Отчетность и логирование
- Каждый прогон фиксировать в `reports/catalog_redesign/tests/<timestamp>/`.
- Снимки (Playwright) сохранять в `reports/catalog_redesign/artifacts/`.
- Для performance тестов — CSV/JSON в `reports/catalog_redesign/perf/`.

### 6.1 Формат отчета об ошибке
```
Заголовок: [Каталог] Краткое описание бага
Компонент: (модель / API / UI / миграции / AI / др.)
Окружение: settings_test_sqlite, commit hash, версия Python
Шаги воспроизведения:
1. ...
2. ...
Ожидание:
Фактический результат:
Логи/артефакты: (прикрепить snippets, скриншоты, Playwright trace)
Коэффициент критичности: blocker / critical / major / minor / trivial
Заметки: гипотезы, предположения, идеи по фиксу
```

### 6.2 Матрица статусов
- **Blocker** — тест стопорит релиз, требуется немедленное исправление.
- **Critical** — ключевая функциональность нарушена, но есть обходной путь.
- **Major** — существенная проблема, но без угрозы основным сценариям.
- **Minor** — косметическое или edge-case отклонение.
- **Trivial** — пожелание/улучшение.

## 7. Регулярность прогонов
- **Каждый commit** в ветку редизайна: unit + API тесты.
- **Перед merge**: полный suite (unit + API + JS unit + основная Playwright-сессия).
- **Перед релизом**: полный regression + performance + AI smoke.
- **После релиза (T+1 день)**: smoke + мониторинг логов (Sentry, Prometheus).

## 8. Артефакты для передачи
- Логи тестов (`.log`, `.json`), отчеты покрытий (`coverage.xml`, `htmlcov/`).
- Playwright traces (`.zip`), скриншоты, видео.
- Отдельный файл `reports/catalog_redesign/summary.md` с итогами прогона.
- Обновленный чеклист (галочки и комментарии) → синхронизация с `CATALOG_REDESIGN_CHECKLIST.md`.

## 9. Дополнительные рекомендации
- Поддерживать изоляцию: для тестов, которые модифицируют глобальные настройки (`settings`), использовать `override_settings`.
- Всегда чистить временные директории по окончании (`self.addCleanup` или менеджеры контекста).
- Для AI тестов — документировать исходные prompt/response, чтобы можно было восстановить при regressions.
- Вести реестр найденных проблем и ссылаться на них в отчете (issue tracker, Notion, etc.).

---

Этот playbook можно расширять по мере добавления новых функций (AI, очереди, rate limiting). Перед погружением в тесты рекомендуется перепроверить актуальность миграций и соответствие кода `CATALOG_REDESIGN_BLUEPRINT.md`.

