# 🎨 СПЕЦИФИКАЦИЯ ПОЛНОГО РЕДИЗАЙНА СТРАНИЦЫ ПРОДУКТА

## 📋 ОГЛАВЛЕНИЕ

1. [Введение и Цели](#введение-и-цели)
2. [Текущая Архитектура](#текущая-архитектура)
3. [Требования к Новому Дизайну](#требования-к-новому-дизайну)
4. [Технический Стек и Структура](#технический-стек-и-структура)
5. [UI/UX Дизайн - 50+ Идей](#uiux-дизайн---50-идей)
6. [Адаптивность](#адаптивность)
7. [Анимации и Transitions](#анимации-и-transitions)
8. [Meta Pixel Интеграция](#meta-pixel-интеграция)
9. [SEO и Производительность](#seo-и-производительность)
10. [Context7 Рекомендации](#context7-рекомендации)
11. [Чеклист Реализации](#чеклист-реализации)

---

## 🎯 ВВЕДЕНИЕ И ЦЕЛИ

### Цель Редизайна
Создать современную, адаптивную и высокопроизводительную страницу продукта с фокусом на:
- ✨ Премиальный UI/UX дизайн
- 📱 Идеальная адаптивность для всех устройств
- 🚀 Высокая производительность и быстрая загрузка
- 🎭 Плавные анимации и transitions
- 🛒 Интуитивный процесс покупки
- 📊 Полная интеграция с MetaPixel для аналитики
- 🔍 Отличная SEO оптимизация

### Для Кого Этот Документ
Этот документ предназначен для AI-кодека (ChatGPT или другой LLM), который будет реализовывать редизайн страницы продукта. Здесь содержится ВСЯ необходимая информация о текущей структуре, требованиях и рекомендациях.

### ⚠️ КРИТИЧЕСКИ ВАЖНО
- **НЕ ЛОМАЙТЕ СУЩЕСТВУЮЩУЮ ФУНКЦИОНАЛЬНОСТЬ** - все текущие функции должны работать как раньше
- **ИСПОЛЬЗУЙТЕ Context7** для Django, Bootstrap, анимаций - проверяйте best practices
- **ИСПОЛЬЗУЙТЕ Последовательное мышление** для планирования архитектуры
- **ТЕСТИРУЙТЕ НА МОБИЛЬНЫХ** устройствах - это приоритет #1

---

## 🏗️ ТЕКУЩАЯ АРХИТЕКТУРА

### Модели Django

#### 1. Product (storefront/models.py)
```python
class Product(models.Model):
    # Основные поля
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    catalog = models.ForeignKey(Catalog, null=True, blank=True)  # Новая система каталогов
    
    # Цены
    price = models.PositiveIntegerField(verbose_name='Ціна (грн)')
    discount_percent = models.PositiveIntegerField(blank=True, null=True)
    
    # Изображения
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    main_image_alt = models.CharField(max_length=200, blank=True, null=True)
    
    # Описания
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    full_description = models.TextField(blank=True)
    
    # Система баллов
    points_reward = models.PositiveIntegerField(default=0, verbose_name='Бали за покупку')
    
    # SEO
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    seo_keywords = models.CharField(max_length=300, blank=True)
    seo_schema = models.JSONField(blank=True, default=dict)
    
    # Размерная сетка
    size_grid = models.ForeignKey(SizeGrid, null=True, blank=True)
    
    # Новые поля для дропшипа
    drop_price = models.PositiveIntegerField(default=0)
    recommended_price = models.PositiveIntegerField(default=0)
    is_dropship_available = models.BooleanField(default=True)
    
    # Properties
    @property
    def has_discount(self):
        return bool(self.discount_percent and self.discount_percent > 0)
    
    @property
    def final_price(self):
        if self.has_discount:
            return int(self.price * (100 - self.discount_percent) / 100)
        return self.price
    
    @property
    def display_image(self):
        """Главное изображение или первое изображение первого цвета"""
        if self.main_image:
            return self.main_image
        first_variant = self.color_variants.first()
        if first_variant:
            first_image = first_variant.images.first()
            if first_image:
                return first_image.image
        return None
```

#### 2. ProductColorVariant (productcolors/models.py)
```python
class ProductColorVariant(models.Model):
    """Цветовой вариант товара"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    # Inventory
    sku = models.CharField(max_length=64, blank=True)
    barcode = models.CharField(max_length=64, blank=True)
    stock = models.PositiveIntegerField(default=0)
    price_override = models.PositiveIntegerField(blank=True, null=True)
    
    metadata = models.JSONField(blank=True, default=dict)
```

#### 3. Color (productcolors/models.py)
```python
class Color(models.Model):
    """Цвет может быть одиночным или комбинированным (два цвета)"""
    name = models.CharField(max_length=100, blank=True)
    primary_hex = models.CharField(max_length=7, help_text='#RRGGBB')
    secondary_hex = models.CharField(max_length=7, blank=True, null=True)
    # Если secondary_hex заполнен - это комбинированный цвет
```

#### 4. ProductColorImage (productcolors/models.py)
```python
class ProductColorImage(models.Model):
    """Изображения для цветового варианта"""
    variant = models.ForeignKey(ProductColorVariant, related_name='images')
    image = models.ImageField(upload_to='product_colors/')
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
```

#### 5. Catalog и Модули (storefront/models.py)
```python
class Catalog(models.Model):
    """Каталог - группировка продуктов"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

class CatalogOption(models.Model):
    """Дополнительные опции/модули для каталога"""
    class OptionType(models.TextChoices):
        SIZE = 'size', 'Розмір'
        MATERIAL = 'material', 'Матеріал'
        COLOR = 'color', 'Колір'
        CUSTOM = 'custom', 'Кастомна опція'
    
    catalog = models.ForeignKey(Catalog, related_name='options')
    name = models.CharField(max_length=200)
    option_type = models.CharField(max_length=50, choices=OptionType.choices)
    is_required = models.BooleanField(default=True)
    is_additional_cost = models.BooleanField(default=False)  # ⚠️ Может быть ПЛАТНЫМ
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    help_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

class CatalogOptionValue(models.Model):
    """Значения опций"""
    option = models.ForeignKey(CatalogOption, related_name='values')
    value = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='catalog_options/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
```

#### 6. SizeGrid (storefront/models.py)
```python
class SizeGrid(models.Model):
    """Размерная сетка с изображением"""
    catalog = models.ForeignKey(Catalog, related_name='size_grids')
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='size_grids/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
```

### Views (storefront/views/product.py)

```python
@cache_page_for_anon(600)  # Кэш 10 минут для анонимных
def product_detail(request, slug):
    """
    Детальная страница товара
    
    Context передаваемый в шаблон:
    - product: объект Product
    - images: дополнительные изображения (ProductImage)
    - color_variants: список dict с:
        - id: ID варианта
        - primary_hex: основной цвет
        - secondary_hex: дополнительный цвет (если есть)
        - is_default: bool
        - images: список URL изображений
    - auto_select_first_color: bool - если нет main_image
    - breadcrumbs: хлебные крошки для SEO
    """
    product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
    images = product.images.all()
    
    # Получаем цветовые варианты
    color_variants = get_detailed_color_variants(product)
    auto_select_first_color = False
    
    if color_variants:
        # Находим default и ставим его первым
        default_index = next(
            (idx for idx, v in enumerate(color_variants) if v.get('is_default')),
            0
        )
        if default_index != 0:
            default_variant = color_variants.pop(default_index)
            color_variants.insert(0, default_variant)
        
        # Если нет главного изображения - автовыбор первого цвета
        if not product.main_image:
            auto_select_first_color = True
    
    # Breadcrumbs
    breadcrumbs = [
        {'name': 'Головна', 'url': reverse('home')},
        {'name': 'Каталог', 'url': reverse('catalog')},
    ]
    if product.category:
        breadcrumbs.append({
            'name': product.category.name,
            'url': reverse('catalog_by_cat', kwargs={'cat_slug': product.category.slug})
        })
    breadcrumbs.append({
        'name': product.title,
        'url': reverse('product', kwargs={'slug': product.slug})
    })
    
    return render(request, 'pages/product_detail.html', {
        'product': product,
        'images': images,
        'color_variants': color_variants,
        'auto_select_first_color': auto_select_first_color,
        'breadcrumbs': breadcrumbs
    })
```

### JavaScript Логика

#### 1. Переключение Цветов и Галереи
```javascript
// Из product_detail.html (строки 249-354)
(function(){
  // 1. Применяем CSS переменные для цветов
  document.querySelectorAll('.color-swatch .swatch').forEach(function(swatch) {
    var primary = swatch.getAttribute('data-primary') || '';
    var secondary = swatch.getAttribute('data-secondary') || '';
    if (primary) { swatch.style.setProperty('--primary-color', primary); }
    if (secondary) {
      swatch.style.setProperty('--secondary-color', secondary);
      // Добавляем divider для комбинированных цветов
      var divider = document.createElement('div');
      divider.className = 'divider';
      swatch.appendChild(divider);
    }
  });
  
  // 2. Парсим данные вариантов
  var dataTag = document.getElementById('variant-data');
  var variants = JSON.parse((dataTag && dataTag.textContent) || '[]');
  
  // 3. Функция пересборки карусели
  function rebuildCarousel(images){
    var carousel = document.getElementById('productCarousel');
    var inner = carousel.querySelector('.carousel-inner');
    var indicators = carousel.querySelector('.carousel-indicators');
    var thumbs = document.getElementById('product-thumbs');
    
    inner.innerHTML = '';
    indicators.innerHTML = '';
    thumbs.innerHTML = '';
    
    var list = images && images.length ? images : [mainImageUrl, ...extraImages];
    
    list.forEach(function(url, idx){
      // Создаем carousel-item
      var item = document.createElement('div');
      item.className = 'carousel-item' + (idx===0?' active':'');
      var img = document.createElement('img');
      img.src = url;
      img.className = 'd-block w-100 h-100 object-fit-contain';
      item.appendChild(img);
      inner.appendChild(item);
      
      // Создаем indicator
      var ind = document.createElement('button');
      ind.setAttribute('data-bs-target', '#productCarousel');
      ind.setAttribute('data-bs-slide-to', String(idx));
      if(idx===0) ind.className='active';
      indicators.appendChild(ind);
      
      // Создаем thumbnail
      var th = document.createElement('button');
      th.className='btn p-0 thumb';
      th.setAttribute('data-bs-slide-to', String(idx));
      var ti = document.createElement('img');
      ti.src = url;
      ti.className='rounded-3 object-fit-cover';
      ti.style.width='72px';
      ti.style.height='72px';
      th.appendChild(ti);
      thumbs.appendChild(th);
    });
  }
  
  // 4. Обработчик клика на цвет
  function onColorClick(e){
    var btn = e.currentTarget;
    var id = parseInt(btn.getAttribute('data-variant'), 10);
    var v = variants.find(function(x){ return x.id===id; });
    if(!v) return;
    
    // Активный стан
    document.querySelectorAll('#color-picker .color-swatch').forEach(function(b){ 
      b.classList.remove('active'); 
    });
    btn.classList.add('active');
    
    // Пересобираем галерею с новыми изображениями
    rebuildCarousel(v.images || []);
  }
  
  // 5. Инициализация
  if(variants.length){
    var def = variants.find(v => v.is_default) || variants[0];
    rebuildCarousel(def && def.images ? def.images : []);
    document.querySelectorAll('#color-picker .color-swatch').forEach(function(b){
      b.addEventListener('click', onColorClick);
    });
  }
})();
```

#### 2. Добавление в Корзину
```javascript
// Из base.html (строки 826-866)
window.AddToCart = function(btn){
  var productId = btn.getAttribute('data-add-to-cart');
  
  // Получаем размер
  var sizeInput = document.querySelector('input[name="size"]:checked');
  var size = (sizeInput ? sizeInput.value : 'S') || 'S';
  
  // Получаем количество
  var qtyInput = document.querySelector('#qty');
  var qty = Math.max(1, parseInt(qtyInput.value || '1', 10));
  
  // Получаем выбранный цвет ⚠️ ВАЖНО!
  var colorVariantId = null;
  var activeColorSwatch = document.querySelector('#color-picker .color-swatch.active');
  if(activeColorSwatch) {
    colorVariantId = activeColorSwatch.getAttribute('data-variant');
  }
  
  // CSRF токен
  var csrfToken = getCookie('csrftoken');
  
  // Формируем body
  var body = new URLSearchParams({
    product_id: String(productId),
    size: String(size).toUpperCase(),
    qty: String(qty)
  });
  if(colorVariantId) {
    body.append('color_variant_id', colorVariantId);
  }
  
  // Отправляем запрос
  fetch('/cart/add/', {
    method: 'POST',
    headers: {
      'X-CSRFToken': csrfToken,
      'X-Requested-With': 'XMLHttpRequest',
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    },
    body: body
  }).then(r => r.json())
    .then(d => {
      // Обновляем badge корзины
      updateCartBadge(d.count);
      showNotification('Товар додано до кошика!');
      
      // MetaPixel tracking
      if(window.trackEvent) {
        window.trackEvent('AddToCart', {
          content_ids: [productId],
          content_type: 'product',
          value: d.total,
          currency: 'UAH'
        });
      }
    })
    .catch(err => {
      showNotification('Помилка додавання до кошика', 'error');
    });
};
```

#### 3. MetaPixel Tracking
```javascript
// Из product_detail.html (строки 674-692, 717-729)
// 1. ViewContent при загрузке страницы
try{
  var pe = document.getElementById('product-analytics-payload');
  if(pe && window.trackEvent){
    window.trackEvent('ViewContent', {
      content_ids: [pe.dataset.id],
      content_name: pe.dataset.title,
      content_type: 'product',
      content_category: pe.dataset.category,
      value: parseFloat(pe.dataset.price),
      currency: 'UAH'
    });
  }
}catch(_){ }

// 2. CustomizeProduct при выборе цвета
document.querySelectorAll('.color-swatch').forEach(function(button){
  button.addEventListener('click', function(){
    try{
      if(window.trackEvent){
        var pe = document.getElementById('product-analytics-payload');
        var variantId = this.getAttribute('data-variant');
        window.trackEvent('CustomizeProduct', {
          content_ids: [pe.dataset.id],
          content_type: 'product',
          variant_id: variantId
        });
      }
    }catch(_){ }
  });
});
```

### Текущий Шаблон (product_detail.html)

#### Структура:
1. **SEO и Meta теги** (строки 1-22)
2. **Хлебные крошки** (строки 20-22)
3. **Двухколоночный Layout** (строки 24-365):
   - Левая колонка: Главное изображение + карусель
   - Правая колонка: Информация о товаре
4. **Модальное окно с информацией о баллах** (строки 367-451)
5. **JavaScript логика** (строки 453-747)

#### Ключевые Элементы:
- **Галерея**: Bootstrap Carousel с индикаторами и thumbnails
- **Селектор цветов**: Кнопки с data-variant, data-primary, data-secondary
- **Размеры**: Radio buttons (S, M, L, XL, XXL)
- **Система баллов**: Badge с модальным окном
- **Вкладки**: Описание + Размерная сетка
- **Контроль количества**: Кастомный qty-control
- **Кнопка "Додати в кошик"**

### CSS Анимации (из styles.css)

```css
/* 1. Появление карточек */
@keyframes cardLift {
  0%   { opacity:0; transform:translateY(24px) scale(.94); filter:blur(10px); }
  60%  { opacity:1; transform:translateY(-2px) scale(1.01); filter:blur(0); }
  100% { opacity:1; transform:none; filter:none; }
}
.reveal-stagger {
  opacity: 0;
}
.reveal-stagger.visible {
  animation: cardLift 560ms cubic-bezier(.2,.8,.2,1) both;
  animation-delay: var(--d, 0ms);
}

/* 2. Переключение цветов */
.color-dot {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.color-dot.active {
  border-color: rgba(255, 255, 255, 0.8);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.4), 0 4px 16px rgba(0, 0, 0, 0.4);
  transform: scale(1.15);
}
.color-dot.switching {
  transform: scale(0.9);
  opacity: 0.7;
}

/* 3. Переключение изображений */
.product-main-image {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.product-main-image.switching {
  opacity: 0.7;
  transform: scale(1.05);
}

/* 4. Пульсация при переключении */
@keyframes colorSwitchPulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.02); box-shadow: 0 8px 30px rgba(139, 92, 246, 0.2); }
  100% { transform: scale(1); }
}

/* 5. Hover эффекты */
.product-card:hover {
  transform: translateY(-5px);
  border-color: rgba(139, 92, 246, 0.3);
  box-shadow: 0 8px 25px rgba(139, 92, 246, 0.15);
}
```

---

## 📝 ТРЕБОВАНИЯ К НОВОМУ ДИЗАЙНУ

### Функциональные Требования

#### 1. Галерея Изображений
- ✅ Главное изображение сверху (крупное)
- ✅ Миниатюры снизу или сбоку (переключение)
- ✅ Плавный переход между изображениями
- ✅ Zoom при наведении (desktop) или pinch-to-zoom (mobile)
- ✅ Lazy loading для производительности
- ✅ Optimized images (WebP/AVIF с fallback)

#### 2. Селектор Цветов
- ✅ Цветные круги/квадраты (НЕ hex коды)
- ✅ Поддержка комбинированных цветов (primary + secondary)
- ✅ Активное состояние с анимацией
- ✅ Автоматическая смена галереи при выборе цвета
- ✅ MetaPixel tracking (CustomizeProduct)

#### 3. Цены и Скидки
- ✅ Финальная цена крупно
- ✅ Старая цена перечеркнута (если есть скидка)
- ✅ Badge с процентом скидки
- ✅ Красивое форматирование (пробелы, валюта)

#### 4. Система Баллов
- ✅ Badge с количеством баллов
- ✅ Иконка-подсказка (!) с hover эффектом
- ✅ Модальное окно с детальной информацией:
  - Как начисляются баллы
  - Как использовать баллы
  - Возможности (промокоды, донаты на ЗСУ)
  - Кнопка перехода к балам (для авторизованных)
  - Кнопка входа (для неавторизованных)

#### 5. Выбор Размера
- ✅ Визуальные кнопки (не dropdown)
- ✅ Активные и неактивные размеры
- ✅ Подсказка о размерной сетке

#### 6. Контроль Количества
- ✅ Кнопки +/- и input
- ✅ Минимум 1, максимум можно ограничить stock
- ✅ Красивый дизайн

#### 7. Дополнительные Модули
- ✅ Секция "Додаткові опції"
- ✅ Отображение модулей из catalog.options
- ✅ Визуальное различие платных/бесплатных модулей
- ✅ Показ дополнительной цены рядом с модулем

#### 8. Описание и Характеристики
- ✅ Вкладки: Описание | Характеристики | Розмірна сітка
- ✅ Или модальные окна (по желанию дизайнера)
- ✅ Размерная сетка может быть:
  - Таблицей
  - Изображением (SizeGrid.image)
  - Инструкцией по измерению

#### 9. Кнопка Заказа
- ✅ Крупная, заметная кнопка
- ✅ Центрирована на mobile
- ✅ Sticky на mobile (прилипает снизу при scroll)
- ✅ Анимация при клике
- ✅ Feedback (успех/ошибка)

#### 10. Instagram Ссылка
- ⚠️ **НОВАЯ ФУНКЦИЯ** - не реализована сейчас
- Нужно:
  1. Добавить поле `instagram_url` в модель Product
  2. Создать миграцию
  3. Добавить в форму админки
  4. Отобразить иконку Instagram на странице продукта
  5. При клике - открывать в новой вкладке

#### 11. Рекомендованные Товары
- ✅ Секция внизу страницы
- ✅ Товары из той же категории
- ✅ Бесконечная карусель (auto-scroll)
- ✅ Smooth анимация
- ✅ Lazy loading
- ✅ Pause на hover

---

## 🎨 UI/UX ДИЗАЙН - 50+ ИДЕЙ

### 🎯 Общие Принципы

1. **Премиальность**: Используйте градиенты, тени, glass morphism, но не переборщите
2. **Читаемость**: Контраст текста и фона должен быть достаточным
3. **Воздух**: Много whitespace, не перегружайте интерфейс
4. **Согласованность**: Все элементы в едином стиле
5. **Производительность**: 60 FPS анимации, быстрая загрузка

### 📱 Макет и Layout

#### Desktop (> 992px)
6. **Двухколоночный layout**: 50/50 или 60/40 (галерея/информация)
7. **Sticky sidebar**: Информация о товаре прилипает при scroll
8. **Широкое изображение**: Используйте пространство эффективно
9. **Thumbnails сбоку**: Вертикальная полоса миниатюр слева от главного изображения

#### Tablet (768px - 991px)
10. **Адаптивные колонки**: 60/40 или stack в одну колонку
11. **Уменьшенные отступы**: Оптимизация пространства
12. **Компактные элементы**: Меньшие кнопки, но все еще удобные

#### Mobile (< 768px)
13. **Одна колонка**: Все элементы друг под другом
14. **Sticky header**: Название товара и цена видны при scroll
15. **Sticky CTA**: Кнопка "Додати в кошик" прилипает снизу
16. **Swipe галерея**: Нативный swipe для переключения фото
17. **Compact controls**: Контролы занимают меньше места

### 🖼️ Галерея Изображений

18. **Главное изображение**:
    - aspect-ratio: 4:5 или 3:4 (портретная для одежды)
    - object-fit: contain (чтобы не обрезать)
    - Фон: gradient или blur (из dominant color)
    
19. **Thumbnails**:
    - Desktop: Вертикальная полоса слева (72x72px)
    - Mobile: Горизонтальная полоса снизу (60x60px)
    - Скругленные углы (border-radius: 12px)
    - Активный thumbnail: border + shadow
    
20. **Переходы**:
    - Fade + scale при смене изображения
    - Crossfade эффект
    - Parallax при scroll (subtle)
    
21. **Zoom**:
    - Desktop: Лупа при hover, открытие в лайтбоксе при клике
    - Mobile: Pinch-to-zoom нативный
    - Лайтбокс с navigation (prev/next)
    
22. **Индикаторы**:
    - Dots снизу для mobile
    - Thumbnails для desktop
    - Счетчик "3/8" в углу

### 🎨 Селектор Цветов

23. **Визуализация**:
    - Круги диаметром 40-48px
    - Внутренний круг 32-36px (цвет)
    - Border 2px для неактивных, 3-4px для активного
    - Box-shadow для глубины
    
24. **Комбинированные цвета**:
    - Split circle (50/50 вертикальная линия)
    - Или gradient (linear-gradient)
    - Тонкий divider между цветами
    
25. **Активное состояние**:
    - Scale(1.15) transform
    - Glowing shadow (box-shadow с цветом)
    - Pulsing animation (subtle)
    
26. **Hover эффекты**:
    - Scale(1.05)
    - Изменение opacity border
    - Tooltip с названием цвета
    
27. **Анимация переключения**:
    - Активный: scale up + glow
    - Неактивные: scale down + opacity
    - Stagger delay между точками
    
28. **Feedback**:
    - Haptic feedback на mobile (vibrate API)
    - Sound effect (опционально, отключаемый)
    - Visual ripple effect

### 💰 Цены и Бейджи

29. **Финальная цена**:
    - font-size: 2.5-3rem (крупно!)
    - font-weight: 700-900 (bold)
    - Gradient text для акцента
    
30. **Старая цена**:
    - text-decoration: line-through
    - opacity: 0.6-0.7
    - Меньший размер (1.2-1.5rem)
    - Рядом с финальной ценой
    
31. **Badge скидки**:
    - background: linear-gradient (red-orange)
    - border-radius: 12-16px
    - padding: 6px 12px
    - font-weight: 600
    - Анимация: gentle pulse
    
32. **Форматирование**:
    - Пробелы между тысячами: "1 350 грн"
    - Или с запятой: "1,350 грн"
    - Валюта после числа (украинская локаль)

### ⭐ Система Баллов

33. **Badge баллов**:
    - Фон: gradient (gold-yellow)
    - Иконка звезды SVG
    - Анимация: sparkle/shimmer
    - Позиция: рядом с ценой или отдельный блок
    
34. **Иконка подсказки (!)**:
    - Круглая кнопка 24-28px
    - Outline стиль или filled
    - Hover: scale + rotate
    - Cursor: help
    - Tooltip: "Дізнатись про бали"
    
35. **Модальное окно**:
    - Glass morphism background
    - backdrop-filter: blur(20px)
    - Smooth animation (fade + scale)
    - Разделы:
      * Header: Иконка + Заголовок
      * Body: Информационные блоки с иконками
      * Footer: CTA кнопка
    
36. **Информационные блоки**:
    - Иконка слева (24px)
    - Текст справа
    - Background: subtle gradient
    - Border: 1px solid с opacity
    - Spacing: gap 1.5rem между блоками
    
37. **CTA кнопки**:
    - Авторизован: "Перейти до балів" (gradient button)
    - Не авторизован: "Увійти" (outline button)
    - Icons: стрелка или иконка входа
    - Hover: lift effect

### 📐 Размеры

38. **Визуальные кнопки**:
    - min-width: 48px, min-height: 48px (touch friendly)
    - border-radius: 12px
    - border: 2px solid
    - background: transparent (неактивный)
    - background: gradient (активный)
    
39. **Активное состояние**:
    - Border color: accent
    - Background: gradient
    - Text: white или контрастный
    - Box-shadow
    
40. **Неактивные размеры**:
    - opacity: 0.4-0.5
    - cursor: not-allowed
    - Tooltip: "Немає в наявності"
    - Pattern/stripe overlay
    
41. **Анимация переключения**:
    - Scale transform
    - Border color transition
    - Background fade

### 🔢 Контроль Количества

42. **Дизайн**:
    - Inline-flex контейнер
    - Background: glass morphism
    - Border-radius: 14px
    - Buttons: 36x36px круглые или квадратные
    - Input: text-align center, width 60px
    
43. **Кнопки +/-**:
    - Icons: - и + (или chevrons)
    - Hover: background change
    - Active: scale down
    - Disabled: opacity 0.4 (если min/max достигнут)
    
44. **Input**:
    - font-size: 1.1rem
    - font-weight: 600
    - No spinners (input[type=number]::-webkit-inner-spin-button)
    - Border: none
    - Background: transparent

### 📦 Дополнительные Модули

45. **Секция модулей**:
    - Заголовок: "Додаткові опції"
    - Collapse/Expand (если много модулей)
    - Grid layout для модулей
    
46. **Карточка модуля**:
    - Background: elevation
    - Border-radius: 16px
    - Padding: 1rem
    - Checkbox или radio
    - Название + описание
    - Цена (если платный): badge справа
    
47. **Платные модули**:
    - Badge: "+ 50 грн" (green gradient)
    - Icon: денег или +
    - Hover: highlight
    
48. **Обязательные модули**:
    - Помечены звездочкой (*)
    - Нельзя отключить
    - Визуально отличаются

### 📄 Описание и Характеристики

49. **Вкладки**:
    - Horizontal tabs (desktop)
    - Dropdown или accordion (mobile)
    - Active: underline + bold
    - Transition: fade content
    
50. **Модальные окна** (альтернатива):
    - Кнопки: "Опис", "Характеристики", "Розмірна сітка"
    - Клик открывает модал
    - Модал: centered, glass morphism
    - Content: scrollable
    
51. **Размерная сетка**:
    - Таблица: responsive table
    - Изображение: zoomable
    - Инструкция: иконки + текст
    - Sticky header в таблице

### 🛒 Кнопка Заказа

52. **Desktop**:
    - Крупная кнопка (min-height: 56px)
    - Gradient background
    - Border-radius: 14px
    - Font-size: 1.1rem, font-weight: 600
    - Icon: корзина или стрелка
    - Hover: lift + shadow increase
    
53. **Mobile**:
    - Sticky внизу экрана
    - Full-width или centered (80% width)
    - Bottom: 16px
    - Z-index: 1000
    - Shadow: large для отделения от контента
    - Safe area insets (iOS)
    
54. **Loading состояние**:
    - Spinner внутри кнопки
    - Text: "Додавання..."
    - Disabled: true
    
55. **Success состояние**:
    - Checkmark icon
    - Text: "Додано!"
    - Background: green gradient
    - Auto-revert через 2s
    
56. **Error состояние**:
    - X icon
    - Text: "Помилка"
    - Background: red gradient
    - Shake animation
    
57. **Анимация клика**:
    - Scale down (0.95)
    - Ripple effect
    - Color pulse

### 🔗 Instagram Ссылка

58. **Иконка**:
    - SVG icon Instagram
    - Размер: 32-40px
    - Позиция: возле заголовка или в углу
    - Gradient fill (Instagram colors)
    
59. **Hover эффект**:
    - Scale(1.1)
    - Rotate(5deg)
    - Shadow glow
    
60. **Клик**:
    - Открывает в новой вкладке (target="_blank")
    - rel="noopener noreferrer"
    - MetaPixel tracking: Custom event "InstagramClick"

### 🎠 Рекомендованные Товары

61. **Секция**:
    - Заголовок: "Вам також сподобається"
    - Subtitle: категория
    - margin-top: 4-5rem (отделить от контента)
    
62. **Карусель**:
    - Auto-scroll (slow, 3-5s per item)
    - Smooth transition
    - Infinite loop
    - Pause on hover
    
63. **Карточки товаров**:
    - Компактный дизайн
    - Изображение + название + цена
    - Hover: lift effect
    - Quick view (опционально)
    
64. **Navigation**:
    - Стрелки prev/next (desktop)
    - Swipe (mobile)
    - Dots indicator (mobile)
    
65. **Анимация**:
    - Slide transition
    - Fade edges (gradient mask)
    - Stagger появление при load

---

## 📱 АДАПТИВНОСТЬ

### Breakpoints

```css
/* Mobile First */
/* Extra Small: < 576px */
/* Small: 576px - 767px */
/* Medium: 768px - 991px */
/* Large: 992px - 1199px */
/* Extra Large: >= 1200px */
```

### Mobile (< 768px)

66. **Layout**: Одна колонка, stack
67. **Images**: Full width, aspect-ratio сохраняется
68. **Thumbnails**: Горизонтальный scroll
69. **Цвета**: Grid 5-6 штук в ряд
70. **Размеры**: Grid 3-4 штуки в ряд
71. **Модули**: Stack вертикально
72. **Tabs**: Accordion или dropdown
73. **CTA**: Sticky bottom, full-width
74. **Typography**: Уменьшенные размеры (h1: 1.75rem)
75. **Spacing**: Уменьшенные отступы (padding: 1rem)

### Tablet (768px - 991px)

76. **Layout**: Две колонки 60/40 или stack
77. **Images**: Larger, но не full screen
78. **Thumbnails**: Вертикально или горизонтально
79. **Controls**: Средний размер
80. **Typography**: h1: 2.25rem

### Desktop (>= 992px)

81. **Layout**: Две колонки 50/50 или 60/40
82. **Images**: Крупные, zoom on hover
83. **Thumbnails**: Вертикально слева
84. **Sticky sidebar**: Информация прилипает
85. **Typography**: h1: 2.5-3rem

### Touch Optimizations

86. **Min touch target**: 44x44px (iOS), 48x48px (Android)
87. **Spacing**: Больший gap между кликабельными элементами
88. **Hover effects**: Только на устройствах с hover
89. **Swipe gestures**: Native feel
90. **Scroll behavior**: Smooth, momentum scrolling

---

## ✨ АНИМАЦИИ И TRANSITIONS

### Принципы

91. **Плавность**: 60 FPS (используйте transform и opacity)
92. **Duration**: 200-400ms для micro, 400-600ms для макро
93. **Easing**: cubic-bezier для natural feel
94. **Purpose**: Каждая анимация должна иметь цель

### Ключевые Анимации

95. **Page Enter**:
```css
@keyframes pageEnter {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

96. **Image Transition**:
```css
.product-image {
  transition: opacity 300ms ease, transform 300ms ease;
}
.product-image.switching {
  opacity: 0.7;
  transform: scale(1.05);
}
```

97. **Color Switch**:
```css
.color-swatch {
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
.color-swatch.active {
  transform: scale(1.15);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.4);
}
```

98. **Button Interactions**:
```css
.btn-cta {
  transition: transform 200ms, box-shadow 200ms;
}
.btn-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
}
.btn-cta:active {
  transform: scale(0.95);
}
```

99. **Modal Animations**:
```css
@keyframes modalEnter {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
```

100. **Carousel Transitions**:
```css
.carousel-item {
  transition: transform 600ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Performance

101. **GPU Acceleration**: Используйте `transform` и `opacity`
102. **Will-change**: Добавляйте для анимируемых элементов
103. **Avoid**: margin, padding, width, height анимации
104. **RequestAnimationFrame**: Для JavaScript анимаций
105. **Intersection Observer**: Для scroll-based анимаций

---

## 📊 META PIXEL ИНТЕГРАЦИЯ

### События для Tracking

106. **ViewContent** (при загрузке страницы):
```javascript
window.trackEvent('ViewContent', {
  content_ids: [productId],
  content_name: productTitle,
  content_type: 'product',
  content_category: categoryName,
  value: finalPrice,
  currency: 'UAH'
});
```

107. **CustomizeProduct** (при выборе цвета):
```javascript
window.trackEvent('CustomizeProduct', {
  content_ids: [productId],
  content_type: 'product',
  variant_id: colorVariantId,
  customization_type: 'color'
});
```

108. **CustomizeProduct** (при выборе размера):
```javascript
window.trackEvent('CustomizeProduct', {
  content_ids: [productId],
  content_type: 'product',
  size: selectedSize,
  customization_type: 'size'
});
```

109. **AddToCart** (при добавлении в корзину):
```javascript
window.trackEvent('AddToCart', {
  content_ids: [productId],
  content_name: productTitle,
  content_type: 'product',
  value: finalPrice * quantity,
  currency: 'UAH'
});
```

110. **ViewImage** (при переключении изображения):
```javascript
// Опционально
window.trackEvent('ViewContent', {
  content_ids: [productId],
  content_type: 'product_image',
  image_index: imageIndex
});
```

111. **InstagramClick** (при клике на Instagram):
```javascript
// Custom event
window.trackEvent('Contact', {
  content_name: 'Instagram',
  content_category: 'Social Media'
});
```

112. **ViewSizeGrid** (при открытии размерной сетки):
```javascript
// Custom event
window.trackEvent('ViewContent', {
  content_type: 'size_grid',
  content_ids: [productId]
});
```

---

## 🚀 SEO И ПРОИЗВОДИТЕЛЬНОСТЬ

### SEO

113. **Meta tags**: Используйте product.seo_title, seo_description
114. **OG tags**: Open Graph для соцсетей
115. **Schema.org**: Product schema (уже есть в шаблоне)
116. **Breadcrumbs**: Schema + визуальные
117. **Alt texts**: Для всех изображений
118. **Canonical URL**: Для избежания дубликатов
119. **Lazy loading**: Для изображений ниже fold

### Производительность

120. **Оптимизация изображений**:
    - WebP + AVIF formats
    - Responsive images (srcset)
    - Lazy loading
    - Blur placeholder
    
121. **Critical CSS**: Inline критичные стили
122. **Defer JS**: Не блокируйте рендеринг
123. **Minify**: CSS, JS, HTML
124. **Compression**: Gzip/Brotli
125. **Caching**: Используйте cache_page_for_anon
126. **Preload**: Шрифты и критичные ресурсы
127. **Database**: Select_related, prefetch_related

---

## 🧩 CONTEXT7 РЕКОМЕНДАЦИИ

### Перед Началом

Используйте Context7 для получения актуальных best practices:

128. **Django**:
```
/django/latest - общие паттерны
/django/models - оптимизация моделей
/django/views - оптимизация views
/django/templates - шаблонизация
```

129. **Bootstrap 5**:
```
/twbs/bootstrap - компоненты
/twbs/bootstrap/v5.3.0 - конкретная версия
Темы: carousel, modal, buttons, grid
```

130. **CSS Animations**:
```
Темы: keyframes, transitions, performance
Best practices для GPU acceleration
```

131. **JavaScript**:
```
Темы: Fetch API, Event Delegation, Performance
Modern ES6+ patterns
```

132. **Accessibility**:
```
ARIA roles, keyboard navigation, screen readers
```

### Во Время Разработки

133. **Проверяйте паттерны**: Используйте Context7 для проверки, что вы используете современные паттерны
134. **Performance**: Ищите оптимизации в Context7
135. **Security**: XSS, CSRF protection patterns
136. **Testing**: Паттерны тестирования Django views

---

## ✅ ЧЕКЛИСТ РЕАЛИЗАЦИИ

### Подготовка

- [ ] Прочитать весь документ
- [ ] Использовать Context7 для Django, Bootstrap
- [ ] Использовать Последовательное мышление для планирования
- [ ] Создать план архитектуры

### База Данных

- [ ] Добавить поле `instagram_url` в Product
- [ ] Создать миграцию
- [ ] Применить миграцию

### Backend

- [ ] Обновить product_detail view (если нужно)
- [ ] Добавить Instagram URL в context
- [ ] Проверить работу get_detailed_color_variants
- [ ] Оптимизировать queries (select_related, prefetch_related)

### Frontend - HTML

- [ ] Создать новый шаблон product_detail.html
- [ ] Структура: семантичный HTML5
- [ ] SEO meta tags
- [ ] Open Graph tags
- [ ] Schema.org markup
- [ ] Breadcrumbs
- [ ] Галерея изображений
- [ ] Селектор цветов
- [ ] Селектор размеров
- [ ] Контроль количества
- [ ] Система баллов
- [ ] Дополнительные модули
- [ ] Описание и характеристики
- [ ] Размерная сетка
- [ ] Кнопка заказа
- [ ] Instagram ссылка
- [ ] Рекомендованные товары

### Frontend - CSS

- [ ] Адаптивный layout (mobile-first)
- [ ] Breakpoints: 576px, 768px, 992px, 1200px
- [ ] Typography система
- [ ] Color система (CSS variables)
- [ ] Spacing система
- [ ] Анимации и transitions
- [ ] Glass morphism эффекты
- [ ] Hover states
- [ ] Active states
- [ ] Loading states
- [ ] Error states
- [ ] Accessibility (focus states)

### Frontend - JavaScript

- [ ] Переключение цветов
- [ ] Пересборка галереи при смене цвета
- [ ] Переключение изображений в галерее
- [ ] Zoom функционал
- [ ] Контроль количества (+/-)
- [ ] Добавление в корзину
- [ ] Модальное окно баллов
- [ ] MetaPixel tracking (все события)
- [ ] Smooth scroll
- [ ] Lazy loading изображений
- [ ] Карусель рекомендаций
- [ ] Instagram клик tracking

### Адаптивность

- [ ] Тестирование на iPhone (Safari)
- [ ] Тестирование на Android (Chrome)
- [ ] Тестирование на iPad
- [ ] Тестирование на Desktop (Chrome, Firefox, Safari)
- [ ] Touch targets >= 48px
- [ ] Swipe gestures
- [ ] Sticky elements (mobile)
- [ ] Safe area insets (iOS)

### Производительность

- [ ] Lighthouse score >= 90
- [ ] Оптимизация изображений (WebP/AVIF)
- [ ] Lazy loading
- [ ] Minification CSS/JS
- [ ] Critical CSS inline
- [ ] Defer non-critical JS
- [ ] Caching headers
- [ ] Compression (Gzip/Brotli)

### SEO

- [ ] Meta title уникальный
- [ ] Meta description уникальное
- [ ] OG tags
- [ ] Twitter cards
- [ ] Schema.org Product
- [ ] Breadcrumbs schema
- [ ] Alt texts для изображений
- [ ] Canonical URL
- [ ] Sitemap включает страницу

### Accessibility

- [ ] Keyboard navigation
- [ ] Screen reader friendly
- [ ] ARIA labels
- [ ] Focus visible
- [ ] Color contrast >= 4.5:1
- [ ] Skip links
- [ ] Alt texts

### Testing

- [ ] Функциональное тестирование
- [ ] Выбор цвета работает
- [ ] Смена изображений работает
- [ ] Добавление в корзину работает
- [ ] Модули выбираются
- [ ] Размеры выбираются
- [ ] Количество изменяется
- [ ] Instagram ссылка открывается
- [ ] Рекомендации загружаются
- [ ] MetaPixel события отправляются
- [ ] Кросс-браузерное тестирование
- [ ] Мобильное тестирование

### Финал

- [ ] Code review
- [ ] Документация обновлена
- [ ] Чистка временных файлов
- [ ] Коммит изменений
- [ ] Deploy на тестовый сервер
- [ ] QA тестирование
- [ ] Исправление багов
- [ ] Deploy на продакшн
- [ ] Мониторинг ошибок
- [ ] Сбор feedback от пользователей

---

## 🎁 ДОПОЛНИТЕЛЬНЫЕ РЕКОМЕНДАЦИИ

### Дизайн-система

- Используйте CSS переменные для цветов, spacing, typography
- Создайте utility классы для быстрой разработки
- Документируйте компоненты

### Компоненты

- Разбейте на переиспользуемые компоненты
- Например: ColorSwatch, SizeButton, QuantityControl
- Используйте BEM или другую методологию

### JavaScript Модули

- Разделите логику на модули:
  - `product-gallery.js` - галерея
  - `product-colors.js` - цвета
  - `product-cart.js` - корзина
  - `product-tracking.js` - MetaPixel
- Используйте ES6 modules или bundler

### Fallbacks

- Если нет main_image - показывайте placeholder
- Если нет цветов - скрывайте селектор
- Если нет размеров - показывайте дефолтный
- Если нет Instagram - не показывайте иконку

### Error Handling

- Graceful degradation
- User-friendly сообщения об ошибках
- Retry механизмы для network requests
- Logging ошибок для debugging

### Analytics

- Кроме MetaPixel, можно добавить Google Analytics
- Track user behavior
- A/B testing готовность
- Heatmaps (Hotjar, Clarity)

---

## 📚 РЕСУРСЫ И ПРИМЕРЫ

### Вдохновение для Дизайна

- Shopify stores (премиальные темы)
- Nike, Adidas product pages
- Apple product pages
- ASOS, Zara mobile apps
- Dribbble, Behance (поиск "product page")

### UI Patterns

- Material Design guidelines
- iOS Human Interface Guidelines
- Bootstrap documentation
- Tailwind CSS patterns

### Performance

- web.dev guides
- PageSpeed Insights
- WebPageTest
- Lighthouse

### Accessibility

- WCAG 2.1 guidelines
- A11y project
- WebAIM resources

---

## 🚨 КРИТИЧЕСКИЕ МОМЕНТЫ

### НЕ ЗАБУДЬТЕ:

1. **Протестировать добавление в корзину** с разными цветами и размерами
2. **Проверить MetaPixel события** в Facebook Event Manager
3. **Убедиться что изображения оптимизированы** (не загружать 5MB фотки)
4. **Проверить на реальных устройствах**, не только в DevTools
5. **Accessibility** - не забывайте про keyboard navigation
6. **Загрузка без JavaScript** - должна быть функциональной
7. **Instagram URL** - проверить что открывается в новой вкладке
8. **Размерная сетка** - может быть картинкой или таблицей
9. **Модули** - показывать цену для платных модулей
10. **Рекомендации** - не грузить все товары сразу, lazy load

---

## 💡 СОВЕТЫ ПО РЕАЛИЗАЦИИ

### Начните с Mobile

Mobile-first подход упрощает адаптацию на desktop.

### Используйте Существующие Компоненты

Bootstrap 5 уже загружен в проект - используйте его компоненты.

### Инкрементальная Разработка

Реализуйте по частям:
1. Базовая структура и layout
2. Галерея изображений
3. Селекторы (цвет, размер)
4. Контролы (количество, CTA)
5. Модули и описание
6. Рекомендации
7. Анимации и polish

### Тестирование на Каждом Этапе

Не накапливайте баги - тестируйте часто.

### Читаемость Кода

- Комментируйте сложную логику
- Используйте понятные имена переменных
- Форматируйте код (Prettier, Black)

### Performance Budget

- Total page size: < 2MB
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Images: WebP/AVIF, < 200KB each

---

## 📞 ПОДДЕРЖКА И ВОПРОСЫ

Если в процессе реализации возникнут вопросы:

1. Проверьте **Context7** для конкретной технологии
2. Посмотрите **существующие шаблоны** в проекте (catalog.html, home.html)
3. Используйте **Последовательное мышление** для решения проблем
4. Проверьте **Django документацию**
5. Проверьте **Bootstrap 5 документацию**

Этот документ содержит всю необходимую информацию для полного редизайна страницы продукта. Следуйте инструкциям, используйте Context7 и Последовательное мышление, и результат будет отличным!

**Удачи! 🚀**















