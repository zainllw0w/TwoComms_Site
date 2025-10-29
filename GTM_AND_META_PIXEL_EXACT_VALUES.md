# 🎯 ТОЧНЫЕ ЗНАЧЕНИЯ для GTM и Meta Pixel

## 📊 ЧТО ПЕРЕДАЕТСЯ АВТОМАТИЧЕСКИ С САЙТА

При успешной покупке на странице `order_success` **автоматически** отправляются данные в:
1. ✅ **Google Tag Manager (GTM)** через `dataLayer.push()`
2. ✅ **Meta Pixel (Facebook Pixel)** через `fbq('track', 'Purchase')`

---

## 🔴 META PIXEL (FACEBOOK PIXEL) - EXACT VALUES

### **Что передается в Meta Pixel АВТОМАТИЧЕСКИ:**

#### **Основные данные Purchase:**
```javascript
fbq('track', 'Purchase', {
  value: 1599.00,           // Сумма заказа
  currency: 'UAH',          // Валюта
  contents: [...],          // Товары
  content_type: 'product'   // Тип контента
})
```

#### **Advanced Matching данные (3-й параметр fbq):**

| **Key (Ключ)** | **Value (Значение)** | **Пример** | **Описание** |
|----------------|---------------------|-----------|--------------|
| `em` | Email (lowercase) | `user@example.com` | Email пользователя (только для авторизованных) |
| `ph` | Phone (только цифры) | `380501234567` | Телефон без +, пробелов, скобок |
| `fn` | First Name (lowercase) | `іван` | Имя (первое слово из ФИО) |
| `ln` | Last Name (lowercase) | `петренко` | Фамилия (последнее слово из ФИО) |
| `ct` | City (lowercase) | `київ` | Город доставки |

### **Пример полного вызова Meta Pixel:**
```javascript
fbq('track', 'Purchase', 
  {
    value: 1599.00,
    currency: 'UAH',
    contents: [
      {id: '123', quantity: 2}
    ],
    content_type: 'product'
  },
  {
    em: 'user@example.com',    // Email
    ph: '380501234567',        // Phone (без +)
    fn: 'іван',                // First Name
    ln: 'петренко',            // Last Name
    ct: 'київ'                 // City
  }
);
```

---

## 🟢 GOOGLE TAG MANAGER (GTM) - EXACT VALUES

### **Что передается в GTM dataLayer АВТОМАТИЧЕСКИ:**

```javascript
window.dataLayer.push({
  event: 'purchase',
  ecommerce: {
    transaction_id: 'TWC29102024N01',
    value: 1599.00,
    currency: 'UAH',
    items: [
      {
        item_id: '123',
        item_name: 'Product Name',
        quantity: 2,
        price: 799.50
      }
    ]
  },
  user_data: {
    email: 'user@example.com',
    phone_number: '+380501234567',
    first_name: 'Іван',
    last_name: 'Петренко',
    address: {
      city: 'Київ'
    }
  }
});
```

### **Data Layer Variables (что создать в GTM):**

| **Variable Name** | **Data Layer Variable Name (KEY)** | **Пример значения (VALUE)** |
|-------------------|-------------------------------------|------------------------------|
| `DLV - User Email` | `user_data.email` | `user@example.com` |
| `DLV - User Phone` | `user_data.phone_number` | `+380501234567` |
| `DLV - User First Name` | `user_data.first_name` | `Іван` |
| `DLV - User Last Name` | `user_data.last_name` | `Петренко` |
| `DLV - User City` | `user_data.address.city` | `Київ` |
| `DLV - Transaction ID` | `ecommerce.transaction_id` | `TWC29102024N01` |
| `DLV - Transaction Value` | `ecommerce.value` | `1599.00` |
| `DLV - Currency` | `ecommerce.currency` | `UAH` |

### **Enhanced Conversions в Google Ads Tag:**

| **Поле в GTM** | **Значение (что вводить)** |
|----------------|----------------------------|
| Email | `{{DLV - User Email}}` |
| Phone Number | `{{DLV - User Phone}}` |
| First Name | `{{DLV - User First Name}}` |
| Last Name | `{{DLV - User Last Name}}` |
| City | `{{DLV - User City}}` |

---

## 📋 СРАВНЕНИЕ: Meta Pixel vs GTM

| **Параметр** | **Meta Pixel (ключ)** | **GTM (путь в dataLayer)** | **Формат** |
|--------------|----------------------|---------------------------|-----------|
| Email | `em` | `user_data.email` | lowercase |
| Phone | `ph` | `user_data.phone_number` | Pixel: только цифры; GTM: с + |
| First Name | `fn` | `user_data.first_name` | Pixel: lowercase; GTM: как есть |
| Last Name | `ln` | `user_data.last_name` | Pixel: lowercase; GTM: как есть |
| City | `ct` | `user_data.address.city` | Pixel: lowercase; GTM: как есть |

---

## ✅ ЧТО УЖЕ РАБОТАЕТ НА САЙТЕ (АВТОМАТИЧЕСКИ)

### **1. При успешном заказе:**

✅ **Отправляется GTM Purchase event** с данными:
- Transaction ID (уникальный номер заказа)
- Value (сумма)
- Currency (UAH)
- Items (товары)
- User Data (email, phone, name, city)

✅ **Отправляется Meta Pixel Purchase** с данными:
- Value (сумма)
- Currency (UAH)
- Contents (товары)
- Advanced Matching (email, phone, name, city)

### **2. Защита от дублирования:**
- ✅ События отправляются **только 1 раз** за сессию
- ✅ Повторные заходы на страницу не дублируют события

### **3. Логирование:**
```javascript
// В консоли браузера вы увидите:
"GTM Purchase event sent: {...}"
"Meta Pixel Purchase event sent with Advanced Matching: {em: '...', ph: '...', ...}"
```

---

## 🔧 ЧТО НУЖНО СДЕЛАТЬ В GTM (ВАША ЗАДАЧА)

### **Шаг 1: Создать триггер**
- **Name:** `purchase`
- **Type:** Custom Event
- **Event name:** `purchase`

### **Шаг 2: Создать Data Layer Variables**

Создайте 8 переменных (copy-paste):

#### **Переменная 1:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - User Email`
- **Data Layer Variable Name:** `user_data.email`

#### **Переменная 2:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - User Phone`
- **Data Layer Variable Name:** `user_data.phone_number`

#### **Переменная 3:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - User First Name`
- **Data Layer Variable Name:** `user_data.first_name`

#### **Переменная 4:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - User Last Name`
- **Data Layer Variable Name:** `user_data.last_name`

#### **Переменная 5:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - User City`
- **Data Layer Variable Name:** `user_data.address.city`

#### **Переменная 6:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Transaction ID`
- **Data Layer Variable Name:** `ecommerce.transaction_id`

#### **Переменная 7:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Transaction Value`
- **Data Layer Variable Name:** `ecommerce.value`

#### **Переменная 8:**
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Currency`
- **Data Layer Variable Name:** `ecommerce.currency`

### **Шаг 3: Настроить Google Ads Conversion Tag**

1. **Tag Type:** Google Ads Conversion Tracking
2. **Conversion ID:** (ваш ID из Google Ads)
3. **Conversion Label:** (ваш Label)
4. **Conversion Value:** `{{DLV - Transaction Value}}`
5. **Currency Code:** `{{DLV - Currency}}`
6. **Order ID:** `{{DLV - Transaction ID}}`

7. **Include user-provided data from your website (Enhanced Conversions):**
   - ☑️ Enable
   - **Email:** `{{DLV - User Email}}`
   - **Phone Number:** `{{DLV - User Phone}}`
   - **First Name:** `{{DLV - User First Name}}`
   - **Last Name:** `{{DLV - User Last Name}}`
   - **City:** `{{DLV - User City}}`

8. **Trigger:** `purchase`

9. **Save** and **Publish**

---

## 🔍 КАК ПРОВЕРИТЬ ЧТО ВСЕ РАБОТАЕТ

### **1. Проверка Meta Pixel:**

Откройте **Chrome DevTools** → **Console** и введите:
```javascript
// Проверьте что Pixel загружен
console.log(window.fbq);

// Проверьте ID пикселя
console.log(window._fbq);
```

Оформите тестовый заказ. В консоли увидите:
```
Meta Pixel Purchase event sent with Advanced Matching: {em: "user@example.com", ph: "380501234567", fn: "іван", ln: "петренко", ct: "київ"}
```

### **2. Проверка GTM:**

Откройте **Chrome DevTools** → **Console** и введите:
```javascript
// Проверьте что GTM загружен
console.log(window.google_tag_manager);

// Проверьте dataLayer
console.log(window.dataLayer);
```

Оформите тестовый заказ. В консоли увидите:
```
GTM Purchase event sent: {event: "purchase", ecommerce: {...}, user_data: {...}}
```

### **3. Проверка в Facebook Events Manager:**

1. Откройте **Facebook Events Manager**
2. Выберите ваш Pixel (ID: `823958313630148`)
3. Перейдите в **Test Events**
4. Оформите тестовый заказ
5. Проверьте что событие `Purchase` пришло
6. Проверьте что есть **Advanced Matching** (email, phone, name, city)

### **4. Проверка в GTM Preview Mode:**

1. В GTM нажмите **Preview**
2. Введите URL сайта
3. Оформите тестовый заказ
4. В GTM Preview проверьте:
   - Событие `purchase` появилось
   - Все переменные `DLV - *` заполнены
   - Google Ads Tag сработал

---

## 📝 ИТОГО

### **Что УЖЕ работает (НЕ нужно настраивать):**

✅ **Meta Pixel Purchase** с Advanced Matching  
✅ **GTM dataLayer.push** с purchase event  
✅ **Данные пользователя** передаются автоматически  
✅ **Защита от дублирования** событий  

### **Что НУЖНО сделать (ВАША задача):**

⚠️ **В GTM:**
1. Создать триггер `purchase` (5 минут)
2. Создать 8 Data Layer переменных (10 минут)
3. Настроить Google Ads Conversion Tag (10 минут)
4. Протестировать в Preview Mode (5 минут)
5. Опубликовать изменения (1 минута)

**Общее время:** ~30 минут

⚠️ **В Facebook/Meta:**
- ✅ **Ничего не нужно!** Pixel уже работает с Advanced Matching!

---

## 🎯 EXACT KEY-VALUE TABLE (для копирования)

### **Meta Pixel Advanced Matching:**
```
em = email (lowercase)
ph = phone (digits only)
fn = first_name (lowercase)
ln = last_name (lowercase)
ct = city (lowercase)
```

### **GTM Data Layer Variables:**
```
user_data.email          → {{DLV - User Email}}
user_data.phone_number   → {{DLV - User Phone}}
user_data.first_name     → {{DLV - User First Name}}
user_data.last_name      → {{DLV - User Last Name}}
user_data.address.city   → {{DLV - User City}}
ecommerce.transaction_id → {{DLV - Transaction ID}}
ecommerce.value          → {{DLV - Transaction Value}}
ecommerce.currency       → {{DLV - Currency}}
```

---

**Дата:** 29 октября 2024  
**Версия:** 2.0 (с Meta Pixel Advanced Matching)  
**Статус:** ✅ Готово к использованию

