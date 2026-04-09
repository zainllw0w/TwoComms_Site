# 🚚 Автоматизация проверки статусов Nova Poshta

## 📋 Описание

Система автоматической проверки статусов посылок через API Новой Почты с обновлением статусов заказов и отправкой уведомлений.

## ✅ Что уже реализовано

### 1. **Автоматическая проверка статусов**
- ✅ Проверка всех заказов с ТТН через API Новой Почты
- ✅ Обновление статуса посылки (`shipment_status`)
- ✅ Отслеживание времени последнего обновления

### 2. **Автоматическое изменение статуса заказа**
Когда посылка получена (статус "отримано"):
- ✅ Статус заказа автоматически меняется на `done` (Отримано)
- ✅ `payment_status` автоматически меняется на `paid` (Оплачено)
- ✅ Отправляется Purchase событие в Facebook Conversions API
- ✅ Отправляется уведомление в Telegram админу
- ✅ Отправляется уведомление пользователю (если есть telegram_id)

### 3. **Уведомления в Telegram**
- ✅ Админ получает уведомление при автоматическом изменении статуса
- ✅ Пользователь получает уведомление о получении посылки
- ✅ Уведомления об изменении статуса посылки

### 4. **Интеграция с Meta Pixel**
- ✅ Purchase событие отправляется через Facebook Conversions API
- ✅ Дедупликация событий через event_id
- ✅ Advanced Matching данных пользователя

---

## 🛠️ Настройка

### Шаг 1: Проверка API ключа Nova Poshta

Убедитесь что в настройках проекта (`.env` или переменные окружения) указан:

```bash
NOVA_POSHTA_API_KEY=ваш_ключ_api
```

### Шаг 2: Настройка Telegram бота

Убедитесь что настроены переменные окружения для Telegram:

```bash
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=id_чата_или_канала  # опционально
TELEGRAM_ADMIN_ID=id_админа  # рекомендуется
```

### Шаг 3: Настройка Facebook Conversions API

Для отправки Purchase событий нужны:

```bash
FACEBOOK_PIXEL_ID=ваш_pixel_id
FACEBOOK_CONVERSIONS_API_TOKEN=ваш_access_token
```

### Шаг 4: Установка cron job

Запустите скрипт для автоматической настройки:

```bash
# Через SSH
ssh qlknpodo@195.191.24.169 'bash -s' < setup_nova_poshta_cron.sh

# Или если уже на сервере
bash setup_nova_poshta_cron.sh
```

Скрипт автоматически:
- Создаст cron задачу каждые 5 минут
- Настроит логирование в `/home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log`
- Покажет текущую конфигурацию

---

## 🔄 Как это работает

### Процесс автоматической проверки:

1. **Cron job запускается каждые 5 минут**
   ```bash
   */5 * * * * python manage.py update_tracking_statuses
   ```

2. **Система проверяет все заказы с ТТН**
   - Получает статус посылки через API Новой Почты
   - Сравнивает с текущим статусом в базе данных

3. **Если статус изменился:**
   - Обновляет `shipment_status` и `shipment_status_updated`
   - Если посылка получена → автоматически:
     - Меняет `status` на `done`
     - Меняет `payment_status` на `paid`
     - Отправляет Purchase событие в Facebook Conversions API
     - Отправляет уведомления в Telegram

4. **Уведомления:**
   - **Админу:** Информация о изменении статуса, оплате, отправке в Facebook Pixel
   - **Пользователю:** Уведомление о получении посылки (если есть telegram_id)

---

## 📊 Использование команды вручную

### Проверка всех заказов:

```bash
python manage.py update_tracking_statuses
```

### Проверка конкретного заказа:

```bash
python manage.py update_tracking_statuses --order-number TWC30102025N01
```

### Dry-run (показать что будет обновлено без изменений):

```bash
python manage.py update_tracking_statuses --dry-run
```

---

## 📝 Логирование

### Логи cron job:

```bash
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log
```

### Просмотр последних записей:

```bash
tail -50 /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log
```

### Поиск ошибок:

```bash
grep -i "error\|failed\|exception" /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log
```

---

## 🔍 Проверка работы

### 1. Проверить что cron настроен:

```bash
crontab -l | grep update_tracking_statuses
```

Должна быть строка:
```
*/5 * * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py update_tracking_statuses >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log 2>&1
```

### 2. Проверить последний запуск:

```bash
tail -20 /home/qlknpodo/TWC/TwoComms_Site/twocomms/logs/nova_poshta_cron.log
```

### 3. Ручной тест:

```bash
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
python manage.py update_tracking_statuses
```

### 4. Проверить что уведомления отправляются:

- Проверить Telegram админу
- Проверить Telegram пользователю (если есть telegram_id)
- Проверить Facebook Events Manager (должны появиться Purchase события)

---

## 🔧 Структура файлов

```
twocomms/orders/
├── nova_poshta_service.py          # Основной сервис работы с API
├── telegram_notifications.py       # Отправка уведомлений в Telegram
├── facebook_conversions_service.py # Отправка событий в Facebook
├── signals.py                      # Django сигналы для уведомлений
└── management/commands/
    └── update_tracking_statuses.py  # Команда для обновления статусов
```

---

## ⚠️ Важные моменты

### 1. **Ключевые слова для определения "получено":**

Система распознает следующие статусы как "получено":
- `отримано`
- `получено`
- `доставлено`
- `вручено`
- `отримано отримувачем`
- `получено получателем`

### 2. **Защита от дублирования:**

- Facebook Conversions API использует `event_id` для дедупликации
- Уведомления в Telegram отправляются только при реальном изменении статуса
- Purchase событие отправляется только один раз при первом изменении на `paid`

### 3. **Обработка ошибок:**

- Если API Nova Poshta недоступен, ошибка логируется, но процесс продолжается для других заказов
- Если Telegram не настроен, уведомления пропускаются без ошибок
- Если Facebook Conversions API не настроен, событие не отправляется, но заказ обновляется

---

## 🎯 Примеры сценариев

### Сценарий 1: Заказ с COD (наложенный платеж)

1. Заказ создан с `pay_type='cod'` и `payment_status='unpaid'`
2. ТТН добавлен администратором
3. Через 5 минут cron проверяет статус → статус "В дорозі"
4. Через несколько часов → статус "Отримано отримувачем"
5. **Автоматически:**
   - `status` → `done`
   - `payment_status` → `paid`
   - Purchase событие отправлено в Facebook
   - Админ получил уведомление в Telegram
   - Пользователь получил уведомление (если есть telegram_id)

### Сценарий 2: Заказ с предоплатой

1. Заказ создан с `pay_type='prepay_200'` и `payment_status='prepaid'`
2. ТТН добавлен
3. При получении → автоматически меняется на `paid`
4. Purchase событие отправляется в Facebook

---

## 🚀 Дополнительные возможности

### Мониторинг через Telegram

Админ будет получать уведомления в формате:

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

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `tail -f logs/nova_poshta_cron.log`
2. Проверьте настройки API ключей
3. Проверьте что cron job запускается: `crontab -l`
4. Ручной запуск для отладки: `python manage.py update_tracking_statuses --dry-run`

---

**Дата создания:** 30.10.2025  
**Версия:** 1.0  
**Статус:** ✅ Готово к использованию

















