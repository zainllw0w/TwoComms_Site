# 🔄 Оставшиеся функции для миграции из views.py

**Дата создания**: 24 октября 2025  
**Всего функций в views.py**: 155  
**Уже мигрировано**: ~50  
**Осталось мигрировать**: ~105

---

## 📋 Инструкция для миграции

### Общие правила:

1. **Создавать новый модуль** в `twocomms/storefront/views/`
2. **Копировать функции** из `storefront/views.py` (на сервере)
3. **Добавить правильные импорты** в начало файла
4. **Обновить `__init__.py`**:
   - Добавить импорт из нового модуля
   - Добавить функции в `_exclude`
   - Добавить функции в `__all__`
5. **Создать алиасы** если названия функций изменились
6. **Коммит и деплой** после каждой группы

### Путь к файлу на сервере:
```
/home/qlknpodo/TWC/TwoComms_Site/twocomms/storefront/views.py
```

### SSH команда для чтения функций:
```bash
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms/storefront
sed -n "START,ENDp" views.py  # где START,END - номера строк
```

---

## 🔴 ПРИОРИТЕТ 1: MONOBANK ПЛАТЕЖИ (~20 функций, 1171 строка)

**Создать файл**: `twocomms/storefront/views/monobank.py` (уже начат, нужно завершить)

### Основные функции (4):
```python
monobank_create_invoice(request)          # Строки: 5757-5903
monobank_create_checkout(request)         # Строки: 6072-6229
monobank_return(request)                  # Строки: 6231-6290
monobank_webhook(request)                 # Строки: 6292-6350
```

### Helper функции (22):
```python
_reset_monobank_session(request, drop_pending=False)        # 5199-5234
_drop_pending_monobank_order(request)                       # 5339-5355
_notify_monobank_order(order, method_label)                 # 5357-5371
_cleanup_expired_monobank_orders()                          # 5373-5398
_get_monobank_public_key()                                  # 5400-5417
_invalidate_monobank_public_key()                           # 5419-5422
_verify_monobank_signature(request)                         # 5424-5493
_ensure_session_key(request)                                # (найти в views.py)
_validate_checkout_payload(raw_payload)                     # (найти в views.py)
_create_or_update_monobank_order(request, customer_data)   # 5495-5642
_monobank_api_request(method, endpoint, ...)               # 5644-5702
_prepare_checkout_customer_data(request)                    # (найти в views.py)
_record_monobank_status(order, payload, source='api')      # 5704-5755
_build_monobank_checkout_payload(order, ...)              # 5900-6070
_fetch_and_apply_invoice_status(order, invoice_id, ...)   # (найти в views.py)
_fetch_and_apply_checkout_status(order, source='api')     # (найти в views.py)
_update_order_from_checkout_result(order, result, ...)    # (найти в views.py)
_create_single_product_order(product, size, ...)          # (найти в views.py)
_cleanup_after_success(request)                            # (найти в views.py)
```

### Зависимости:
- `orders.models.Order`
- `orders.telegram_notifications`
- `Product`, `PromoCode`
- `ProductColorVariant`
- `requests`, `cryptography`

### Константы:
```python
MONOBANK_SUCCESS_STATUSES = {'success', 'hold'}
MONOBANK_PENDING_STATUSES = {'processing'}
MONOBANK_FAILURE_STATUSES = {'failure', 'expired', 'rejected', 'canceled', 'cancelled', 'reversed'}
```

---

## 🟡 ПРИОРИТЕТ 2: WHOLESALE (ОПТОВЫЕ ПРОДАЖИ) (~15 функций)

**Создать файл**: `twocomms/storefront/views/wholesale.py`

### Основные функции (10):
```python
wholesale_page(request)                           # Страница оптовых продаж
wholesale_order_form(request)                     # Форма заказа
generate_wholesale_invoice(request)               # Генерация счета
download_invoice_file(request, invoice_id)        # Скачать счет
delete_wholesale_invoice(request, invoice_id)     # Удалить счет
get_user_invoices(request)                        # Список счетов пользователя
check_invoice_approval_status(request, invoice_id) # Проверка статуса
check_payment_status(request, invoice_id)         # Проверка оплаты
create_wholesale_payment(request)                 # Создать платеж
wholesale_payment_webhook(request)                # Webhook для платежей
```

### Дополнительные функции (5):
```python
wholesale_prices_xlsx(request)                    # XLSX файл с ценами
pricelist_page(request)                          # Страница прайс-листа
pricelist_redirect(request)                      # Редирект на прайс-лист
test_pricelist(request)                          # Тестовый прайс-лист
update_invoice_status(request, invoice_id)       # Обновить статус счета
```

### Admin функции (3):
```python
toggle_invoice_approval(request, invoice_id)      # Переключить одобрение
toggle_invoice_payment_status(request, invoice_id) # Переключить статус оплаты
reset_all_invoices_status(request)               # Сбросить все статусы
```

### Зависимости:
- `orders.models` (Invoice, WholesaleOrder?)
- `openpyxl` для XLSX
- Модели счетов

---

## 🟢 ПРИОРИТЕТ 3: ADMIN PANEL (~45 функций)

### 3.1 Admin Orders (~8 функций)

**Добавить в**: `twocomms/storefront/views/admin.py`

```python
admin_panel(request)                             # Главная страница админки
admin_order_update(request)                      # Обновить заказ
admin_update_payment_status(request)             # Обновить статус оплаты
admin_approve_payment(request)                   # Подтвердить оплату
admin_order_delete(request, pk: int)             # Удалить заказ
my_orders(request)                               # Мои заказы
update_payment_method(request)                   # Изменить метод оплаты
confirm_payment(request)                         # Подтвердить платеж
```

### 3.2 Admin Products (~9 функций)

```python
admin_product_new(request)                       # Создать товар
admin_product_edit(request, pk)                  # Редактировать товар
admin_product_edit_simple(request, pk)           # Простое редактирование
admin_product_edit_unified(request, pk)          # Унифицированное редактирование
admin_product_delete(request, pk)                # Удалить товар
admin_product_colors(request, pk)                # Цвета товара
admin_product_color_delete(request, product_pk, color_pk) # Удалить цвет
admin_product_image_delete(request, product_pk, image_pk) # Удалить изображение
api_colors(request)                              # API цветов
```

### 3.3 Admin Categories (~3 функции)

```python
admin_category_new(request)                      # Создать категорию
admin_category_edit(request, pk)                 # Редактировать категорию
admin_category_delete(request, pk)               # Удалить категорию
```

### 3.4 Admin Promocodes (~5 функций)

```python
admin_promocodes(request)                        # Список промокодов
admin_promocode_create(request)                  # Создать промокод
admin_promocode_edit(request, pk)                # Редактировать промокод
admin_promocode_toggle(request, pk)              # Переключить статус
admin_promocode_delete(request, pk)              # Удалить промокод
```

### 3.5 Admin Invoices (~3 функции)

```python
admin_update_invoice_status(request, invoice_id) # Обновить статус счета
admin_print_proposal_update_status(request)      # Обновить статус предложения
admin_print_proposal_award_points(request)       # Начислить баллы
admin_print_proposal_award_promocode(request)    # Выдать промокод
```

### 3.6 Admin Users (~2 функции)

```python
admin_update_user(request)                       # Обновить пользователя
dev_grant_admin(request)                         # Выдать админа (dev)
```

---

## 🔵 ПРИОРИТЕТ 4: OFFLINE STORES (~20 функций)

**Создать файл**: `twocomms/storefront/views/stores.py`

### Основные функции (5):
```python
admin_offline_stores(request)                    # Список магазинов
admin_offline_store_create(request)              # Создать магазин
admin_offline_store_edit(request, pk)            # Редактировать магазин
admin_offline_store_toggle(request, pk)          # Переключить статус
admin_offline_store_delete(request, pk)          # Удалить магазин
```

### Управление магазином (10):
```python
admin_store_management(request, store_id)                        # Управление
admin_store_get_order_items(request, store_id, order_id)       # Товары заказа
admin_store_get_product_colors(request, store_id, product_id)  # Цвета товара
admin_store_add_product_to_order(request, store_id)            # Добавить в заказ
admin_store_remove_product_from_order(request, store_id, order_id, item_id) # Удалить
admin_store_add_products_to_store(request, store_id)           # Добавить товары
admin_store_generate_invoice(request, store_id)                # Генерация счета
admin_store_update_product(request, store_id, product_id)      # Обновить товар
admin_store_remove_product(request, store_id, product_id)      # Удалить товар
admin_store_mark_product_sold(request, store_id, product_id)   # Отметить проданным
```

### Helper функции (7):
```python
_get_store_inventory_items(store)                # Инвентарь магазина
_get_store_sales(store)                          # Продажи магазина
_calculate_inventory_stats(inventory_items)      # Статистика инвентаря
_calculate_sales_stats(sales_items)              # Статистика продаж
_build_category_stats(inventory_items)           # Статистика по категориям
_serialize_sale(sale)                            # Сериализация продажи
_compose_store_stats(inventory_items, sales_items) # Общая статистика
```

---

## 🟣 ПРИОРИТЕТ 5: DROPSHIPPING (~4 функции)

**Создать файл**: `twocomms/storefront/views/dropship.py`

```python
admin_update_dropship_status(request, order_id)  # Обновить статус
admin_get_dropship_order(request, order_id)      # Получить заказ
admin_update_dropship_order(request, order_id)   # Обновить заказ
admin_delete_dropship_order(request, order_id)   # Удалить заказ
```

### Зависимости:
- `orders.models.DropshipperOrder`

---

## ⚪ ПРИОРИТЕТ 6: DEBUG FUNCTIONS (~5 функций)

**Варианты**:
1. Создать `debug.py`
2. Удалить (если не используются)

```python
debug_media(request)                             # Отладка медиа
debug_media_page(request)                        # Страница отладки медиа
debug_product_images(request)                    # Отладка изображений
debug_invoices(request)                          # Отладка счетов
```

---

## 🟤 ПРИОРИТЕТ 7: MISC FUNCTIONS (~10 функций)

### Добавить в соответствующие модули:

```python
# В static_pages.py:
delivery_view(request)                           # Страница доставки
cooperation(request)                             # Страница сотрудничества

# В checkout.py:
process_guest_order(request)                     # Обработка гостевого заказа
order_create(request)                            # Создание заказа (алиас?)

# В admin.py или отдельный модуль:
custom_sitemap(request)                          # Кастомная карта сайта

# Helper для feeds (в static_pages.py):
_sanitize_feed_description(raw: str)             # Очистка описания
_material_for_product(product)                   # Материал товара
_normalize_color_name(raw_color)                 # Нормализация цвета
_absolute_media_url(base_url, path)              # Абсолютный URL медиа
_get_product_image_url(product, request)         # URL изображения
```

---

## 📝 Helper функции (уже частично мигрированы)

### В cart.py (✅ мигрированы):
```python
_reset_monobank_session
_normalize_color_variant_id
_get_color_variant_safe
_hex_to_name
_translate_color_to_ukrainian
_color_label_from_variant
```

### Еще нужно мигрировать:
```python
_allocate_discount(line_totals, discount)        # В cart.py
```

---

## 🔧 Порядок миграции (рекомендуемый)

### Этап 1: Быстрые победы (1-2 часа)
1. ✅ Debug functions → удалить или создать `debug.py`
2. ✅ Misc functions → распределить по существующим модулям
3. ✅ Helper functions → добавить в соответствующие модули

### Этап 2: Бизнес-логика (2-3 часа)
1. ✅ Dropshipping → `dropship.py` (4 функции)
2. ✅ Wholesale → `wholesale.py` (~15 функций)

### Этап 3: Admin панель (3-4 часа)
1. ✅ Admin Orders → `admin.py` (~8 функций)
2. ✅ Admin Products → `admin.py` (~9 функций)
3. ✅ Admin Categories → `admin.py` (~3 функции)
4. ✅ Admin Promocodes → `admin.py` (~5 функций)
5. ✅ Admin Invoices → `admin.py` (~3 функции)
6. ✅ Admin Users → `admin.py` (~2 функции)

### Этап 4: Критичная инфраструктура (4-6 часов)
1. ✅ Offline Stores → `stores.py` (~20 функций)
2. ✅ Monobank → `monobank.py` (~26 функций, 1171 строка)

---

## ⚠️ Важные замечания

### Безопасность:
- **Monobank** - критично для платежей, требует тщательного тестирования
- **Webhook** функции не забыть добавить `@csrf_exempt`
- **Admin** функции должны иметь `@staff_required` или проверки прав

### Тестирование:
- После каждой группы - деплой и проверка
- Особое внимание к Monobank (платежная система)
- Проверить все URL в `urls.py`

### Обратная совместимость:
- Создавать алиасы для функций с измененными названиями
- Проверять что `urls.py` продолжает работать
- Не удалять старый `views.py` до полной миграции

---

## 📊 Статистика

| Группа | Функций | Статус | Приоритет |
|--------|---------|--------|-----------|
| **Monobank** | ~26 | ⏳ Начато | 🔴 Высокий |
| **Wholesale** | ~15 | ⏳ TODO | 🟡 Высокий |
| **Admin Panel** | ~30 | ⏳ TODO | 🟢 Средний |
| **Offline Stores** | ~20 | ⏳ TODO | 🔵 Средний |
| **Dropshipping** | ~4 | ⏳ TODO | 🟣 Низкий |
| **Debug** | ~5 | ⏳ TODO | ⚪ Низкий |
| **Misc** | ~10 | ⏳ TODO | 🟤 Низкий |
| **Всего** | **~110** | **0% готово** | - |

---

## 🚀 Пример миграции

### 1. Создать файл:
```bash
touch twocomms/storefront/views/wholesale.py
```

### 2. Добавить структуру:
```python
"""
Wholesale views - Оптовые продажи.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
# ... другие импорты

# Функции здесь
```

### 3. Скопировать функции из views.py:
```bash
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms/storefront
# Найти нужные функции и скопировать
```

### 4. Обновить `__init__.py`:
```python
# Добавить импорт
from .wholesale import (
    wholesale_page,
    wholesale_order_form,
    # ... все функции
)

# Добавить в _exclude
_exclude = {
    # ...
    'wholesale_page', 'wholesale_order_form', # ...
}

# Добавить в __all__
__all__ = [
    # ...
    'wholesale_page', 'wholesale_order_form', # ...
]
```

### 5. Коммит и деплой:
```bash
git add -A
git commit -m "feat: migrate wholesale functions to wholesale.py"
git push origin main
# Деплой на сервер
```

---

## ✅ Чек-лист для каждого модуля

- [ ] Файл создан с правильными импортами
- [ ] Все функции скопированы из views.py
- [ ] Добавлены необходимые зависимости
- [ ] Обновлен `__init__.py` (импорт, _exclude, __all__)
- [ ] Созданы алиасы для совместимости
- [ ] Написаны docstrings
- [ ] Код проверен локально (если возможно)
- [ ] Коммит с описательным сообщением
- [ ] Деплой на сервер
- [ ] Проверка работы сайта
- [ ] Проверка соответствующих URL

---

**Готово для параллельной миграции!** 🤖

Каждый бот может взять отдельную группу функций и мигрировать её независимо.


















