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
import re
from decimal import Decimal
from typing import Optional, Dict, Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
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

    MAX_EVENT_AGE_SECONDS = 7 * 24 * 60 * 60
    MIN_EVENT_VALUE = 0.01
    DEFAULT_PREPAYMENT_VALUE = 200.0
    PHONE_MIN_LENGTH = 10
    PHONE_MAX_LENGTH = 15
    CITY_SANITIZE_RE = re.compile(r'[^a-z0-9]')
    
    def __init__(self):
        """Инициализация сервиса с настройками из ENV"""
        self.access_token = getattr(settings, 'FACEBOOK_CONVERSIONS_API_TOKEN', None)
        self.pixel_id = getattr(settings, 'FACEBOOK_PIXEL_ID', None)
        self.test_event_code = getattr(settings, 'FACEBOOK_CAPI_TEST_EVENT_CODE', None)
        self.retry_max_attempts = getattr(settings, 'FACEBOOK_CAPI_MAX_RETRIES', 3)
        self.retry_initial_delay = getattr(settings, 'FACEBOOK_CAPI_RETRY_DELAY', 1)
        self.retry_backoff = getattr(settings, 'FACEBOOK_CAPI_RETRY_BACKOFF', 2)
        
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

    def _is_valid_email(self, email: Optional[str]) -> bool:
        """Проверяет формат email согласно Django validator."""
        if not email:
            return False
        try:
            validate_email(email.strip())
            return True
        except ValidationError:
            return False

    def _clean_phone_digits(self, phone: Optional[str]) -> Optional[str]:
        """Возвращает только цифры телефона если длина валидна."""
        if not phone:
            return None
        digits = ''.join(filter(str.isdigit, str(phone)))
        if self.PHONE_MIN_LENGTH <= len(digits) <= self.PHONE_MAX_LENGTH:
            return digits
        return None

    def _normalize_city_value(self, city: Optional[str]) -> Optional[str]:
        """Удаляет пробелы и спецсимволы перед хешированием."""
        if not city:
            return None
        normalized = self.CITY_SANITIZE_RE.sub('', city.lower().strip())
        return normalized or None

    def _ensure_positive_value(
        self,
        raw_value: Optional[Any],
        order,
        context: str,
        fallback: Optional[float] = None,
    ) -> float:
        """Гарантирует положительное значение для custom_data.value."""
        try:
            value = float(raw_value or 0)
        except (TypeError, ValueError):
            value = 0.0

        if value <= 0 and fallback is not None and fallback > 0:
            logger.warning(
                "⚠️ Invalid %s value for order %s: %s. Using fallback %.2f",
                context,
                order.order_number,
                raw_value,
                fallback,
            )
            value = float(fallback)

        if value <= 0:
            logger.error(
                "❌ Invalid %s value for order %s: %s. Using %.2f",
                context,
                order.order_number,
                raw_value,
                self.MIN_EVENT_VALUE,
            )
            value = self.MIN_EVENT_VALUE

        return value

    def _calculate_event_time(self, order) -> int:
        """Возвращает event_time, ограничивая возраст события 7 днями."""
        current_time = int(time.time())
        order_created = getattr(order, 'created', None)
        if not order_created:
            logger.warning(
                "⚠️ Order %s has no creation timestamp, using current time for event_time",
                order.order_number,
            )
            return current_time

        try:
            event_time = int(order_created.timestamp())
        except Exception:
            logger.warning(
                "⚠️ Failed to read created timestamp for order %s, using current time",
                order.order_number,
            )
            return current_time

        if current_time - event_time > self.MAX_EVENT_AGE_SECONDS:
            logger.warning(
                "⚠️ Order %s created more than 7 days ago. Using current time for event_time",
                order.order_number,
            )
            return current_time
        return event_time

    def _get_response_attr(self, response, attr: str):
        """Безопасно получает атрибут из ответа SDK или словаря."""
        if response is None:
            return None
        if hasattr(response, attr):
            return getattr(response, attr)
        if isinstance(response, dict):
            return response.get(attr)
        try:
            return response[attr]
        except Exception:
            return None

    def _validate_response(self, response, order, event_name: str, event_id: str) -> bool:
        """Проверяет, что API принял событие без ошибок."""
        if response is None:
            logger.error(
                "❌ Facebook Conversions API returned empty response for %s event (%s)",
                event_name,
                order.order_number,
            )
            return False

        errors = self._get_response_attr(response, 'errors')
        if errors:
            logger.error(
                "❌ Facebook API errors for %s event (order %s, event_id %s): %s",
                event_name,
                order.order_number,
                event_id,
                errors,
            )
            return False

        warnings = self._get_response_attr(response, 'warnings')
        if warnings:
            logger.warning(
                "⚠️ Facebook API warnings for %s event (order %s): %s",
                event_name,
                order.order_number,
                warnings,
            )

        events_received = self._get_response_attr(response, 'events_received')
        try:
            events_received_value = int(events_received)
        except (TypeError, ValueError):
            events_received_value = 0 if events_received is None else events_received

        if not events_received_value:
            logger.error(
                "❌ Facebook API accepted 0 %s events for order %s (event_id %s)",
                event_name,
                order.order_number,
                event_id,
            )
            return False

        events_dropped = self._get_response_attr(response, 'events_dropped')
        if events_dropped:
            logger.warning(
                "⚠️ Facebook API dropped %s %s events for order %s",
                events_dropped,
                event_name,
                order.order_number,
            )

        return True

    def _send_request_with_retry(self, event_request, order, event_name: str):
        """Отправляет запрос в Facebook с повторными попытками при ошибках."""
        attempt = 1
        delay = self.retry_initial_delay
        while attempt <= max(1, self.retry_max_attempts):
            try:
                return event_request.execute()
            except Exception as exc:
                if attempt >= max(1, self.retry_max_attempts):
                    logger.error(
                        "❌ Failed to send %s event for order %s after %s attempts: %s",
                        event_name,
                        order.order_number,
                        attempt,
                        exc,
                        exc_info=True,
                    )
                    raise

                logger.warning(
                    "⚠️ Attempt %s/%s failed for %s event (order %s): %s. Retrying in %s s",
                    attempt,
                    self.retry_max_attempts,
                    event_name,
                    order.order_number,
                    exc,
                    delay,
                )
                time.sleep(max(0.5, delay))
                delay *= max(1, self.retry_backoff)
                attempt += 1
    
    def _prepare_user_data(self, order) -> 'UserData':
        """
        Подготавливает user_data для Advanced Matching.
        
        Advanced Matching повышает качество атрибуции событий,
        связывая серверные события с пользователями Facebook.
        """
        from facebook_business.adobjects.serverside import UserData
        
        user_data = UserData()
        
        # Email (хешированный, только валидный)
        email = None
        if order.user and order.user.email:
            email = order.user.email
        elif getattr(order, 'email', None):
            email = order.email
        if email:
            if self._is_valid_email(email):
                user_data.email = self._hash_data(email)
            else:
                logger.warning(
                    "⚠️ Invalid email for order %s skipped from Advanced Matching: %s",
                    order.order_number,
                    email,
                )
        
        # Phone (хешированный, только цифры)
        if order.phone:
            phone_digits = self._clean_phone_digits(order.phone)
            if phone_digits:
                user_data.phone = self._hash_data(phone_digits)
            else:
                logger.warning(
                    "⚠️ Invalid phone for order %s skipped from Advanced Matching: %s",
                    order.order_number,
                    order.phone,
                )
        
        # Full Name (хешированный)
        if order.full_name:
            # Разделяем на имя и фамилию
            name_parts = order.full_name.strip().split()
            if len(name_parts) >= 1:
                user_data.first_name = self._hash_data(name_parts[0])
            if len(name_parts) >= 2:
                user_data.last_name = self._hash_data(name_parts[-1])
        
        # City (хешированный с нормализацией)
        normalized_city = self._normalize_city_value(order.city)
        if normalized_city:
            user_data.city = self._hash_data(normalized_city)
        
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
        custom_data.value = self._ensure_positive_value(
            order.total_sum,
            order,
            'Purchase value',
        )
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

    def send_add_payment_info_event(
        self,
        order,
        payment_amount: Optional[float] = None,
        event_id: Optional[str] = None,
        source_url: Optional[str] = None,
        test_event_code: Optional[str] = None,
    ) -> bool:
        """
        Отправляет AddPaymentInfo событие (добавление платежных данных) в Facebook CAPI.
        Используется при создании инвойса Monobank, чтобы дедуплицировать с браузерным событием.
        """
        if not self.enabled:
            logger.warning("Facebook Conversions API disabled, skipping AddPaymentInfo event")
            return False

        try:
            resolved_event_id = (
                event_id
                or getattr(order, 'get_add_payment_event_id', lambda: None)()
                or order.get_facebook_event_id(event_type='add_payment_info')
            )
            logger.info(
                "📊 Generated AddPaymentInfo event_id for order %s: %s",
                order.order_number,
                resolved_event_id,
            )

            event_time = self._calculate_event_time(order)
            user_data = self._prepare_user_data(order)
            custom_data = self._prepare_custom_data(order)

            # Используем сумму платежа (предоплата или полная)
            value_to_send = payment_amount if payment_amount is not None else order.total_sum
            custom_data.value = self._ensure_positive_value(
                value_to_send,
                order,
                'AddPaymentInfo value',
                fallback=self.MIN_EVENT_VALUE,
            )
            custom_data.currency = 'UAH'

            event = self.Event(
                event_name='AddPaymentInfo',
                event_time=event_time,
                event_id=resolved_event_id,
                user_data=user_data,
                custom_data=custom_data,
                action_source=self.ActionSource.WEBSITE,
                event_source_url=source_url or f"https://twocomms.com/orders/{order.order_number}/"
            )

            event_request = self.EventRequest(
                pixel_id=self.pixel_id,
                events=[event]
            )
            test_code = test_event_code or self.test_event_code
            if test_code:
                event_request.test_event_code = test_code

            response = self._send_request_with_retry(event_request, order, 'AddPaymentInfo')
            if not self._validate_response(response, order, 'AddPaymentInfo', resolved_event_id):
                return False

            logger.info(
                "✅ AddPaymentInfo event sent to Facebook Conversions API: "
                "Order %s, Value %.2f UAH, Event ID: %s",
                order.order_number,
                custom_data.value,
                resolved_event_id,
            )

            # Сохраняем маркер отправки (не критично для основного потока)
            try:
                if not order.payment_payload:
                    order.payment_payload = {}
                order.payment_payload['fb_capi_add_payment_info'] = {
                    'event_name': 'AddPaymentInfo',
                    'event_id': resolved_event_id,
                    'sent_at': int(time.time()),
                    'value': custom_data.value,
                    'currency': 'UAH'
                }
                order.save(update_fields=['payment_payload'])
            except Exception as payload_err:
                logger.warning(
                    "⚠️ Failed to persist AddPaymentInfo payload for order %s: %s",
                    order.order_number,
                    payload_err,
                )

            return True
        except Exception as e:
            logger.error(
                "❌ Failed to send AddPaymentInfo event to Facebook Conversions API: %s",
                e,
                exc_info=True,
            )
            return False
    
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
            # Event ID для дедупликации - всегда генерируем детерминированный
            # НЕ используем event_id из tracking_data, так как он не сохраняется при создании заказа
            event_id = order.get_purchase_event_id()
            logger.info(
                f"📊 Generated Purchase event_id for order {order.order_number}: {event_id}"
            )
            
            # Event Time (timestamp заказа с ограничением по возрасту)
            event_time = self._calculate_event_time(order)
            
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
            
            # Отправляем с повторными попытками
            response = self._send_request_with_retry(event_request, order, 'Purchase')
            if not self._validate_response(response, order, 'Purchase', event_id):
                return False
            
            logger.info(
                f"✅ Purchase event sent to Facebook Conversions API: "
                f"Order {order.order_number}, Value {order.total_sum} UAH, "
                f"Event ID: {event_id}"
            )
            
            # Сохраняем информацию об отправке в payload
            if not order.payment_payload:
                order.payment_payload = {}
            purchase_value = custom_data.value or self._ensure_positive_value(
                order.total_sum,
                order,
                'Purchase value',
            )

            order.payment_payload['fb_conversions_api'] = {
                'event_name': 'Purchase',
                'event_id': event_id,
                'sent_at': int(time.time()),
                'value': purchase_value,
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
            # Event ID для дедупликации - всегда генерируем детерминированный
            event_id = order.get_lead_event_id()
            logger.info(
                f"📋 Generated Lead event_id for order {order.order_number}: {event_id}"
            )
            
            # Event Time
            event_time = self._calculate_event_time(order)
            
            # User Data
            user_data = self._prepare_user_data(order)
            
            # Custom Data (для Lead - базовая информация)
            # Для prepaid используем сумму предоплаты, не полную сумму заказа
            custom_data = self.CustomData()
            if order.payment_status == 'prepaid':
                prepayment_amount = order.get_prepayment_amount()
                prepayment_value = self._ensure_positive_value(
                    prepayment_amount,
                    order,
                    'Lead prepayment value',
                    fallback=self.DEFAULT_PREPAYMENT_VALUE,
                )
                custom_data.value = prepayment_value
            else:
                custom_data.value = self._ensure_positive_value(
                    order.total_sum,
                    order,
                    'Lead value',
                )
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
            response = self._send_request_with_retry(event_request, order, 'Lead')
            if not self._validate_response(response, order, 'Lead', event_id):
                return False
            
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
