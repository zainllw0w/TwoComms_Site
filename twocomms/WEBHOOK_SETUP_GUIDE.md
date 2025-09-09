# Подробная инструкция по настройке Telegram Webhook

## Ваш токен бота
```
7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY
```

## ✅ Что уже настроено

### 1. Webhook установлен
- **URL**: `https://twocomms.shop/accounts/telegram/webhook/`
- **Статус**: ✅ Активен
- **IP адрес**: `195.191.24.169` (ваш сервер)

### 2. Проверка webhook
```bash
curl -s "https://api.telegram.org/bot7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY/getWebhookInfo"
```

**Результат:**
```json
{
    "ok": true,
    "result": {
        "url": "https://twocomms.shop/accounts/telegram/webhook/",
        "has_custom_certificate": false,
        "pending_update_count": 0,
        "max_connections": 40,
        "ip_address": "195.191.24.169",
        "allowed_updates": ["message", "callback_query"]
    }
}
```

## 🔧 Что нужно настроить

### 1. Добавить токен в sPanel Environment Variables

1. **Зайдите в sPanel** → Environment Variables
2. **Добавьте новую переменную:**
   - **Name**: `TELEGRAM_BOT_TOKEN`
   - **Value**: `7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY`
3. **Сохраните изменения**

### 2. Перезапустить приложение

После добавления переменной окружения нужно перезапустить Django приложение:

```bash
# На сервере
touch passenger_wsgi.py
```

## 🧪 Тестирование

### 1. Тест с реальным ботом

1. **Найдите вашего бота** в Telegram: `@twocommsbot`
2. **Напишите любое сообщение** (например, "Привет")
3. **Бот должен ответить** с инструкциями

### 2. Тест с пользователем сайта

1. **Создайте аккаунт** на сайте или войдите в существующий
2. **Зайдите в профиль** → настройки
3. **В поле "Telegram"** введите ваш username (например, `@yourusername`)
4. **Нажмите кнопку** "📱 Получать статусы"
5. **Откроется бот** - напишите любое сообщение
6. **Бот должен подтвердить** ваш аккаунт

## 🔍 Диагностика проблем

### Если бот не отвечает

1. **Проверьте токен в sPanel:**
   ```bash
   # На сервере
   echo $TELEGRAM_BOT_TOKEN
   ```

2. **Проверьте логи Django:**
   ```bash
   # На сервере
   tail -f django.log
   ```

3. **Проверьте webhook статус:**
   ```bash
   curl -s "https://api.telegram.org/bot7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY/getWebhookInfo" | python3 -m json.tool
   ```

### Если пользователь не подтверждается

1. **Убедитесь, что telegram username введен в профиле**
2. **Проверьте формат username** (с @ или без @)
3. **Убедитесь, что пользователь не подтвержден ранее**

### Если уведомления не приходят

1. **Проверьте, что telegram_id сохранен:**
   ```python
   # В Django shell
   from accounts.models import UserProfile
   profile = UserProfile.objects.get(user__username='your_username')
   print(f"Telegram ID: {profile.telegram_id}")
   ```

2. **Проверьте токен бота в настройках**

## 📱 Команды для управления webhook

### Удалить webhook
```bash
curl -X POST "https://api.telegram.org/bot7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY/deleteWebhook"
```

### Переустановить webhook
```bash
curl -X POST "https://api.telegram.org/bot7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://twocomms.shop/accounts/telegram/webhook/"}'
```

### Получить информацию о боте
```bash
curl -s "https://api.telegram.org/bot7503235642:AAEnR8-2NKw0nJ6HUQLofKuycMC2XS9jLMY/getMe" | python3 -m json.tool
```

## 🎯 Ожидаемое поведение

### При первом сообщении боту:
```
👋 Добро пожаловать в TwoComms!

Для получения уведомлений о статусе ваших заказов нужно связать ваш Telegram с аккаунтом на сайте.

📋 Как это сделать:
1. Зайдите в свой профиль на сайте
2. В поле "Telegram" введите ваш username: @yourusername
3. Нажмите кнопку "Получать статусы в Telegram"
4. Вернитесь сюда и напишите любое сообщение

🌐 Перейти в профиль
```

### После подтверждения:
```
🎉 Отлично! Ваш Telegram успешно подтвержден!

Теперь вы будете получать уведомления о статусе ваших заказов.

🔔 Вы будете получать уведомления о:
• Новых заказах
• Изменении статуса посылок  
• Получении заказов

📋 Полезные ссылки:
• Мои заказы
• Профиль
```

## 🚀 Готово!

После выполнения всех шагов:
1. ✅ Webhook настроен
2. ✅ Токен добавлен в sPanel
3. ✅ Приложение перезапущено
4. ✅ Бот готов к работе

Пользователи смогут подтверждать Telegram одним сообщением!
