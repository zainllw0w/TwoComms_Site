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
        
    def is_configured(self):
        """Проверяет, настроен ли бот"""
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, message):
        """Отправляет сообщение в Telegram"""
        if not self.is_configured():
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            return False
    
    def format_order_message(self, order):
        """Форматирует сообщение о заказе"""
        user_info = f"👤 <b>{order.full_name}</b>\n"
        user_info += f"📞 {order.phone}\n"
        user_info += f"🏙️ {order.city}\n"
        user_info += f"📦 {order.np_office}\n\n"
        
        order_info = f"🛒 <b>Заказ #{order.order_number}</b>\n"
        order_info += f"💰 Сумма: {order.total_sum} грн\n"
        order_info += f"💳 Оплата: {order.get_payment_status_display()}\n"
        order_info += f"📊 Статус: {order.get_status_display()}\n"
        order_info += f"⏰ Время: {order.created.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        # Информация о товарах
        items_info = "📦 <b>Товары:</b>\n"
        for item in order.items.all():
            items_info += f"• {item.product.title} - {item.quantity} шт\n"
            if item.color_variant:
                items_info += f"  Цвет: {item.color_variant.color.name}\n"
        
        # Промокод если есть
        promo_info = ""
        if order.promo_code:
            promo_info = f"\n🎫 Промокод: {order.promo_code.code}\n"
            promo_info += f"💸 Скидка: {order.discount_amount} грн\n"
        
        message = f"🆕 <b>Новый заказ!</b>\n\n{user_info}{order_info}{items_info}{promo_info}"
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
            
        message = f"📊 <b>Обновление заказа #{order.order_number}</b>\n\n"
        message += f"👤 {order.full_name}\n"
        message += f"📞 {order.phone}\n\n"
        message += f"Статус изменен: <b>{old_status}</b> → <b>{new_status}</b>\n"
        message += f"⏰ {timezone.now().strftime('%d.%m.%Y %H:%M')}"
        
        return self.send_message(message)


# Глобальный экземпляр для использования
telegram_notifier = TelegramNotifier()
