# Промпт для создания Instagram/Meta фида на основе Google Merchant Feed v3

## 📋 Контекст и цель

Необходимо создать Django management команду для генерации **Instagram/Meta Commerce Platform фида** на основе существующего **Google Merchant Feed v3**. 

**КРИТИЧЕСКАЯ ЦЕЛЬ:** Фидер будет использоваться для запуска рекламы на каталоге (Dynamic Product Ads / Advantage+ Catalog Ads) в Instagram для Черной Пятницы. Поэтому **критически важно** обеспечить:
- ✅ **Точное сопоставление ID с Meta Pixel** - `g:id` в фиде должен ТОЧНО совпадать с `content_ids` в Pixel событиях
- ✅ **Все обязательные поля для рекламы** - включая `quantity_to_sell_on_facebook` для Checkout
- ✅ **Оптимизация для Instagram** - правильные размеры изображений, rich_text_description
- ✅ **Идеальная структура** - все поля заполнены правильно для максимальной эффективности рекламы

Фидер должен:
- Использовать структуру и логику существующего Google фида
- Фильтровать товары по специфическим критериям (худи с более чем 2 фотографиями)
- Правильно обрабатывать изображения (последнее добавленное = основное)
- Соответствовать требованиям Meta Commerce Platform для рекламы
- **Гарантировать совместимость с Meta Pixel** для правильного сопоставления событий

---

## 🔍 Анализ существующего Google Merchant Feed v3

### Текущая реализация

**Файл:** `twocomms/storefront/management/commands/generate_google_merchant_feed.py`

**Ключевые характеристики:**
- Формат: XML RSS 2.0 с namespace `g:` (Google Merchant Center)
- URL фида: `https://twocomms.shop/media/google-merchant-v3.xml`
- Структура: варианты товаров (цвет × размер) с `item_group_id` для группировки

### Фильтрация товаров в Google фиде

```python
products = Product.objects.filter(
    status='published', 
    is_dropship_available=True
).select_related('category').prefetch_related(
    'color_variants__color',
    'color_variants__images',
    'images'
)
```

### Структура данных товаров

1. **Product** (основная модель товара)
   - `images` (ProductImage) - общие изображения товара
   - `color_variants` (ProductColorVariant) - варианты цветов
   - `display_image` - главное изображение

2. **ProductColorVariant** (вариант цвета)
   - `images` (ProductColorImage) - изображения для конкретного цветового варианта
   - `color` (Color) - цвет варианта

3. **ProductImage** (общие изображения товара)
   - `image` - ImageField
   - `id` - автоинкремент (последнее = максимальный id)

4. **ProductColorImage** (изображения цветового варианта)
   - `image` - ImageField
   - `order` - порядок сортировки
   - `id` - автоинкремент (последнее = максимальный id)

### Обработка изображений в Google фиде

```python
# Основное изображение варианта
if var.get('image'):
    g_image_link.text = f"https://twocomms.shop{var['image'].url}"
elif product.display_image:
    g_image_link.text = f"https://twocomms.shop{product.display_image.url}"

# Дополнительные изображения товара
for i, img in enumerate(product.images.all()[:9]):
    g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
    g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"

# Изображения варианта
for img in cv.images.all()[:2]:
    g_additional_image_link = ET.SubElement(item, 'g:additional_image_link')
    g_additional_image_link.text = f"https://twocomms.shop{img.image.url}"
```

---

## 🎯 Требования к Instagram/Meta фиду

### 1. Фильтрация товаров

**Обязательные критерии:**
- ✅ `status='published'`
- ✅ `is_dropship_available=True`
- ✅ **Только товары с БОЛЕЕ чем 2 фотографиями** (>= 3 фотографий)
- ✅ **В основном худи** (приоритет, но не строгое ограничение)

**Определение количества фотографий:**
```python
# Подсчет всех фотографий товара
total_images = (
    len(product.images.all()) +  # Общие изображения товара
    sum(len(cv.images.all()) for cv in product.color_variants.all())  # Изображения всех вариантов
)

# Фильтр: только товары с >= 3 фотографиями
if total_images < 3:
    continue  # Пропускаем товар
```

**Определение худи:**
```python
def is_hoodie(product):
    """Проверка, является ли товар худи"""
    # Проверка через категорию
    if product.category and product.category.slug == 'hoodie':
        return True
    
    # Проверка через название товара
    title_lower = (product.title or '').lower()
    slug_lower = (product.slug or '').lower()
    category_name = (product.category.name if product.category else '').lower()
    
    keywords = ['худи', 'hoodie', 'hood', 'hudi']
    return any(kw in title_lower or kw in slug_lower or kw in category_name for kw in keywords)
```

### 2. Обработка изображений (КРИТИЧНО!)

**Требование:** Последняя добавленная фотография должна стать **основной** (заглавной) в фиде.

**⚠️ ВАЖНО:** Модели `ProductImage` и `ProductColorImage` НЕ имеют поля `created_at`. 
Поэтому "последнее добавленное" определяется по **максимальному `id`** (автоинкремент).

**Алгоритм:**
```python
def get_all_product_images(product):
    """
    Собирает все изображения товара и возвращает отсортированный список.
    Последнее изображение (максимальный id) = основное.
    
    ВАЖНО: Собираем ВСЕ изображения:
    - product.images (общие изображения товара)
    - cv.images для ВСЕХ цветовых вариантов
    
    Сортировка: по id по убыванию (reverse=True)
    - all_images[0] = изображение с максимальным id = последнее добавленное
    - Игнорируем поле 'order' у ProductColorImage, сортируем ТОЛЬКО по id
    """
    all_images = []
    
    # 1. Общие изображения товара (ProductImage)
    # ВАЖНО: ProductImage НЕ имеет ordering в модели, но для явности используем .order_by('-id')
    for img in product.images.all().order_by('-id'):
        all_images.append({
            'image': img.image,
            'id': img.id,
            'type': 'product'
        })
    
    # 2. Изображения всех цветовых вариантов (ProductColorImage)
    # ВАЖНО: собираем изображения ВСЕХ вариантов, не только первого
    for cv in product.color_variants.all():
        # КРИТИЧНО: ProductColorImage имеет ordering = ['order', 'id'] в модели
        # Нужно явно использовать .order_by('-id') чтобы игнорировать поле 'order'
        # и получить изображения отсортированные ТОЛЬКО по id по убыванию
        for img in cv.images.all().order_by('-id'):
            all_images.append({
                'image': img.image,
                'id': img.id,
                'type': 'variant',
                'variant_id': cv.id
            })
    
    # 3. Финальная сортировка по id (по убыванию) - последнее = максимальный id
    # ВАЖНО: сортируем ТОЛЬКО по id, игнорируя поле 'order'
    # Это гарантирует, что all_images[0] = изображение с максимальным id = последнее добавленное
    all_images.sort(key=lambda x: x['id'], reverse=True)
    
    return all_images

# Использование:
all_images = get_all_product_images(product)
if not all_images:
    continue  # Пропускаем товар без изображений

# Последнее изображение (максимальный id) = основное
# ВАЖНО: all_images[0] = изображение с максимальным id = последнее добавленное
main_image = all_images[0]['image']  # → используется в g:image_link

# Остальные изображения = дополнительные
additional_images = all_images[1:]   # → используются в additional_image_link
```

### 3. Формат фида Meta Commerce Platform

**Формат:** XML RSS 2.0 с namespace `g:` (аналогично Google, но есть нюансы)

**Структура:**
```xml
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>TwoComms - Instagram Shop</title>
    <description>Product Feed for Instagram Shopping</description>
    <link>https://twocomms.shop</link>
    <atom:link href="https://twocomms.shop/media/instagram-feed.xml" rel="self" type="application/rss+xml" />
    
    <item>
        <g:id>TC-123-cv2-S</g:id>
        <g:item_group_id>TC-GROUP-123</g:item_group_id>
        <g:title>Худі — чорний — S</g:title>
        <g:description>Опис товару...</g:description>
        <g:link>https://twocomms.shop/product/slug/</g:link>
        <g:image_link>https://twocomms.shop/media/last_added_image.jpg</g:image_link>
        <additional_image_link>https://twocomms.shop/media/image2.jpg</additional_image_link>
        <additional_image_link>https://twocomms.shop/media/image3.jpg</additional_image_link>
        <g:availability>in stock</g:availability>
        <g:condition>new</g:condition>
        <g:price>950.00 UAH</g:price>
        <g:brand>TwoComms</g:brand>
        <g:size>S</g:size>
        <color>чорний</color>
        <!-- Другие поля -->
    </item>
</channel>
</rss>
```

### 4. Обязательные поля Meta Commerce Platform

**⚠️ КРИТИЧЕСКИ ВАЖНО: Сопоставление с Meta Pixel**

**ID товара (`g:id`) ДОЛЖЕН ТОЧНО совпадать с `content_ids` в Meta Pixel событиях!**

Формат ID: `TC-{product_id:04d}-{COLOR}-{SIZE}` (например: `TC-0007-BLK-M`)

**Использовать функцию:** `get_offer_id()` из `storefront.utils.analytics_helpers`

Это критично для:
- ✅ Правильного сопоставления Pixel событий с товарами в каталоге
- ✅ Работы Dynamic Product Ads / Advantage+ Catalog Ads
- ✅ Ретаргетинга и оптимизации рекламы
- ✅ Точного отслеживания конверсий

**Обязательные поля:**
- `g:id` - уникальный ID товара (макс 100 символов) - **ИСПОЛЬЗОВАТЬ get_offer_id()!**
- `g:title` - название (макс 200 символов, рекомендуется 65)
- `g:description` - описание (макс 9999 символов, plain text, без CAPS, без ссылок) - **ОБЯЗАТЕЛЬНО как fallback**
- `g:rich_text_description` - HTML описание (ПРЕДПОЧТИТЕЛЬНЕЕ, если доступно)
- `g:availability` - "in stock" или "out of stock"
- `g:condition` - "new", "refurbished", "used"
- `g:price` - формат: "950.00 UAH" (число + пробел + валюта, точка для десятичных)
- `g:link` - полный URL товара (https://twocomms.shop/product/{slug}/)
- `g:image_link` - основное изображение (JPEG/PNG, минимум 500x500px, до 8MB)
- `g:brand` - "TwoComms"
- **`quantity_to_sell_on_facebook`** - **КРИТИЧНО для Checkout!** (целое число >= 1 для in stock)

**Важные поля для одежды:**
- `g:size` - размер (S, M, L, XL, XXL) - **обязательно для одежды**
- `color` - цвет (БЕЗ префикса `g:`, просто `color`)
- `g:item_group_id` - для группировки вариантов
- `additional_image_link` - дополнительные изображения (БЕЗ префикса `g:`, можно несколько)

**Опциональные, но рекомендуемые:**
- `g:google_product_category` - "1604" (Apparel & Accessories > Clothing) - **ОБЯЗАТЕЛЬНО для Checkout**
- `g:product_type` - название категории
- `g:age_group` - "adult"
- `g:gender` - "male", "female", "unisex"
- `g:material` - состав ткани
- `g:sale_price` - цена со скидкой (если есть)
- `g:sale_price_effective_date` - даты действия скидки (ISO 8601, опционально для Черной Пятницы)
- `g:mpn` - "TC-{product_id}"
- `internal_label` - внутренние метки для фильтрации (например: `['hoodie','black_friday']`)

**Требования к изображениям для Instagram:**
- `g:image_link`: минимум 500x500px, рекомендуется:
  - **1024x1024px (1:1)** для carousel/collection ads
  - **1200x628px (1.91:1)** для single image ads
- `additional_image_link`: можно добавить тег `INSTAGRAM_STANDARD_PREFERRED` (опционально)

### 5. Отличия от Google фида

| Поле | Google | Meta/Instagram |
|------|--------|----------------|
| `color` | `g:color` | `color` (без префикса) |
| `size` | `g:size` | `g:size` (с префиксом) |
| `additional_image_link` | `g:additional_image_link` | `additional_image_link` (без префикса) |
| Формат цены | "950 UAH" | "950.00 UAH" (рекомендуется с .00) |
| Основное изображение | Первое из варианта или display_image | **Последнее добавленное (максимальный id)** |

---

## 💻 Технические детали реализации

### Структура команды

**Файл:** `twocomms/storefront/management/commands/generate_instagram_feed.py`

**Базовая структура:**
```python
"""
Django команда для генерации Instagram/Meta Commerce Platform фида
Основано на Google Merchant Feed v3 с модификациями для Meta
"""
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.utils import timezone
from storefront.models import Product
from productcolors.models import ProductColorVariant
from typing import List, Dict, Optional

class Command(BaseCommand):
    help = 'Генерирует XML фид для Instagram/Meta Commerce Platform'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='media/instagram-feed.xml',
            help='Путь к выходному XML файлу',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без создания файла',
        )
    
    def handle(self, *args, **options):
        # Реализация генерации фида
        pass
```

### Функции-помощники

```python
def get_all_product_images(product) -> List[Dict]:
    """
    Собирает все изображения товара (общие + вариантов).
    Возвращает список отсортированный по id (по убыванию).
    Последнее изображение (максимальный id) = основное.
    
    ВАЖНО:
    - Собираем ВСЕ изображения: product.images + все cv.images для всех вариантов
    - Сортировка ТОЛЬКО по id (игнорируем поле 'order' у ProductColorImage)
    - all_images[0] = изображение с максимальным id = последнее добавленное
    
    КРИТИЧНО: ProductColorImage имеет ordering = ['order', 'id'] в модели.
    Нужно явно использовать .order_by('-id') чтобы игнорировать поле 'order'
    и получить последнее добавленное изображение (максимальный id).
    """
    all_images = []
    
    # 1. Общие изображения товара (ProductImage)
    # ВАЖНО: ProductImage НЕ имеет ordering в модели, но для явности используем .order_by('-id')
    for img in product.images.all().order_by('-id'):
        all_images.append({
            'image': img.image,
            'id': img.id,
            'type': 'product'
        })
    
    # 2. Изображения ВСЕХ цветовых вариантов (ProductColorImage)
    # ВАЖНО: собираем изображения ВСЕХ вариантов, не только первого
    for cv in product.color_variants.all():
        # КРИТИЧНО: ProductColorImage имеет ordering = ['order', 'id'] в модели
        # Нужно явно использовать .order_by('-id') чтобы игнорировать поле 'order'
        # и получить изображения отсортированные ТОЛЬКО по id по убыванию
        for img in cv.images.all().order_by('-id'):
            all_images.append({
                'image': img.image,
                'id': img.id,
                'type': 'variant',
                'variant_id': cv.id
            })
    
    # 3. Финальная сортировка по id (по убыванию) - последнее = максимальный id
    # ВАЖНО: сортируем ТОЛЬКО по id, игнорируя поле 'order'
    # Это гарантирует, что all_images[0] = изображение с максимальным id = последнее добавленное
    all_images.sort(key=lambda x: x['id'], reverse=True)
    
    return all_images

def count_total_images(product) -> int:
    """Подсчитывает общее количество изображений товара"""
    count = len(product.images.all())
    for cv in product.color_variants.all():
        count += len(cv.images.all())
    return count

def is_hoodie(product) -> bool:
    """Проверка, является ли товар худи"""
    if product.category and product.category.slug == 'hoodie':
        return True
    
    title_lower = (product.title or '').lower()
    slug_lower = (product.slug or '').lower()
    category_name = (product.category.name if product.category else '').lower()
    
    keywords = ['худи', 'hoodie', 'hood', 'hudi']
    return any(kw in title_lower or kw in slug_lower or kw in category_name for kw in keywords)

def normalize_title_for_feed(title: str) -> str:
    """Снижает долю ЗАГЛАВНЫХ для фида (из Google фида)"""
    if not title:
        return ""
    letters = [c for c in title if c.isalpha()]
    if not letters:
        return title
    upper_count = sum(1 for c in letters if c.isupper())
    ratio = upper_count / len(letters)
    if ratio >= 0.6:
        return title.title()
    return title

def hex_to_basic_color_name(primary_hex: str, secondary_hex: Optional[str] = None) -> str:
    """Преобразование hex в имя цвета (из Google фида)"""
    # ... (использовать существующую реализацию)
    pass

def format_price_for_meta(price: int) -> str:
    """Форматирует цену для Meta фида: "950.00 UAH" """
    return f"{price}.00 UAH"

def get_quantity_to_sell(product, variant_id=None, size='S') -> int:
    """
    Получает quantity_to_sell_on_facebook для товара.
    КРИТИЧНО для Checkout на Facebook/Instagram.
    
    Логика:
    1. Если есть stock у варианта - использовать его
    2. Если stock = 0, но availability = 'in stock' - использовать дефолт (100)
    3. Если availability = 'out of stock' - вернуть 0
    """
    # TODO: Реализовать логику получения stock из варианта
    # Пока используем дефолтное значение для in stock товаров
    return 100  # Дефолтное значение для товаров in stock

def get_description_for_feed(product) -> tuple:
    """
    Возвращает (description, rich_text_description) для фида.
    
    Приоритет:
    1. rich_text_description (если есть full_description с HTML)
    2. description (plain text)
    3. short_description
    4. Дефолтное описание
    """
    # Проверяем full_description (может содержать HTML)
    if product.full_description:
        # Если содержит HTML теги - используем как rich_text_description
        if '<' in product.full_description and '>' in product.full_description:
            return (product.description or product.short_description or '', product.full_description)
        else:
            return (product.full_description, None)
    
    # Используем description или short_description
    description = product.description or product.short_description or ''
    return (description, None)
```

### Основная логика генерации

```python
def handle(self, *args, **options):
    output_file = options['output']
    dry_run = options['dry_run']
    
    # Создаем корневой элемент RSS
    rss = ET.Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:g', 'http://base.google.com/ns/1.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = ET.SubElement(rss, 'channel')
    
    # Заголовок канала
    title = ET.SubElement(channel, 'title')
    title.text = 'TwoComms - Instagram Shop'
    
    link = ET.SubElement(channel, 'link')
    link.text = 'https://twocomms.shop'
    
    description = ET.SubElement(channel, 'description')
    description.text = 'Product Feed for Instagram Shopping'
    
    atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
    atom_link.set('href', 'https://twocomms.shop/media/instagram-feed.xml')
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # Получаем товары с предварительной загрузкой
    products = Product.objects.filter(
        status='published',
        is_dropship_available=True
    ).select_related('category').prefetch_related(
        'color_variants__color',
        'color_variants__images',
        'images'
    )
    
    total_products = products.count()
    processed_products = 0
    skipped_products = 0
    
    self.stdout.write(f'Обрабатываем {total_products} товаров...')
    
    for product in products.iterator(chunk_size=1000):
        # 1. Проверка количества изображений (>= 3)
        total_images_count = count_total_images(product)
        if total_images_count < 3:
            skipped_products += 1
            continue
        
        # 2. Получаем все изображения (отсортированные по id, последнее = основное)
        # ВАЖНО: get_all_product_images собирает ВСЕ изображения и сортирует по id по убыванию
        all_images = get_all_product_images(product)
        if not all_images:
            skipped_products += 1
            continue
        
        # ВАЖНО: all_images[0] = изображение с максимальным id = последнее добавленное
        # Это изображение должно быть в g:image_link (основное)
        main_image = all_images[0]['image']  # Последнее добавленное → g:image_link
        
        # Остальные изображения = дополнительные → additional_image_link
        additional_images = all_images[1:]   # Остальные
        
        # 3. Формируем варианты цветов (как в Google фиде)
        variants = []
        try:
            color_variants = product.color_variants.all()
            for cv in color_variants:
                color_name = (cv.color.name or "").strip()
                if not color_name:
                    color_name = hex_to_basic_color_name(
                        getattr(cv.color, 'primary_hex', ''),
                        getattr(cv.color, 'secondary_hex', None)
                    )
                
                variants.append({
                    'key': f"cv{cv.id}",
                    'color': color_name,
                    'variant_id': cv.id
                })
        except Exception:
            pass
        
        if not variants:
            variants = [{
                'key': 'default',
                'color': 'чорний',
                'variant_id': None
            }]
        
        # 4. Генерируем варианты (цвет × размер)
        group_id = f"TC-GROUP-{product.id}"
        base_title = normalize_title_for_feed(product.title)
        
        DEFAULT_SIZES = ["S", "M", "L", "XL", "XXL"]
        
        for var in variants:
            for size in DEFAULT_SIZES:
                item = ET.SubElement(channel, 'item')
                
                # g:id - КРИТИЧЕСКИ ВАЖНО: использовать get_offer_id() для совместимости с Pixel!
                g_id = ET.SubElement(item, 'g:id')
                try:
                    from storefront.utils.analytics_helpers import get_offer_id
                    # Используем ТОЧНО ту же функцию, что и в Pixel событиях
                    offer_id = get_offer_id(
                        product_id=product.id,
                        color_variant_id=var.get('variant_id'),
                        size=size,
                        color_name=var.get('color')  # Передаем цвет для правильного slug
                    )
                except Exception as e:
                    # Fallback только в случае критической ошибки
                    self.stdout.write(
                        self.style.WARNING(
                            f'Ошибка генерации offer_id для товара {product.id}: {e}. '
                            f'Используется fallback формат.'
                        )
                    )
                    offer_id = f"TC-{product.id:04d}-{var['key']}-{size}"
                g_id.text = offer_id
                
                # g:item_group_id
                g_item_group_id = ET.SubElement(item, 'g:item_group_id')
                g_item_group_id.text = group_id
                
                # g:title
                g_title = ET.SubElement(item, 'g:title')
                g_title.text = f"{base_title} — {var['color']} — {size}"
                
                # g:description и g:rich_text_description
                description_text, rich_text = get_description_for_feed(product)
                if not description_text:
                    description_text = f"Якісний {product.category.name.lower() if product.category else 'одяг'} з ексклюзивним дизайном від TwoComms"
                
                # description (обязательно как fallback)
                g_description = ET.SubElement(item, 'g:description')
                g_description.text = description_text
                
                # rich_text_description (предпочтительнее, если доступно)
                if rich_text:
                    g_rich_text_description = ET.SubElement(item, 'g:rich_text_description')
                    g_rich_text_description.text = rich_text
                
                # g:link
                g_link = ET.SubElement(item, 'g:link')
                g_link.text = f"https://twocomms.shop/product/{product.slug}/"
                
                # g:image_link (ОСНОВНОЕ - последнее добавленное)
                # ВАЖНО: main_image = изображение с максимальным id (последнее добавленное)
                # Это изображение должно быть основным в фиде
                g_image_link = ET.SubElement(item, 'g:image_link')
                g_image_link.text = f"https://twocomms.shop{main_image.url}"
                
                # additional_image_link (БЕЗ префикса g:)
                for img_data in additional_images:
                    additional_image_link = ET.SubElement(item, 'additional_image_link')
                    additional_image_link.text = f"https://twocomms.shop{img_data['image'].url}"
                
                # g:availability
                g_availability = ET.SubElement(item, 'g:availability')
                g_availability.text = 'in stock'
                
                # quantity_to_sell_on_facebook - КРИТИЧНО для Checkout!
                quantity = get_quantity_to_sell(product, var.get('variant_id'), size)
                g_quantity = ET.SubElement(item, 'quantity_to_sell_on_facebook')
                g_quantity.text = str(quantity)
                
                # g:condition
                g_condition = ET.SubElement(item, 'g:condition')
                g_condition.text = 'new'
                
                # g:price
                g_price = ET.SubElement(item, 'g:price')
                g_price.text = format_price_for_meta(product.price)
                
                # g:sale_price (если есть скидка)
                if product.has_discount:
                    g_sale_price = ET.SubElement(item, 'g:sale_price')
                    g_sale_price.text = format_price_for_meta(product.final_price)
                    
                    # Опционально: sale_price_effective_date (для Черной Пятницы)
                    # Можно добавить логику для установки дат акции
                    # g_sale_price_effective_date = ET.SubElement(item, 'g:sale_price_effective_date')
                    # g_sale_price_effective_date.text = "2025-11-24T00:00:00+02:00/2025-11-30T23:59:59+02:00"
                
                # g:brand
                g_brand = ET.SubElement(item, 'g:brand')
                g_brand.text = 'TwoComms'
                
                # g:mpn
                g_mpn = ET.SubElement(item, 'g:mpn')
                g_mpn.text = f"TC-{product.id}"
                
                # g:size (обязательно для одежды)
                g_size = ET.SubElement(item, 'g:size')
                g_size.text = size
                
                # color (БЕЗ префикса g:)
                color = ET.SubElement(item, 'color')
                color.text = var['color']
                
                # g:item_group_id уже добавлен выше
                
                # Категория
                if product.category:
                    g_product_type = ET.SubElement(item, 'g:product_type')
                    g_product_type.text = product.category.name
                    
                    g_google_product_category = ET.SubElement(item, 'g:google_product_category')
                    g_google_product_category.text = '1604'  # Apparel & Accessories > Clothing
                
                # Возрастная группа и пол
                g_age_group = ET.SubElement(item, 'g:age_group')
                g_age_group.text = 'adult'
                
                g_gender = ET.SubElement(item, 'g:gender')
                if product.category:
                    category_name = product.category.name.lower()
                    if any(word in category_name for word in ['чоловіч', 'мужск', 'men']):
                        g_gender.text = 'male'
                    elif any(word in category_name for word in ['жіноч', 'женск', 'women']):
                        g_gender.text = 'female'
                    else:
                        g_gender.text = 'unisex'
                else:
                    g_gender.text = 'unisex'
                
                # Материал (из Google фида)
                def get_material(p):
                    slug = (p.slug or '').lower()
                    cat = (p.category.name if p.category else '').lower()
                    if any(k in slug for k in ['hood', 'hudi', 'hoodie']) or any(k in cat for k in ['худі','худи','hood']):
                        return '90% бавовна, 10% поліестер'
                    if any(k in slug for k in ['long', 'longsleeve', 'longsliv']) or any(k in cat for k in ['лонгслів','лонгслив','лонг']):
                        return '95% бамбук, 5% еластан'
                    if any(k in slug for k in ['tshirt','t-shirt','tee','tshort','futbol']) or any(k in cat for k in ['футболк']):
                        return '95% бавовна, 5% еластан'
                    return '95% бавовна, 5% еластан'
                
                g_material = ET.SubElement(item, 'g:material')
                g_material.text = get_material(product)
                
                # internal_label - опционально для фильтрации в product sets
                # Полезно для Черной Пятницы: можно добавить метки типа 'black_friday', 'hoodie'
                if is_hoodie(product):
                    internal_label = ET.SubElement(item, 'internal_label')
                    internal_label.text = "['hoodie']"
                    # Можно добавить дополнительные метки:
                    # internal_label.text = "['hoodie','black_friday','sale']"
        
        processed_products += 1
    
    # Сохранение файла
    if not dry_run:
        tree = ET.ElementTree(rss)
        ET.indent(tree, space="  ", level=0)
        
        with open(output_file, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
        
        self.stdout.write(
            self.style.SUCCESS(f'Instagram/Meta фид создан: {output_file}')
        )
    
    self.stdout.write(
        self.style.SUCCESS(
            f'Обработка завершена! '
            f'Обработано: {processed_products}, '
            f'Пропущено (мало фото): {skipped_products}'
        )
    )
```

---

## ✅ Чек-лист реализации

### Базовые функции
- [ ] Создать файл `generate_instagram_feed.py` в `twocomms/storefront/management/commands/`
- [ ] Реализовать функцию `get_all_product_images()` для сбора всех изображений
- [ ] Реализовать функцию `count_total_images()` для подсчета фотографий
- [ ] Реализовать функцию `is_hoodie()` для определения худи
- [ ] Реализовать функцию `get_quantity_to_sell()` для получения количества
- [ ] Реализовать функцию `get_description_for_feed()` для получения описания

### Фильтрация и обработка
- [ ] Реализовать фильтрацию товаров (>= 3 фотографий)
- [ ] Реализовать логику: последнее изображение (максимальный id) = основное
- [ ] Использовать формат XML RSS 2.0 с namespace `g:`

### Критически важные поля
- [ ] **Использовать get_offer_id() для g:id** (совместимость с Pixel!)
- [ ] Добавить `quantity_to_sell_on_facebook` (критично для Checkout!)
- [ ] Добавить `g:google_product_category` (обязательно для Checkout)
- [ ] Добавить поддержку `g:rich_text_description` (предпочтительнее)
- [ ] Правильно форматировать поля (color без g:, additional_image_link без g:)
- [ ] Форматировать цену как "950.00 UAH"

### Опциональные улучшения
- [ ] Добавить поддержку `internal_label` для фильтрации
- [ ] Добавить поддержку `sale_price_effective_date` (для Черной Пятницы)
- [ ] Добавить все остальные обязательные поля Meta

### Тестирование и валидация
- [ ] Протестировать генерацию фида на реальных данных
- [ ] Проверить валидность XML (через валидатор)
- [ ] **Проверить, что ID товаров ТОЧНО совпадают с content_ids в Pixel** (критично!)
- [ ] Убедиться, что последнее изображение действительно основное
- [ ] Проверить, что quantity_to_sell_on_facebook >= 1 для in stock товаров
- [ ] Проверить, что все обязательные поля присутствуют
- [ ] Проверить формат всех полей (с g: и без g:)

---

## 📝 КРИТИЧЕСКИ ВАЖНЫЕ ЗАМЕЧАНИЯ

### 1. Сопоставление с Meta Pixel (КРИТИЧНО!)

**⚠️ ID товара ДОЛЖЕН ТОЧНО совпадать с content_ids в Pixel событиях!**

- Используйте **ТОЧНО** функцию `get_offer_id()` из `storefront.utils.analytics_helpers`
- Формат: `TC-{product_id:04d}-{COLOR}-{SIZE}` (например: `TC-0007-BLK-M`)
- Это критично для работы Dynamic Product Ads и ретаргетинга
- Проверьте, что ID в фиде совпадает с `content_ids` в событиях ViewContent, AddToCart, Purchase

**Проверка сопоставления:**
```python
# В фиде
<g:id>TC-0007-BLK-M</g:id>

# В Pixel событии ViewContent
content_ids: ["TC-0007-BLK-M"]  # ← Должно совпадать ТОЧНО!
```

### 2. Обязательные поля для рекламы

- ✅ **quantity_to_sell_on_facebook** - КРИТИЧНО для Checkout! Должно быть >= 1 для in stock товаров
- ✅ **google_product_category** - ОБЯЗАТЕЛЬНО для Checkout (для расчета налогов)
- ✅ **rich_text_description** - ПРЕДПОЧТИТЕЛЬНЕЕ чем description (если доступно)
- ✅ **Все variant_fields** (size, color) должны быть заполнены для ВСЕХ вариантов, даже out of stock

### 3. Изображения (КРИТИЧНО!)

- **Последнее изображение = основное**: 
  - ⚠️ Критически важно, чтобы изображение с **максимальным `id`** (последнее добавленное) было в поле `g:image_link`, а не в `additional_image_link`.
  - Модели `ProductImage` и `ProductColorImage` НЕ имеют поля `created_at`, поэтому "последнее добавленное" определяется по максимальному `id` (автоинкремент BigAutoField).
  - **КРИТИЧНО**: `ProductColorImage` имеет `ordering = ['order', 'id']` в модели. 
    При использовании `.all()` Django применит эту сортировку (сначала по `order`, потом по `id`).
    **Нужно явно использовать `.order_by('-id')`** чтобы игнорировать поле `order` и получить последнее добавленное изображение.
  - Функция `get_all_product_images()` собирает **ВСЕ** изображения (product.images + все cv.images для всех вариантов) 
    с явной сортировкой `.order_by('-id')` и затем финально сортирует по `id` по убыванию.
  - `all_images[0]` = изображение с максимальным id = последнее добавленное = основное (`g:image_link`).
  - `all_images[1:]` = остальные изображения = дополнительные (`additional_image_link`).
  - **ВАЖНО**: Используйте `.order_by('-id')` при получении изображений, чтобы игнорировать поле `order`.

- **Размеры изображений**:
  - Минимум: 500x500px
  - Рекомендуется для carousel/collection: 1024x1024px (1:1)
  - Рекомендуется для single image: 1200x628px (1.91:1)
- **Формат**: JPEG или PNG, до 8MB

### 4. Фильтрация по количеству фото

Товары с менее чем 3 фотографиями должны быть полностью исключены из фида.

### 5. Формат цены

Meta рекомендует формат "950.00 UAH" (с .00), но также принимает "950 UAH". Для консистентности используйте формат с .00.

### 6. Поля без префикса g:

- `color` (не `g:color`)
- `additional_image_link` (не `g:additional_image_link`)
- `quantity_to_sell_on_facebook` (не `g:quantity_to_sell_on_facebook`)
- `internal_label` (не `g:internal_label`)

### 7. Тестирование и валидация

После реализации обязательно протестируйте на реальных данных и проверьте:

- ✅ Товары с < 3 фото не попадают в фид
- ✅ Последнее изображение действительно основное
- ✅ XML валидный (проверить через валидатор)
- ✅ Все обязательные поля присутствуют
- ✅ **ID товаров ТОЧНО совпадают с content_ids в Pixel событиях** (критично!)
- ✅ quantity_to_sell_on_facebook >= 1 для всех in stock товаров
- ✅ google_product_category присутствует для всех товаров
- ✅ rich_text_description используется, если доступно
- ✅ Формат цены правильный ("950.00 UAH")
- ✅ Поля без g: префикса правильно оформлены

### 8. Оптимизация для Черной Пятницы

- Используйте `internal_label` для маркировки товаров (например: `['black_friday','hoodie']`)
- Добавьте `sale_price_effective_date` для товаров со скидкой
- Убедитесь, что все товары имеют достаточное количество изображений (>= 3)
- Проверьте, что quantity_to_sell_on_facebook установлено правильно для предотвращения overselling

---

## 🔗 Полезные ссылки

### Документация Meta
- [Meta Commerce Platform - Product Feed Fields](https://developers.facebook.com/docs/commerce-platform/catalog/fields)
- [Meta Commerce Platform - Feed Format](https://developers.facebook.com/docs/commerce-platform/catalog/feed)
- [Meta Commerce Platform - Best Practices](https://developers.facebook.com/docs/commerce-platform/catalog/best-practices)
- [Dynamic Product Ads - Product Audiences](https://developers.facebook.com/docs/marketing-api/dynamic-product-ads/product-audiences)
- [Advantage+ Catalog Ads](https://developers.facebook.com/docs/marketing-api/advantage-creative-for-catalog)

### Внутренние файлы проекта
- Существующий Google фид: `twocomms/storefront/management/commands/generate_google_merchant_feed.py`
- Функция get_offer_id: `twocomms/storefront/utils/analytics_helpers.py`
- URL Google фида: `https://twocomms.shop/media/google-merchant-v3.xml`

### Проверка сопоставления Pixel
- Проверить формат content_ids в Pixel событиях: `twocomms/orders/facebook_conversions_service.py`
- Проверить события ViewContent, AddToCart, Purchase в шаблонах

---

## 🎯 Итоговые рекомендации для идеального фида

1. **Используйте ТОЧНО get_offer_id()** - это гарантирует совместимость с Pixel
2. **Всегда добавляйте quantity_to_sell_on_facebook** - критично для Checkout
3. **Используйте rich_text_description** - предпочтительнее для Meta
4. **Правильные размеры изображений** - 1024x1024px для carousel, 1200x628px для single
5. **Последнее изображение = основное** - это требование задачи
6. **Все обязательные поля** - для максимальной эффективности рекламы
7. **Тестируйте сопоставление с Pixel** - проверьте, что ID совпадают

---

**Дата создания:** 2025-01-XX  
**Версия:** 2.0 (обновлено с учетом глубокого анализа)  
**Статус:** Готов к реализации с полной оптимизацией для Instagram рекламы

