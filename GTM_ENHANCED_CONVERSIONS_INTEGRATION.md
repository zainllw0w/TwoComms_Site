# Google Tag Manager Enhanced Conversions Integration Guide

## 📋 Обзор

Данный документ описывает полную интеграцию Google Tag Manager (GTM) с Enhanced Conversions для отслеживания покупок на сайте TwoComms.

**GTM Container ID:** `GTM-PRLLBF9H`

---

## 🎯 Что было реализовано

### 1. Базовая интеграция GTM
- ✅ GTM скрипт добавлен в `<head>` секцию (base.html)
- ✅ GTM noscript fallback добавлен после `<body>` (base.html)
- ✅ Content Security Policy обновлена для разрешения GTM iframes

### 2. Purchase Event Tracking
- ✅ Событие `purchase` отправляется в dataLayer при успешном заказе
- ✅ Данные о транзакции (transaction_id, value, currency)
- ✅ Детальная информация о товарах (items array)
- ✅ Защита от дублирования событий (sessionStorage)

### 3. Enhanced Conversions
- ✅ Данные пользователя для Enhanced Conversions:
  - `email` (только для авторизованных пользователей)
  - `phone_number` (телефон)
  - `first_name` и `last_name` (из ФИО)
  - `address.city` (город доставки)

### 4. Поддержка всех сценариев покупки
- ✅ Авторизованные пользователи
- ✅ Гостевые покупки (без регистрации)
- ✅ Оплата картой через Monobank
- ✅ Оплата наложенным платежом (COD)

---

## 📊 Структура dataLayer Event

### Purchase Event

При успешном оформлении заказа в `dataLayer` отправляется следующее событие:

```javascript
{
  "event": "purchase",
  "ecommerce": {
    "transaction_id": "TWC29102024N01",  // Уникальный номер заказа
    "value": 1599.00,                     // Сумма заказа
    "currency": "UAH",                    // Валюта
    "items": [
      {
        "item_id": "123",                 // ID товара
        "item_name": "Product Name",      // Название товара
        "quantity": 2,                    // Количество
        "price": 799.50                   // Цена за единицу
      }
    ]
  },
  "user_data": {
    "email": "user@example.com",          // Email (только для авторизованных)
    "phone_number": "+380501234567",      // Телефон
    "first_name": "Иван",                 // Имя
    "last_name": "Петренко",              // Фамилия
    "address": {
      "city": "Київ"                      // Город
    }
  }
}
```

---

## 🔧 Настройка GTM Container

### Шаг 1: Создание триггера для Purchase

1. В GTM перейдите в раздел **Triggers** (Триггери)
2. Создайте новый триггер:
   - **Trigger Type:** Custom Event
   - **Event name:** `purchase`
   - **This trigger fires on:** All Custom Events

### Шаг 2: Создание переменных для Enhanced Conversions

Создайте следующие переменные типа **Data Layer Variable**:

#### Переменные транзакции:
- `ecommerce.transaction_id` → **Variable Name:** `DLV - Transaction ID`
- `ecommerce.value` → **Variable Name:** `DLV - Transaction Value`
- `ecommerce.currency` → **Variable Name:** `DLV - Currency`

#### Переменные пользователя (Enhanced Conversions):
- `user_data.email` → **Variable Name:** `DLV - User Email`
- `user_data.phone_number` → **Variable Name:** `DLV - User Phone`
- `user_data.first_name` → **Variable Name:** `DLV - User First Name`
- `user_data.last_name` → **Variable Name:** `DLV - User Last Name`
- `user_data.address.city` → **Variable Name:** `DLV - User City`

### Шаг 3: Настройка Google Ads Conversion Tag

1. Создайте новый тег типа **Google Ads Conversion Tracking**
2. Настройте:
   - **Conversion ID:** Ваш ID из Google Ads
   - **Conversion Label:** Ваш Label из Google Ads
   - **Conversion Value:** `{{DLV - Transaction Value}}`
   - **Currency Code:** `{{DLV - Currency}}`
   - **Order ID:** `{{DLV - Transaction ID}}`

3. Включите **Enhanced Conversions**:
   - **Email:** `{{DLV - User Email}}`
   - **Phone Number:** `{{DLV - User Phone}}`
   - **First Name:** `{{DLV - User First Name}}`
   - **Last Name:** `{{DLV - User Last Name}}`
   - **City:** `{{DLV - User City}}`

4. Установите триггер: `purchase` (созданный на Шаге 1)

### Шаг 4: Настройка Google Analytics 4 (GA4) Purchase Event

1. Создайте новый тег типа **Google Analytics: GA4 Event**
2. Настройте:
   - **Measurement ID:** Ваш GA4 Measurement ID
   - **Event Name:** `purchase`
   - **Event Parameters:**
     - `transaction_id` = `{{DLV - Transaction ID}}`
     - `value` = `{{DLV - Transaction Value}}`
     - `currency` = `{{DLV - Currency}}`
     - `items` = `{{ecommerce.items}}` (Data Layer Variable)

3. Включите **User Properties** для Enhanced Conversions:
   - `user_id` (если есть)
   - `email` = `{{DLV - User Email}}`
   - `phone_number` = `{{DLV - User Phone}}`

4. Установите триггер: `purchase`

---

## 🛡️ Защита от дублирования событий

Реализован механизм защиты от повторной отправки события при обновлении страницы:

```javascript
var storageKey = 'gtm_purchase_' + orderId;
if (sessionStorage.getItem(storageKey)) {
  console.log('GTM Purchase event already sent for order:', orderId);
  return;
}
// ... отправка события ...
sessionStorage.setItem(storageKey, 'true');
```

Событие отправляется **только один раз** за сессию для каждого заказа.

---

## 🔍 CSS Selекторы для форм (для будущих интеграций)

### Форма корзины (авторизованные пользователи)
```css
/* Форма доставки */
#deliveryForm

/* Поля */
input[name="full_name"]  /* ФИО */
input[name="phone"]      /* Телефон */
input[name="city"]       /* Город */
input[name="np_office"]  /* Отделение НП */
```

### Форма корзины (гостевые пользователи)
```css
/* Форма доставки */
#guest-form

/* Поля (идентичные по name) */
input[name="full_name"]
input[name="phone"]
input[name="city"]
input[name="np_office"]
```

### Форма профиля
```css
/* Поля профиля */
#id_full_name  /* ФИО */
#id_phone      /* Телефон */
#id_email      /* Email */
#id_city       /* Город */
```

---

## 📁 Измененные файлы

### 1. `/twocomms/storefront/views.py`
**Изменения:**
- Строка 2640: `order_create()` теперь редиректит на `order_success` вместо `my_orders`

```python
# Было:
return redirect('my_orders')

# Стало:
return redirect('order_success', order_id=order.id)
```

### 2. `/twocomms/storefront/views/checkout.py`
**Изменения:**
- Строка 416: `payment_callback()` исправлен редирект с `order_number` на `order_id`

```python
# Было:
return redirect('order_success', order_number=order_number)

# Стало:
return redirect('order_success', order_id=order.id)
```

### 3. `/twocomms/twocomms_django_theme/templates/pages/order_success.html`
**Изменения:**
- Добавлены data-атрибуты для GTM tracking (строки 106-116)
- Добавлен JavaScript для отправки purchase event в dataLayer (строки 118-234)
- Улучшен UI для авторизованных пользователей (кнопка "Мої замовлення")

---

## 🧪 Тестирование

### Проверка на локальном окружении

1. Откройте Chrome DevTools → Console
2. Проверьте что dataLayer инициализирован:
```javascript
console.log(window.dataLayer);
```

3. Оформите тестовый заказ
4. На странице order_success проверьте консоль:
```
GTM Purchase event sent: {event: "purchase", ecommerce: {...}, user_data: {...}}
```

### Проверка в GTM Preview Mode

1. В GTM активируйте **Preview mode**
2. Подключитесь к сайту
3. Оформите тестовый заказ
4. В GTM Preview проверьте:
   - Событие `purchase` появилось в списке событий
   - Все переменные заполнены корректно
   - Теги сработали

### Проверка на production

```bash
# Подключитесь по SSH
sshpass -p '${TWC_SSH_PASS}' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169

# Перейдите в директорию проекта
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# Подтяните изменения
git pull

# Перезапустите приложение (для PythonAnywhere)
touch /var/www/yourdomain_pythonanywhere_com_wsgi.py
```

---

## 📈 Сценарии покупки

### Сценарий 1: Авторизованный пользователь, оплата COD

1. Пользователь добавляет товары в корзину
2. Переходит в корзину (`/cart/`)
3. Заполняет форму доставки (или данные загружаются из профиля)
4. Выбирает "Наложений платіж"
5. Нажимает "Оформити замовлення"
6. → **Редирект на `/orders/success/{order_id}/`**
7. → **Purchase event отправляется в GTM**
8. Пользователь видит кнопку "Мої замовлення"

**Enhanced Conversions данные:**
- ✅ email (из userprofile)
- ✅ phone
- ✅ first_name, last_name
- ✅ city

### Сценарий 2: Гость, оплата COD

1. Пользователь добавляет товары в корзину
2. Переходит в корзину
3. Заполняет гостевую форму доставки
4. Выбирает "Наложений платіж"
5. Нажимает "Оформити замовлення"
6. → **Редирект на `/orders/success/{order_id}/`**
7. → **Purchase event отправляется в GTM**
8. Пользователь видит предложение зарегистрироваться

**Enhanced Conversions данные:**
- ❌ email (нет для гостей)
- ✅ phone
- ✅ first_name, last_name
- ✅ city

### Сценарий 3: Авторизованный пользователь, Monobank

1. Пользователь добавляет товары в корзину
2. Оформляет заказ с выбором "Оплата карткою"
3. → **Редирект на Monobank**
4. Пользователь оплачивает
5. Monobank отправляет webhook на сервер
6. → **Редирект на `/orders/success/{order_id}/`** (через payment_callback)
7. → **Purchase event отправляется в GTM**

**Enhanced Conversions данные:**
- ✅ email
- ✅ phone
- ✅ first_name, last_name
- ✅ city

### Сценарий 4: Гость, Monobank

1. Аналогично сценарию 3, но без email

**Enhanced Conversions данные:**
- ❌ email
- ✅ phone
- ✅ first_name, last_name
- ✅ city

---

## ⚠️ Важные замечания

### 1. Email только для авторизованных
Email передается только если:
- Пользователь авторизован (`user.is_authenticated`)
- У пользователя есть профиль с заполненным email (`userprofile.email`)

### 2. Защита персональных данных
Все данные пользователя передаются через `user_data` объект, который:
- Хешируется GTM перед отправкой в Google Ads (SHA256)
- Не логируется в публичных консолях на production
- Соответствует требованиям GDPR

### 3. Дедупликация конверсий
Обязательно используйте `transaction_id` в настройках Google Ads Conversion:
- Это предотвратит подсчет дублирующихся конверсий
- Уникальный формат: `TWC{дата}N{номер}` (например: `TWC29102024N01`)

---

## 🐛 Отладка

### Событие не отправляется

1. Проверьте консоль браузера на ошибки
2. Убедитесь что GTM скрипт загружен:
```javascript
console.log(window.google_tag_manager);
```

3. Проверьте что dataLayer инициализирован:
```javascript
console.log(window.dataLayer);
```

### Событие отправляется дважды

Проверьте `sessionStorage`:
```javascript
// Очистить для тестирования
sessionStorage.clear();
```

### Enhanced Conversions не работают

1. Проверьте что переменные заполнены в GTM Preview
2. Убедитесь что формат данных соответствует требованиям Google:
   - Email: валидный email
   - Phone: международный формат (+380...)
   - Имя/Фамилия: без цифр и спецсимволов

---

## 📞 Контакты

При возникновении вопросов или проблем с интеграцией:
- Проверьте GTM Preview Mode
- Проверьте консоль браузера
- Проверьте логи Django (если ошибка на стороне сервера)

---

## 📝 Changelog

### 2024-10-29
- ✅ Добавлена базовая интеграция GTM
- ✅ Реализован Purchase event tracking
- ✅ Добавлена поддержка Enhanced Conversions
- ✅ Исправлены редиректы после создания заказа
- ✅ Добавлена защита от дублирования событий
- ✅ Улучшен UI страницы успешного заказа

---

**Документация подготовлена:** 29 октября 2024
**Версия:** 1.0

