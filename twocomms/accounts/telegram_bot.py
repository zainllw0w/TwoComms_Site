"""
Telegram бот для подтверждения пользователей
"""
import os
import django
import requests
import json
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGRAM_SETTINGS_MODULE', 'twocomms.production_settings')
django.setup()

from accounts.models import UserProfile


class TelegramBot:
    """Telegram бот для подтверждения пользователей"""
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, chat_id, text, parse_mode='HTML'):
        """Отправляет сообщение пользователю"""
        if not self.bot_token:
            return False
            
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
            return False
    
    def set_webhook(self, webhook_url):
        """Устанавливает webhook для бота"""
        if not self.bot_token:
            return False
            
        url = f"{self.base_url}/setWebhook"
        data = {'url': webhook_url}
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка установки webhook: {e}")
            return False
    
    def get_webhook_info(self):
        """Получает информацию о webhook"""
        if not self.bot_token:
            return None
            
        url = f"{self.base_url}/getWebhookInfo"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Ошибка получения webhook info: {e}")
        return None
    
    def process_start_command(self, user_id, username=None):
        """Обрабатывает команду /start"""
        try:
            # Ищем пользователя по telegram_id
            profile = UserProfile.objects.filter(telegram_id=user_id).first()
            
            if profile:
                # Пользователь уже подтвержден
                message = f"""✅ <b>Добро пожаловать, {profile.user.username}!</b>

Вы уже подтвердили свой Telegram для получения уведомлений о статусе заказов.

🔔 <b>Вы будете получать уведомления о:</b>
• Новых заказах
• Изменении статуса посылок
• Получении заказов

📋 <b>Полезные ссылки:</b>
• <a href="https://twocomms.shop/my-orders/">Мои заказы</a>
• <a href="https://twocomms.shop/profile/">Профиль</a>"""
                
                self.send_message(user_id, message)
                return True
            else:
                # Пользователь не найден - нужно связать аккаунт
                message = f"""👋 <b>Добро пожаловать в TwoComms!</b>

Для получения уведомлений о статусе ваших заказов нужно связать ваш Telegram с аккаунтом на сайте.

📋 <b>Как это сделать:</b>
1. Зайдите в свой профиль на сайте
2. В поле "Telegram" введите ваш username: @{username or 'ваш_username'}
3. Нажмите кнопку "Получать статусы в Telegram"
4. Вернитесь сюда и нажмите /start

🌐 <a href="https://twocomms.shop/profile/">Перейти в профиль</a>"""
                
                self.send_message(user_id, message)
                return False
                
        except Exception as e:
            print(f"Ошибка обработки команды /start: {e}")
            return False
    
    def link_user_account(self, telegram_id, telegram_username):
        """Связывает Telegram аккаунт с пользователем"""
        try:
            # Ищем пользователя по telegram username
            profile = UserProfile.objects.filter(telegram=telegram_username).first()
            
            if profile and not profile.telegram_id:
                # Связываем аккаунт
                profile.telegram_id = telegram_id
                profile.save()
                
                message = f"""🎉 <b>Отлично! Ваш Telegram успешно связан!</b>

Теперь вы будете получать уведомления о статусе ваших заказов.

🔔 <b>Вы будете получать уведомления о:</b>
• Новых заказах
• Изменении статуса посылок  
• Получении заказов

📋 <b>Полезные ссылки:</b>
• <a href="https://twocomms.shop/my-orders/">Мои заказы</a>
• <a href="https://twocomms.shop/profile/">Профиль</a>"""
                
                self.send_message(telegram_id, message)
                return True
            else:
                message = """❌ <b>Не удалось связать аккаунт</b>

Убедитесь, что:
1. Вы ввели правильный Telegram username в профиле
2. Username начинается с @
3. Вы еще не связывали этот Telegram

🌐 <a href="https://twocomms.shop/profile/">Проверить профиль</a>"""
                
                self.send_message(telegram_id, message)
                return False
                
        except Exception as e:
            print(f"Ошибка связывания аккаунта: {e}")
            return False
    
    def process_webhook_update(self, update_data):
        """Обрабатывает обновление от webhook"""
        try:
            if 'message' in update_data:
                message = update_data['message']
                user_id = message['from']['id']
                username = message['from'].get('username')
                text = message.get('text', '')
                
                if text == '/start':
                    return self.process_start_command(user_id, username)
                    
        except Exception as e:
            print(f"Ошибка обработки webhook: {e}")
        return False


# Глобальный экземпляр бота
telegram_bot = TelegramBot()
