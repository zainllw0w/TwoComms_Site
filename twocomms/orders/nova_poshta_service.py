"""
Сервис для работы с API Новой Почты
"""
import requests
import json
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import Order
from .telegram_notifications import TelegramNotifier


class NovaPoshtaService:
    """Сервис для работы с API Новой Почты"""
    
    API_URL = "https://api.novaposhta.ua/v2.0/json/"
    
    def __init__(self):
        self.api_key = getattr(settings, 'NOVA_POSHTA_API_KEY', '')
        self.telegram_notifier = TelegramNotifier()
    
    def get_tracking_info(self, ttn_number):
        """
        Получает информацию о статусе посылки по ТТН
        
        Args:
            ttn_number (str): Номер ТТН
            
        Returns:
            dict: Информация о посылке или None при ошибке
        """
        if not ttn_number or not self.api_key:
            return None
            
        try:
            payload = {
                "apiKey": self.api_key,
                "modelName": "TrackingDocument",
                "calledMethod": "getStatusDocuments",
                "methodProperties": {
                    "Documents": [
                        {
                            "DocumentNumber": ttn_number,
                            "Phone": ""  # Можно добавить телефон для более точного поиска
                        }
                    ]
                }
            }
            
            response = requests.post(self.API_URL, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success') and data.get('data'):
                return data['data'][0] if data['data'] else None
                
        except Exception as e:
            print(f"Ошибка при получении статуса посылки {ttn_number}: {e}")
            
        return None
    
    def update_order_tracking_status(self, order):
        """
        Обновляет статус посылки для заказа
        
        Args:
            order (Order): Заказ для обновления
            
        Returns:
            bool: True если статус обновлен, False если нет
        """
        if not order.tracking_number:
            return False
            
        tracking_info = self.get_tracking_info(order.tracking_number)
        
        if not tracking_info:
            return False
            
        # Извлекаем статус из ответа API
        status = tracking_info.get('Status', '')
        status_description = tracking_info.get('StatusDescription', '')
        
        # Формируем полное описание статуса
        full_status = f"{status} - {status_description}" if status_description else status
        
        # Проверяем, изменился ли статус
        if order.shipment_status != full_status:
            old_status = order.shipment_status
            order.shipment_status = full_status
            order.shipment_status_updated = timezone.now()
            
            # Автоматически меняем статус заказа при получении посылки
            order_status_changed = self._update_order_status_if_delivered(order, status, status_description)
            
            order.save()
            
            # Отправляем уведомление в Telegram если есть пользователь с Telegram
            # Если статус заказа изменился на "отримано", отправляем специальное уведомление
            if order_status_changed:
                self._send_delivery_notification(order, full_status)
            else:
                self._send_status_notification(order, old_status, full_status)
            
            return True
        else:
            # Если статус посылки не изменился, но заказ еще не "done", 
            # проверяем, нужно ли изменить статус заказа
            if order.status != 'done':
                order_status_changed = self._update_order_status_if_delivered(order, status, status_description)
                if order_status_changed:
                    order.save()
                    self._send_delivery_notification(order, full_status)
                    return True
            
        return False
    
    def _update_order_status_if_delivered(self, order, status, status_description):
        """
        Автоматически меняет статус заказа на 'done' при получении посылки.
        
        НОВАЯ ЛОГИКА (30.10.2024):
        1. Меняет status на 'done' (получено)
        2. Если payment_status != 'paid' → меняет на 'paid'
        3. Отправляет Purchase событие в Facebook Conversions API
        
        Args:
            order (Order): Заказ
            status (str): Статус посылки
            status_description (str): Описание статуса
            
        Returns:
            bool: True если статус заказа был изменен
        """
        # Проверяем, что посылка получена
        delivered_keywords = [
            'отримано', 'получено', 'доставлено', 'вручено', 
            'отримано отримувачем', 'получено получателем'
        ]
        
        status_lower = status.lower()
        description_lower = status_description.lower() if status_description else ''
        
        is_delivered = any(keyword in status_lower or keyword in description_lower 
                          for keyword in delivered_keywords)
        
        # Если посылка получена и статус заказа еще не 'done'
        if is_delivered and order.status != 'done':
            old_order_status = order.status
            old_payment_status = order.payment_status
            
            # 1. Меняем статус заказа
            order.status = 'done'
            print(f"✅ Заказ {order.order_number}: статус изменен с '{old_order_status}' на 'done' (посылка получена)")
            
            # 2. Автоматически меняем payment_status на 'paid' если не оплачено
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                print(f"💰 Заказ {order.order_number}: payment_status изменен с '{old_payment_status}' на 'paid'")
                
                # 3. Отправляем Purchase событие в Facebook Conversions API
                self._send_facebook_purchase_event(order)
            
            return True
        
        return False
    
    def _send_facebook_purchase_event(self, order):
        """
        Отправляет Purchase событие в Facebook Conversions API.
        
        Вызывается автоматически когда:
        - Посылка получена через Новую Почту
        - payment_status изменен на 'paid'
        
        Args:
            order (Order): Заказ для которого отправляется событие
        """
        try:
            from .facebook_conversions_service import get_facebook_conversions_service
            
            fb_service = get_facebook_conversions_service()
            
            if fb_service.enabled:
                success = fb_service.send_purchase_event(order)
                if success:
                    print(f"📊 Facebook Purchase event sent for order {order.order_number}")
                else:
                    print(f"⚠️ Failed to send Facebook Purchase event for order {order.order_number}")
            else:
                print(f"⚠️ Facebook Conversions API not enabled, skipping Purchase event")
                
        except Exception as e:
            print(f"❌ Error sending Facebook Purchase event for order {order.order_number}: {e}")
    
    def _send_delivery_notification(self, order, shipment_status):
        """
        Отправляет специальное уведомление о получении посылки
        
        Args:
            order (Order): Заказ
            shipment_status (str): Статус посылки
        """
        if not order.user or not order.user.userprofile.telegram_id:
            return
            
        # Формируем сообщение о доставке
        message = self._format_delivery_message(order, shipment_status)
        
        # Отправляем личное сообщение пользователю
        self.telegram_notifier.send_personal_message(
            order.user.userprofile.telegram_id, 
            message
        )
    
    def _send_status_notification(self, order, old_status, new_status):
        """
        Отправляет уведомление об изменении статуса в Telegram
        
        Args:
            order (Order): Заказ
            old_status (str): Старый статус
            new_status (str): Новый статус
        """
        if not order.user or not order.user.userprofile.telegram_id:
            return
            
        # Формируем сообщение
        message = self._format_status_message(order, old_status, new_status)
        
        # Отправляем личное сообщение пользователю
        self.telegram_notifier.send_personal_message(
            order.user.userprofile.telegram_id, 
            message
        )
    
    def _format_delivery_message(self, order, shipment_status):
        """
        Форматирует красивое сообщение о получении посылки
        
        Args:
            order (Order): Заказ
            shipment_status (str): Статус посылки
            
        Returns:
            str: Отформатированное сообщение
        """
        message = f"""🎉 <b>ПОСИЛКА ОТРИМАНА!</b>

🆔 <b>Замовлення:</b> #{order.order_number}
📋 <b>ТТН:</b> {order.tracking_number}
📦 <b>Статус:</b> {shipment_status}

✅ <b>Ваше замовлення успішно доставлено!</b>
💰 <b>Сума:</b> {order.total_sum} грн

🕐 <b>Час отримання:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Дякуємо за покупку! Сподіваємося, що товар вам сподобався.</i>

🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мої замовлення</a>"""
        
        return message
    
    def _format_status_message(self, order, old_status, new_status):
        """
        Форматирует сообщение об изменении статуса
        
        Args:
            order (Order): Заказ
            old_status (str): Старый статус
            new_status (str): Новый статус
            
        Returns:
            str: Отформатированное сообщение
        """
        message = f"""📦 <b>ОНОВЛЕННЯ СТАТУСУ ПОСИЛКИ</b>

🆔 <b>Замовлення:</b> #{order.order_number}
📋 <b>ТТН:</b> {order.tracking_number}

📊 <b>Статус змінено:</b>
├─ Було: {old_status or 'Невідомо'}
└─ Стало: <b>{new_status}</b>

🕐 <b>Час оновлення:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Слідкуйте за оновленнями статусу вашої посилки!</i>

🔗 <b>Корисні посилання:</b>
• <a href="https://t.me/twocomms">💬 Допомога в Telegram</a>
• <a href="https://twocomms.shop/my-orders/">📋 Мої замовлення</a>"""
        
        return message
    
    def update_all_tracking_statuses(self):
        """
        Обновляет статусы всех заказов с ТТН
        
        Returns:
            dict: Статистика обновлений
        """
        orders_with_ttn = Order.objects.filter(
            tracking_number__isnull=False
        ).exclude(tracking_number='')
        
        updated_count = 0
        error_count = 0
        
        for order in orders_with_ttn:
            try:
                if self.update_order_tracking_status(order):
                    updated_count += 1
            except Exception as e:
                print(f"Ошибка при обновлении заказа {order.order_number}: {e}")
                error_count += 1
        
        return {
            'total_orders': orders_with_ttn.count(),
            'updated': updated_count,
            'errors': error_count
        }
