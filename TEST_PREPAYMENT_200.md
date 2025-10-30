# 🧪 ТЕСТИРОВАНИЕ ПРЕДОПЛАТЫ 200 ГРН

## ✅ ЧТО БЫЛО ИСПРАВЛЕНО:

### 1. JavaScript (main.js)
**Изменено:** Default значение с `'full'` на `'online_full'` (3 места)
```javascript
// БЫЛО:
pay_type: getAnyVal('pay_type') || 'full'

// СТАЛО:
pay_type: getAnyVal('pay_type') || 'online_full'
```

### 2. Backend (monobank.py)
**Добавлено:** Подробное логирование для отладки:
```python
monobank_logger.info(f'Request body: {body}')
monobank_logger.info(f'pay_type from body: {body.get("pay_type")}')
monobank_logger.info(f'Auth user: pay_type from body={body.get("pay_type")}, from profile={prof.pay_type}, final={pay_type}')
```

---

## 🧪 КАК ТЕСТИРОВАТЬ:

### Шаг 1: Очистите кеш браузера
**ОБЯЗАТЕЛЬНО!** Без этого будет старая версия JavaScript!

**Chrome/Edge:**
1. `Ctrl+Shift+Delete` (Windows) или `Cmd+Shift+Delete` (Mac)
2. Выберите "Изображения и другие файлы, сохраненные в кеше"
3. Нажмите "Удалить данные"
4. Перезагрузите страницу с `Ctrl+F5`

**Firefox:**
1. `Ctrl+Shift+Delete`
2. Выберите "Кеш"
3. Нажмите "Удалить сейчас"
4. Перезагрузите с `Ctrl+F5`

### Шаг 2: Откройте консоль браузера (F12)
Перейдите на вкладку "Network" чтобы видеть запросы

### Шаг 3: Тест предоплаты
1. Откройте https://twocomms.shop/cart/
2. Добавьте товары (например на 500 грн)
3. Выберите в селекте **"Передплата 200 грн"**
4. Нажмите кнопку **"Внести передплату 200 грн"**
5. В Network найдите запрос к `/cart/monobank/create-invoice/`
6. Посмотрите:
   - **Request Payload:** должен содержать `"pay_type": "prepay_200"`
   - **Response:** должен содержать `"invoice_url": "https://pay.mbnk.biz/..."`
7. **ОЖИДАЕТСЯ:** Перенаправление на MonoPay с суммой **200 грн**
8. **ОЖИДАЕТСЯ:** Название товара **"Передплата за замовлення TWC..."**

### Шаг 4: Тест полной оплаты
1. Откройте https://twocomms.shop/cart/
2. Добавьте товары (например на 500 грн)
3. Выберите в селекте **"Онлайн оплата (повна сума)"**
4. Нажмите кнопку **"Перейти до оплати"**
5. В Network найдите запрос к `/cart/monobank/create-invoice/`
6. Посмотрите:
   - **Request Payload:** должен содержать `"pay_type": "online_full"`
   - **Response:** должен содержать `"invoice_url": "..."`
7. **ОЖИДАЕТСЯ:** Перенаправление на MonoPay с суммой **500 грн (полная)**
8. **ОЖИДАЕТСЯ:** Названия реальных товаров в инвойсе

---

## 📊 ПРОВЕРКА ЛОГОВ НА СЕРВЕРЕ:

Если MonoPay показывает неправильную сумму, проверьте логи:

```bash
# Подключитесь к серверу
sshpass -p '[REDACTED_SSH_PASSWORD]' ssh qlknpodo@195.191.24.169

# Смотрите логи в реальном времени
tail -f ~/logs/django.log | grep -E "monobank_create_invoice|pay_type|Payment amount"

# Или последние 100 строк
tail -100 ~/logs/django.log | grep -E "pay_type|Payment amount"
```

**Что искать в логах:**

### Для предоплаты 200 грн:
```
Request body: {'full_name': 'Иван Иванов', 'phone': '+380...', 'pay_type': 'prepay_200', ...}
pay_type from body: prepay_200
Auth user: pay_type from body=prepay_200, from profile=online_full, final=prepay_200
Customer data: full_name=Иван Иванов, pay_type=prepay_200
Payment amount: 200 (pay_type=prepay_200)  ← ВАЖНО! Должно быть 200!
Order created: TWC30102025N01 (ID: 123)
✅ Invoice created successfully: https://pay.mbnk.biz/...
```

### Для полной оплаты:
```
Request body: {'full_name': 'Иван Иванов', 'phone': '+380...', 'pay_type': 'online_full', ...}
pay_type from body: online_full
Auth user: pay_type from body=online_full, from profile=online_full, final=online_full
Customer data: full_name=Иван Иванов, pay_type=online_full
Payment amount: 500 (pay_type=online_full)  ← Полная сумма товаров
Order created: TWC30102025N02 (ID: 124)
✅ Invoice created successfully: https://pay.mbnk.biz/...
```

---

## ❌ ЕСЛИ НЕ РАБОТАЕТ:

### Проблема 1: pay_type в логах = `None` или `online_full` вместо `prepay_200`
**Причина:** JavaScript не отправляет правильный pay_type  
**Решение:** 
1. Очистите кеш браузера
2. Проверьте что в селекте выбрано именно `prepay_200`
3. В консоли браузера (F12) проверьте Request Payload

### Проблема 2: Сумма в MonoPay не 200 грн
**Причина:** Backend получает неправильный pay_type  
**Решение:**
1. Проверьте логи (см. выше)
2. Найдите строку `Payment amount: XXX (pay_type=YYY)`
3. Если pay_type != `prepay_200` - проблема в JavaScript
4. Отправьте скриншот консоли браузера (Network tab)

### Проблема 3: Ошибка 500
**Причина:** Проблема на сервере  
**Решение:**
1. Проверьте логи: `tail -100 ~/logs/django.log`
2. Найдите traceback ошибки
3. Отправьте полный текст ошибки

---

## ✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:

### Предоплата 200 грн:
- ✅ Выбираете "Передплата 200 грн" в селекте
- ✅ Нажимаете "Внести передплату 200 грн"
- ✅ Открывается MonoPay с **суммой 200 грн**
- ✅ Название товара: **"Передплата за замовлення TWC30102025N01"**
- ✅ После оплаты: payment_status = 'prepaid'
- ✅ Facebook Pixel → Lead событие

### Полная оплата:
- ✅ Выбираете "Онлайн оплата (повна сума)" в селекте
- ✅ Нажимаете "Перейти до оплати"
- ✅ Открывается MonoPay с **полной суммой** (например 500 грн)
- ✅ Названия товаров: **"Футболка S", "Штани M"** (реальные товары)
- ✅ После оплаты: payment_status = 'paid'
- ✅ Facebook Pixel → Purchase событие

---

## 📝 ОТПРАВЬТЕ МНЕ:

Если не работает, отправьте:
1. **Скриншот консоли браузера** (F12 → Network → запрос create-invoice)
2. **Логи с сервера** (tail -100 ~/logs/django.log | grep pay_type)
3. **Какую сумму показывает MonoPay** (200 или другую?)

---

**Сервер перезапущен, изменения применены. Тестируйте!** 🚀

