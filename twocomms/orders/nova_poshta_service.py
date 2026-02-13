"""
Сервис для работы с API Новой Почты

Этот модуль обеспечивает интеграцию с Nova Poshta API для отслеживания статусов посылок.
Основные функции:
- Получение статуса посылки по ТТН
- Автоматическое обновление статусов заказов
- Отправка уведомлений в Telegram и Facebook
- Обработка ошибок API с детальным логированием
"""
import requests
import json
import logging
import time
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from .models import Order
from .telegram_notifications import TelegramNotifier

logger = logging.getLogger(__name__)


class NovaPoshtaAPIError(Exception):
    """Ошибка при работе с Nova Poshta API"""


class NovaPoshtaService:
    """
    Сервис для работы с API Новой Почты

    Документация API: https://api.novapost.com/developers/index.html#overview

    Основные методы:
    - get_tracking_info(ttn_number) - получить статус посылки
    - update_order_tracking_status(order) - обновить статус заказа
    - update_all_tracking_statuses() - обновить все заказы с ТТН
    """

    API_URL = "https://api.novaposhta.ua/v2.0/json/"

    # Коды статусов Nova Poshta (StatusCode)
    STATUS_ACCEPTED = 1  # Прийнято
    STATUS_SENT = 2  # Відправлено
    STATUS_ARRIVED_CITY = 3  # Прибуло в місто
    STATUS_ARRIVED_WAREHOUSE = 4  # Прибуло в відділення
    STATUS_RECEIVED_OLD = 5  # Отримано (старый формат)
    STATUS_REFUSED = 6  # Відмова
    STATUS_SENT_ALT = 7  # Відправлено (альтернативный)
    STATUS_UNKNOWN = 8  # Невідомо
    STATUS_RECEIVED = 9  # Отримано одержувачем (ОСНОВНОЙ КОД ДЛЯ ПОЛУЧЕНИЯ)
    STATUS_RETURNED = 10  # Повернено відправнику
    STATUS_REFUSED_ALT = 11  # Відмова (альтернативный)

    # Настройки повторных запросов
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # секунды
    REQUEST_TIMEOUT = 10  # секунды

    # Настройки rate limiting
    RATE_LIMIT_KEY = 'nova_poshta_api_calls'
    RATE_LIMIT_MAX_CALLS = 60  # максимум вызовов
    RATE_LIMIT_PERIOD = 60  # за период в секундах

    # Ключи кеша
    LAST_UPDATE_CACHE_KEY = 'nova_poshta_last_update'
    UPDATE_LOCK_CACHE_KEY = 'nova_poshta_update_lock'
    FALLBACK_CHECK_MULTIPLIER = 3  # fallback после N интервалов cron
    UPDATE_LOCK_TIMEOUT = 10 * 60  # 10 минут

    def __init__(self):
        self.api_key = getattr(settings, 'NOVA_POSHTA_API_KEY', '')
        self.api_url = getattr(settings, 'NOVA_POSHTA_API_URL', self.API_URL)
        self.telegram_notifier = TelegramNotifier()

        if not self.api_key:
            logger.warning("NOVA_POSHTA_API_KEY не настроен в settings")
        if self.api_url != self.API_URL:
            logger.debug(f"Using custom Nova Poshta API URL: {self.api_url}")

    def _check_rate_limit(self):
        """
        Проверяет и применяет rate limiting для API запросов

        Returns:
            bool: True если запрос можно выполнить, False если лимит превышен
        """
        current_calls = cache.get(self.RATE_LIMIT_KEY, 0)

        if current_calls >= self.RATE_LIMIT_MAX_CALLS:
            logger.warning(
                f"Rate limit exceeded: {current_calls}/{self.RATE_LIMIT_MAX_CALLS} "
                f"calls in {self.RATE_LIMIT_PERIOD}s"
            )
            return False

        # Увеличиваем счетчик
        cache.set(
            self.RATE_LIMIT_KEY,
            current_calls + 1,
            self.RATE_LIMIT_PERIOD
        )
        return True

    def get_tracking_info(self, ttn_number, phone=None):
        """
        Получает информацию о статусе посылки по ТТН

        Использует метод API: TrackingDocument.getStatusDocuments
        Документация: https://api.novapost.com/developers/index.html#tracking

        Args:
            ttn_number (str): Номер ТТН (накладной)
            phone (str, optional): Телефон для более точного поиска

        Returns:
            dict: Информация о посылке с полями:
                - Number: номер ТТН
                - Status: текстовый статус
                - StatusCode: числовой код статуса (9 = получено)
                - StatusDescription: описание статуса
                - DateCreated: дата создания
                - DateLastMovementStatus: дата последнего изменения
                и другие поля
            None: В случае ошибки или если посылка не найдена

        Raises:
            NovaPoshtaAPIError: При критических ошибках API
        """
        if not ttn_number or not self.api_key:
            logger.warning(
                f"Cannot get tracking info: "
                f"ttn_number={'present' if ttn_number else 'missing'}, "
                f"api_key={'present' if self.api_key else 'missing'}"
            )
            return None

        # Проверяем rate limit
        if not self._check_rate_limit():
            logger.error(f"Rate limit exceeded for TTN {ttn_number}")
            return None

        logger.debug(f"Requesting tracking info for TTN: {ttn_number}")

        payload = {
            "apiKey": self.api_key,
            "modelName": "TrackingDocument",
            "calledMethod": "getStatusDocuments",
            "methodProperties": {
                "Documents": [
                    {
                        "DocumentNumber": ttn_number,
                        "Phone": phone or ""
                    }
                ]
            }
        }

        # Попытки с повторными запросами при сетевых ошибках
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"API request attempt {attempt + 1}/{self.MAX_RETRIES}")

                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=self.REQUEST_TIMEOUT
                )
                response.raise_for_status()

                data = response.json()
                logger.debug(f"API response for TTN {ttn_number}: {json.dumps(data, ensure_ascii=False)}")

                # Проверяем наличие ошибок в ответе API
                if data.get('errors') and len(data.get('errors', [])) > 0:
                    errors = data.get('errors', [])
                    error_msg = ', '.join(str(e) for e in errors)
                    logger.error(f"Nova Poshta API errors for TTN {ttn_number}: {error_msg}")
                    return None

                # Проверяем предупреждения (warnings)
                if data.get('warnings') and len(data.get('warnings', [])) > 0:
                    warnings = data.get('warnings', [])
                    warning_msg = ', '.join(str(w) for w in warnings)
                    logger.warning(f"Nova Poshta API warnings for TTN {ttn_number}: {warning_msg}")

                # Проверяем успешность запроса
                if not data.get('success'):
                    logger.warning(f"API returned success=false for TTN {ttn_number}")
                    return None

                # Проверяем наличие данных
                if not data.get('data'):
                    logger.warning(f"No data in API response for TTN {ttn_number}")
                    return None

                # Обрабатываем данные (может быть массив или объект)
                tracking_data = None
                if isinstance(data['data'], list):
                    if len(data['data']) == 0:
                        logger.warning(f"Empty data array for TTN {ttn_number}")
                        return None
                    tracking_data = data['data'][0]
                elif isinstance(data['data'], dict):
                    tracking_data = data['data']
                else:
                    logger.error(
                        f"Unexpected data type for TTN {ttn_number}: "
                        f"{type(data['data'])}"
                    )
                    return None

                # Логируем полученную информацию
                status = tracking_data.get('Status', 'Unknown')
                status_code = tracking_data.get('StatusCode')
                status_description = tracking_data.get('StatusDescription', '')

                logger.info(
                    f"Tracking info for TTN {ttn_number}: "
                    f"Status='{status}', StatusCode={status_code}, "
                    f"Description='{status_description}'"
                )

                return tracking_data

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    f"Timeout error for TTN {ttn_number} "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

            except requests.exceptions.RequestException as e:
                last_error = e
                logger.error(
                    f"Network error for TTN {ttn_number} "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

            except ValueError as e:
                last_error = e
                logger.error(f"JSON parsing error for TTN {ttn_number}: {e}")
                return None

            except Exception as e:
                last_error = e
                logger.exception(f"Unexpected error for TTN {ttn_number}: {e}")
                return None

        # Все попытки исчерпаны
        logger.error(
            f"Failed to get tracking info for TTN {ttn_number} "
            f"after {self.MAX_RETRIES} attempts. Last error: {last_error}"
        )
        return None

    def update_order_tracking_status(self, order):
        """
        Обновляет статус посылки для заказа

        Алгоритм:
        1. Получает информацию о статусе через API
        2. Проверяет изменился ли статус
        3. Обновляет shipment_status в заказе
        4. Автоматически меняет status на 'done' если StatusCode=9 (получено)
        5. Меняет payment_status на 'paid' при получении
        6. Отправляет Purchase событие в Facebook
        7. Отправляет уведомления в Telegram

        Args:
            order (Order): Заказ для обновления

        Returns:
            bool: True если статус обновлен, False если нет
        """
        if not order.tracking_number:
            logger.debug(f"Order {order.order_number}: no tracking number")
            return False

        logger.info(f"Updating tracking status for order {order.order_number}")

        tracking_info = self.get_tracking_info(order.tracking_number)

        if not tracking_info:
            logger.warning(f"Failed to get tracking info for order {order.order_number}")
            return False

        # Извлекаем данные из ответа API
        status = tracking_info.get('Status', '')
        status_code = tracking_info.get('StatusCode')
        status_description = tracking_info.get('StatusDescription', '')

        # Нормализуем код статуса (может приходить как строка)
        try:
            status_code = int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            logger.warning(
                f"Order {order.order_number}: unexpected StatusCode format "
                f"({status_code})"
            )
            status_code = None

        # Формируем полное описание статуса для сохранения
        full_status = f"{status} - {status_description}" if status_description else status

        # КРИТИЧЕСКИ ВАЖНО: Сравниваем только основной Status (без description)
        # для определения изменения статуса. Description может меняться каждый раз
        # (например, добавляется время), но это не означает изменение статуса.
        current_status_base = (order.shipment_status or '').split(' - ')[0].strip()
        new_status_base = status.strip()

        # Проверяем, изменился ли основной статус
        status_changed = current_status_base != new_status_base

        if status_changed:
            old_status = order.shipment_status
            old_status_base = current_status_base

            # Сохраняем полное описание статуса (с description) для отображения
            order.shipment_status = full_status.strip()
            order.shipment_status_updated = timezone.now()

            logger.info(
                f"Order {order.order_number}: shipment_status changed "
                f"from '{old_status_base}' to '{new_status_base}' "
                f"(full: '{old_status}' -> '{full_status}')"
            )

            # Автоматически меняем статус заказа при получении посылки
            order_status_changed = self._update_order_status_if_delivered(
                order, status, status_description, status_code
            )

            # Явно указываем поля для обновления для гарантии сохранения
            try:
                order.save(update_fields=['shipment_status', 'shipment_status_updated', 'status', 'payment_status'])
                logger.debug(f"Order {order.order_number}: changes saved successfully")
            except Exception as e:
                logger.error(
                    f"Order {order.order_number}: failed to save changes: {e}",
                    exc_info=True
                )
                # Пытаемся сохранить еще раз без update_fields
                try:
                    order.save()
                    logger.info(f"Order {order.order_number}: saved without update_fields")
                except Exception as e2:
                    logger.error(
                        f"Order {order.order_number}: failed to save even without update_fields: {e2}",
                        exc_info=True
                    )
                    return False

            # Отправляем уведомления только если статус действительно изменился
            if order_status_changed:
                self._send_delivery_notification(order, full_status)
            else:
                self._send_status_notification(order, old_status, full_status)

            return True
        else:
            # Если статус посылки не изменился, но заказ еще не "done",
            # проверяем, нужно ли изменить статус заказа
            if order.status != 'done':
                order_status_changed = self._update_order_status_if_delivered(
                    order, status, status_description, status_code
                )
                if order_status_changed:
                    # Явно указываем поля для обновления для гарантии сохранения
                    try:
                        order.save(update_fields=['status', 'payment_status'])
                        logger.debug(f"Order {order.order_number}: order status changes saved successfully")
                    except Exception as e:
                        logger.error(
                            f"Order {order.order_number}: failed to save order status changes: {e}",
                            exc_info=True
                        )
                        # Пытаемся сохранить еще раз без update_fields
                        try:
                            order.save()
                            logger.info(f"Order {order.order_number}: saved without update_fields")
                        except Exception as e2:
                            logger.error(
                                f"Order {order.order_number}: failed to save even without update_fields: {e2}",
                                exc_info=True
                            )
                            return False

                    self._send_delivery_notification(order, full_status)
                    logger.info(
                        f"Order {order.order_number}: status changed to 'done' "
                        f"without shipment_status change"
                    )
                    return True

        logger.debug(f"Order {order.order_number}: no changes")
        return False

    def _update_order_status_if_delivered(self, order, status, status_description, status_code=None):
        """
        Автоматически меняет статус заказа на 'done' при получении посылки.

        ЛОГИКА ОПРЕДЕЛЕНИЯ ПОЛУЧЕНИЯ:
        1. ПРИОРИТЕТ: Проверка StatusCode == 9 (надежный метод)
        2. РЕЗЕРВ: Проверка по ключевым словам в тексте статуса

        При получении посылки:
        1. Меняет status на 'done' (получено)
        2. Если payment_status != 'paid' → меняет на 'paid'
        3. Отправляет Purchase событие в Facebook Conversions API
        4. Отправляет уведомление админу

        Args:
            order (Order): Заказ
            status (str): Статус посылки (текст)
            status_description (str): Описание статуса (текст)
            status_code (int, optional): Код статуса Nova Poshta (StatusCode)

        Returns:
            bool: True если статус заказа был изменен
        """
        # МЕТОД 1: Проверка по коду статуса (НАДЕЖНО)
        is_delivered_by_code = status_code == self.STATUS_RECEIVED

        # МЕТОД 2: Проверка по ключевым словам (РЕЗЕРВНЫЙ)
        delivered_keywords = [
            'отримано', 'получено', 'доставлено', 'вручено',
            'отримано отримувачем', 'получено получателем',
            'отримано одержувачем', 'вручено адресату'
        ]

        status_lower = (status or '').lower().strip()
        description_lower = (status_description or '').lower().strip()

        is_delivered_by_keywords = any(
            keyword in status_lower or keyword in description_lower
            for keyword in delivered_keywords
        )

        # Объединяем результаты (приоритет StatusCode)
        is_delivered = is_delivered_by_code or is_delivered_by_keywords

        # Логируем анализ
        logger.debug(
            f"Order {order.order_number} delivery check: "
            f"StatusCode={status_code}, is_delivered_by_code={is_delivered_by_code}, "
            f"is_delivered_by_keywords={is_delivered_by_keywords}, "
            f"final_is_delivered={is_delivered}"
        )

        # Если посылка получена и статус заказа еще не 'done'
        if is_delivered and order.status != 'done':
            old_order_status = order.status
            old_payment_status = order.payment_status

            # 1. Меняем статус заказа
            order.status = 'done'
            logger.info(
                f"✅ Order {order.order_number}: status changed from "
                f"'{old_order_status}' to 'done' (parcel received, StatusCode={status_code})"
            )

            # 2. Автоматически меняем payment_status на 'paid' если посылка получена
            # ВАЖНО: Когда посылка получена (отримано), статус оплаты меняется на 'paid'
            # независимо от того, была ли предоплата или нет.
            # Предоплата (prepaid) меняется на 'paid' только когда посылка полностью получена.
            payment_status_changed = False
            if order.payment_status != 'paid':
                order.payment_status = 'paid'
                payment_status_changed = True
                logger.info(
                    f"💰 Order {order.order_number}: payment_status changed "
                    f"from '{old_payment_status}' to 'paid' (parcel received - full payment)"
                )

                # 3. Отправляем Purchase событие в Facebook Conversions API
                self._send_facebook_purchase_event(order)
            else:
                logger.debug(
                    f"💰 Order {order.order_number}: payment_status already 'paid', "
                    f"no change needed"
                )

            # 4. Отправляем уведомление админу об автоматическом изменении статуса
            self._send_admin_delivery_notification(order, old_order_status, payment_status_changed)

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
                payment_payload = order.payment_payload or {}
                facebook_events = payment_payload.get('facebook_events', {})

                if facebook_events.get('purchase_sent'):
                    logger.info(
                        f"📊 Facebook Purchase event already sent for order {order.order_number}, skipping duplicate"
                    )
                    return

                success = fb_service.send_purchase_event(order)
                if success:
                    facebook_events['purchase_sent'] = True
                    facebook_events['purchase_sent_at'] = timezone.now().isoformat()
                    payment_payload['facebook_events'] = facebook_events
                    order.payment_payload = payment_payload
                    try:
                        order.save(update_fields=['payment_payload'])
                    except Exception:
                        order.save()
                    logger.info(f"📊 Facebook Purchase event sent for order {order.order_number}")
                else:
                    logger.warning(f"⚠️ Failed to send Facebook Purchase event for order {order.order_number}")
            else:
                logger.debug("Facebook Conversions API not enabled, skipping Purchase event")

        except Exception as e:
            logger.exception(f"❌ Error sending Facebook Purchase event for order {order.order_number}: {e}")

    def _send_admin_delivery_notification(self, order, old_status, payment_status_changed):
        """
        Отправляет уведомление админу об автоматическом изменении статуса заказа

        Args:
            order (Order): Заказ
            old_status (str): Старый статус заказа
            payment_status_changed (bool): Изменился ли payment_status
        """
        if not self.telegram_notifier.is_configured():
            logger.debug("Telegram notifier not configured, skipping admin notification")
            return

        status_display = {
            'new': 'В обробці',
            'prep': 'Готується до відправлення',
            'ship': 'Відправлено',
            'done': 'Отримано',
            'cancelled': 'Скасовано',
        }

        old_status_text = status_display.get(old_status, old_status)
        new_status_text = status_display.get('done', 'Отримано')

        message = f"""🤖 <b>АВТОМАТИЧНЕ ОНОВЛЕННЯ СТАТУСУ</b>

🆔 <b>Замовлення:</b> #{order.order_number}
📋 <b>ТТН:</b> {order.tracking_number or 'Не вказано'}

📊 <b>Статус замовлення:</b>
├─ Було: {old_status_text}
└─ Стало: <b>{new_status_text}</b>

"""

        if payment_status_changed:
            message += "💰 <b>Статус оплати:</b> автоматично змінено на <b>ОПЛАЧЕНО</b>\n"
            message += "📊 <b>Facebook Pixel:</b> Purchase подія відправлена\n"
            message += "\n"

        message += f"""👤 <b>Клієнт:</b> {order.full_name}
📞 <b>Телефон:</b> {order.phone}
🏙️ <b>Місто:</b> {order.city}
💰 <b>Сума:</b> {order.total_sum} грн

🕐 <b>Час оновлення:</b> {timezone.now().strftime('%d.%m.%Y %H:%M')}

<i>Статус змінено автоматично через API Нової Пошти</i>"""

        try:
            self.telegram_notifier.send_admin_message(message)
            logger.debug(f"Admin notification sent for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send admin notification for order {order.order_number}: {e}")

    def _send_delivery_notification(self, order, shipment_status):
        """
        Отправляет специальное уведомление о получении посылки

        Args:
            order (Order): Заказ
            shipment_status (str): Статус посылки
        """
        if not order.user:
            logger.debug(f"Order {order.order_number}: no user, skipping delivery notification")
            return

        # Проверяем есть ли telegram_id у пользователя
        try:
            userprofile = getattr(order.user, 'userprofile', None)
            if userprofile is None:
                logger.debug(f"Order {order.order_number}: user has no profile")
                return

            telegram_id = getattr(userprofile, 'telegram_id', None)
            if not telegram_id:
                logger.debug(f"Order {order.order_number}: user has no telegram_id")
                return
        except (AttributeError, ObjectDoesNotExist) as e:
            logger.debug(
                f"Error accessing userprofile for order {order.order_number}: {e}"
            )
            return

        # Формируем сообщение о доставке
        message = self._format_delivery_message(order, shipment_status)

        # Отправляем личное сообщение пользователю
        try:
            self.telegram_notifier.send_personal_message(telegram_id, message)
            logger.info(f"Delivery notification sent to user for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send delivery notification for order {order.order_number}: {e}")

    def _send_status_notification(self, order, old_status, new_status):
        """
        Отправляет уведомление об изменении статуса в Telegram

        Args:
            order (Order): Заказ
            old_status (str): Старый статус
            new_status (str): Новый статус
        """
        if not order.user:
            logger.debug(f"Order {order.order_number}: no user, skipping status notification")
            return

        # Проверяем есть ли telegram_id у пользователя
        try:
            userprofile = getattr(order.user, 'userprofile', None)
            if userprofile is None:
                logger.debug(f"Order {order.order_number}: user has no profile")
                return

            telegram_id = getattr(userprofile, 'telegram_id', None)
            if not telegram_id:
                logger.debug(f"Order {order.order_number}: user has no telegram_id")
                return
        except (AttributeError, ObjectDoesNotExist) as e:
            logger.debug(
                f"Error accessing userprofile for order {order.order_number}: {e}"
            )
            return

        # Формируем сообщение
        message = self._format_status_message(order, old_status, new_status)

        # Отправляем личное сообщение пользователю
        try:
            self.telegram_notifier.send_personal_message(telegram_id, message)
            logger.info(f"Status notification sent to user for order {order.order_number}")
        except Exception as e:
            logger.error(f"Failed to send status notification for order {order.order_number}: {e}")

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

        Фильтрует заказы:
        - У которых есть tracking_number
        - Которые не в статусе 'done' или 'cancelled'

        Returns:
            dict: Статистика обновлений:
                - total_orders: общее количество заказов с ТТН
                - processed: обработано заказов
                - updated: обновлено статусов
                - errors: количество ошибок
        """
        logger.info("Starting update of all tracking statuses")

        # Получаем заказы с ТТН
        orders_with_ttn = Order.objects.filter(
            tracking_number__isnull=False
        ).exclude(
            tracking_number=''
        )

        total_orders = orders_with_ttn.count()
        updated_count = 0
        error_count = 0
        processed_count = 0

        logger.info(f"Found {total_orders} orders with TTN to process")

        for order in orders_with_ttn:
            processed_count += 1
            try:
                logger.debug(
                    f"Processing order {order.order_number} "
                    f"({processed_count}/{total_orders})"
                )

                if self.update_order_tracking_status(order):
                    updated_count += 1
                    logger.info(
                        f"✓ Order {order.order_number} updated "
                        f"({updated_count} updated so far)"
                    )

            except Exception as e:
                error_count += 1
                logger.exception(
                    f"✗ Error updating order {order.order_number}: {e}"
                )

        result = {
            'total_orders': total_orders,
            'processed': processed_count,
            'updated': updated_count,
            'errors': error_count
        }

        logger.info(
            f"Finished updating tracking statuses: "
            f"{updated_count}/{total_orders} updated, {error_count} errors"
        )

        # Сохраняем время последнего обновления в кеш
        cache.set(self.LAST_UPDATE_CACHE_KEY, timezone.now(), timeout=None)

        return result

    @staticmethod
    def get_last_update_time():
        """
        Получает время последнего успешного обновления статусов

        Returns:
            datetime: Время последнего обновления или None
        """
        return cache.get(NovaPoshtaService.LAST_UPDATE_CACHE_KEY)

    @staticmethod
    def should_trigger_fallback_update():
        """
        Проверяет нужно ли запустить резервное обновление

        Если с момента последнего обновления прошло больше чем 
        NOVA_POSHTA_UPDATE_INTERVAL * FALLBACK_CHECK_MULTIPLIER минут,
        возвращает True (значит cron не работает)

        По умолчанию: 5 минут * 3 = 15 минут

        Returns:
            bool: True если нужно запустить резервное обновление
        """
        last_update = NovaPoshtaService.get_last_update_time()

        if last_update is None:
            # Первый запуск - нужно обновить
            logger.info("No previous updates found, fallback needed")
            return True

        # Получаем интервал обновления из настроек
        update_interval = getattr(settings, 'NOVA_POSHTA_UPDATE_INTERVAL', 5)
        try:
            update_interval = int(update_interval)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid NOVA_POSHTA_UPDATE_INTERVAL value: {update_interval}, using default 5 minutes"
            )
            update_interval = 5
        threshold_minutes = max(
            update_interval * NovaPoshtaService.FALLBACK_CHECK_MULTIPLIER,
            15  # минимум 15 минут
        )

        # Проверяем прошло ли больше порогового времени
        time_since_update = timezone.now() - last_update
        threshold = timedelta(minutes=threshold_minutes)

        needs_update = time_since_update > threshold

        if needs_update:
            logger.warning(
                f"Last update was {time_since_update.total_seconds() / 60:.1f} minutes ago "
                f"(threshold: {threshold_minutes} minutes), fallback needed"
            )

        return needs_update
