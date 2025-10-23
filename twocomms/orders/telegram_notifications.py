"""
Telegram уведомления для заказов
"""
import requests
import os
from django.conf import settings
from django.utils import timezone
from datetime import datetime


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self):
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.admin_id = os.environ.get('TELEGRAM_ADMIN_ID')
        
    def is_configured(self):
        """Проверяет, настроен ли бот"""
        return bool(self.bot_token and (self.chat_id or self.admin_id))
    
    def send_message(self, message, parse_mode='HTML'):
        """Отправляет сообщение в Telegram"""
        if not self.is_configured():
            return False
            
        # Используем админ ID, если он доступен, иначе chat_id
        target_id = self.admin_id if self.admin_id else self.chat_id
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': target_id,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            return False
    
    def send_personal_message(self, telegram_id, message, parse_mode='HTML'):
        """Отправляет личное сообщение пользователю по telegram_id"""
        if not self.bot_token or not telegram_id:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            return False
    
    def format_order_message(self, order):
        """Форматирует HTML сообщение о заказе с поддержкой Telegram"""
        # Основная информация о заказе
        order_header = f"🆕 <b>НОВЕ ЗАМОВЛЕННЯ #{order.order_number}</b>\n"
        
        # Подсчитываем товары
        total_items = 0
        subtotal = 0
        
        for item in order.items.all():
            total_items += item.qty
            subtotal += item.line_total
        
        # Создаем единый блок с всей информацией
        full_block = f"""
<pre language="text">
┌─────────────────────────────────────────┐
│  🆕 ЗАКАЗ #{order.order_number}                   │
├─────────────────────────────────────────┤
│  👤 КЛИЕНТ:
│     Имя: {order.full_name}
│     Телефон: {order.phone}
│     Город: {order.city}
│     НП: {order.np_office}
├─────────────────────────────────────────┤
│  📋 ДЕТАЛИ ЗАКАЗА:
│     Статус оплаты: {order.get_payment_status_display()}
│     Статус заказа: {order.get_status_display()}
│     Время создания: {order.created.strftime('%d.%m.%Y %H:%M')}
├─────────────────────────────────────────┤
│  📦 ТОВАРЫ В ЗАКАЗЕ ({order.items.count()} позиций):
"""
        
        # Добавляем товары
        for i, item in enumerate(order.items.all(), 1):
            full_block += f"│     {i}. {item.title}\n"
            
            # Добавляем детали товара каждая на новой строке с └
            if item.size:
                full_block += f"│        └ Размер: {item.size}\n"
            if item.qty:
                full_block += f"│        └ Количество: {item.qty}\n"
            if item.color_variant:
                full_block += f"│        └ Цвет: {item.color_variant.color.name}\n"
            if item.unit_price:
                full_block += f"│        └ Цена: {item.unit_price} грн\n"
            
            if i < order.items.count():
                full_block += "│     ───────────────────────────────────\n"
        
        # Добавляем итоговую информацию
        full_block += f"├─────────────────────────────────────────┤\n"
        full_block += f"│  📊 ИТОГОВАЯ ИНФОРМАЦИЯ:\n"
        full_block += f"│     Всего товаров: {total_items} шт.\n"
        full_block += f"│     Сумма товаров: {subtotal} грн\n"
        
        if order.promo_code:
            full_block += f"│     Промокод: {order.promo_code.code}\n"
            full_block += f"│     Скидка: -{order.discount_amount} грн\n"
        
        full_block += f"├─────────────────────────────────────────┤\n"
        full_block += f"│  💳 ИТОГО К ОПЛАТЕ: {order.total_sum} грн\n"
        full_block += f"└─────────────────────────────────────────┘"
        full_block += "</pre>"
        
        # Добавляем ссылки
        links = """

🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мої замовлення</a>"""
        
        # Собираем полное сообщение
        message = f"{order_header}\n{full_block}\n{links}"
        
        return message
    
    def send_new_order_notification(self, order):
        """Отправляет уведомление о новом заказе"""
        if not self.is_configured():
            return False
            
        message = self.format_order_message(order)
        return self.send_message(message)
    
    def send_order_status_update(self, order, old_status, new_status):
        """Отправляет уведомление об изменении статуса заказа"""
        if not self.is_configured():
            return False
            
        message = f"📊 <b>Оновлення замовлення #{order.order_number}</b>\n\n"
        message += f"👤 {order.full_name}\n"
        message += f"📞 {order.phone}\n\n"
        message += f"Статус змінено: <b>{old_status}</b> → <b>{new_status}</b>\n"
        message += f"⏰ {timezone.now().strftime('%d.%m.%Y %H:%M')}"
        
        return self.send_message(message)
    
    def send_ttn_added_notification(self, order):
        """
        Отправляет уведомление о добавлении ТТН к заказу
        
        Args:
            order (Order): Заказ с добавленным ТТН
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            return False
            
        if not order.user:
            return False
            
        # Получаем Telegram username из профиля пользователя
        try:
            from accounts.models import UserProfile
            profile = UserProfile.objects.get(user=order.user)
            telegram_username = profile.telegram
            
            if not telegram_username:
                return False
                
            # Формируем сообщение
            message = self._format_ttn_added_message(order)
            
            # Отправляем сообщение с упоминанием пользователя
            if telegram_username.startswith('@'):
                telegram_username = telegram_username[1:]
                
            full_message = f"@{telegram_username}\n\n{message}"
            return self.send_message(full_message)
            
        except Exception as e:
            print(f"Ошибка при отправке уведомления о ТТН: {e}")
            return False
    
    def _format_ttn_added_message(self, order):
        """
        Форматирует сообщение о добавлении ТТН
        
        Args:
            order (Order): Заказ с ТТН
            
        Returns:
            str: Отформатированное сообщение
        """
        message = f"""📦 <b>ТТН ДОДАНО ДО ЗАМОВЛЕННЯ</b>

🆔 <b>Замовлення:</b> #{order.order_number}
📋 <b>ТТН:</b> {order.tracking_number}

📊 <b>Статус замовлення:</b> {order.get_status_display()}
💰 <b>Сума:</b> {order.total_sum} грн

🕐 <b>Час додавання:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Тепер ви можете відстежувати статус вашої посилки!</i>

🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мої замовлення</a>"""
        
        return message
    
    def send_ttn_added_notification(self, order):
        """Отправляет уведомление пользователю о добавлении ТТН"""
        if not order.user or not order.user.userprofile.telegram_id:
            return False
        
        message = self._format_ttn_added_message(order)
        return self.send_personal_message(order.user.userprofile.telegram_id, message)
    
    def send_order_status_update(self, order, old_status, new_status):
        """Отправляет уведомление пользователю об изменении статуса заказа"""
        if not order.user or not order.user.userprofile.telegram_id:
            return False
        
        message = self._format_status_update_message(order, old_status, new_status)
        return self.send_personal_message(order.user.userprofile.telegram_id, message)
    
    def send_ttn_notification(self, order):
        """Отправляет уведомление дропшиперу о добавлении ТТН"""
        if not order.dropshipper or not order.dropshipper.userprofile.telegram_id:
            return False
        
        if not order.tracking_number:
            return False
        
        message = f"""📦 <b>ТТН ДОДАНО ДО ВАШОГО ЗАМОВЛЕННЯ!</b>

🆔 <b>Замовлення:</b> #{order.order_number}

🚚 <b>Номер ТТН:</b> <code>{order.tracking_number}</code>

📍 <b>Клієнт:</b> {order.client_name}
📞 <b>Телефон:</b> {order.client_phone}
🏢 <b>Адреса:</b> {order.client_np_address or '—'}

💰 <b>Ваш прибуток:</b> {order.profit} грн

🔗 <b>Відстежити посилку:</b>
<a href="https://novaposhta.ua/tracking/?cargo_number={order.tracking_number}">Відкрити на сайті Нової Пошти</a>

<i>Тепер ви можете відстежувати статус доставки!</i>"""
        
        return self.send_personal_message(order.dropshipper.userprofile.telegram_id, message)
    
    def _format_status_update_message(self, order, old_status, new_status):
        """Форматирует сообщение об изменении статуса заказа"""
        message = f"""📋 <b>ОНОВЛЕННЯ СТАТУСУ ЗАМОВЛЕННЯ</b>

🆔 <b>Замовлення:</b> #{order.order_number}

📊 <b>Статус змінено:</b>
├─ Було: {old_status}
└─ Стало: <b>{new_status}</b>

💰 <b>Сума:</b> {order.total_sum} грн

🕐 <b>Час оновлення:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Слідкуйте за оновленнями вашого замовлення!</i>

🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мої замовлення</a>"""

        return message
    
    def send_invoice_notification(self, invoice):
        """
        Отправляет уведомление о новой накладной админу
        
        Args:
            invoice (WholesaleInvoice): Накладная
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            return False
            
        message = self.format_invoice_message(invoice)
        return self.send_message(message)
    
    def format_invoice_message(self, invoice):
        """
        Форматирует сообщение о накладной
        
        Args:
            invoice (WholesaleInvoice): Накладная
            
        Returns:
            str: Отформатированное сообщение
        """
        # Основная информация о накладной
        invoice_header = f"📋 <b>НОВА НАКЛАДНА #{invoice.invoice_number}</b>\n"
        
        # Создаем блок с информацией о накладной
        full_block = f"""
<pre language="text">
┌─────────────────────────────────────────┐
│  📋 НАКЛАДНА #{invoice.invoice_number}                │
├─────────────────────────────────────────┤
│  🏢 КОМПАНІЯ:
│     Назва: {invoice.company_name}
│     Номер: {invoice.company_number or 'Не вказано'}
│     Телефон: {invoice.contact_phone}
│     Адреса: {invoice.delivery_address}
├─────────────────────────────────────────┤
│  📊 ДЕТАЛІ НАКЛАДНОЇ:
│     Статус: {invoice.get_status_display()}
│     Футболки: {invoice.total_tshirts} шт.
│     Худі: {invoice.total_hoodies} шт.
│     Загальна сума: {invoice.total_amount} грн
│     Дата створення: {invoice.created_at.strftime('%d.%m.%Y %H:%M')}
└─────────────────────────────────────────┘
</pre>"""
        
        # Добавляем ссылки
        links = f"""
🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/admin-panel/collaboration/">📋 Адмін панель</a>
• <a href="https://twocomms.shop/wholesale/download-invoice/{invoice.id}/">📥 Скачати накладну</a>"""
        
        # Собираем полное сообщение
        message = f"{invoice_header}\n{full_block}\n{links}"
        
        return message
    
    def send_invoice_document(self, invoice, file_path):
        """
        Отправляет документ накладной в Telegram
        
        Args:
            invoice (WholesaleInvoice): Накладная
            file_path (str): Путь к файлу накладной
            
        Returns:
            bool: True если документ отправлен успешно
        """
        if not self.is_configured():
            return False
            
        # Используем админ ID, если он доступен, иначе chat_id
        target_id = self.admin_id if self.admin_id else self.chat_id
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
            
            # Читаем файл
            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    'chat_id': target_id,
                    'caption': f"📋 Накладна #{invoice.invoice_number}\n🏢 {invoice.company_name}\n💰 {invoice.total_amount} грн",
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, files=files, data=data, timeout=30)
                return response.status_code == 200
        except Exception as e:
            print(f"Ошибка при отправке документа накладной: {e}")
            return False
    
    def send_dropshipper_order_notification(self, order):
        """
        Отправляет уведомление админу о новом заказе дропшиппера
        
        Args:
            order (DropshipperOrder): Заказ дропшиппера
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            return False
            
        message = self._format_dropshipper_order_message(order)
        return self.send_message(message)
    
    def _format_dropshipper_order_message(self, order):
        """
        Форматирует сообщение о новом заказе дропшиппера
        
        Args:
            order (DropshipperOrder): Заказ дропшиппера
            
        Returns:
            str: Отформатированное HTML сообщение
        """
        # Определяем эмодзи статуса
        status_emoji = "📋"
        if order.status == 'draft':
            status_emoji = "⏳"
        elif order.status == 'pending':
            status_emoji = "🔔"
        elif order.status == 'confirmed':
            status_emoji = "✅"
        
        # Заголовок
        header = f"🆕 <b>НОВИЙ ДРОПШИП ЗАМОВЛЕННЯ</b>\n"
        
        # Получаем информацию о дропшиппере
        dropshipper_profile = None
        try:
            dropshipper_profile = order.dropshipper.userprofile
        except:
            pass
        
        dropshipper_company = dropshipper_profile.company_name if dropshipper_profile and dropshipper_profile.company_name else order.dropshipper.username
        dropshipper_telegram = dropshipper_profile.telegram if dropshipper_profile and dropshipper_profile.telegram else 'не підключено'
        dropshipper_phone = dropshipper_profile.phone if dropshipper_profile and dropshipper_profile.phone else 'не вказано'
        
        # Основной блок информации
        full_block = f"""
<pre language="text">
┌─────────────────────────────────────────┐
│  {status_emoji} ЗАМОВЛЕННЯ #{order.order_number}
├─────────────────────────────────────────┤
│  👤 ДРОПШИПЕР:
│     Компанія: {dropshipper_company}
│     Telegram: @{dropshipper_telegram}
│     Телефон: {dropshipper_phone}
├─────────────────────────────────────────┤
│  📦 КЛІЄНТ:
│     ПІБ: {order.client_name if order.client_name else 'Не вказано'}
│     Телефон: {order.client_phone if order.client_phone else 'Не вказано'}"""
        
        if order.client_np_address:
            full_block += f"\n│     Адреса НП: {order.client_np_address}"
        
        full_block += f"""
├─────────────────────────────────────────┤
│  📋 СТАТУС:
│     Замовлення: {order.get_status_display()}
│     Оплата: {order.get_payment_status_display()}
│     Створено: {order.created_at.strftime('%d.%m.%Y %H:%M')}
├─────────────────────────────────────────┤
│  📦 ТОВАРИ ({order.items.count()} позицій):
"""
        
        # Добавляем товары
        for i, item in enumerate(order.items.all(), 1):
            full_block += f"│     {i}. {item.product.title}\n"
            
            # Детали товара
            if item.size:
                full_block += f"│        └ Розмір: {item.size}\n"
            if item.quantity:
                full_block += f"│        └ Кількість: {item.quantity}\n"
            if item.color_variant:
                full_block += f"│        └ Колір: {item.color_variant.color.name if hasattr(item.color_variant.color, 'name') else str(item.color_variant.color)}\n"
            if item.drop_price:
                full_block += f"│        └ Ціна дропа: {item.drop_price} грн\n"
            if item.selling_price:
                full_block += f"│        └ Ціна продажу: {item.selling_price} грн\n"
            
            if i < order.items.count():
                full_block += "│     ───────────────────────────────────\n"
        
        # Информация об оплате
        payment_method_text = "💳 Оплачено передоплатою" if order.payment_method == 'prepaid' else "📦 Накладний платіж"
        dropshipper_payment = order.dropshipper_payment_required if order.dropshipper_payment_required else 0
        
        # Итоговая информация
        full_block += f"""├─────────────────────────────────────────┤
│  💰 ФІНАНСИ:
│     Сума продажу: {order.total_selling_price} грн
│     Собівартість: {order.total_drop_price} грн
│     Прибуток дропшипера: {order.profit} грн
├─────────────────────────────────────────┤
│  💳 ОПЛАТА:
│     Спосіб: {payment_method_text}
│     Дропшипер сплачує: {dropshipper_payment} грн"""
        
        if order.payment_method == 'cod':
            full_block += "\n│     📦 Віднімається з накладки при отриманні"
        
        full_block += f"""
├─────────────────────────────────────────┤
│  💳 ВСЬОГО: {order.total_selling_price} грн
└─────────────────────────────────────────┘
</pre>"""
        
        # Добавляем ссылки
        links = f"""
🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Підтримка в Telegram</a>
• <a href="https://twocomms.shop/admin/orders/dropshipperorder/{order.id}/change/">⚙️ Керування замовленням</a>
• <a href="https://twocomms.shop/orders/dropshipper/orders/">📋 Всі замовлення дропшипера</a>
"""
        
        # Дополнительная информация
        additional_info = ""
        if order.status == 'draft':
            additional_info = "\n⚠️ <b>Увага!</b> Замовлення потребує підтвердження дропшипером."
        elif order.order_source:
            additional_info = f"\n🔗 <b>Джерело замовлення:</b> {order.order_source}"
        
        # Собираем полное сообщение
        message = f"{header}\n{full_block}\n{links}{additional_info}"
        
        return message
    
    def send_dropshipper_payment_notification(self, order):
        """
        Отправляет уведомление админу об оплате дропшип заказа
        
        Args:
            order (DropshipperOrder): Оплаченный заказ дропшиппера
            
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            return False
            
        message = self._format_dropshipper_payment_message(order)
        return self.send_message(message)
    
    def _format_dropshipper_payment_message(self, order):
        """
        Форматирует сообщение об оплате дропшип заказа
        
        Args:
            order (DropshipperOrder): Оплаченный заказ дропшиппера
            
        Returns:
            str: Отформатированное HTML сообщение
        """
        # Получаем информацию о дропшиппере
        dropshipper_profile = None
        try:
            dropshipper_profile = order.dropshipper.userprofile
        except:
            pass
        
        dropshipper_company = dropshipper_profile.company_name if dropshipper_profile and dropshipper_profile.company_name else order.dropshipper.username
        
        # Заголовок с эмодзи
        header = f"💰 <b>ДРОПШИП ЗАМОВЛЕННЯ ОПЛАЧЕНО!</b>\n"
        
        # Основной блок информации
        full_block = f"""
<pre language="text">
┌─────────────────────────────────────────┐
│  ✅ ЗАМОВЛЕННЯ #{order.order_number}
├─────────────────────────────────────────┤
│  👤 ДРОПШИПЕР:
│     Компанія: {dropshipper_company}
├─────────────────────────────────────────┤
│  📦 КЛІЄНТ:
│     ПІБ: {order.client_name if order.client_name else 'Не вказано'}
│     Телефон: {order.client_phone if order.client_phone else 'Не вказано'}
├─────────────────────────────────────────┤
│  💳 ОПЛАТА:
│     Статус: ОПЛАЧЕНО ✅
│     Сума: {order.dropshipper_payment_required} грн
│     Спосіб: {order.get_payment_method_display()}
│     Час оплати: {timezone.now().strftime('%d.%m.%Y %H:%M')}
├─────────────────────────────────────────┤
│  📦 ТОВАРИ ({order.items.count()} позицій):
"""
        
        # Добавляем товары
        for i, item in enumerate(order.items.all(), 1):
            full_block += f"│     {i}. {item.product.title}"
            if item.size:
                full_block += f" · {item.size}"
            if item.color_variant:
                full_block += f" · {item.color_variant.color.name if hasattr(item.color_variant.color, 'name') else str(item.color_variant.color)}"
            full_block += f" (×{item.quantity})\n"
        
        full_block += f"""├─────────────────────────────────────────┤
│  💰 ФІНАНСИ:
│     Сума продажу: {order.total_selling_price} грн
│     Собівартість: {order.total_drop_price} грн
│     Прибуток дропшипера: {order.profit} грн
└─────────────────────────────────────────┘
</pre>"""
        
        # Добавляем ссылки
        links = f"""
🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Підтримка в Telegram</a>
• <a href="https://twocomms.shop/admin/orders/dropshipperorder/{order.id}/change/">⚙️ Керування замовленням</a>

✅ <i>Замовлення готове до відправки!</i>
"""
        
        # Собираем полное сообщение
        message = f"{header}\n{full_block}\n{links}"
        
        return message


# Глобальный экземпляр для использования
telegram_notifier = TelegramNotifier()
