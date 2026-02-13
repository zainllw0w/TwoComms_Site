"""
Telegram бот для подтверждения пользователей
"""
import os
import django
import requests
from django.conf import settings

# Настройка Django только если еще не настроен
if not django.apps.apps.ready:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')
    django.setup()

from accounts.models import UserProfile
from django.db.models import Q


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

    def _normalize_username(self, username):
        """Нормализует username: убирает @, пробелы, приводит к нижнему регистру"""
        if not username:
            return ''
        # Убираем @ в начале
        cleaned = username.lstrip('@')
        # Убираем пробелы
        cleaned = cleaned.strip()
        # Приводим к нижнему регистру для сравнения
        cleaned = cleaned.lower()
        return cleaned

    def process_start_command(self, user_id, username=None, start_param=None):
        """Обрабатывает команду /start

        Args:
            user_id: Telegram ID пользователя
            username: Telegram username пользователя
            start_param: Параметр из команды /start (может быть Instagram или Telegram username)
        """
        try:
            print(f"🔵 process_start_command: user_id={user_id}, username={username}, start_param={start_param}")

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
                # Если есть параметр в /start, используем его для поиска
                # Иначе используем Telegram username
                search_username = start_param or username
                return self.auto_confirm_user(user_id, username, search_username)

        except Exception as e:
            print(f"❌ Error in process_start_command: {e}")
            import traceback
            traceback.print_exc()
            return False

    def auto_confirm_user(self, user_id, username=None, search_username=None):
        """Автоматически подтверждает пользователя по введенному username

        Args:
            user_id: Telegram ID пользователя
            username: Telegram username пользователя (для логирования)
            search_username: Username для поиска в профилях (может быть Telegram или Instagram)
        """
        try:
            print(f"🔵 auto_confirm_user called: user_id={user_id}, username={username}, search_username={search_username}")

            # Используем search_username если передан, иначе username
            search_value = search_username or username

            if not search_value:
                print(f"❌ No username provided")
                return False

            # Убираем @ если есть (как в старой версии)
            clean_username = search_value.lstrip('@')
            print(f"🟡 Clean username: '{clean_username}' (original: '{search_value}')")

            # Ищем профили по полю telegram (как в старой версии, но ищем ВСЕ, не только неподтвержденные)
            # Варианты: с @ и без @
            profiles_telegram_without_at = UserProfile.objects.filter(telegram=clean_username)
            profiles_telegram_with_at = UserProfile.objects.filter(telegram=f"@{clean_username}")

            print(f"🟢 Profiles by telegram (without @): {profiles_telegram_without_at.count()}")
            print(f"🟢 Profiles by telegram (with @): {profiles_telegram_with_at.count()}")

            # Ищем профили по полю instagram
            profiles_instagram_without_at = UserProfile.objects.filter(instagram=clean_username)
            profiles_instagram_with_at = UserProfile.objects.filter(instagram=f"@{clean_username}")

            print(f"🟢 Profiles by instagram (without @): {profiles_instagram_without_at.count()}")
            print(f"🟢 Profiles by instagram (with @): {profiles_instagram_with_at.count()}")

            # Объединяем все результаты
            all_telegram_profiles = list(profiles_telegram_without_at) + list(profiles_telegram_with_at)
            all_instagram_profiles = list(profiles_instagram_without_at) + list(profiles_instagram_with_at)

            for p in all_telegram_profiles:
                print(f"   - Profile: {p.user.username}, telegram='{p.telegram}', telegram_id={p.telegram_id}")
            for p in all_instagram_profiles:
                print(f"   - Profile: {p.user.username}, instagram='{p.instagram}', telegram_id={p.telegram_id}")

            # Объединяем все результаты
            all_matching_profiles = list(all_telegram_profiles) + list(all_instagram_profiles)

            # Убираем дубликаты (если профиль найден и по telegram и по instagram)
            seen_profiles = set()
            unique_profiles = []
            for profile in all_matching_profiles:
                if profile.id not in seen_profiles:
                    seen_profiles.add(profile.id)
                    unique_profiles.append(profile)

            all_matching_profiles = unique_profiles
            print(f"🟣 Total unique matching profiles: {len(all_matching_profiles)}")

            if len(all_matching_profiles) == 0:
                print(f"❌ No matching profiles found for username: '{clean_username}'")
                print(f"   Searched in telegram and instagram fields")
                print(f"   Search variants: ['{clean_username}', '@{clean_username}']")
                return False

            # Сначала проверяем, есть ли профиль уже привязанный к этому telegram_id
            already_linked_profile = None
            for profile in all_matching_profiles:
                if profile.telegram_id == user_id:
                    already_linked_profile = profile
                    print(f"✅ Profile {profile.user.username} already linked to this telegram_id")
                    break

            if already_linked_profile:
                # Профиль уже привязан - показываем сообщение и возвращаем True
                if already_linked_profile.telegram in [clean_username, f"@{clean_username}"]:
                    matched_field = 'telegram'
                    matched_username = already_linked_profile.telegram
                else:
                    matched_field = 'instagram'
                    matched_username = already_linked_profile.instagram

                message = f"""<b>Ласкаво просимо, {already_linked_profile.user.username}!</b>

Ви вже підтвердили свій Telegram ({matched_username}) для отримання сповіщень про статус замовлень.

🔔 <b>Ви будете отримувати сповіщення про:</b>
• Нові замовлення
• Зміну статусу посилок
• Отримання замовлень

📋 <b>Корисні посилання:</b>
• <a href="https://twocomms.shop/my-orders/">Мої замовлення</a>
• <a href="https://twocomms.shop/profile/">Профіль</a>"""

                self.send_message(user_id, message)
                return True

            # Выбираем профиль для привязки
            # Приоритет: профили без telegram_id или с другим telegram_id
            profile_to_link = None

            for profile in all_matching_profiles:
                print(f"🔍 Checking profile: {profile.user.username}, telegram_id={profile.telegram_id}")
                if profile.telegram_id is None:
                    # Неподтвержденный профиль - идеальный вариант
                    profile_to_link = profile
                    print(f"✅ Found unconfirmed profile: {profile.user.username}")
                    break
                elif profile.telegram_id != user_id:
                    # Профиль привязан к другому Telegram - можно перепривязать
                    profile_to_link = profile
                    print(f"⚠️ Found profile linked to different telegram_id ({profile.telegram_id}), will reassign to {user_id}")
                    break

            # Если не нашли подходящий профиль для привязки
            if not profile_to_link:
                print(f"❌ No suitable profile found for linking (all profiles already linked to this telegram_id)")
                return False

            # Привязываем telegram_id к профилю
            old_telegram_id = profile_to_link.telegram_id
            profile_to_link.telegram_id = user_id
            profile_to_link.save()
            print(f"✅ Profile saved: {profile_to_link.user.username}, telegram_id={old_telegram_id} -> {user_id}")

            # Определяем какой username был использован для поиска
            if profile_to_link.telegram in [clean_username, f"@{clean_username}"]:
                matched_field = 'telegram'
                matched_username = profile_to_link.telegram
            else:
                matched_field = 'instagram'
                matched_username = profile_to_link.instagram

            message = f"""🎉 <b>Відмінно! Ваш Telegram успішно підтверджено!</b>

Підтверджено аккаунт {matched_username} ({profile_to_link.user.username})

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
            print(f"❌ Error in auto_confirm_user: {e}")
            import traceback
            traceback.print_exc()
            return False

    def link_user_account(self, telegram_id, telegram_username):
        """Связывает Telegram аккаунт с пользователем или дропшипером

        Ищет профиль по полям telegram и instagram
        """
        try:
            print(f"🔵 link_user_account called: telegram_id={telegram_id}, telegram_username={telegram_username}")

            # Нормализуем username
            normalized_username = self._normalize_username(telegram_username)
            search_variants = [normalized_username, f"@{normalized_username}"]

            print(f"🟡 Search variants: {search_variants}")

            # Используем case-insensitive поиск
            telegram_q = Q()
            for variant in search_variants:
                telegram_q |= Q(telegram__iexact=variant)

            # Ищем пользователя по telegram username
            profile = UserProfile.objects.filter(telegram_q).first()

            # Если не найдено, ищем по instagram username
            if not profile:
                instagram_q = Q()
                for variant in search_variants:
                    instagram_q |= Q(instagram__iexact=variant)
                profile = UserProfile.objects.filter(instagram_q).first()
                print(f"🟡 Searching by instagram: found={profile is not None}")

            if profile:
                # Проверяем, не привязан ли уже к другому Telegram
                if profile.telegram_id and profile.telegram_id != telegram_id:
                    print(f"⚠️ Profile {profile.user.username} already linked to telegram_id={profile.telegram_id}, reassigning to {telegram_id}")

                # Связываем аккаунт (перепривязываем если нужно)
                profile.telegram_id = telegram_id
                profile.save()
                print(f"✅ Profile linked: {profile.user.username}, telegram_id={telegram_id}")

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
1. Ви ввели правильний Telegram або Instagram username у профілі або налаштуваннях компанії
2. Username починається з @ (або без, бот додасть автоматично)
3. Ви ще не пов'язували цей Telegram

🌐 <b>Перевірити:</b>
• <a href="https://twocomms.shop/profile/">Профіль</a>
• <a href="https://twocomms.shop/orders/dropshipper/company/">Налаштування компанії (для дропшиперів)</a>"""

                self.send_message(telegram_id, message)
                return False

        except Exception as e:
            print(f"❌ Error in link_user_account: {e}")
            import traceback
            traceback.print_exc()
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

                # Обрабатываем команду /start
                if text and text.startswith('/start'):
                    print(f"🟢 Processing /start command")
                    # Извлекаем параметр из команды /start (если есть)
                    # Формат: /start username или /start@botname username
                    start_param = None
                    parts = text.split(' ', 1)
                    if len(parts) > 1:
                        start_param = parts[1].strip()
                        print(f"🟡 Start parameter: {start_param}")

                    result = self.process_start_command(user_id, username, start_param)
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
            import traceback
            traceback.print_exc()
            return False

    def process_any_message(self, user_id, username=None, text=''):
        """Обрабатывает любое сообщение от пользователя"""
        try:
            # Всегда пытаемся подтвердить пользователя по username
            # Это позволяет привязывать один Telegram к нескольким аккаунтам
            # Также проверяем, может быть в тексте сообщения указан Instagram username
            search_username = username

            # Если в тексте есть что-то похожее на username (начинается с @ или просто текст)
            if text and text.strip() and not text.startswith('/'):
                # Пробуем использовать текст сообщения как username для поиска
                search_username = text.strip()
                print(f"🟡 Using message text as search username: {search_username}")

            result = self.auto_confirm_user(user_id, username, search_username)

            if result:
                return True
            else:
                # Если не удалось подтвердить, показываем инструкцию
                message = f"""👋 <b>Ласкаво просимо до TwoComms!</b>

Для отримання сповіщень про статус ваших замовлень потрібно пов'язати ваш Telegram з акаунтом на сайті.

📝 <b>Що потрібно зробити:</b>
1. Перейдіть на сайт <a href="https://twocomms.shop/profile/">twocomms.shop/profile/</a>
2. У полі "Telegram" або "Instagram" введіть ваш username: @{username or 'ваш_username'}
3. Натисніть кнопку "Підтвердити Telegram"
4. Поверніться до цього бота та напишіть будь-яке повідомлення

💡 <b>Підказка:</b> Ви можете вказати Telegram або Instagram username - бот знайде ваш профіль.

🔔 <b>Після підтвердження ви будете отримувати:</b>
• Сповіщення про нові замовлення
• Зміну статусу посилок
• Отримання замовлень

❓ <b>Потрібна допомога?</b> Зверніться до підтримки на сайті."""

                self.send_message(user_id, message)
                return False

        except Exception as e:
            print(f"❌ Error in process_any_message: {e}")
            import traceback
            traceback.print_exc()
            return False


# Глобальный экземпляр бота
telegram_bot = TelegramBot()
