# 📊 Facebook Pixel - Отдельная установка

## ✅ Facebook Pixel настроен отдельно!

### **Что сделано:**

#### **1. Создан отдельный файл для Facebook Pixel:**
- ✅ **Файл:** `templates/partials/facebook_pixel.html`
- ✅ **Содержит:** Оригинальный код Facebook Pixel
- ✅ **ID:** `1101270515449298`
- ✅ **Условие:** Загружается только в продакшене (`{% if not debug %}`)

#### **2. Подключен ко всем шаблонам:**
- ✅ **Добавлен в:** `base.html` (строка 33)
- ✅ **Доступен на:** Всех страницах сайта
- ✅ **Наследование:** Все шаблоны наследуются от `base.html`

#### **3. Убран из analytics.html:**
- ✅ **Избежано:** Дублирование кода
- ✅ **Чистота:** Отдельные файлы для разных аналитических систем

### **Структура файлов:**

```
templates/
├── base.html                    # Основной шаблон (включает Facebook Pixel)
├── partials/
│   ├── facebook_pixel.html      # 🆕 Facebook Pixel код
│   ├── analytics.html           # Другие аналитические системы
│   └── seo_meta.html           # SEO мета-теги
└── pages/
    ├── index.html              # Наследует от base.html
    ├── product_detail.html     # Наследует от base.html
    ├── cart.html               # Наследует от base.html
    └── ...                     # Все остальные страницы
```

### **Код Facebook Pixel:**

```html
<!-- Meta Pixel Code -->
{% if not debug %}
<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '1101270515449298');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id=1101270515449298&ev=PageView&noscript=1"
/></noscript>
{% endif %}
<!-- End Meta Pixel Code -->
```

## 🚀 Инструкция для сервера:

### **Шаг 1: Обновите код**
```bash
cd /home/your_username/TwoComms_Site/twocomms
git pull origin main
```

### **Шаг 2: Соберите статические файлы**
```bash
python manage.py collectstatic --noinput --settings=twocomms.production_settings
```

### **Шаг 3: Перезапустите веб-приложение**
```bash
# В PythonAnywhere:
# 1. Перейдите в Web tab
# 2. Нажмите "Reload" для вашего домена
```

## 🎯 Ожидаемый результат:

### **На всех страницах сайта:**
- ✅ **Facebook Pixel загружается** с ID: `1101270515449298`
- ✅ **PageView отслеживается** на каждой странице
- ✅ **Код работает** только в продакшене
- ✅ **Отдельный файл** для удобства управления

### **Страницы с Facebook Pixel:**
- ✅ **Главная** (`/`)
- ✅ **Каталог** (`/catalog/`)
- ✅ **Детали товара** (`/product/...`)
- ✅ **Корзина** (`/cart/`)
- ✅ **Профиль** (`/profile/`)
- ✅ **Все остальные** страницы сайта

## 🔍 Проверка работы:

### **1. В браузере:**
- Откройте любую страницу сайта
- Откройте Developer Tools (F12)
- В Console должно быть: `fbq` функция доступна
- В Network должен быть запрос к `fbevents.js`

### **2. В Facebook Ads Manager:**
- Перейдите в Events Manager
- Выберите ваш Pixel ID: `1101270515449298`
- Проверьте события PageView
- Должны отображаться посещения страниц

### **3. Facebook Pixel Helper (расширение):**
- Установите расширение Facebook Pixel Helper
- Откройте любую страницу сайта
- Должен показывать активный Pixel с ID: `1101270515449298`

## 📈 Дополнительные события:

### **Для отслеживания покупок добавьте в шаблоны:**

```html
<!-- В шаблоне успешного заказа -->
<script>
fbq('track', 'Purchase', {
  value: {{ order.total_amount }},
  currency: 'UAH',
  content_ids: [{% for item in order.items %}'{{ item.product.id }}'{% if not forloop.last %},{% endif %}{% endfor %}]
});
</script>
```

```html
<!-- В шаблоне добавления в корзину -->
<script>
fbq('track', 'AddToCart', {
  value: {{ product.final_price }},
  currency: 'UAH',
  content_ids: ['{{ product.id }}']
});
</script>
```

## ✅ Готово!

**Facebook Pixel теперь установлен отдельно и работает на всех страницах сайта!** 🎉

- **ID:** `1101270515449298`
- **Статус:** Активен на всех страницах
- **Отслеживание:** PageView на каждой странице
- **Управление:** Отдельный файл для удобства
