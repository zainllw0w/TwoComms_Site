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
    
    def send_message(self, message, parse_mode='HTML'):
        """Отправляет сообщение в Telegram"""
        if not self.is_configured():
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
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
        order_header = f"🆕 <b>НОВЫЙ ЗАКАЗ #{order.order_number}</b>\n"
        
        # Информация о клиенте в блоке pre
        user_info = f"""
<pre language="yaml">
👤 КЛИЕНТ:
  Имя: {order.full_name}
  Телефон: {order.phone}
  Город: {order.city}
  НП: {order.np_office}
</pre>
"""
        
        # Детали заказа в блоке pre
        order_details = f"""
<pre language="json">
📋 ДЕТАЛИ ЗАКАЗА:
{{
  "Статус оплаты": "{order.get_payment_status_display()}",
  "Статус заказа": "{order.get_status_display()}",
  "Время создания": "{order.created.strftime('%d.%m.%Y %H:%M')}"
}}
</pre>
"""
        
        # Товары в заказе в блоке pre
        items_info = f"""
<pre language="text">
📦 ТОВАРЫ В ЗАКАЗЕ ({order.items.count()} позиций):
"""
        total_items = 0
        subtotal = 0
        
        for i, item in enumerate(order.items.all(), 1):
            details = []
            if item.size:
                details.append(f"Размер: {item.size}")
            if item.color_variant:
                details.append(f"Цвет: {item.color_variant.color.name}")
            
            details_str = f" ({', '.join(details)})" if details else ""
            items_info += f"{i}. {item.title}{details_str}\n"
            items_info += f"   └ {item.qty} × {item.unit_price} = {item.line_total} грн\n"
            
            if i < order.items.count():
                items_info += "   ───────────────\n"
            
            total_items += item.qty
            subtotal += item.line_total
        
        items_info += "</pre>\n"
        
        # Итоговая информация в блоке pre
        total_section = f"""
<pre language="text">
📊 ИТОГОВАЯ ИНФОРМАЦИЯ:
Всего товаров: {total_items} шт.
Сумма товаров: {subtotal} грн
"""
        
        if order.promo_code:
            total_section += f"Промокод: {order.promo_code.code}\n"
            total_section += f"Скидка: -{order.discount_amount} грн\n"
        
        total_section += f"ИТОГО К ОПЛАТЕ: {order.total_sum} грн
</pre>
"""
        
        # Красивый блок с итоговой информацией
        summary_block = f"""
<pre language="text">
┌─────────────────────────────┐
│  🆕 ЗАКАЗ #{order.order_number}        │
├─────────────────────────────┤
│  👤 {order.full_name:<25} │
│  📞 {order.phone:<25} │
│  🏙️ {order.city:<25} │
│  📦 {order.np_office:<25} │
├─────────────────────────────┤
│  💳 {order.get_payment_status_display():<25} │
│  📊 {order.get_status_display():<25} │
│  ⏰ {order.created.strftime('%d.%m.%Y %H:%M'):<25} │
├─────────────────────────────┤
│  📊 Товаров: {total_items} шт.        │
│  💰 Сумма: {subtotal} грн        │
"""
        
        if order.promo_code:
            summary_block += f"│  🎫 Промокод: {order.promo_code.code:<15} │\n"
            summary_block += f"│  💸 Скидка: -{order.discount_amount} грн        │\n"
        
        summary_block += f"│  💳 ИТОГО: {order.total_sum} грн        │\n"
        summary_block += "└─────────────────────────────┘"
        summary_block += "</pre>"
        
        # Собираем полное сообщение
        message = f"{order_header}\n{user_info}{order_details}{items_info}{total_section}\n{summary_block}"
        
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
