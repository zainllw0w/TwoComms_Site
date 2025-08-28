# 🚀 Развертывание TwoComms на PythonAnywhere

Подробные инструкции по развертыванию интернет-магазина TwoComms на бесплатном хостинге PythonAnywhere.

## 📋 Предварительные требования

1. **Аккаунт на GitHub** с загруженным проектом
2. **Бесплатный аккаунт на PythonAnywhere**
3. **Базовые знания командной строки**

## 🔧 Пошаговое развертывание

### Шаг 1: Регистрация на PythonAnywhere

1. **Перейдите на [pythonanywhere.com](https://www.pythonanywhere.com)**
2. **Нажмите "Create a Beginner account"** (бесплатный аккаунт)
3. **Заполните форму регистрации**
4. **Подтвердите email**

### Шаг 2: Клонирование проекта

1. **Откройте Bash консоль** в PythonAnywhere
2. **Выполните команды:**

```bash
# Клонируйте ваш репозиторий (замените YOUR_USERNAME на ваше имя пользователя)
git clone https://github.com/YOUR_USERNAME/twocomms.git

# Перейдите в папку проекта
cd twocomms

# Создайте виртуальное окружение
python3 -m venv .venv

# Активируйте виртуальное окружение
source .venv/bin/activate

# Установите зависимости
pip install -r twocomms/requirements.txt
```

### Шаг 3: Настройка базы данных

```bash
# Перейдите в папку Django проекта
cd twocomms

# Создайте миграции
python manage.py makemigrations

# Примените миграции
python manage.py migrate

# Создайте суперпользователя
python manage.py createsuperuser
```

### Шаг 4: Создание веб-приложения

1. **Перейдите в раздел "Web"** в PythonAnywhere
2. **Нажмите "Add a new web app"**
3. **Выберите "Manual configuration"**
4. **Выберите Python 3.9** или новее
5. **Нажмите "Next"**

### Шаг 5: Настройка WSGI файла

1. **Нажмите на ссылку WSGI configuration file**
2. **Замените содержимое на:**

```python
import os
import sys

# Добавьте путь к проекту (замените YOUR_USERNAME на ваше имя пользователя)
path = '/home/YOUR_USERNAME/twocomms'
if path not in sys.path:
    sys.path.append(path)

# Добавьте путь к виртуальному окружению
path = '/home/YOUR_USERNAME/twocomms/.venv/lib/python3.9/site-packages'
if path not in sys.path:
    sys.path.append(path)

# Настройте переменные окружения
os.environ['DJANGO_SETTINGS_MODULE'] = 'twocomms.production_settings'

# Импортируйте Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Шаг 6: Настройка статических файлов

1. **В разделе "Static files"** добавьте:

**Для статических файлов:**
- **URL**: `/static/`
- **Directory**: `/home/YOUR_USERNAME/twocomms/twocomms_django_theme/static/`

**Для медиа файлов:**
- **URL**: `/media/`
- **Directory**: `/home/YOUR_USERNAME/twocomms/media/`

### Шаг 7: Сбор статических файлов

```bash
# Вернитесь в Bash консоль
cd /home/YOUR_USERNAME/twocomms/twocomms

# Соберите статические файлы
python manage.py collectstatic --noinput
```

### Шаг 8: Настройка базы данных (опционально)

Если хотите использовать MySQL вместо SQLite:

1. **Перейдите в раздел "Databases"**
2. **Создайте новую базу данных**
3. **Обновите настройки в `production_settings.py`:**

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'YOUR_USERNAME$twocomms',
        'USER': 'YOUR_USERNAME',
        'PASSWORD': 'your-database-password',
        'HOST': 'YOUR_USERNAME.mysql.pythonanywhere-services.com',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
```

### Шаг 9: Запуск приложения

1. **Нажмите "Reload"** в разделе Web
2. **Ваш сайт будет доступен по адресу**: `YOUR_USERNAME.pythonanywhere.com`

## 🔒 Настройки безопасности

### Обновление SECRET_KEY

```bash
# В Bash консоли сгенерируйте новый SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Скопируйте результат и обновите в `production_settings.py`:

```python
SECRET_KEY = 'ваш-новый-secret-key'
```

### Настройка HTTPS (для платных аккаунтов)

Если у вас платный аккаунт, можете включить HTTPS:

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

## 📊 Мониторинг и логи

### Просмотр логов

1. **В разделе "Web"** нажмите на ссылку "Log files"
2. **Просматривайте error.log** для ошибок
3. **Просматривайте access.log** для доступа

### Настройка логирования

Логирование уже настроено в `production_settings.py`. Логи сохраняются в файл `django.log`.

## 🔧 Устранение неполадок

### Ошибка 500

1. **Проверьте логи** в разделе Web → Log files
2. **Убедитесь, что все зависимости установлены**
3. **Проверьте настройки в `production_settings.py`**

### Статические файлы не загружаются

1. **Проверьте настройки Static files** в разделе Web
2. **Убедитесь, что выполнили `collectstatic`**
3. **Проверьте права доступа к папкам**

### База данных не работает

1. **Проверьте настройки DATABASES** в `production_settings.py`
2. **Убедитесь, что миграции применены**
3. **Проверьте подключение к базе данных**

## 📈 Оптимизация производительности

### Кэширование

В `production_settings.py` уже настроено кэширование в памяти.

### Сжатие статических файлов

```bash
# Установите django-compressor
pip install django-compressor

# Добавьте в INSTALLED_APPS
INSTALLED_APPS = [
    # ... другие приложения
    'compressor',
]

# Добавьте в MIDDLEWARE
MIDDLEWARE = [
    # ... другие middleware
    'django.middleware.gzip.GZipMiddleware',
]
```

## 🔄 Обновление приложения

Для обновления приложения:

```bash
# В Bash консоли
cd /home/YOUR_USERNAME/twocomms
git pull origin main

# Активируйте виртуальное окружение
source .venv/bin/activate

# Установите новые зависимости
pip install -r twocomms/requirements.txt

# Примените миграции
cd twocomms
python manage.py makemigrations
python manage.py migrate

# Соберите статические файлы
python manage.py collectstatic --noinput

# Перезагрузите веб-приложение
# В разделе Web нажмите "Reload"
```

## 📞 Поддержка

Если возникли проблемы:

1. **Проверьте логи** в PythonAnywhere
2. **Обратитесь в поддержку PythonAnywhere**
3. **Создайте issue в GitHub репозитории**

---

**Удачи с развертыванием! 🚀**
