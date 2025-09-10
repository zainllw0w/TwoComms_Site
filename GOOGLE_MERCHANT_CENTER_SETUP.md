# 🛒 Google Merchant Center - Настройка для TwoComms

## 📊 **АНАЛИЗ ТЕКУЩЕЙ РЕАЛИЗАЦИИ**

### ✅ **ЧТО РЕАЛИЗОВАНО ПРАВИЛЬНО:**

#### 1. **Product Schema (JSON-LD):**
- ✅ Все обязательные поля присутствуют
- ✅ Правильная структура данных
- ✅ Совместимость с Google Merchant Center
- ✅ Дополнительные свойства товара

#### 2. **Обязательные поля:**
- ✅ `name` - название товара
- ✅ `description` - описание товара
- ✅ `sku` - артикул товара
- ✅ `mpn` - номер производителя
- ✅ `gtin` - глобальный номер товара
- ✅ `url` - ссылка на товар
- ✅ `image` - изображения товара
- ✅ `brand` - бренд
- ✅ `offers` - предложение с ценой и валютой

#### 3. **Дополнительные поля для одежды:**
- ✅ `age_group` - возрастная группа (adult)
- ✅ `gender` - пол (male/female/unisex)
- ✅ `size` - размеры (S,M,L,XL,XXL)
- ✅ `material` - материал (100% cotton)
- ✅ `color` - цвета из цветовых вариантов
- ✅ `condition` - состояние (new)
- ✅ `availability` - наличие (in stock)

#### 4. **Google Merchant Center фид:**
- ✅ XML фид в формате RSS 2.0
- ✅ Все обязательные поля Google
- ✅ Правильные теги с namespace
- ✅ Динамическая генерация
- ✅ URL: `https://twocomms.shop/google-merchant-feed.xml`

## 🚀 **УЛУЧШЕНИЯ ДЛЯ GOOGLE MERCHANT CENTER**

### 1. **Расширенная Product Schema:**
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Название товара",
  "description": "Описание товара",
  "sku": "TC-123",
  "mpn": "TC-123",
  "gtin": "TC00000123",
  "url": "https://twocomms.shop/product/slug/",
  "image": ["url1", "url2", "url3"],
  "brand": {
    "@type": "Brand",
    "name": "TwoComms"
  },
  "manufacturer": {
    "@type": "Organization",
    "name": "TwoComms"
  },
  "offers": {
    "@type": "Offer",
    "price": "500",
    "priceCurrency": "UAH",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition",
    "seller": {
      "@type": "Organization",
      "name": "TwoComms"
    },
    "shippingDetails": {
      "@type": "OfferShippingDetails",
      "shippingRate": {
        "@type": "MonetaryAmount",
        "value": "0",
        "currency": "UAH"
      }
    }
  },
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "age_group",
      "value": "adult"
    },
    {
      "@type": "PropertyValue",
      "name": "gender",
      "value": "unisex"
    },
    {
      "@type": "PropertyValue",
      "name": "material",
      "value": "100% cotton"
    }
  ]
}
```

### 2. **XML фид для Google Merchant Center:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
  <channel>
    <title>TwoComms - Стріт & Мілітарі Одяг</title>
    <link>https://twocomms.shop</link>
    <description>Магазин стріт & мілітарі одягу з ексклюзивним дизайном</description>
    
    <item>
      <g:id>TC-123</g:id>
      <g:title>Название товара</g:title>
      <g:description>Описание товара</g:description>
      <g:link>https://twocomms.shop/product/slug/</g:link>
      <g:image_link>https://twocomms.shop/media/products/image.jpg</g:image_link>
      <g:availability>in stock</g:availability>
      <g:price>500 UAH</g:price>
      <g:condition>new</g:condition>
      <g:brand>TwoComms</g:brand>
      <g:mpn>TC-123</g:mpn>
      <g:gtin>TC00000123</g:gtin>
      <g:product_type>Футболки</g:product_type>
      <g:google_product_category>1604</g:google_product_category>
      <g:age_group>adult</g:age_group>
      <g:gender>unisex</g:gender>
      <g:size>S,M,L,XL,XXL</g:size>
      <g:material>100% cotton</g:material>
      <g:color>Черный,Белый,Серый</g:color>
    </item>
  </channel>
</rss>
```

## 📋 **ПОШАГОВАЯ НАСТРОЙКА GOOGLE MERCHANT CENTER**

### Шаг 1: Создание аккаунта
1. Перейдите на [Google Merchant Center](https://merchants.google.com/)
2. Создайте аккаунт или войдите в существующий
3. Подтвердите веб-сайт `twocomms.shop`

### Шаг 2: Настройка фида
1. Перейдите в раздел "Продукты" > "Фиды"
2. Нажмите "+" для создания нового фида
3. Выберите "Основной фид"
4. Укажите URL фида: `https://twocomms.shop/google-merchant-feed.xml`
5. Название фида: "TwoComms Products"

### Шаг 3: Настройка атрибутов
1. Перейдите в "Настройки" > "Атрибуты товаров"
2. Настройте маппинг полей:
   - `id` → `g:id`
   - `title` → `g:title`
   - `description` → `g:description`
   - `link` → `g:link`
   - `image_link` → `g:image_link`
   - `price` → `g:price`
   - `availability` → `g:availability`
   - `condition` → `g:condition`
   - `brand` → `g:brand`

### Шаг 4: Настройка доставки
1. Перейдите в "Настройки" > "Доставка"
2. Добавьте зону доставки "Украина"
3. Укажите стоимость доставки: 0 грн
4. Срок доставки: 1-5 рабочих дней

### Шаг 5: Настройка налогов
1. Перейдите в "Настройки" > "Налоги"
2. Добавьте налоговую ставку для Украины: 20%
3. Укажите, что цены включают налоги

### Шаг 6: Запуск фида
1. Вернитесь к фиду
2. Нажмите "Запустить"
3. Дождитесь обработки (может занять несколько часов)
4. Проверьте статус в разделе "Диагностика"

## 🔧 **КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ**

### Генерация статического фида:
```bash
python manage.py generate_google_merchant_feed --output=google_merchant_feed.xml
```

### Предварительный просмотр:
```bash
python manage.py generate_google_merchant_feed --dry-run
```

### Проверка фида:
```bash
# Проверьте доступность фида
curl https://twocomms.shop/google-merchant-feed.xml

# Проверьте валидность XML
xmllint --noout https://twocomms.shop/google-merchant-feed.xml
```

## 📊 **МОНИТОРИНГ И ОПТИМИЗАЦИЯ**

### Ключевые метрики:
1. **Количество одобренных товаров** - должно быть 100%
2. **Количество отклоненных товаров** - должно быть 0%
3. **Время обработки фида** - должно быть < 1 часа
4. **Частота обновления** - рекомендуется ежедневно

### Диагностика проблем:
1. **Отсутствующие изображения** - проверьте URL изображений
2. **Неправильные цены** - убедитесь в правильности валюты
3. **Дублирующиеся ID** - проверьте уникальность SKU
4. **Неправильные категории** - используйте Google Product Categories

## 🎯 **ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ**

### Краткосрочные (1-2 недели):
- ✅ Товары появятся в Google Shopping
- ✅ Улучшится видимость в поиске Google
- ✅ Рост трафика с Google Shopping

### Среднесрочные (1-3 месяца):
- 📈 Рост продаж на 20-30%
- 🎯 Улучшение CTR в Google Shopping
- 💰 Снижение стоимости привлечения клиентов

### Долгосрочные (3-6 месяцев):
- 🏆 Стабильные позиции в Google Shopping
- 📊 Рост органического трафика
- 🌟 Повышение узнаваемости бренда

## 🚨 **ВАЖНЫЕ ЗАМЕЧАНИЯ**

### Обязательные требования:
1. **Все товары должны иметь изображения** (минимум 1, рекомендуется 3-5)
2. **Цены должны быть актуальными** и в правильной валюте
3. **Описания должны быть уникальными** и информативными
4. **Товары должны быть в наличии** (availability: in stock)

### Рекомендации:
1. **Обновляйте фид ежедневно** для актуальности данных
2. **Мониторьте диагностику** для выявления проблем
3. **Оптимизируйте изображения** для лучшего отображения
4. **Используйте релевантные категории** Google Product Categories

## 📞 **ПОДДЕРЖКА**

При возникновении проблем:
1. Проверьте диагностику в Google Merchant Center
2. Убедитесь в доступности фида: `https://twocomms.shop/google-merchant-feed.xml`
3. Проверьте валидность XML структуры
4. Обратитесь в поддержку Google Merchant Center

---

**Успешной настройки Google Merchant Center! 🛒🚀**
