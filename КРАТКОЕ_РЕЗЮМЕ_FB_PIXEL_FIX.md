# 🎯 КРАТКОЕ РЕЗЮМЕ: Исправление Facebook Pixel

## ✅ ЧТО ИСПРАВЛЕНО

Ваш Facebook Pixel **НЕ РАЗЛИЧАЛ** два разных сценария:

1. **Заявка** - пользователь оформил заказ, но НЕ оплатил (менеджер должен позвонить)
2. **Покупка** - пользователь оформил заказ И ОПЛАТИЛ через MonoPay/Mono Checkout

Оба сценария отправляли событие `Purchase`, что **искажало статистику** и **ROAS**.

---

## 🔧 РЕШЕНИЕ

Теперь код **проверяет статус оплаты** (`order.payment_status`):

### **Если НЕ оплачено** (`unpaid`, `checking`, `partial`):
- ✅ Отправляет `fbq('track', 'Lead')` в Facebook Pixel
- ✅ Отправляет `event: 'lead'` в Google Tag Manager
- ✅ Показывает текст: *"Ваша заявка відправлена в обробку. Менеджер зв'яжеться"*

### **Если ОПЛАЧЕНО** (`paid`):
- ✅ Отправляет `fbq('track', 'Purchase')` в Facebook Pixel
- ✅ Отправляет `event: 'purchase'` в Google Tag Manager
- ✅ Показывает текст: *"✅ Оплата успішно пройшла! Оплачено через Monobank"*

---

## 📋 ЧТО НУЖНО СДЕЛАТЬ ВРУЧНУЮ

### **В Google Tag Manager (15-20 минут):**

1. **Создать триггер:**
   - Name: `Lead Event`
   - Type: Custom Event
   - Event name: `lead`

2. **Создать 4 переменные:**
   - `DLV - Lead Order ID` → `lead_data.order_id`
   - `DLV - Lead Value` → `lead_data.value`
   - `DLV - Lead Payment Status` → `lead_data.payment_status`
   - `DLV - Lead Currency` → `lead_data.currency`

3. **Создать Google Ads Lead Conversion Tag** (если нужно):
   - Trigger: `Lead Event`
   - Value: `{{DLV - Lead Value}}`
   - Enhanced Conversions: да

4. **Publish** изменения

### **В Facebook Ads (30-60 минут):**

1. **Создать две отдельные кампании:**
   - **Кампания A:** Оптимизация на Lead (заявки)
   - **Кампания B:** Оптимизация на Purchase (покупки)

2. **Настроить воронку:**
   - Custom Audience: Lead без Purchase
   - Ретаргетинг с скидкой для завершения покупки
   - Lookalike от людей с Purchase

---

## 🧪 КАК ПРОТЕСТИРОВАТЬ

### **Тест 1: Заявка (Lead)**
1. Оформите заказ БЕЗ оплаты
2. На странице успеха откройте консоль браузера (F12)
3. Должно быть:
   ```
   📋 GTM Lead event sent (UNPAID): {...}
   📋 Meta Pixel Lead event sent (UNPAID) with Advanced Matching: {...}
   ```
4. В Facebook Events Manager → Test Events проверьте событие **Lead**

### **Тест 2: Покупка (Purchase)**
1. Оформите заказ И оплатите через MonoPay
2. После оплаты откройте консоль браузера
3. Должно быть:
   ```
   ✅ GTM Purchase event sent (PAID): {...}
   ✅ Meta Pixel Purchase event sent (PAID) with Advanced Matching: {...}
   ```
4. В Facebook Events Manager → Test Events проверьте событие **Purchase**

---

## 📊 РЕЗУЛЬТАТ

### **До исправления:**
- ❌ Все заказы = Purchase
- ❌ ROAS завышен
- ❌ Невозможно оптимизировать по Lead

### **После исправления:**
- ✅ Lead и Purchase отдельно
- ✅ ROAS точный
- ✅ Можно создать воронку Lead → Purchase
- ✅ Можно оптимизировать каждый этап

---

## 🚀 ДЕПЛОЙ

Изменения внесены в файл:
```
/twocomms/twocomms_django_theme/templates/pages/order_success.html
```

**Деплой на сервер:**
```bash
cd /Users/zainllw0w/PycharmProjects/TwoComms
git add twocomms/twocomms_django_theme/templates/pages/order_success.html
git commit -m "Fix: Разделение Lead и Purchase событий в Facebook Pixel"
git push
```

**SSH деплой:**
```bash
sshpass -p '${TWC_SSH_PASS}' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull && sudo systemctl restart twocomms'"
```

---

## 📖 ПОЛНАЯ ДОКУМЕНТАЦИЯ

Смотрите файл:
```
FACEBOOK_PIXEL_LEAD_VS_PURCHASE_FIX.md
```

Там подробно описано:
- Техническая реализация
- Настройка GTM
- Настройка Facebook Ads
- Тестирование
- Рекомендации по оптимизации

---

**Время внедрения:** ~1-1.5 часа  
**Статус:** ✅ Готово к деплою  
**Приоритет:** 🔴 ВЫСОКИЙ (влияет на статистику и ROAS)

