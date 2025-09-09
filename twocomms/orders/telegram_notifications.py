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

🔗 <b>Полезные ссылки:</b>
• <a href="https://t.me/twocomms">💬 Помощь в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мои заказы</a>"""
        
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
            
        message = f"📊 <b>Обновление заказа #{order.order_number}</b>\n\n"
        message += f"👤 {order.full_name}\n"
        message += f"📞 {order.phone}\n\n"
        message += f"Статус изменен: <b>{old_status}</b> → <b>{new_status}</b>\n"
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
        message = f"""📦 <b>ТТН ДОБАВЛЕН К ЗАКАЗУ</b>

🆔 <b>Заказ:</b> #{order.order_number}
📋 <b>ТТН:</b> {order.tracking_number}

📊 <b>Статус заказа:</b> {order.get_status_display()}
💰 <b>Сумма:</b> {order.total_sum} грн

🕐 <b>Время добавления:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Теперь вы можете отслеживать статус вашей посылки!</i>

🔗 <b>Полезные ссылки:</b>
• <a href="https://t.me/twocomms">💬 Помощь в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мои заказы</a>"""
        
        return message


# Глобальный экземпляр для использования
telegram_notifier = TelegramNotifier()
