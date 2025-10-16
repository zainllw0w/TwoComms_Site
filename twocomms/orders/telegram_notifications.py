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


# Глобальный экземпляр для использования
telegram_notifier = TelegramNotifier()
