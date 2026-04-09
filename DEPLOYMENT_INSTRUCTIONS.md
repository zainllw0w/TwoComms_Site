# 🚀 Инструкции по деплою исправлений аудита

## Что было исправлено

### 🎯 Производительность
- ✅ Оптимизирован `product_detail` view с использованием `select_related` и `prefetch_related`
- ✅ Исправлена проблема N+1 запросов в `get_detailed_color_variants`
- ✅ Ожидаемое улучшение: TTFB страницы товара с 4.2s до <500ms

### 🔒 Безопасность
- ✅ `SECRET_KEY` теперь обязателен в production (приложение не запустится без него)
- ✅ Добавлена поддержка аутентификации Redis с паролем
- ✅ Добавлен middleware для rate limiting (100 запросов/минуту на IP)
- ✅ Удален `@csrf_exempt` с пользовательских endpoints (`add_to_cart`, `cart_remove`)

### 🧹 Качество кода
- ✅ Удалены все `console.log` и `console.error` из JS файлов
- ✅ Добавлена зависимость `django-ratelimit==5.0.0`

## 📋 Предварительные требования

1. **sshpass** должен быть установлен:
   ```bash
   # macOS
   brew install hudochenkov/sshpass/sshpass
   
   # Linux
   sudo apt-get install sshpass
   ```

2. **Git** доступ к репозиторию

3. **SSH** доступ к серверу (уже настроен в скрипте)

## 🚀 Деплой

### Автоматический деплой (рекомендуется)

Просто запустите скрипт:

```bash
./deploy_fixes.sh
```

Скрипт автоматически:
1. Подключится к серверу
2. Скачает последний код из ветки `fix-audit-errors-f88J2`
3. Установит новые зависимости
4. Запустит миграции (если есть)
5. Соберет статические файлы
6. Перезапустит приложение
7. Очистит кэш

### Ручной деплой

Если автоматический скрипт не работает, выполните команды вручную:

```bash
# 1. Подключитесь к серверу
ssh qlknpodo@195.191.24.169

# 2. Перейдите в директорию проекта
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# 3. Скачайте последний код
git fetch origin
git checkout fix-audit-errors-f88J2
git pull origin fix-audit-errors-f88J2

# 4. Активируйте виртуальное окружение
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate

# 5. Установите зависимости
pip install -r requirements.txt

# 6. Запустите миграции
python manage.py migrate --noinput

# 7. Соберите статику
python manage.py collectstatic --noinput

# 8. Перезапустите приложение
touch passenger_wsgi.py

# 9. Очистите кэш
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
>>> exit()
```

## ⚙️ Настройка переменных окружения

### ОБЯЗАТЕЛЬНО: SECRET_KEY

После деплоя убедитесь, что на сервере установлен `SECRET_KEY`:

```bash
# Подключитесь к серверу
ssh qlknpodo@195.191.24.169

# Проверьте, есть ли SECRET_KEY в .env файле
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
cat .env | grep SECRET_KEY

# Если нет, сгенерируйте новый ключ
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Добавьте его в .env файл
echo "SECRET_KEY=<ваш_сгенерированный_ключ>" >> .env
```

### ОПЦИОНАЛЬНО: Redis Password

Если вы хотите защитить Redis паролем:

```bash
# 1. Настройте Redis с паролем
# Отредактируйте /etc/redis/redis.conf или локальный конфиг
# Добавьте: requirepass your_secure_password

# 2. Добавьте пароль в .env
echo "REDIS_PASSWORD=your_secure_password" >> .env

# 3. Перезапустите Redis
sudo systemctl restart redis
```

## 🔍 Проверка после деплоя

### 1. Проверьте логи

```bash
ssh qlknpodo@195.191.24.169
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/django.log
```

Убедитесь, что нет ошибок при запуске.

### 2. Проверьте сайт

Откройте в браузере: https://twocomms.shop

Проверьте:
- ✅ Главная страница загружается
- ✅ Страница товара загружается быстро (должно быть <1s вместо 4.2s)
- ✅ Добавление в корзину работает
- ✅ Удаление из корзины работает
- ✅ Нет ошибок в консоли браузера

### 3. Проверьте производительность

```bash
# Проверьте время загрузки страницы товара
curl -w "@curl-format.txt" -o /dev/null -s "https://twocomms.shop/product/some-product-slug/"

# Где curl-format.txt содержит:
# time_namelookup:  %{time_namelookup}\n
# time_connect:  %{time_connect}\n
# time_starttransfer:  %{time_starttransfer}\n
# time_total:  %{time_total}\n
```

### 4. Проверьте rate limiting

```bash
# Попробуйте сделать много запросов быстро
for i in {1..110}; do curl -s -o /dev/null -w "%{http_code}\n" https://twocomms.shop/; done

# Должны увидеть 429 (Too Many Requests) после 100 запросов
```

## 🐛 Решение проблем

### Проблема: Приложение не запускается

**Причина:** Скорее всего не установлен `SECRET_KEY`

**Решение:**
```bash
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
# Добавьте полученный ключ в .env файл
echo "SECRET_KEY=<ключ>" >> .env
touch passenger_wsgi.py
```

### Проблема: Redis не работает

**Причина:** Redis может быть не запущен или неправильно настроен

**Решение:**
```bash
# Проверьте статус Redis
sudo systemctl status redis

# Если не запущен, запустите
sudo systemctl start redis

# Проверьте подключение
redis-cli ping
# Должно вернуть: PONG
```

### Проблема: Статические файлы не загружаются

**Решение:**
```bash
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate
python manage.py collectstatic --noinput --clear
touch passenger_wsgi.py
```

## 📊 Мониторинг

### Логи для мониторинга

```bash
# Django логи
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/django.log

# Ошибки
tail -f /home/qlknpodo/TWC/TwoComms_Site/twocomms/stderr.log

# Системные логи (если есть доступ)
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Метрики для отслеживания

- **TTFB страницы товара:** должен быть <500ms (было 4.2s)
- **Количество SQL запросов:** должно уменьшиться на 30-50%
- **Ошибки 429:** появятся при превышении лимита (это нормально)
- **Ошибки в консоли браузера:** должны исчезнуть

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи (см. выше)
2. Убедитесь, что все переменные окружения установлены
3. Проверьте, что Redis работает
4. Попробуйте перезапустить приложение: `touch passenger_wsgi.py`

## 🎉 Готово!

После успешного деплоя ваш сайт будет:
- ⚡ Быстрее (страница товара загружается в 8 раз быстрее)
- 🔒 Безопаснее (обязательный SECRET_KEY, rate limiting, CSRF защита)
- 🧹 Чище (нет console.log в production)
- 💪 Надежнее (оптимизированные запросы к БД)

