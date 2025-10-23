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
            print(f"🔵 auto_confirm_user called: user_id={user_id}, username={username}")
            
            if not username:
                print(f"❌ No username provided")
                return False
            
            # Убираем @ если есть
            clean_username = username.lstrip('@')
            print(f"🟡 Clean username: {clean_username}")
            
            # Ищем все профили с таким telegram username (без @) - только неподтвержденные
            profiles_without_at = UserProfile.objects.filter(telegram=clean_username, telegram_id__isnull=True)
            print(f"🟢 Profiles without @: {profiles_without_at.count()}")
            
            # Ищем все профили с таким telegram username (с @) - только неподтвержденные
            profiles_with_at = UserProfile.objects.filter(telegram=f"@{clean_username}", telegram_id__isnull=True)
            print(f"🟢 Profiles with @: {profiles_with_at.count()}")
            
            # Объединяем результаты
            all_matching_profiles = list(profiles_without_at) + list(profiles_with_at)
            print(f"🟣 Total matching profiles: {len(all_matching_profiles)}")
            
            if len(all_matching_profiles) == 0:
                print(f"❌ No matching profiles found")
                return False
            
            # Привязываем только к ПЕРВОМУ найденному неподтвержденному профилю
            profile = all_matching_profiles[0]
            print(f"✅ Linking to profile: {profile.user.username} (company: {profile.company_name})")
            
            # Привязываем telegram_id к профилю
            profile.telegram_id = user_id
            profile.save()
            print(f"✅ Profile saved with telegram_id={user_id}")
            
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
        """Связывает Telegram аккаунт с пользователем или дропшипером"""
        try:
            # Ищем пользователя по telegram username
            profile = UserProfile.objects.filter(telegram=telegram_username).first()
            
            if profile and not profile.telegram_id:
                # Связываем аккаунт
                profile.telegram_id = telegram_id
                profile.save()
                
                # Проверяем, это дропшипер или обычный пользователь
                # Если у пользователя есть company_name, считаем его дропшипером
                is_dropshipper = bool(profile.company_name)
                
                if is_dropshipper:
                    # Сообщение для дропшипера
                    message = f"""🎉 <b>Відмінно! Ваш Telegram успішно пов'язано!</b>

Тепер ви будете отримувати сповіщення про дропшип замовлення та їх статуси.

🔔 <b>Ви будете отримувати сповіщення про:</b>
• Нові замовлення від клієнтів
• Підтвердження замовлень адміністратором
• Зміну статусів замовлень
• Відправку товарів (з ТТН)
• Оплати і виплати
• Доставку та отримання товарів

📋 <b>Корисні посилання:</b>
• <a href="https://twocomms.shop/orders/dropshipper/dashboard/">Дропшип панель</a>
• <a href="https://twocomms.shop/orders/dropshipper/orders/">Мої замовлення</a>
• <a href="https://twocomms.shop/orders/dropshipper/company/">Налаштування компанії</a>"""
                else:
                    # Сообщение для обычного пользователя
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
1. Ви ввели правильний Telegram username у профілі або налаштуваннях компанії
2. Username починається з @ (або без, бот додасть автоматично)
3. Ви ще не пов'язували цей Telegram

🌐 <b>Перевірити:</b>
• <a href="https://twocomms.shop/profile/">Профіль</a>
• <a href="https://twocomms.shop/orders/dropshipper/company/">Налаштування компанії (для дропшиперів)</a>"""
                
                self.send_message(telegram_id, message)
                return False
                
        except Exception as e:
            return False
    
    def process_webhook_update(self, update_data):
        """Обрабатывает обновление от webhook"""
        try:
            print(f"🔵 Webhook update received: {update_data}")
            
            if 'message' in update_data:
                message = update_data['message']
                user_id = message['from']['id']
                username = message['from'].get('username')
                text = message.get('text', '')
                
                print(f"🟡 Message from user_id={user_id}, username={username}, text={text}")
                
                if text == '/start':
                    print(f"🟢 Processing /start command")
                    result = self.process_start_command(user_id, username)
                    print(f"🟣 /start result: {result}")
                    return result
                else:
                    # Обрабатываем любое другое сообщение
                    print(f"🟢 Processing any message")
                    result = self.process_any_message(user_id, username, text)
                    print(f"🟣 Any message result: {result}")
                    return result
                    
        except Exception as e:
            print(f"❌ Webhook error: {e}")
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
