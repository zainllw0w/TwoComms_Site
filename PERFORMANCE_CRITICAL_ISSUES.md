# КРИТИЧЕСКИЕ ПРОБЛЕМЫ - Детальный анализ

**Дата:** 2025-01-30  
**Статус:** Глубокий анализ с проверкой через Context7

---

## 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА #1: Отсутствие фильтра по status='published'

### Проблема:
В публичных views НЕТ фильтра по `status='published'`, что позволяет показывать черновики и архивированные товары на сайте.

### Затронутые файлы:

#### 1. `twocomms/storefront/views/catalog.py`

**home()** (строка 41-50):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
featured = Product.objects.select_related('category').filter(
    featured=True
).order_by('-id').first()

product_qs = Product.objects.select_related('category').order_by('-id')
```

**Исправление:**
```python
featured = Product.objects.select_related('category').filter(
    featured=True,
    status='published'  # ✅ ДОБАВИТЬ
).order_by('-id').first()

product_qs = Product.objects.select_related('category').filter(
    status='published'  # ✅ ДОБАВИТЬ
).order_by('-id')
```

**load_more_products()** (строка 105):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
product_qs = Product.objects.select_related('category').order_by('-id')
```

**Исправление:**
```python
product_qs = Product.objects.select_related('category').filter(
    status='published'  # ✅ ДОБАВИТЬ
).order_by('-id')
```

**catalog()** (строка 159-165):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
if cat_slug:
    product_qs = Product.objects.select_related('category').filter(
        category=category
    ).order_by('-id')
else:
    product_qs = Product.objects.select_related('category').order_by('-id')
```

**Исправление:**
```python
if cat_slug:
    product_qs = Product.objects.select_related('category').filter(
        category=category,
        status='published'  # ✅ ДОБАВИТЬ
    ).order_by('-id')
else:
    product_qs = Product.objects.select_related('category').filter(
        status='published'  # ✅ ДОБАВИТЬ
    ).order_by('-id')
```

**search()** (строка 209):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
product_qs = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images')

if query:
    product_qs = product_qs.filter(title__icontains=query)
```

**Исправление:**
```python
product_qs = Product.objects.select_related('category').prefetch_related('images', 'color_variants__images').filter(
    status='published'  # ✅ ДОБАВИТЬ
)

if query:
    product_qs = product_qs.filter(title__icontains=query)
```

#### 2. `twocomms/storefront/views/product.py`

**product_detail()** (строка 52):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
```

**Исправление:**
```python
product = get_object_or_404(
    Product.objects.select_related('category').filter(status='published'),  # ✅ ДОБАВИТЬ
    slug=slug
)
```

**НО:** Нужно проверить - возможно, для детальной страницы нужно показывать товар даже если он в draft (для превью). Но для публичного доступа - только published.

**Рекомендация:** Добавить проверку прав доступа:
```python
product = get_object_or_404(
    Product.objects.select_related('category'),
    slug=slug
)

# Проверяем доступ: только published для всех, или draft для staff
if product.status != 'published' and not request.user.is_staff:
    from django.http import Http404
    raise Http404("Product not found")
```

#### 3. `twocomms/storefront/views/api.py`

**get_product_json()** (строка 34):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
product = Product.objects.select_related('category').get(id=product_id)
```

**Исправление:**
```python
product = Product.objects.select_related('category').filter(
    status='published'  # ✅ ДОБАВИТЬ
).get(id=product_id)
```

**get_related_products()** (строка 230):
```python
# ❌ ПРОБЛЕМА: Нет фильтра по status
related = Product.objects.filter(
    category=product.category
).exclude(
    id=product_id
).select_related('category')[:6]
```

**Исправление:**
```python
related = Product.objects.filter(
    category=product.category,
    status='published'  # ✅ ДОБАВИТЬ
).exclude(
    id=product_id
).select_related('category')[:6]
```

### Риски:
1. **Безопасность:** Черновики товаров видны публично
2. **SEO:** Индексация неопубликованных товаров
3. **UX:** Пользователи видят недоступные товары
4. **Производительность:** Загружаются лишние товары из БД

### Приоритет: 🔴 КРИТИЧНО

---

## 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА #2: N+1 запросы в циклах

### Детальный анализ всех N+1 проблем:

#### 1. `view_cart` (cart.py:141)
- **Проблема:** `Product.objects.get(id=product_id)` в цикле
- **Исправление:** Использовать `in_bulk()`
- **Приоритет:** 🔴 КРИТИЧНО

#### 2. `cart_items_api` (cart.py:1039)
- **Проблема:** `Product.objects.get(id=product_id)` в цикле
- **Исправление:** Использовать `in_bulk()`
- **Приоритет:** 🔴 КРИТИЧНО

#### 3. `checkout` (checkout.py:66)
- **Проблема:** `Product.objects.get(id=product_id)` в цикле
- **Исправление:** Использовать `in_bulk()`
- **Приоритет:** 🔴 КРИТИЧНО

#### 4. `_get_color_variant_safe` (utils.py:294)
- **Проблема:** Вызывается в цикле, делает отдельный запрос для каждого варианта
- **Исправление:** Создать `_get_color_variants_bulk()` функцию
- **Приоритет:** 🔴 КРИТИЧНО

---

## 🟡 ПРОБЛЕМА #3: Отсутствие prefetch_related для images

### Затронутые views:

1. **home()** - нет prefetch_related для images
2. **load_more_products()** - нет prefetch_related для images
3. **catalog()** - нет prefetch_related для images
4. **product_detail()** - нет prefetch_related для images
5. **get_product_json()** - нет prefetch_related для images
6. **get_related_products()** - нет prefetch_related для images

### Исправление:
Добавить `.prefetch_related('images', 'color_variants__images')` во все queryset'ы.

---

## 🟡 ПРОБЛЕМА #4: Отсутствие фильтра по is_active для Category

### Проблема:
В некоторых views категории загружаются без фильтра по `is_active=True`.

### Проверка:
- `get_categories_cached()` - нужно проверить, есть ли там фильтр

---

## 📊 СВОДНАЯ ТАБЛИЦА ВСЕХ ПРОБЛЕМ

| # | Файл | Функция | Строка | Проблема | Приоритет | Статус |
|---|------|---------|--------|----------|-----------|--------|
| 1 | catalog.py | home | 41-50 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 2 | catalog.py | load_more_products | 105 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 3 | catalog.py | catalog | 159-165 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 4 | catalog.py | search | 209 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 5 | product.py | product_detail | 52 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 6 | api.py | get_product_json | 34 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 7 | api.py | get_related_products | 230 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 8 | cart.py | view_cart | 141 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 9 | cart.py | cart_items_api | 1039 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 10 | checkout.py | checkout | 66 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 11 | utils.py | _get_color_variant_safe | 294 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 12 | catalog.py | home | 50 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 13 | catalog.py | load_more_products | 105 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 14 | catalog.py | catalog | 165 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 15 | product.py | product_detail | 52 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 16 | api.py | get_product_json | 34 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 17 | api.py | get_related_products | 230 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |

---

## 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА #5: N+1 в @property display_image

### Проблема:
Метод `display_image` в модели `Product` вызывает запросы к БД:
```python
@property
def display_image(self):
    if self.main_image:
        return self.main_image
    
    # ❌ ПРОБЛЕМА: Запрос к БД
    first_color_variant = self.color_variants.first()
    if first_color_variant:
        # ❌ ПРОБЛЕМА: Еще один запрос к БД
        first_image = first_color_variant.images.first()
        if first_image:
            return first_image.image
    
    return None
```

### Где используется:
- `product_card.html` (строка 12): `{% if p.display_image %}`
- `index.html` (строка 315): В кэше используется `p.display_image.name`

### Проблема:
При отображении списка товаров (например, 20 товаров):
- Если у товара нет `main_image`, вызывается `color_variants.first()` - 20 запросов
- Затем `images.first()` - еще 20 запросов
- Итого: 40 дополнительных запросов для списка из 20 товаров

### Решение:
1. **Использовать prefetch_related** при загрузке товаров:
```python
Product.objects.select_related('category').prefetch_related(
    'color_variants__images',
    'images'
)
```

2. **Или кэшировать результат** в queryset:
```python
# В view после загрузки товаров
for product in products:
    # Предзагружаем display_image
    if not product.main_image:
        # Используем prefetched данные
        variants = list(product.color_variants.all())
        if variants:
            images = list(variants[0].images.all())
            if images:
                product._cached_display_image = images[0].image
```

3. **Или изменить логику** - всегда использовать main_image или передавать image_url из view.

### Приоритет: 🔴 КРИТИЧНО (для списков товаров)

---

## 🟡 ПРОБЛЕМА #6: N+1 в build_color_preview_map

### Проблема:
В строке 73 `catalog_helpers.py`:
```python
images = list(getattr(variant, 'images', []).all() if hasattr(variant, 'images') else [])
```

### Проблема:
Даже если prefetch_related был использован, вызов `.all()` может вызвать дополнительный запрос, если prefetch не сработал правильно.

### Исправление:
```python
# Использовать prefetched cache
images = getattr(variant, '_prefetched_objects_cache', {}).get('images', [])
if not images:
    # Fallback if prefetch didn't work
    images = list(variant.images.all()) if hasattr(variant, 'images') else []
```

### Приоритет: 🟡 ВЫСОКИЙ

---

## 📊 ОБНОВЛЕННАЯ СВОДНАЯ ТАБЛИЦА

| # | Файл | Функция | Строка | Проблема | Приоритет | Статус |
|---|------|---------|--------|----------|-----------|--------|
| 1 | catalog.py | home | 41-50 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 2 | catalog.py | load_more_products | 105 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 3 | catalog.py | catalog | 159-165 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 4 | catalog.py | search | 209 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 5 | product.py | product_detail | 52 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 6 | api.py | get_product_json | 34 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 7 | api.py | get_related_products | 230 | Нет фильтра status='published' | 🔴 КРИТИЧНО | ⏳ |
| 8 | cart.py | view_cart | 141 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 9 | cart.py | cart_items_api | 1039 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 10 | checkout.py | checkout | 66 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 11 | utils.py | _get_color_variant_safe | 294 | N+1 в цикле | 🔴 КРИТИЧНО | ⏳ |
| 12 | models.py | display_image | 274 | N+1 в @property | 🔴 КРИТИЧНО | ⏳ |
| 13 | catalog_helpers.py | build_color_preview_map | 73 | N+1 для images | 🟡 ВЫСОКИЙ | ⏳ |
| 14 | catalog.py | home | 50 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 15 | catalog.py | load_more_products | 105 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 16 | catalog.py | catalog | 165 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 17 | product.py | product_detail | 52 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 18 | api.py | get_product_json | 34 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |
| 19 | api.py | get_related_products | 230 | Нет prefetch_related | 🟡 ВЫСОКИЙ | ⏳ |

---

**Статус:** ✅ Критические проблемы найдены и задокументированы  
**Всего проблем:** 19 (12 критических, 7 высокого приоритета)

