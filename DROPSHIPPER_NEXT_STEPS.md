# 🚀 ДРОПШИППИНГ: СЛЕДУЮЩИЕ ШАГИ

**Дата:** 2025-10-21  
**Текущая версия:** v109

---

## ✅ ЧТО УЖЕ ГОТОВО

### 1. Модальное окно добавления товара (v109)
- ✅ Сворачиваемое описание
- ✅ Красивые цены (градиенты, диапазон)
- ✅ **Автообновление счетчика заказов** (исправлено в v109)
- ✅ Центрирование модального окна

### 2. Список заказов
- ✅ Красивые карточки с градиентами
- ✅ Цветовая кодировка статусов
- ✅ Отображение TTN
- ✅ Кнопка "Підтвердити" для дропшиппера

### 3. Статусы заказов
- ✅ `draft` - Чернетка
- ✅ `pending` - Очікує підтвердження
- ✅ `confirmed` - Підтверджено
- ✅ `processing` - В обробці
- ✅ `shipped` - Відправлено
- ✅ `delivered` - Доставлено
- ✅ `cancelled` - Скасовано

---

## 📋 ЧТО ОСТАЛОСЬ СДЕЛАТЬ

### ПРИОРИТЕТ 1: Telegram уведомления

#### 1.1. При создании заказа (draft)
**Событие:** Дропшиппер создает заказ  
**Кому:** Дропшипперу  
**Сообщение:**
```
🎉 Замовлення створено!

📦 Номер: #DS-12345
👤 Клієнт: Іванов Іван
📞 Телефон: +380501234567
💰 Сума: 1500 грн
💵 Прибуток: 300 грн

⚠️ Не забудьте підтвердити замовлення!

[Підтвердити замовлення]
```

#### 1.2. При подтверждении дропшиппером (draft → pending)
**Событие:** Дропшиппер нажимает "Підтвердити"  
**Кому:** **АДМИНУ В TELEGRAM**  
**Сообщение:**
```
🔔 НОВЕ ЗАМОВЛЕННЯ ВІД ДРОПШИПЕРА!

📦 Номер: #DS-12345
👤 Дропшипер: @username (ФОП Синило)
📱 Телефон дропшипера: +380939693920

👥 КЛІЄНТ:
Ім'я: Іванов Іван
Телефон: +380501234567
Адреса: Київ, відділення №5

🛒 ТОВАРИ:
• Худі "Команда Сірко" x 1 (розмір M)
  Ціна дропа: 1350 грн
  Ціна продажу: 1650 грн

💰 ФІНАНСИ:
Сума продажу: 1650 грн
Собівартість: 1350 грн
Прибуток дропшипера: 300 грн

📝 Примітки: [якщо є]
🔗 Джерело: [якщо є]

[✅ Підтвердити] [❌ Скасувати] [📝 Переглянути]
```

#### 1.3. При изменении статуса админом
**Событие:** Админ меняет статус в админ-панели  
**Кому:** Дропшипперу  
**Сообщение:**
```
📬 Статус замовлення оновлено!

📦 #DS-12345
🔄 Новий статус: Підтверджено
👤 Клієнт: Іванов Іван

[Переглянути замовлення]
```

#### 1.4. При добавлении TTN
**Событие:** Админ добавляет TTN  
**Кому:** Дропшипперу  
**Сообщение:**
```
🚚 Замовлення відправлено!

📦 #DS-12345
👤 Клієнт: Іванов Іван
📮 TTN: 59001234567890

🔍 Відстежити посилку:
https://novaposhta.ua/tracking/?cargo_number=59001234567890

[Переглянути замовлення]
```

---

### ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ

#### 1. `twocomms/orders/telegram_notifications.py`
Добавить функции:
```python
async def send_order_created_notification(order):
    """Уведомление дропшипперу о создании заказа"""
    pass

async def send_order_pending_admin_notification(order):
    """ВАЖНО: Уведомление админу о новом подтвержденном заказе"""
    pass

async def send_order_status_changed_notification(order, old_status, new_status):
    """Уведомление дропшипперу о смене статуса"""
    pass

async def send_order_ttn_added_notification(order):
    """Уведомление дропшипперу о добавлении TTN"""
    pass
```

#### 2. `twocomms/orders/signals.py`
Добавить сигналы:
```python
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import DropshipperOrder

@receiver(post_save, sender=DropshipperOrder)
def order_created_handler(sender, instance, created, **kwargs):
    if created:
        # Отправить уведомление дропшипперу
        pass

@receiver(pre_save, sender=DropshipperOrder)
def order_status_changed_handler(sender, instance, **kwargs):
    if instance.pk:
        old_instance = DropshipperOrder.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            # Отправить уведомление о смене статуса
            
            # ВАЖНО: Если draft → pending, отправить АДМИНУ!
            if old_instance.status == 'draft' and instance.status == 'pending':
                # Отправить АДМИНУ в Telegram
                pass
```

#### 3. `twocomms/orders/dropshipper_views.py`
В функции `dropshipper_add_to_cart`:
```python
# После создания заказа
if data.get('status') == 'pending':
    # Отправить уведомление админу
    asyncio.run(send_order_pending_admin_notification(order))
```

---

### ПРИОРИТЕТ 2: Админ-панель

#### 2.1. Django Admin
В `twocomms/orders/admin.py` добавить:
```python
from django.contrib import admin
from .models import DropshipperOrder, DropshipperOrderItem

@admin.register(DropshipperOrder)
class DropshipperOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'dropshipper', 'client_name', 'status', 'total_selling_price', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'client_name', 'client_phone']
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('order_number', 'dropshipper', 'status', 'payment_status')
        }),
        ('Клиент', {
            'fields': ('client_name', 'client_phone', 'client_np_address')
        }),
        ('Доставка', {
            'fields': ('tracking_number',)
        }),
        ('Финансы', {
            'fields': ('total_drop_price', 'total_selling_price', 'profit')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'order_source')
        }),
    )
    
    readonly_fields = ['order_number', 'total_drop_price', 'total_selling_price', 'profit']
    
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = DropshipperOrder.objects.get(pk=obj.pk)
            
            # Если изменился статус - отправить уведомление
            if old_obj.status != obj.status:
                asyncio.run(send_order_status_changed_notification(obj, old_obj.status, obj.status))
            
            # Если добавили TTN - отправить уведомление
            if not old_obj.tracking_number and obj.tracking_number:
                asyncio.run(send_order_ttn_added_notification(obj))
        
        super().save_model(request, obj, form, change)
```

---

## 🎯 WORKFLOW (КАК ДОЛЖНО РАБОТАТЬ)

```
1. ДРОПШИППЕР создает заказ через модальное окно
   ↓
   status: draft
   🔔 Telegram → Дропшипперу: "Замовлення створено"
   
2. ДРОПШИППЕР нажимает "Підтвердити" в списке заказов
   ↓
   status: pending
   🔔 Telegram → АДМИНУ: "НОВЕ ЗАМОВЛЕННЯ ВІД ДРОПШИПЕРА!" + inline кнопки
   
3. АДМИН нажимает "✅ Підтвердити" в Telegram или админ-панели
   ↓
   status: confirmed
   🔔 Telegram → Дропшипперу: "Статус оновлено: Підтверджено"
   
4. АДМИН обрабатывает заказ
   ↓
   status: processing
   🔔 Telegram → Дропшипперу: "Статус оновлено: В обробці"
   
5. АДМИН отправляет заказ + добавляет TTN в админ-панели
   ↓
   status: shipped + tracking_number
   🔔 Telegram → Дропшипперу: "Відправлено! TTN: 59001234567890" + ссылка на отслеживание
   
6. КЛИЕНТ получает заказ
   ↓
   status: delivered
   🔔 Telegram → Дропшипперу: "Доставлено! Очікує виплати"
```

---

## 📝 ШАБЛОНЫ КНОПОК TELEGRAM

### Inline Keyboard для админа (при pending):
```python
keyboard = [
    [
        InlineKeyboardButton("✅ Підтвердити", callback_data=f"order_confirm_{order.id}"),
        InlineKeyboardButton("❌ Скасувати", callback_data=f"order_cancel_{order.id}")
    ],
    [
        InlineKeyboardButton("📝 Переглянути", url=f"https://twocomms.shop/admin/orders/dropshipperorder/{order.id}/change/")
    ]
]
```

### Inline Keyboard для дропшиппера:
```python
keyboard = [
    [
        InlineKeyboardButton("📦 Переглянути замовлення", url=f"https://twocomms.shop/orders/dropshipper/orders/")
    ]
]
```

---

## 🔒 БЕЗОПАСНОСТЬ

1. **Проверка прав доступа:**
   - Только дропшипперы могут создавать/подтверждать заказы
   - Только админы могут изменять статусы confirmed → shipped
   - Только админы могут добавлять TTN

2. **Валидация:**
   - TTN должен быть в формате Новой Почты (14 цифр)
   - Цена продажи должна быть >= цены дропа
   - Телефон клиента должен быть валидным

---

## 📚 ПОЛЕЗНЫЕ ССЫЛКИ

- **Telegram Bot API:** https://core.telegram.org/bots/api
- **Django Signals:** https://docs.djangoproject.com/en/4.2/topics/signals/
- **Async in Django:** https://docs.djangoproject.com/en/4.2/topics/async/

---

**Версия документа:** 1.0  
**Дата:** 2025-10-21

