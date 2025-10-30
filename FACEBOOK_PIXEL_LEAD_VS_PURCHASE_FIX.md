# 🎯 ИСПРАВЛЕНИЕ: Facebook Pixel Lead vs Purchase

**Дата:** 30 октября 2025  
**Проблема:** Facebook Pixel не различал заявки (Lead) и оплаченные покупки (Purchase)  
**Решение:** Условная отправка событий на основе `payment_status`

---

## ❌ ПРОБЛЕМА (ДО ИСПРАВЛЕНИЯ)

### Что было неправильно:

На странице `order_success.html` **ВСЕГДА** отправлялось событие `Purchase` в Facebook Pixel, независимо от того, оплатил пользователь заказ или нет.

### Два сценария, которые путались:

#### **Сценарий 1: Заявка (Lead)** 
- Пользователь оформил заказ через форму
- Не оплатил (будет звонить менеджер)
- `payment_status = 'unpaid'` / `'checking'` / `'partial'`
- ❌ Facebook Pixel отправлял `Purchase` (НЕПРАВИЛЬНО!)

#### **Сценарий 2: Покупка (Purchase)**
- Пользователь оформил заказ И оплатил через MonoPay
- Платеж прошел успешно
- `payment_status = 'paid'`
- ✅ Facebook Pixel отправлял `Purchase` (ПРАВИЛЬНО!)

### Последствия:

1. ❌ Facebook Ads считал заявки как покупки
2. ❌ Искажалась статистика конверсий
3. ❌ Невозможно было оптимизировать по Lead vs Purchase
4. ❌ ROAS (Return on Ad Spend) рассчитывался неправильно

---

## ✅ РЕШЕНИЕ (ПОСЛЕ ИСПРАВЛЕНИЯ)

### Что изменилось:

Теперь код **проверяет `payment_status`** и отправляет **разные события**:

```javascript
var paymentStatus = el.dataset.paymentStatus; // 'paid', 'unpaid', 'checking', 'partial'
var isPaid = paymentStatus === 'paid';

if (isPaid) {
  // Отправляем Purchase
  fbq('track', 'Purchase', {...});
  dataLayer.push({ event: 'purchase', ... });
} else {
  // Отправляем Lead
  fbq('track', 'Lead', {...});
  dataLayer.push({ event: 'lead', ... });
}
```

---

## 📊 СОБЫТИЯ И ИХ ПАРАМЕТРЫ

### **1. Purchase Event (Оплаченный заказ)**

#### Facebook Pixel:
```javascript
fbq('track', 'Purchase', {
  value: 1599.00,              // Сумма заказа
  currency: 'UAH',             // Валюта
  contents: [                  // Товары
    {id: '123', quantity: 2}
  ],
  content_type: 'product'
}, {
  // Advanced Matching
  em: 'user@example.com',      // Email
  ph: '380501234567',          // Телефон (только цифры)
  fn: 'іван',                  // Имя (lowercase)
  ln: 'петренко',              // Фамилия (lowercase)
  ct: 'київ'                   // Город (lowercase)
});
```

#### Google Tag Manager:
```javascript
dataLayer.push({
  event: 'purchase',
  ecommerce: {
    transaction_id: 'TWC30102025N01',
    value: 1599.00,
    currency: 'UAH',
    items: [...]
  },
  user_data: {
    email: 'user@example.com',
    phone_number: '+380501234567',
    first_name: 'Іван',
    last_name: 'Петренко',
    address: { city: 'Київ' }
  }
});
```

### **2. Lead Event (Заявка без оплаты)**

#### Facebook Pixel:
```javascript
fbq('track', 'Lead', {
  value: 1599.00,              // Предполагаемая сумма заказа
  currency: 'UAH',
  content_name: 'Order TWC30102025N01',
  content_category: 'order_lead'
}, {
  // Advanced Matching
  em: 'user@example.com',
  ph: '380501234567',
  fn: 'іван',
  ln: 'петренко',
  ct: 'київ'
});
```

#### Google Tag Manager:
```javascript
dataLayer.push({
  event: 'lead',
  lead_data: {
    order_id: 'TWC30102025N01',
    value: 1599.00,
    currency: 'UAH',
    payment_status: 'unpaid'
  },
  user_data: {
    email: 'user@example.com',
    phone_number: '+380501234567',
    first_name: 'Іван',
    last_name: 'Петренко',
    address: { city: 'Київ' }
  }
});
```

---

## 🔧 ЧТО НУЖНО НАСТРОИТЬ В GTM

### **Шаг 1: Создать новый триггер для Lead**

1. Откройте GTM → **Triggers** → **New**
2. **Name:** `Lead Event`
3. **Trigger Type:** Custom Event
4. **Event name:** `lead`
5. **Save**

### **Шаг 2: Создать Data Layer Variables для Lead**

Создайте 4 новые переменные:

#### Переменная 1:
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Lead Order ID`
- **Data Layer Variable Name:** `lead_data.order_id`

#### Переменная 2:
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Lead Value`
- **Data Layer Variable Name:** `lead_data.value`

#### Переменная 3:
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Lead Payment Status`
- **Data Layer Variable Name:** `lead_data.payment_status`

#### Переменная 4:
- **Variable Type:** Data Layer Variable
- **Variable Name:** `DLV - Lead Currency`
- **Data Layer Variable Name:** `lead_data.currency`

### **Шаг 3: Настроить Google Ads Lead Conversion Tag** (если нужно)

1. **Tag Type:** Google Ads Conversion Tracking
2. **Conversion ID:** (ваш Lead Conversion ID)
3. **Conversion Label:** (ваш Lead Label)
4. **Conversion Value:** `{{DLV - Lead Value}}`
5. **Currency Code:** `{{DLV - Lead Currency}}`
6. **Order ID:** `{{DLV - Lead Order ID}}`
7. **Enhanced Conversions:**
   - Email: `{{DLV - User Email}}`
   - Phone: `{{DLV - User Phone}}`
   - First Name: `{{DLV - User First Name}}`
   - Last Name: `{{DLV - User Last Name}}`
   - City: `{{DLV - User City}}`
8. **Trigger:** `Lead Event`
9. **Save** and **Publish**

### **Шаг 4: Настроить Meta (Facebook) Conversions API (опционально)**

Если используете Conversions API (рекомендуется для надежности):

1. В GTM создайте **Tag** → **Custom HTML**
2. Отправляйте Lead и Purchase события на ваш backend
3. Backend отправляет события в Meta Conversions API

---

## 🎨 ИЗМЕНЕНИЯ В UI (Текст страницы)

Теперь страница `order_success.html` показывает **разный текст** в зависимости от статуса оплаты:

### **Для оплаченных заказов (`payment_status == 'paid'`):**
```html
<h3>✅ Оплата успішно пройшла!</h3>
<p>Дякуємо за покупку! Ваше замовлення оплачено через Monobank та відправлено в обробку.</p>
```

### **Для неоплаченных заказов (`payment_status != 'paid'`):**
```html
<h3>Ваша заявка відправлена в обробку</h3>
<p>Менеджер зв'яжеться з вами найближчим часом для підтвердження замовлення.</p>
```

---

## 📋 КАК ПРОВЕРИТЬ ЧТО ВСЕ РАБОТАЕТ

### **Тест 1: Заявка без оплаты (Lead)**

1. Откройте сайт в режиме инкогнито
2. Откройте **Chrome DevTools** → **Console**
3. Оформите заказ **БЕЗ оплаты**
4. На странице успеха проверьте консоль:

**Должно быть:**
```
📋 GTM Lead event sent (UNPAID): {event: "lead", lead_data: {...}, user_data: {...}}
📋 Meta Pixel Lead event sent (UNPAID) with Advanced Matching: {em: "...", ph: "..."}
```

5. Откройте **Facebook Events Manager** → **Test Events**
6. Проверьте что пришло событие **Lead** (не Purchase!)

### **Тест 2: Покупка с оплатой (Purchase)**

1. Откройте сайт в режиме инкогнито
2. Откройте **Chrome DevTools** → **Console**
3. Оформите заказ и **ОПЛАТИТЕ через MonoPay**
4. После редиректа на страницу успеха проверьте консоль:

**Должно быть:**
```
✅ GTM Purchase event sent (PAID): {event: "purchase", ecommerce: {...}, user_data: {...}}
✅ Meta Pixel Purchase event sent (PAID) with Advanced Matching: {em: "...", ph: "..."}
```

5. Откройте **Facebook Events Manager** → **Test Events**
6. Проверьте что пришло событие **Purchase** (не Lead!)

### **Тест 3: Проверка в GTM Preview Mode**

1. В GTM нажмите **Preview**
2. Введите URL сайта
3. Оформите заявку (без оплаты)
4. Проверьте что сработал триггер `Lead Event`
5. Оформите заказ с оплатой
6. Проверьте что сработал триггер `purchase`

---

## 🚀 ПРЕИМУЩЕСТВА НОВОГО ПОДХОДА

### **1. Точная атрибуция**
- ✅ Lead события теперь отслеживаются отдельно
- ✅ Purchase события только для оплаченных заказов
- ✅ Можно оптимизировать рекламу по разным целям

### **2. Правильный ROAS**
- ✅ ROAS считается только по реальным покупкам
- ✅ Не искажается заявками без оплаты

### **3. Advanced Matching**
- ✅ Для обоих событий передаются данные пользователя
- ✅ Улучшенная атрибуция и ретаргетинг

### **4. Защита от дублирования**
- ✅ События отправляются только 1 раз за сессию
- ✅ Разные ключи в sessionStorage для Lead и Purchase

---

## 📊 СТАТУСЫ ОПЛАТЫ

Ваша система использует следующие статусы (`Order.payment_status`):

| Статус | Описание | Событие |
|--------|----------|---------|
| `unpaid` | Не оплачено | **Lead** 📋 |
| `checking` | На проверке | **Lead** 📋 |
| `partial` | Частичная оплата | **Lead** 📋 |
| `paid` | Оплачено полностью | **Purchase** ✅ |

---

## 🔄 ПОТОК ОПЛАТЫ

### **Вариант A: Заявка (Lead)**
```
1. Пользователь оформляет заказ
   ↓
2. create_order() создает Order с payment_status='unpaid'
   ↓
3. Редирект на order_success
   ↓
4. JavaScript проверяет payment_status != 'paid'
   ↓
5. Отправляет fbq('track', 'Lead') ✅
```

### **Вариант B: Покупка (Purchase)**
```
1. Пользователь оформляет заказ
   ↓
2. create_order() создает Order с payment_status='unpaid'
   ↓
3. Пользователь выбирает оплату картой
   ↓
4. Редирект на MonoPay
   ↓
5. MonoPay обрабатывает платеж
   ↓
6. MonoPay отправляет webhook на сервер
   ↓
7. Webhook обновляет payment_status='paid'
   ↓
8. Редирект на order_success через payment_callback
   ↓
9. JavaScript проверяет payment_status == 'paid'
   ↓
10. Отправляет fbq('track', 'Purchase') ✅
```

---

## 💡 РЕКОМЕНДАЦИИ

### **1. Создайте отдельные кампании в Facebook Ads**

#### Кампания на Lead (Заявки):
- **Цель:** Lead Generation
- **Оптимизация:** Lead
- **Ставка:** Ниже, чем для Purchase
- **Аудитория:** Широкая (холодный трафик)

#### Кампания на Purchase (Покупки):
- **Цель:** Conversions
- **Оптимизация:** Purchase
- **Ставка:** Выше, чем для Lead
- **Аудитория:** Теплая (ретаргетинг Lead, Lookalike)

### **2. Настройте воронку в Facebook Analytics**

```
Lead → (менеджер звонит) → Purchase
```

Это позволит видеть:
- Конверсию Lead → Purchase
- Среднее время от Lead до Purchase
- % отказов на этапе звонка менеджера

### **3. Оптимизируйте процесс звонков**

Если конверсия Lead → Purchase низкая:
- Ускорьте обработку заявок
- Обучите менеджеров продажам
- Добавьте автоматические SMS-уведомления
- Внедрите CRM для трекинга Lead

### **4. Используйте автоматизацию**

Настройте в Facebook Ads:
- **Custom Audience:** Люди с Lead событием (но без Purchase)
- **Retargeting:** Показывайте рекламу с скидкой для завершения покупки
- **Lookalike:** Создайте Lookalike от людей с Purchase (не Lead!)

### **5. Мониторинг и A/B тесты**

Регулярно проверяйте:
- Соотношение Lead / Purchase
- Средний чек Lead vs Purchase
- ROAS для каждого типа конверсии
- Качество трафика по источникам

---

## 📝 ИТОГО

### **Что было исправлено:**

1. ✅ Добавлена проверка `payment_status` в JavaScript
2. ✅ Разделена логика отправки Lead vs Purchase
3. ✅ Изменен текст страницы в зависимости от статуса
4. ✅ Добавлен новый GTM event `lead`
5. ✅ Сохранены все Advanced Matching данные для обоих событий

### **Что нужно сделать вручную:**

1. ⚠️ Настроить GTM триггер `Lead Event`
2. ⚠️ Создать Data Layer Variables для Lead
3. ⚠️ Настроить Google Ads Lead Conversion (если нужно)
4. ⚠️ Протестировать оба сценария
5. ⚠️ Создать отдельные кампании в Facebook Ads

### **Время на настройку:**

- ✅ **Код исправлен:** ГОТОВО
- ⏱️ **GTM настройка:** 15-20 минут
- ⏱️ **Тестирование:** 10 минут
- ⏱️ **Настройка кампаний:** 30-60 минут

**Общее время:** ~1-1.5 часа

---

## 🎯 РЕЗУЛЬТАТ

После внедрения вы сможете:

1. ✅ Видеть реальное количество Lead и Purchase
2. ✅ Рассчитывать правильный ROAS
3. ✅ Оптимизировать рекламу по разным целям
4. ✅ Анализировать воронку Lead → Purchase
5. ✅ Улучшать конверсию на каждом этапе

**Facebook Pixel теперь работает правильно! 🎉**

---

**Автор:** AI Assistant  
**Дата:** 30 октября 2025  
**Версия:** 1.0  
**Статус:** ✅ Готово к деплою

