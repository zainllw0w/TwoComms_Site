"""
Telegram бот для подтверждения пользователей
"""
import os
import django
import requests
import json
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
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
            return None
    
    def process_start_command(self, user_id, username=None):
        """Обрабатывает команду /start"""
        try:
            # Ищем пользователя по telegram_id
            profile = UserProfile.objects.filter(telegram_id=user_id).first()
            
            if profile:
                # Пользователь уже подтвержден
                message = f"""<b>Ласкаво просимо, {profile.user.username}!</b>

Ви вже підтвердили свій Telegram для отримання сповіщень про статус замовлень.

🔔 <b>Ви будете отримувати сповіщення про:</b>
• Нові замовлення
• Зміну статусу посилок
• Отримання замовлень

📋 <b>Корисні посилання:</b>
• <a href="https://twocomms.shop/my-orders/">Мої замовлення</a>
• <a href="https://twocomms.shop/profile/">Профіль</a>"""
                
                self.send_message(user_id, message)
                return True
            else:
                # Автоматически подтверждаем пользователя
                return self.auto_confirm_user(user_id, username)
                
        except Exception as e:
            return False
    
    def auto_confirm_user(self, user_id, username=None):
        """Автоматически подтверждает пользователя по введенному username"""
        try:
            if not username:
                return False
            
            # Убираем @ если есть
            clean_username = username.lstrip('@')
            
            # Ищем все профили с таким telegram username (без @) - только неподтвержденные
            profiles_without_at = UserProfile.objects.filter(telegram=clean_username, telegram_id__isnull=True)
            
            # Ищем все профили с таким telegram username (с @) - только неподтвержденные
            profiles_with_at = UserProfile.objects.filter(telegram=f"@{clean_username}", telegram_id__isnull=True)
            
            # Объединяем результаты
            all_matching_profiles = list(profiles_without_at) + list(profiles_with_at)
            
            if len(all_matching_profiles) == 0:
                return False
            
            # Привязываем только к ПЕРВОМУ найденному неподтвержденному профилю
            profile = all_matching_profiles[0]
            
            # Привязываем telegram_id к профилю
            profile.telegram_id = user_id
            profile.save()
            
            message = f"""🎉 <b>Відмінно! Ваш Telegram успішно підтверджено!</b>

Підтверджено аккаунт @{clean_username} ({profile.user.username})

Тепер ви будете отримувати сповіщення про статус ваших замовлень.

🔔 <b>Ви будете отримувати сповіщення про:</b>
• Нові замовлення
• Зміну статусу посилок  
• Отримання замовлень

📋 <b>Корисні посилання:</b>
• <a href="https://twocomms.shop/my-orders/">Мої замовлення</a>
• <a href="https://twocomms.shop/profile/">Профіль</a>"""
            
            self.send_message(user_id, message)
            return True
                
        except Exception as e:
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
                
                message = f"""🎉 <b>Відмінно! Ваш Telegram успішно пов'язано!</b>

Тепер ви будете отримувати сповіщення про статус ваших замовлень.

🔔 <b>Ви будете отримувати сповіщення про:</b>
• Нові замовлення
• Зміну статусу посилок  
• Отримання замовлень

📋 <b>Корисні посилання:</b>
• <a href="https://twocomms.shop/my-orders/">Мої замовлення</a>
• <a href="https://twocomms.shop/profile/">Профіль</a>"""
                
                self.send_message(telegram_id, message)
                return True
            else:
                message = """<b>Не вдалося пов'язати акаунт</b>

Переконайтеся, що:
1. Ви ввели правильний Telegram username у профілі
2. Username починається з @
3. Ви ще не пов'язували цей Telegram

🌐 <a href="https://twocomms.shop/profile/">Перевірити профіль</a>"""
                
                self.send_message(telegram_id, message)
                return False
                
        except Exception as e:
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
                    result = self.process_start_command(user_id, username)
                    return result
                else:
                    # Обрабатываем любое другое сообщение
                    result = self.process_any_message(user_id, username, text)
                    return result
                    
        except Exception as e:
        return False
    
    def process_any_message(self, user_id, username=None, text=''):
        """Обрабатывает любое сообщение от пользователя"""
        try:
            # Всегда пытаемся подтвердить пользователя по username
            # Это позволяет привязывать один Telegram к нескольким аккаунтам
            result = self.auto_confirm_user(user_id, username)
            
            if result:
                return True
            else:
                # Если не удалось подтвердить, показываем инструкцию
                message = f"""👋 <b>Ласкаво просимо до TwoComms!</b>

Для отримання сповіщень про статус ваших замовлень потрібно пов'язати ваш Telegram з акаунтом на сайті.

📝 <b>Що потрібно зробити:</b>
1. Перейдіть на сайт <a href="https://twocomms.shop/profile/">twocomms.shop/profile/</a>
2. У полі "Telegram" введіть ваш username: @{username or 'ваш_username'}
3. Натисніть кнопку "Підтвердити Telegram"
4. Поверніться до цього бота та напишіть будь-яке повідомлення

🔔 <b>Після підтвердження ви будете отримувати:</b>
• Сповіщення про нові замовлення
• Зміну статусу посилок
• Отримання замовлень

❓ <b>Потрібна допомога?</b> Зверніться до підтримки на сайті."""
                
                self.send_message(user_id, message)
                return False
                
        except Exception as e:
            return False


# Глобальный экземпляр бота
telegram_bot = TelegramBot()
