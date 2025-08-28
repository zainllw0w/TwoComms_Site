# Исправление ошибки ALLOWED_HOSTS на PythonAnywhere

## Проблема:
```
DisallowedHost at /
Invalid HTTP_HOST header: 'twocomms.pythonanywhere.com'. You may need to add 'twocomms.pythonanywhere.com' to ALLOWED_HOSTS.
```

## ✅ РЕШЕНО: Домен добавлен в настройки

Домен `twocomms.pythonanywhere.com` добавлен в:
- `twocomms/settings.py` (основные настройки)
- `twocomms/production_settings.py` (продакшн настройки)

## Что нужно сделать на PythonAnywhere:

### 1. Обновите проект с GitHub
```bash
cd /home/twocomms/TwoComms_Site
git pull origin main
```

### 2. Перезапустите веб-приложение
1. Перейдите в раздел "Web" на PythonAnywhere
2. Нажмите кнопку "Reload"

### 3. Проверьте работу сайта
Откройте https://twocomms.pythonanywhere.com/

## Если проблема остается:

### Проверьте WSGI конфигурацию
В разделе "Web" на PythonAnywhere найдите файл WSGI и убедитесь, что он использует правильные настройки:

```python
# /var/www/twocomms_pythonanywhere_com_wsgi.py
import os
import sys

# Добавьте путь к проекту
path = '/home/twocomms/TwoComms_Site'
if path not in sys.path:
    sys.path.append(path)

# Установите переменную окружения для настроек
os.environ['DJANGO_SETTINGS_MODULE'] = 'twocomms.production_settings'

# Импортируйте Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Временное решение (если ничего не помогает):
Добавьте в `twocomms/settings.py`:
```python
ALLOWED_HOSTS = [
    'twocomms.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
    '*',  # ВНИМАНИЕ: только для отладки!
]
```

## Проверки:

### Проверьте структуру проекта:
```bash
cd /home/twocomms/TwoComms_Site
ls -la
cat twocomms/settings.py | grep ALLOWED_HOSTS
```

### Проверьте переменные окружения:
```bash
echo $DJANGO_SETTINGS_MODULE
```

### Проверьте права доступа:
```bash
chmod -R 755 /home/twocomms/TwoComms_Site
```

## Безопасность:
После исправления проблемы уберите `'*'` из `ALLOWED_HOSTS` и оставьте только нужные домены.
