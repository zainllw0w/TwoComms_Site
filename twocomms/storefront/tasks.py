import logging
from celery import shared_task
from django.core.management import call_command
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task
def generate_google_merchant_feed_task():
    """
    Asynchronous task to generate Google Merchant Feed.
    This is a heavy operation involving many DB queries and XML generation.
    """
    logger.info("Starting async Google Merchant Feed generation...")
    try:
        call_command('generate_google_merchant_feed')
        logger.info("Successfully generated Google Merchant Feed.")
    except Exception as e:
        logger.error(f"Error generating Google Merchant Feed: {e}", exc_info=True)

@shared_task
def send_telegram_notification_task(message, chat_id=None, parse_mode='HTML'):
    """
    Asynchronous task to send Telegram notifications.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification.")
        return

    target_chat_id = chat_id or settings.TELEGRAM_ADMIN_CHAT_ID
    if not target_chat_id:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID not set, skipping notification.")
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': target_chat_id,
        'text': message,
        'parse_mode': parse_mode
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Telegram notification sent to {target_chat_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram notification: {e}")
