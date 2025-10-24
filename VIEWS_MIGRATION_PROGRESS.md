# 📊 Отчет о миграции views.py

**Дата**: 24 октября 2025  
**Статус**: 🔄 В процессе

---

## 🎯 Цель миграции

Разбить монолитный файл `storefront/views.py` (7,791 строк) на модульную структуру для:
- Улучшения читаемости кода
- Упрощения поддержки и тестирования
- Соблюдения принципа Single Responsibility
- Ускорения разработки новых функций

---

## ✅ Выполнено (Сегодня)

### 1. **Модуль `cart.py`** — Корзина покупок
Мигрированы функции:
- ✓ `cart_summary` — Краткая сводка корзины (AJAX)
- ✓ `cart_mini` — HTML для мини-корзины
- ✓ Helper functions: `_reset_monobank_session`, `_get_color_variant_safe`, `_color_label_from_variant`, `_hex_to_name`, `_translate_color_to_ukrainian`, `_normalize_color_variant_id`

**Итого**: +2 основных функции, +6 вспомогательных

### 2. **Модуль `profile.py`** — Избранное
Мигрированы функции:
- ✓ `toggle_favorite` — Добавить/удалить из избранного (универсальная)
- ✓ `favorites_list` — Список избранных товаров (с поддержкой гостей)
- ✓ `check_favorite_status` — Проверка статуса избранного
- ✓ `favorites_count` — Количество избранных

**Итого**: +4 функции

**Всего мигрировано сегодня**: 6 основных + 6 вспомогательных = **12 функций**

---

## 📦 Существующие модули

| Модуль | Функции | Статус |
|--------|---------|--------|
| `utils.py` | Helper функции, константы | ✅ Готово |
| `auth.py` | Аутентификация (login, register, logout) | ✅ Готово |
| `catalog.py` | Каталог товаров (home, catalog, search) | ✅ Готово |
| `product.py` | Детали товара | ✅ Готово |
| `cart.py` | Корзина + промокоды | ✅ Расширено |
| `checkout.py` | Оформление заказа | ✅ Готово |
| `profile.py` | Профиль + заказы + избранное | ✅ Расширено |
| `admin.py` | Админ панель | ⚠️ Частично |
| `api.py` | AJAX endpoints | ✅ Готово (+ DRF) |
| `static_pages.py` | Статические страницы | ✅ Готово |

---

## ⏳ Осталось мигрировать (~153 функции)

### 🔴 Приоритет 1: Monobank (Платежи) — ~20 функций
**Создать новый модуль**: `monobank.py`

Функции:
- `monobank_create_invoice`
- `monobank_create_checkout`
- `monobank_return`
- `monobank_webhook`
- `_fetch_and_apply_invoice_status`
- `_fetch_and_apply_checkout_status`
- `_update_order_from_checkout_result`
- `_build_monobank_checkout_payload`
- `_create_single_product_order`
- `_prepare_checkout_customer_data`
- `_monobank_api_request`
- `_create_or_update_monobank_order`
- `_validate_checkout_payload`
- `_ensure_session_key`
- `_verify_monobank_signature`
- `_get_monobank_public_key`
- `_invalidate_monobank_public_key`
- `_notify_monobank_order`
- `_drop_pending_monobank_order`
- `_cleanup_expired_monobank_orders`
- `_cleanup_after_success`
- `_record_monobank_status`

### 🟡 Приоритет 2: Wholesale (Оптовые продажи) — ~15 функций
**Создать новый модуль**: `wholesale.py`

Функции:
- `wholesale_page`
- `wholesale_order_form`
- `generate_wholesale_invoice`
- `download_invoice_file`
- `delete_wholesale_invoice`
- `get_user_invoices`
- `update_invoice_status`
- `check_invoice_approval_status`
- `check_payment_status`
- `toggle_invoice_approval`
- `toggle_invoice_payment_status`
- `reset_all_invoices_status`
- `create_wholesale_payment`
- `wholesale_payment_webhook`
- `wholesale_prices_xlsx`
- `pricelist_page`
- `pricelist_redirect`
- `test_pricelist`

### 🟢 Приоритет 3: Admin Panel — ~40 функций
**Расширить существующий модуль**: `admin.py`

Группы функций:
1. **Orders** (~10):
   - `admin_panel`, `admin_order_update`, `admin_update_payment_status`, `admin_approve_payment`, `admin_order_delete`, `my_orders`, `update_payment_method`, `confirm_payment`

2. **Products** (~15):
   - `admin_product_new`, `admin_product_edit`, `admin_product_edit_simple`, `admin_product_edit_unified`, `admin_product_delete`, `admin_product_colors`, `admin_product_color_delete`, `admin_product_image_delete`, `api_colors`

3. **Categories** (~5):
   - `admin_category_new`, `admin_category_edit`, `admin_category_delete`

4. **Promocodes** (~5):
   - `admin_promocodes`, `admin_promocode_create`, `admin_promocode_edit`, `admin_promocode_toggle`, `admin_promocode_delete`

5. **Invoice Admin** (~4):
   - `admin_update_invoice_status`, `admin_print_proposal_update_status`, `admin_print_proposal_award_points`, `admin_print_proposal_award_promocode`

6. **Users** (~2):
   - `admin_update_user`, `dev_grant_admin`

### 🔵 Приоритет 4: Offline Stores — ~15 функций
**Создать новый модуль**: `stores.py`

Функции:
- `admin_offline_stores`
- `admin_offline_store_create`
- `admin_offline_store_edit`
- `admin_offline_store_toggle`
- `admin_offline_store_delete`
- `admin_store_management`
- `admin_store_get_order_items`
- `admin_store_get_product_colors`
- `admin_store_add_product_to_order`
- `admin_store_remove_product_from_order`
- `admin_store_add_products_to_store`
- `admin_store_generate_invoice`
- `admin_store_update_product`
- `admin_store_remove_product`
- `admin_store_mark_product_sold`
- Helper functions: `_get_store_inventory_items`, `_get_store_sales`, `_calculate_inventory_stats`, `_calculate_sales_stats`, `_build_category_stats`, `_serialize_sale`, `_compose_store_stats`

### 🟣 Приоритет 5: Dropshipping — ~5 функций
**Создать новый модуль**: `dropship.py`

Функции:
- `admin_update_dropship_status`
- `admin_get_dropship_order`
- `admin_update_dropship_order`
- `admin_delete_dropship_order`

### ⚪ Приоритет 6: Points/Promo — ~8 функций
**Расширить модуль**: `profile.py` или создать `loyalty.py`

Функции:
- `user_points`
- `my_promocodes`
- `buy_with_points`
- `purchase_with_points`

### 🔴 Приоритет 7: Debug/Dev Functions — ~10 функций
**Решение**: Удалить или переместить в отдельный debug.py

Функции:
- `debug_media`
- `debug_media_page`
- `debug_product_images`
- `debug_invoices`

### 🟡 Приоритет 8: Misc Functions — ~10 функций
Функции:
- `cooperation`
- `delivery_view`
- `process_guest_order`
- `add_print`
- Вспомогательные функции для feeds

---

## 📈 Статистика миграции

| Показатель | Значение |
|-----------|----------|
| **Начальный размер views.py** | 7,791 строк |
| **Функций в начале** | ~159 |
| **Мигрировано функций** | 6 основных + 6 вспомогательных |
| **Осталось мигрировать** | ~153 |
| **Прогресс** | ~4% |
| **Созданных модулей** | 10 |
| **Нужно создать модулей** | 5 |

---

## 🚀 План дальнейшей работы

### Этап 1: Критические модули (1-2 дня)
1. ✅ `cart.py` — расширен
2. ✅ `profile.py` — расширен
3. 🔄 `monobank.py` — создать (приоритет!)
4. 🔄 `wholesale.py` — создать

### Этап 2: Admin панель (2-3 дня)
1. 🔄 Расширить `admin.py` всеми admin функциями
2. 🔄 Создать `stores.py`
3. 🔄 Создать `dropship.py`

### Этап 3: Дополнительные модули (1 день)
1. 🔄 Создать `loyalty.py` (points + promocodes)
2. 🔄 Удалить debug функции или создать `debug.py`

### Этап 4: Финализация (1 день)
1. 🔄 Удалить старый `views.py`
2. 🔄 Обновить все тесты
3. 🔄 Проверить 100% покрытие URL
4. 🔄 Финальный отчет

---

## 💡 Выводы

### ✅ Преимущества текущей миграции:
- Код стал более читаемым
- Легче писать unit tests
- Проще ориентироваться в проекте
- Модули имеют четкую ответственность
- Обратная совместимость через `__init__.py`

### ⚠️ Сложности:
- Большое количество функций для миграции
- Необходимость сохранения обратной совместимости
- Конфликты при merge (решается автоматически)
- Множество зависимостей между функциями

### 🎯 Следующие шаги:
1. **Продолжить миграцию** по приоритетам
2. **Создать monobank.py** (критично для платежей)
3. **Создать wholesale.py** (важно для бизнеса)
4. **Расширить admin.py** (много функций)

---

## 📝 Рекомендации

1. **Не удалять старый views.py** пока не мигрированы все функции
2. **Тестировать после каждой миграции** группы функций
3. **Сохранять обратную совместимость** через алиасы
4. **Документировать изменения** в коммитах
5. **Проверять работу сайта** после каждого деплоя

---

**Статус**: ✅ Миграция идет по плану  
**Следующая цель**: Создать `monobank.py` с ~20 функциями платежной системы

