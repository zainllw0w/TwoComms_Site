# 🔑 GTM Enhanced Conversions - Key-Value данные

## 📊 Данные пользователя (User Data)

### Для ВСЕХ пользователей (авторизованных и гостей):

| **Ключ (Key)** | **Пример значения (Value)** | **Откуда берется** |
|----------------|----------------------------|-------------------|
| `phone_number` | `+380501234567` | Поле "Телефон" в форме заказа |
| `first_name` | `Іван` | Первое слово из ФИО |
| `last_name` | `Петренко` | Последнее слово из ФИО |
| `address.city` | `Київ` | Поле "Город" в форме заказа |

### Только для АВТОРИЗОВАННЫХ пользователей:

| **Ключ (Key)** | **Пример значения (Value)** | **Откуда берется** |
|----------------|----------------------------|-------------------|
| `email` | `user@example.com` | Email из профиля пользователя |

---

## 💰 Данные транзакции (Transaction Data)

| **Ключ (Key)** | **Пример значения (Value)** | **Описание** |
|----------------|----------------------------|-------------|
| `transaction_id` | `TWC29102024N01` | Уникальный номер заказа (формат: TWC+дата+N+номер) |
| `value` | `1599.00` | Общая сумма заказа в гривнах |
| `currency` | `UAH` | Валюта (гривна) |

---

## 🛍️ Данные товаров (Items Data)

Для каждого товара в заказе:

| **Ключ (Key)** | **Пример значения (Value)** | **Описание** |
|----------------|----------------------------|-------------|
| `items[].item_id` | `123` | ID товара в базе данных |
| `items[].item_name` | `Футболка TwoComms` | Название товара |
| `items[].quantity` | `2` | Количество единиц товара |
| `items[].price` | `799.50` | Цена за одну единицу |

---

## 🎯 Где это используется в GTM

### 1. В Data Layer Variables создайте:

```
Имя переменной в GTM           →    Путь в dataLayer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DLV - Transaction ID           →    ecommerce.transaction_id
DLV - Transaction Value        →    ecommerce.value
DLV - Currency                 →    ecommerce.currency

DLV - User Email               →    user_data.email
DLV - User Phone               →    user_data.phone_number
DLV - User First Name          →    user_data.first_name
DLV - User Last Name           →    user_data.last_name
DLV - User City                →    user_data.address.city
```

### 2. В Google Ads Conversion Tag используйте:

**Enhanced Conversions:**
- Адрес электронной почты: `{{DLV - User Email}}`
- Номер телефона: `{{DLV - User Phone}}`
- Имя: `{{DLV - User First Name}}`
- Фамилия: `{{DLV - User Last Name}}`
- Город: `{{DLV - User City}}`

**Transaction Data:**
- Order ID: `{{DLV - Transaction ID}}`
- Conversion Value: `{{DLV - Transaction Value}}`
- Currency Code: `{{DLV - Currency}}`

---

## 🔍 CSS Селекторы (если понадобятся)

### Форма корзины (авторизованные):
```css
#deliveryForm                    /* Вся форма */
input[name="full_name"]          /* ФИО */
input[name="phone"]              /* Телефон */
input[name="city"]               /* Город */
input[name="np_office"]          /* Отделение НП */
```

### Форма корзины (гости):
```css
#guest-form                      /* Вся форма */
input[name="full_name"]          /* ФИО */
input[name="phone"]              /* Телефон */
input[name="city"]               /* Город */
input[name="np_office"]          /* Отделение НП */
```

### Форма профиля:
```css
#id_full_name                    /* ФИО */
#id_phone                        /* Телефон */
#id_email                        /* Email */
#id_city                         /* Город */
```

---

## 📋 Полная структура события в dataLayer

```javascript
{
  "event": "purchase",
  "ecommerce": {
    "transaction_id": "TWC29102024N01",
    "value": 1599.00,
    "currency": "UAH",
    "items": [
      {
        "item_id": "123",
        "item_name": "Футболка TwoComms",
        "quantity": 2,
        "price": 799.50
      }
    ]
  },
  "user_data": {
    "email": "user@example.com",        // Только для авторизованных
    "phone_number": "+380501234567",
    "first_name": "Іван",
    "last_name": "Петренко",
    "address": {
      "city": "Київ"
    }
  }
}
```

---

## ✅ Что уже работает

- ✅ **Событие `purchase`** отправляется автоматически при успешном заказе
- ✅ **Все данные** заполняются из заказа
- ✅ **Защита от дублирования** (событие отправляется только 1 раз)
- ✅ **4 сценария покупки** поддерживаются:
  - Авторизованный + Наложенный платеж
  - Гость + Наложенный платеж
  - Авторизованный + Monobank
  - Гость + Monobank

---

## 🚀 Что осталось сделать (в GTM)

1. **Создать триггер `purchase`** (Custom Event)
2. **Создать 8 Data Layer переменных** (см. таблицу выше)
3. **Настроить Google Ads Conversion Tag** с Enhanced Conversions
4. **Протестировать в Preview Mode**
5. **Опубликовать изменения в GTM**

**Время: ~40 минут**

---

## 📞 Контактные данные для Enhanced Conversions

### Данные которые ВСЕГДА доступны (100% заказов):
- ✅ Телефон (`phone_number`)
- ✅ Имя (`first_name`)
- ✅ Фамилия (`last_name`)
- ✅ Город (`address.city`)

### Данные которые доступны УСЛОВНО:
- ⚠️ Email (`email`) - только для авторизованных пользователей (~50% заказов)

### Данные которые НЕ доступны:
- ❌ Почтовый адрес (улица, дом) - не собирается
- ❌ Почтовый индекс - не собирается
- ❌ Страна - всегда Украина (можно добавить константу)
- ❌ Штат/регион - не применимо для Украины

---

## 🎯 Итого

У вас есть **все ключевые данные** для Google Ads Enhanced Conversions:

✅ **Email** (для половины заказов)  
✅ **Телефон** (для всех заказов)  
✅ **Имя и Фамилия** (для всех заказов)  
✅ **Город** (для всех заказов)  

Этого **достаточно** для значительного улучшения точности отслеживания конверсий!

---

**Дата:** 29 октября 2024  
**Версия:** 1.0

