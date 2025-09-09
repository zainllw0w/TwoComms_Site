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
        order_info += f"💳 Оплата: {order.get_payment_status_display()}\n"
        order_info += f"📊 Статус: {order.get_status_display()}\n"
        order_info += f"⏰ Время: {order.created.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        # Информация о товарах
        items_info = "📦 <b>Товары в заказе:</b>\n"
        items_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        total_items = 0
        subtotal = 0
        
        for i, item in enumerate(order.items.all(), 1):
            # Основная информация о товаре
            items_info += f"<b>{i}.</b> {item.title}\n"
            
            # Детали товара в одной строке
            details = []
            if item.size:
                details.append(f"Размер: {item.size}")
            if item.color_variant:
                details.append(f"Цвет: {item.color_variant.color.name}")
            
            # Количество и цена в одной строке
            price_info = f"<b>{item.qty} шт.</b> × <b>{item.unit_price} грн</b> = <b>{item.line_total} грн</b>"
            
            if details:
                items_info += f"   └ {', '.join(details)} | {price_info}\n"
            else:
                items_info += f"   └ {price_info}\n"
            
            if i < order.items.count():
                items_info += "   ───────────────────────────────────────\n"
            
            total_items += item.qty
            subtotal += item.line_total
        
        items_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        items_info += f"📊 Всего товаров: <b>{total_items} шт.</b>\n"
        items_info += f"💰 Сумма товаров: <b>{subtotal} грн</b>\n"
        
        # Промокод и скидка
        if order.promo_code:
            items_info += f"🎫 Промокод: <b>{order.promo_code.code}</b>\n"
            items_info += f"💸 Скидка: <b>-{order.discount_amount} грн</b>\n"
            items_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            items_info += f"💳 <b>ИТОГО К ОПЛАТЕ: {order.total_sum} грн</b>\n"
        else:
            items_info += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            items_info += f"💳 <b>ИТОГО К ОПЛАТЕ: {order.total_sum} грн</b>\n"
        
        message = f"🆕 <b>НОВЫЙ ЗАКАЗ!</b>\n\n{user_info}{order_info}{items_info}"
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
