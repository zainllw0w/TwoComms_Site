# 📘 ИНСТРУКЦИЯ: Настройка Facebook Conversions API

**Дата:** 30 октября 2025  
**Цель:** Автоматическая отправка Purchase событий когда пользователь получает заказ через Новую Почту

---

## 🎯 ЧТО ТАКОЕ CONVERSIONS API

**Facebook Conversions API** - это серверный способ отправки событий в Facebook напрямую с вашего сервера.

### **Преимущества:**
✅ Работает без браузера пользователя  
✅ Не блокируется AdBlock  
✅ Надежнее чем JavaScript Pixel  
✅ Дополняет browser Pixel (дедупликация)  
✅ Официально рекомендуется Facebook  

### **Когда используется в вашем проекте:**
- Когда Новая Почта обновляет статус → "Отримано"
- Cron job (каждые 5 минут) проверяет статусы
- Автоматически отправляет Purchase событие в Facebook

---

## 📋 ЧТО ВАМ ПОНАДОБИТСЯ

Для настройки Conversions API нужно получить:

1. **Pixel ID** - у вас уже есть: `823958313630148`
2. **Access Token** - нужно получить (инструкция ниже)
3. **Test Event Code** - для тестирования (опционально)

---

## 🔑 ШАГ 1: ПОЛУЧЕНИЕ ACCESS TOKEN

### **1.1. Откройте Events Manager**

Перейдите: https://business.facebook.com/events_manager2/

Выберите ваш Pixel: **823958313630148**

### **1.2. Перейдите в Settings**

```
Events Manager → Выберите Pixel (823958313630148) → Settings (Налаштування)
```

### **1.3. Найдите раздел "Conversions API"**

Прокрутите вниз до раздела:
```
🔧 Conversions API
```

### **1.4. Нажмите "Generate Access Token"**

```
┌────────────────────────────────────────────────────────┐
│  Conversions API                                       │
├────────────────────────────────────────────────────────┤
│                                                         │
│  Access Token: (not set)                               │
│                                                         │
│  [Generate Access Token]                               │
│                                                         │
└────────────────────────────────────────────────────────┘
```

Нажмите кнопку **"Generate Access Token"**

### **1.5. Скопируйте Token**

Появится окно с токеном:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Your Access Token                                  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                      ┃
┃  EAABsbCS1iHgBO7ZCxvqL9kZAw...                      ┃
┃  (длинная строка ~200 символов)                    ┃
┃                                                      ┃
┃  ⚠️ ВАЖНО: Сохраните этот токен в безопасном месте  ┃
┃  Он больше не будет показан                         ┃
┃                                                      ┃
┃  [Copy]                                              ┃
┃                                                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Нажмите "Copy"** - токен скопирован в буфер обмена.

⚠️ **ВАЖНО:** Сохраните токен - он НЕ будет показан повторно!

---

## 🌍 ШАГ 2: ДОБАВЛЕНИЕ TOKEN В .ENV

### **2.1. На локальной машине**

Откройте файл `.env` (если нет - создайте):
```bash
nano /Users/zainllw0w/PycharmProjects/TwoComms/twocomms/.env
```

Добавьте строку:
```bash
# Facebook Conversions API
FACEBOOK_PIXEL_ID=823958313630148
FACEBOOK_CONVERSIONS_API_TOKEN=EAABsbCS1iHgBO7ZCxvqL9kZAw...
```

(замените `EAABsbCS1iHgBO7ZCxvqL9kZAw...` на ваш реальный токен)

### **2.2. На продакшн сервере**

Подключитесь к серверу:
```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169
```

Откройте `.env`:
```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
nano .env
```

Добавьте те же строки:
```bash
FACEBOOK_PIXEL_ID=823958313630148
FACEBOOK_CONVERSIONS_API_TOKEN=EAABsbCS1iHgBO7ZCxvqL9kZAw...
```

Сохраните: `Ctrl+X` → `Y` → `Enter`

Перезапустите приложение:
```bash
touch tmp/restart.txt
```

---

## 🧪 ШАГ 3: ТЕСТИРОВАНИЕ CONVERSIONS API

### **3.1. Получите Test Event Code (опционально)**

В Events Manager → Settings → Conversions API:
```
Test Events: [Create Test Event Code]
```

Код будет выглядеть как: `TEST12345`

### **3.2. Отправьте тестовое событие**

На сервере выполните:
```bash
python manage.py shell
```

Введите:
```python
from orders.facebook_conversions import FacebookConversionsAPI
from orders.models import Order

# Получите любой оплаченный заказ
order = Order.objects.filter(payment_status='paid').first()

# Отправьте тестовое событие
fb_api = FacebookConversionsAPI(test_event_code='TEST12345')
result = fb_api.send_purchase_event(order)

print(result)
```

### **3.3. Проверьте в Events Manager**

Перейдите: **Events Manager → Test Events**

Должно появиться событие:
```
✅ Purchase
   Source: Server (Conversions API)
   Value: 1500 UAH
   Test Event: TEST12345
```

Если событие появилось - **настройка успешна!** 🎉

---

## 📊 ШАГ 4: ПРОВЕРКА РАБОТЫ В PRODUCTION

### **4.1. Создайте тестовый заказ**

1. Оформите заказ с передплатой 200 грн
2. Оплатите через MonoPay
3. Менеджер создает ТТН в Новой Почте
4. Дождитесь статуса "Отримано" (или измените вручную в админке)

### **4.2. Проверьте логи**

На сервере:
```bash
tail -f /var/log/twocomms/conversions_api.log
```

Должно быть:
```
[2025-10-30 15:30:00] Purchase event sent for order TWC30102025N01
[2025-10-30 15:30:00] Facebook response: {"events_received": 1, "fbtrace_id": "..."}
```

### **4.3. Проверьте в Events Manager**

Events Manager → Overview → должны появиться события:
```
📊 Последние 24 часа:
   Server (Conversions API): 5 событий
   Browser (Pixel): 12 событий
```

---

## 🔄 ШАГ 5: ДЕДУПЛИКАЦИЯ (ВАЖНО!)

Facebook может получить одно и то же событие дважды:
1. Из браузера (JavaScript Pixel)
2. С сервера (Conversions API)

Для дедупликации используется **event_id**.

### **Как это работает:**

**JavaScript Pixel** (в браузере):
```javascript
fbq('track', 'Purchase', {
  value: 1500,
  currency: 'UAH'
}, {
  eventID: 'order_TWC30102025N01_purchase'  // ← уникальный ID
});
```

**Conversions API** (с сервера):
```python
{
  "event_name": "Purchase",
  "event_id": "order_TWC30102025N01_purchase",  # ← тот же ID
  "event_time": 1698675000,
  ...
}
```

Facebook видит одинаковый `event_id` → считает как **одно событие**.

**В нашей реализации это уже настроено! ✅**

---

## 📈 ШАГ 6: МОНИТОРИНГ И ОПТИМИЗАЦИЯ

### **6.1. Event Match Quality**

Events Manager → Data Sources → Pixel → **Event Match Quality**

Показывает качество данных:
```
Event Match Quality: 8.2 / 10  ✅ Хорошо
```

Чем выше - тем лучше атрибуция.

### **6.2. Улучшение Quality Score**

Передавайте больше данных:
- ✅ Email (у вас есть для авторизованных)
- ✅ Phone (у вас есть)
- ✅ First Name, Last Name (у вас есть)
- ✅ City (у вас есть)
- 🔲 ZIP Code (можно добавить)
- 🔲 IP Address (можно добавить)
- 🔲 User Agent (можно добавить)

### **6.3. Проверка ошибок**

Events Manager → Diagnostics → **Data Quality Issues**

Если есть ошибки - они будут показаны здесь.

---

## ⚙️ ШАГ 7: НАСТРОЙКА CRON JOB

### **7.1. Создайте cron task**

На сервере:
```bash
crontab -e
```

Добавьте строку (проверка каждые 5 минут):
```bash
*/5 * * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py update_tracking_statuses >> /var/log/twocomms/np_cron.log 2>&1
```

Сохраните: `Ctrl+X` → `Y` → `Enter`

### **7.2. Проверьте что cron работает**

Подождите 5 минут, затем:
```bash
tail -f /var/log/twocomms/np_cron.log
```

Должно быть:
```
[2025-10-30 15:35:00] Checking 15 orders...
[2025-10-30 15:35:01] Order TWC30102025N01: status updated
[2025-10-30 15:35:01] Purchase event sent to Facebook
```

---

## 🔐 БЕЗОПАСНОСТЬ

### **⚠️ НЕ ДЕЛАЙТЕ:**

❌ НЕ коммитьте токен в Git  
❌ НЕ показывайте токен в логах  
❌ НЕ делитесь токеном с другими  

### **✅ ДЕЛАЙТЕ:**

✅ Храните токен в `.env`  
✅ Добавьте `.env` в `.gitignore`  
✅ Используйте environment variables  
✅ Регулярно обновляйте токен (раз в год)  

---

## 📋 CHECKLIST: ЧТО НАСТРОИТЬ

- [ ] 1. Получить Access Token в Events Manager
- [ ] 2. Добавить token в `.env` (локально)
- [ ] 3. Добавить token в `.env` (на сервере)
- [ ] 4. Перезапустить приложение
- [ ] 5. Протестировать с Test Event Code
- [ ] 6. Проверить в Events Manager что событие пришло
- [ ] 7. Настроить cron job для НП
- [ ] 8. Протестировать на реальном заказе
- [ ] 9. Проверить Event Match Quality (должно быть > 7)
- [ ] 10. Мониторить ошибки в Diagnostics

---

## 🆘 TROUBLESHOOTING

### **Проблема: События не приходят**

**Проверьте:**
1. Токен правильный в `.env`
2. Pixel ID правильный
3. Нет ошибок в логах: `tail -f /var/log/twocomms/conversions_api.log`
4. Cron job запускается: `tail -f /var/log/twocomms/np_cron.log`

### **Проблема: Event Match Quality низкий**

**Решение:**
- Добавьте больше user data (email, phone, name)
- Хешируйте данные (SHA256) перед отправкой
- Используйте правильный формат телефонов (+380...)

### **Проблема: Дубликаты событий**

**Решение:**
- Используйте одинаковый `event_id` для Pixel и API
- Формат: `order_{order_number}_purchase`
- Facebook автоматически дедуплицирует

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

### **Официальная документация:**
- Conversions API: https://developers.facebook.com/docs/marketing-api/conversions-api/
- Event Reference: https://developers.facebook.com/docs/meta-pixel/reference
- Best Practices: https://www.facebook.com/business/help/308855623112583

### **Python SDK:**
- GitHub: https://github.com/facebook/facebook-python-business-sdk
- Docs: https://facebook-business-sdk.readthedocs.io/

### **Полезные инструменты:**
- Event Manager: https://business.facebook.com/events_manager2/
- Pixel Helper (Chrome Extension): проверка Pixel в браузере
- Test Events: тестирование без влияния на статистику

---

## ✅ ИТОГО

После настройки у вас будет:

1. ✅ **Двойная отправка событий:**
   - Browser (JavaScript Pixel) - для онлайн оплаты
   - Server (Conversions API) - для автоматических обновлений

2. ✅ **Автоматический Purchase:**
   - Когда клиент получает товар через НП
   - Отправляется с сервера без участия пользователя

3. ✅ **Надежная аналитика:**
   - Не блокируется AdBlock
   - Дедупликация событий
   - Высокий Event Match Quality

4. ✅ **Правильный ROAS:**
   - Purchase только когда товар получен
   - Честная статистика конверсий

---

**После настройки напишите мне - я помогу проверить что все работает правильно!** 🚀

---

**Автор:** AI Assistant  
**Дата:** 30 октября 2025  
**Версия:** 1.0  
**Статус:** ✅ Готово к использованию

