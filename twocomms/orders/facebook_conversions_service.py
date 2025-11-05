"""
Facebook Conversions API Service

Сервис для отправки серверных событий (Purchase, Lead) в Facebook через Conversions API.
Используется для автоматической отправки событий при изменении статуса заказа.

Документация Facebook Conversions API:
https://developers.facebook.com/docs/marketing-api/conversions-api

Установка зависимостей:
pip install facebook-business

ENV переменные (настраиваются в cPanel):
- FACEBOOK_CONVERSIONS_API_TOKEN: Access Token для Conversions API
- FACEBOOK_PIXEL_ID: ID Facebook Pixel
"""

import logging
import hashlib
import time
from decimal import Decimal
from typing import Optional, Dict, Any

from django.conf import settings
from storefront.utils.analytics_helpers import get_offer_id as build_offer_id

logger = logging.getLogger(__name__)


class FacebookConversionsService:
    """
    Сервис для работы с Facebook Conversions API.
    
    Основные возможности:
    - Отправка Purchase событий при полной оплате
    - Отправка Lead событий при предоплате
    - Advanced Matching (email, phone, user_data)
    - Дедупликация с клиентскими событиями через event_id
    """
    
    def __init__(self):
        """Инициализация сервиса с настройками из ENV"""
        self.access_token = getattr(settings, 'FACEBOOK_CONVERSIONS_API_TOKEN', None)
        self.pixel_id = getattr(settings, 'FACEBOOK_PIXEL_ID', None)
        self.test_event_code = getattr(settings, 'FACEBOOK_CAPI_TEST_EVENT_CODE', None)
        
        # Проверяем наличие обязательных настроек
        if not self.access_token or not self.pixel_id:
            logger.error(
                "❌ Facebook Conversions API не настроен! "
                "Необходимо установить FACEBOOK_CONVERSIONS_API_TOKEN и FACEBOOK_PIXEL_ID в ENV. "
                f"Access Token: {'установлен' if self.access_token else 'НЕ установлен'}, "
                f"Pixel ID: {'установлен' if self.pixel_id else 'НЕ установлен'}"
            )
            self.enabled = False
        else:
            self.enabled = True
            logger.info(
                f"✅ Facebook Conversions API configured: Pixel ID={self.pixel_id}"
            )
            
        # Импортируем Facebook SDK только если настройки есть
        if self.enabled:
            try:
                from facebook_business.adobjects.serverside import (
                    Event,
                    UserData,
                    CustomData,
                    EventRequest,
                    ActionSource
                )
                from facebook_business.api import FacebookAdsApi
                
                self.Event = Event
                self.UserData = UserData
                self.CustomData = CustomData
                self.EventRequest = EventRequest
                self.ActionSource = ActionSource
                
                # Инициализируем Facebook API
                FacebookAdsApi.init(access_token=self.access_token)
                
                logger.info("✅ Facebook Conversions API initialized successfully")
            except ImportError:
                logger.error(
                    "facebook-business SDK not installed! "
                    "Install with: pip install facebook-business"
                )
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Facebook Conversions API: {e}")
                self.enabled = False
    
    def _hash_data(self, value: Optional[str]) -> Optional[str]:
        """
        Хеширует данные для Facebook (SHA-256).
        Facebook требует хешированные email и phone для приватности.
        """
        if not value:
            return None
        
        # Очищаем и нормализуем значение
        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        
        # Хешируем SHA-256
        return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()
    
    def _prepare_user_data(self, order) -> 'UserData':
        """
        Подготавливает user_data для Advanced Matching.
        
        Advanced Matching повышает качество атрибуции событий,
        связывая серверные события с пользователями Facebook.
        """
        from facebook_business.adobjects.serverside import UserData
        
        user_data = UserData()
        
        # Email (хешированный)
        if order.user and order.user.email:
            user_data.email = self._hash_data(order.user.email)
        
        # Phone (хешированный, только цифры)
        if order.phone:
            # Очищаем номер телефона (только цифры)
            phone_digits = ''.join(filter(str.isdigit, order.phone))
            if phone_digits:
                user_data.phone = self._hash_data(phone_digits)
        
        # Full Name (хешированный)
        if order.full_name:
            # Разделяем на имя и фамилию
            name_parts = order.full_name.strip().split()
            if len(name_parts) >= 1:
                user_data.first_name = self._hash_data(name_parts[0])
            if len(name_parts) >= 2:
                user_data.last_name = self._hash_data(name_parts[-1])
        
        # City (хешированный)
        if order.city:
            user_data.city = self._hash_data(order.city)
        
        # Country (для Украины)
        user_data.country_code = self._hash_data('ua')

        tracking_data = {}
        if order.payment_payload and isinstance(order.payment_payload, dict):
            tracking_data = order.payment_payload.get('tracking') or {}

        fbp_value = tracking_data.get('fbp')
        if fbp_value:
            user_data.fbp = fbp_value

        fbc_value = tracking_data.get('fbc')
        if fbc_value:
            user_data.fbc = fbc_value

        external_source = tracking_data.get('external_id')
        if not external_source:
            # Fallback: генерируем external_id если не передан из checkout
            if order.user_id:
                external_source = f"user:{order.user_id}"
            elif order.session_key:
                external_source = f"session:{order.session_key}"
            elif order.order_number:
                external_source = f"order:{order.order_number}"
            
            if external_source:
                logger.info(
                    f"📊 External ID generated as fallback for order {order.order_number}: {external_source}"
                )
        else:
            logger.debug(
                f"📊 External ID from tracking_data for order {order.order_number}: {external_source}"
            )
        
        if external_source:
            hashed_external = self._hash_data(external_source)
            if hashed_external:
                user_data.external_id = hashed_external
                logger.debug(
                    f"📊 External ID hashed for order {order.order_number}: {hashed_external[:16]}..."
                )
        else:
            logger.warning(
                f"⚠️ External ID not available for order {order.order_number} - this may reduce match quality!"
            )
        
        # Client IP address (если есть в payload)
        if order.payment_payload and isinstance(order.payment_payload, dict):
            client_ip = order.payment_payload.get('client_ip_address')
            if client_ip:
                user_data.client_ip_address = client_ip
            
            # User Agent
            user_agent = order.payment_payload.get('client_user_agent')
            if user_agent:
                user_data.client_user_agent = user_agent
        
        return user_data
    
    def _prepare_custom_data(self, order) -> 'CustomData':
        """
        Подготавливает custom_data с деталями заказа.
        
        Включает:
        - value: общая сумма
        - currency: валюта (UAH)
        - content_ids: список offer_ids (TC-{id}-{variant}-{SIZE})
        - content_name: название товаров
        - content_type: тип контента (product)
        - num_items: количество товаров
        """
        from facebook_business.adobjects.serverside import CustomData, Content
        
        custom_data = CustomData()
        
        # Основные данные
        custom_data.value = float(order.total_sum)
        custom_data.currency = 'UAH'
        
        # Получаем товары заказа
        order_items = order.items.select_related('product', 'color_variant').all()
        
        if order_items:
            # Content IDs (offer_ids в формате фида)
            content_ids = []
            for item in order_items:
                # Генерируем offer_id для каждого товара
                color_variant_id = item.color_variant.id if item.color_variant else None
                size = (item.size or 'S').upper()  # Размер из OrderItem или S по умолчанию
                
                # Используем метод из Product модели для генерации offer_id
                getter = getattr(item.product, "get_offer_id", None)
                if callable(getter):
                    offer_id = getter(color_variant_id, size)
                else:
                    offer_id = build_offer_id(item.product.id, color_variant_id, size)
                content_ids.append(offer_id)
            
            custom_data.content_ids = content_ids
            
            # Content Names (названия товаров)
            content_names = [item.title for item in order_items]
            custom_data.content_name = ', '.join(content_names[:3])  # Первые 3 товара
            
            # Content Type
            custom_data.content_type = 'product'
            
            # Num Items (общее количество)
            custom_data.num_items = sum(item.qty for item in order_items)
            
            # Contents (детальная информация о товарах)
            contents = []
            for item in order_items:
                # Генерируем offer_id для каждого товара
                color_variant_id = item.color_variant.id if item.color_variant else None
                size = (item.size or 'S').upper()
                getter = getattr(item.product, "get_offer_id", None)
                if callable(getter):
                    offer_id = getter(color_variant_id, size)
                else:
                    offer_id = build_offer_id(item.product.id, color_variant_id, size)
                
                content = Content(
                    product_id=offer_id,  # Используем offer_id вместо product.id
                    quantity=item.qty,
                    item_price=float(item.unit_price),
                    title=item.title
                )
                contents.append(content)
            custom_data.contents = contents
        
        # Order ID
        custom_data.order_id = order.order_number
        
        return custom_data
    
    def send_purchase_event(
        self,
        order,
        source_url: Optional[str] = None,
        test_event_code: Optional[str] = None,
    ) -> bool:
        """
        Отправляет Purchase событие в Facebook Conversions API.
        
        Используется когда:
        - Заказ полностью оплачен (payment_status = 'paid')
        - Товар получен через Новую Почту и автоматически оплачен
        
        Args:
            order: Объект заказа (Order model)
            source_url: URL страницы (опционально)
            
        Returns:
            bool: True если событие отправлено успешно
        """
        if not self.enabled:
            logger.warning("Facebook Conversions API disabled, skipping Purchase event")
            return False
        
        try:
            # Event ID для дедупликации (приоритет - из tracking_data)
            event_id = None
            if order.payment_payload and isinstance(order.payment_payload, dict):
                tracking_data = order.payment_payload.get('tracking') or {}
                event_id = tracking_data.get('event_id')
                if event_id:
                    logger.info(
                        f"📊 Using event_id from tracking_data for order {order.order_number}: {event_id}"
                    )
            
            # Fallback: генерируем event_id если не передан
            if not event_id:
                event_id = order.get_facebook_event_id()
                logger.info(
                    f"📊 Generated fallback event_id for order {order.order_number}: {event_id}"
                )
            
            # Event Time (timestamp заказа)
            event_time = int(order.created.timestamp())
            
            # User Data (Advanced Matching)
            user_data = self._prepare_user_data(order)
            
            # Custom Data (детали покупки)
            custom_data = self._prepare_custom_data(order)
            
            # Создаем событие
            event = self.Event(
                event_name='Purchase',
                event_time=event_time,
                event_id=event_id,
                user_data=user_data,
                custom_data=custom_data,
                action_source=self.ActionSource.WEBSITE,
                event_source_url=source_url or f"https://twocomms.com/orders/{order.order_number}/"
            )
            
            # Создаем запрос
            event_request = self.EventRequest(
                pixel_id=self.pixel_id,
                events=[event]
            )
            
            # Добавляем test_event_code если есть
            test_code = test_event_code or self.test_event_code
            if test_code:
                event_request.test_event_code = test_code
            
            # Отправляем
            response = event_request.execute()
            
            logger.info(
                f"✅ Purchase event sent to Facebook Conversions API: "
                f"Order {order.order_number}, Value {order.total_sum} UAH, "
                f"Event ID: {event_id}"
            )
            
            # Сохраняем информацию об отправке в payload
            if not order.payment_payload:
                order.payment_payload = {}
            order.payment_payload['fb_conversions_api'] = {
                'event_name': 'Purchase',
                'event_id': event_id,
                'sent_at': int(time.time()),
                'value': float(order.total_sum),
                'currency': 'UAH'
            }
            order.save(update_fields=['payment_payload'])
            
            return True
            
        except Exception as e:
            logger.error(
                f"❌ Failed to send Purchase event to Facebook Conversions API: {e}",
                exc_info=True
            )
            return False
    
    def send_lead_event(
        self,
        order,
        source_url: Optional[str] = None,
        test_event_code: Optional[str] = None,
    ) -> bool:
        """
        Отправляет Lead событие в Facebook Conversions API.
        
        Используется когда:
        - Предоплата внесена (payment_status = 'prepaid')
        - Заявка без оплаты (payment_status = 'unpaid', но заказ создан)
        
        Args:
            order: Объект заказа (Order model)
            source_url: URL страницы (опционально)
            
        Returns:
            bool: True если событие отправлено успешно
        """
        if not self.enabled:
            logger.warning("Facebook Conversions API disabled, skipping Lead event")
            return False
        
        try:
            # Event ID для дедупликации (приоритет - из tracking_data)
            event_id = None
            if order.payment_payload and isinstance(order.payment_payload, dict):
                tracking_data = order.payment_payload.get('tracking') or {}
                event_id = tracking_data.get('lead_event_id') or tracking_data.get('event_id')
                if event_id:
                    logger.info(
                        f"📊 Using lead event_id from tracking_data for order {order.order_number}: {event_id}"
                    )
            
            # Fallback: детерминированный event_id для Lead
            if not event_id:
                event_id = order.get_facebook_event_id(event_type='lead')
                logger.info(
                    f"📊 Generated fallback lead event_id for order {order.order_number}: {event_id}"
                )
            
            # Event Time
            event_time = int(order.created.timestamp())
            
            # User Data
            user_data = self._prepare_user_data(order)
            
            # Custom Data (для Lead - базовая информация)
            # Для prepaid используем сумму предоплаты, не полную сумму заказа
            custom_data = self.CustomData()
            if order.payment_status == 'prepaid':
                prepayment_amount = order.get_prepayment_amount()
                prepayment_value = float(prepayment_amount or 0)
                if prepayment_value <= 0:
                    prepayment_value = 200.0  # стандартная сумма предоплаты
                custom_data.value = prepayment_value
            else:
                custom_data.value = float(order.total_sum)
            custom_data.currency = 'UAH'
            custom_data.content_name = f"Lead: Order {order.order_number}"
            
            # Создаем событие
            event = self.Event(
                event_name='Lead',
                event_time=event_time,
                event_id=event_id,
                user_data=user_data,
                custom_data=custom_data,
                action_source=self.ActionSource.WEBSITE,
                event_source_url=source_url or f"https://twocomms.com/orders/{order.order_number}/"
            )
            
            # Создаем запрос
            event_request = self.EventRequest(
                pixel_id=self.pixel_id,
                events=[event]
            )
            
            # Добавляем test_event_code если есть
            test_code = test_event_code or self.test_event_code
            if test_code:
                event_request.test_event_code = test_code
            
            # Отправляем
            response = event_request.execute()
            
            logger.info(
                f"✅ Lead event sent to Facebook Conversions API: "
                f"Order {order.order_number}, Event ID: {event_id}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"❌ Failed to send Lead event to Facebook Conversions API: {e}",
                exc_info=True
            )
            return False
    
    def send_event_for_order_status(self, order) -> bool:
        """
        Автоматически определяет и отправляет нужное событие на основе статуса заказа.
        
        Логика:
        - payment_status = 'paid' → Purchase
        - payment_status = 'prepaid' → Lead
        - payment_status = 'unpaid' → Lead (если заказ создан через форму)
        
        Args:
            order: Объект заказа
            
        Returns:
            bool: True если событие отправлено
        """
        if order.payment_status == 'paid':
            return self.send_purchase_event(order)
        elif order.payment_status == 'prepaid':
            return self.send_lead_event(order)
        elif order.payment_status in ('unpaid', 'checking'):
            logger.info(
                "Skipping Facebook event for order %s with payment_status=%s",
                order.order_number,
                order.payment_status,
            )
            return False
        else:
            logger.warning(f"Unknown payment_status for order {order.order_number}: {order.payment_status}")
            return False


# Глобальный экземпляр сервиса
_facebook_service = None

def get_facebook_conversions_service() -> FacebookConversionsService:
    """Возвращает глобальный экземпляр Facebook Conversions Service (Singleton)"""
    global _facebook_service
    if _facebook_service is None:
        _facebook_service = FacebookConversionsService()
    return _facebook_service
