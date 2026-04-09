# 🚚 Инструкция: Автоматизация Nova Poshta

## 📋 Что делает система

Система автоматически проверяет статусы посылок через API Новой Почты **каждые 5 минут** и:

1. ✅ Обновляет статус посылки в базе данных
2. ✅ Когда посылка получена → автоматически меняет статус заказа на "Отримано"
3. ✅ Автоматически меняет статус оплаты на "Оплачено"
4. ✅ Отправляет Purchase событие в Meta Pixel (Facebook)
5. ✅ Отправляет уведомления в Telegram админу и пользователю

---

## ⚙️ Настройка (один раз)

### Шаг 1: Настроить cron job

Подключитесь к серверу и запустите скрипт:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && bash -s'" < setup_nova_poshta_cron.sh
```

Или если уже на сервере:

```bash
bash setup_nova_poshta_cron.sh
```

Это настроит автоматическую проверку **каждые 5 минут**.

### Шаг 2: Проверить что работает

Проверьте что cron настроен:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "crontab -l | grep update_tracking_statuses"
```

Должна быть строка с `*/5 * * * *`.

---

## 🔄 Как это работает

### Когда добавляется ТТН к заказу:

1. Администратор добавляет номер ТТН в заказ
2. Система начинает отслеживать этот заказ
3. Каждые 5 минут проверяется статус через API Новой Почты

### Когда посылка получена:

1. **API Nova Poshta** возвращает статус "Отримано отримувачем"
2. **Автоматически:**
   - Статус заказа → `done` (Отримано)
   - Статус оплаты → `paid` (Оплачено)
   - Отправляется Purchase событие в **Meta Pixel**
   - Админ получает уведомление в **Telegram**
   - Пользователь получает уведомление (если есть telegram_id)

---

## 📊 Проверка работы

### Просмотр логов:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "tail -50 /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log"
```

### Ручной запуск проверки:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py update_tracking_statuses'"
```

### Проверка конкретного заказа:

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && python manage.py update_tracking_statuses --order-number TWC30102025N01'"
```

---

## 💬 Что получает админ в Telegram

Когда статус меняется автоматически, админ получает сообщение:

```
🤖 АВТОМАТИЧНЕ ОНОВЛЕННЯ СТАТУСУ

🆔 Замовлення: #TWC30102025N01
📋 ТТН: 59001234567890

📊 Статус замовлення:
├─ Було: Відправлено
└─ Стало: Отримано

💰 Статус оплати: автоматично змінено на ОПЛАЧЕНО
📊 Facebook Pixel: Purchase подія відправлена

👤 Клієнт: Іван Петренко
📞 Телефон: +380501234567
🏙️ Місто: Київ
💰 Сума: 1599.00 грн

🕐 Час оновлення: 30.10.2025 14:23

Статус змінено автоматично через API Нової Пошти
```

---

## ✅ Важно

### Что нужно настроить:

1. ✅ **NOVA_POSHTA_API_KEY** - ключ API Новой Почты (должен быть в .env)
2. ✅ **TELEGRAM_BOT_TOKEN** и **TELEGRAM_ADMIN_ID** - для уведомлений
3. ✅ **FACEBOOK_PIXEL_ID** и **FACEBOOK_CONVERSIONS_API_TOKEN** - для Meta Pixel

### Система автоматически распознает получение по ключевым словам:

- "отримано"
- "получено"
- "доставлено"
- "вручено"
- "отримано отримувачем"

---

## 🔧 Устранение проблем

### Cron не запускается:

1. Проверьте что задача в crontab: `crontab -l`
2. Проверьте логи: `tail -f logs/nova_poshta_cron.log`
3. Проверьте права на файл лога

### Уведомления не приходят:

1. Проверьте что Telegram настроен (TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)
2. Проверьте что бот запущен
3. Проверьте логи на ошибки

### Meta Pixel события не отправляются:

1. Проверьте что Facebook Conversions API настроен
2. Проверьте что FACEBOOK_PIXEL_ID и FACEBOOK_CONVERSIONS_API_TOKEN установлены
3. Проверьте логи на ошибки API

---

## 📝 Дополнительная информация

Подробная документация: `NOVA_POSHTA_AUTOMATION_SETUP.md`

---

**Версия:** 1.0  
**Дата:** 30.10.2025  
**Статус:** ✅ Готово к использованию

















