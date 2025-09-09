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
        """Форматирует HTML сообщение о заказе"""
        # Основная информация о заказе
        order_header = f"""
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px;">
    <h2 style="margin: 0; text-align: center;">🆕 НОВЫЙ ЗАКАЗ #{order.order_number}</h2>
</div>
"""
        
        # Информация о клиенте
        user_info = f"""
<div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #28a745;">
    <h3 style="margin: 0 0 10px 0; color: #333;">👤 Информация о клиенте</h3>
    <p style="margin: 5px 0;"><strong>Имя:</strong> {order.full_name}</p>
    <p style="margin: 5px 0;"><strong>Телефон:</strong> <code style="background: #e9ecef; padding: 2px 6px; border-radius: 4px;">{order.phone}</code></p>
    <p style="margin: 5px 0;"><strong>Город:</strong> {order.city}</p>
    <p style="margin: 5px 0;"><strong>НП:</strong> {order.np_office}</p>
</div>
"""
        
        # Детали заказа
        order_details = f"""
<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #ffc107;">
    <h3 style="margin: 0 0 10px 0; color: #856404;">📋 Детали заказа</h3>
    <p style="margin: 5px 0;"><strong>Статус оплаты:</strong> <em>{order.get_payment_status_display()}</em></p>
    <p style="margin: 5px 0;"><strong>Статус заказа:</strong> <em>{order.get_status_display()}</em></p>
    <p style="margin: 5px 0;"><strong>Время создания:</strong> <code style="background: #e9ecef; padding: 2px 6px; border-radius: 4px;">{order.created.strftime('%d.%m.%Y %H:%M')}</code></p>
</div>
"""
        
        # Товары в заказе (сворачиваемый блок)
        items_html = ""
        total_items = 0
        subtotal = 0
        
        for i, item in enumerate(order.items.all(), 1):
            details = []
            if item.size:
                details.append(f"<span style='background: #007bff; color: white; padding: 2px 6px; border-radius: 4px; font-size: 12px;'>{item.size}</span>")
            if item.color_variant:
                details.append(f"<span style='background: #6c757d; color: white; padding: 2px 6px; border-radius: 4px; font-size: 12px;'>{item.color_variant.color.name}</span>")
            
            items_html += f"""
            <div style="padding: 10px; border-bottom: 1px solid #dee2e6; {'border-bottom: none;' if i == order.items.count() else ''}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{i}. {item.title}</strong>
                        {f'<br><small style="color: #6c757d;">{" • ".join(details)}</small>' if details else ''}
                    </div>
                    <div style="text-align: right;">
                        <strong>{item.qty} × {item.unit_price} = {item.line_total} грн</strong>
                    </div>
                </div>
            </div>
            """
            
            total_items += item.qty
            subtotal += item.line_total
        
        items_section = f"""
<details style="background: #e3f2fd; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2196f3;">
    <summary style="padding: 15px; cursor: pointer; font-weight: bold; color: #1976d2;">
        📦 Товары в заказе ({order.items.count()} позиций) - {total_items} шт.
    </summary>
    <div style="background: white; border-radius: 0 0 8px 8px; overflow: hidden;">
        {items_html}
    </div>
</details>
"""
        
        # Итоговая информация
        total_section = f"""
<div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; border-radius: 10px; text-align: center;">
    <div style="margin-bottom: 10px;">
        <strong>📊 Всего товаров: {total_items} шт.</strong><br>
        <strong>💰 Сумма товаров: {subtotal} грн</strong>
    </div>
"""
        
        if order.promo_code:
            total_section += f"""
    <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; margin: 10px 0;">
        <strong>🎫 Промокод: <code style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 4px;">{order.promo_code.code}</code></strong><br>
        <strong>💸 Скидка: -{order.discount_amount} грн</strong>
    </div>
"""
        
        total_section += f"""
    <div style="background: rgba(255,255,255,0.3); padding: 15px; border-radius: 8px; font-size: 18px;">
        <strong>💳 ИТОГО К ОПЛАТЕ: {order.total_sum} грн</strong>
    </div>
</div>
"""
        
        # Код для красивого отображения
        code_section = f"""
<pre style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #6c757d; font-family: 'Courier New', monospace; font-size: 12px; overflow-x: auto;">
┌─────────────────────────────────────────┐
│  🆕 ЗАКАЗ #{order.order_number}                    │
├─────────────────────────────────────────┤
│  👤 {order.full_name:<30} │
│  📞 {order.phone:<30} │
│  🏙️ {order.city:<30} │
│  📦 {order.np_office:<30} │
├─────────────────────────────────────────┤
│  💳 {order.get_payment_status_display():<30} │
│  📊 {order.get_status_display():<30} │
│  ⏰ {order.created.strftime('%d.%m.%Y %H:%M'):<30} │
└─────────────────────────────────────────┘
</pre>
"""
        
        # Собираем полное сообщение
        message = f"""
{order_header}
{user_info}
{order_details}
{items_section}
{total_section}
{code_section}
"""
        
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
