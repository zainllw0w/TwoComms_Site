# 🔧 Исправление ошибки RecursionError в passenger_wsgi.py

## ❌ Ошибка
```
RecursionError: maximum recursion depth exceeded
File "passenger_wsgi.py", line 16, in module
wsgi = load_source('wsgi', 'passenger_wsgi.py')
```

## 🔍 Диагностика проблемы

Эта ошибка возникает из-за:
1. **Циклического импорта** в WSGI файле
2. **Неправильного использования** `load_source`
3. **Проблем с путями** Python
4. **Конфликта модулей** Django

## 🛠️ Решения

### Решение 1: Использование исправленного файла

Замените содержимое `passenger_wsgi.py` на исправленную версию:

```python
import os
import sys

# Добавляем корень приложения в PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

# Указываем модуль настроек для продакшена
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.production_settings")

# Импортируем Django WSGI приложение
import django
from django.core.wsgi import get_wsgi_application

# Инициализируем Django
django.setup()

# Создаем WSGI приложение
application = get_wsgi_application()
```

### Решение 2: Для PythonAnywhere

Используйте файл `pythonanywhere_wsgi.py`:

```python
import os
import sys

# Укажите правильный путь к вашему проекту
path = '/home/yourusername/twocomms'
if path not in sys.path:
    sys.path.append(path)

# Укажите правильный модуль настроек
os.environ['DJANGO_SETTINGS_MODULE'] = 'twocomms.production_settings'

# Создаем WSGI приложение
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### Решение 3: Минимальная версия

Если проблемы продолжаются, используйте минимальную версию:

```python
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

# Настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')

# WSGI приложение
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

## 🔧 Пошаговое исправление

### 1. Создайте резервную копию
```bash
cp passenger_wsgi.py passenger_wsgi.py.backup
```

### 2. Замените содержимое файла
```bash
cp passenger_wsgi_fixed.py passenger_wsgi.py
```

### 3. Проверьте права доступа
```bash
chmod 644 passenger_wsgi.py
```

### 4. Перезапустите сервер
- **PythonAnywhere:** Нажмите кнопку "Reload" в Web tab
- **Другие хостинги:** Перезапустите веб-сервер

## 🚨 Альтернативные решения

### Если проблема не решается:

1. **Проверьте пути Python:**
   ```python
   import sys
   print(sys.path)
   ```

2. **Проверьте переменные окружения:**
   ```python
   import os
   print(os.environ.get('DJANGO_SETTINGS_MODULE'))
   ```

3. **Используйте абсолютные пути:**
   ```python
   import os
   sys.path.insert(0, '/full/path/to/your/project')
   ```

4. **Проверьте настройки Django:**
   ```python
   from django.conf import settings
   print(settings.DEBUG)
   ```

## 📋 Проверка после исправления

### 1. Проверка WSGI файла
```bash
python passenger_wsgi.py
# Должно работать без ошибок
```

### 2. Проверка Django
```bash
python manage.py check --deploy
```

### 3. Проверка статических файлов
```bash
python manage.py collectstatic --noinput
```

### 4. Тестирование на сервере
- Откройте сайт в браузере
- Проверьте, что все страницы загружаются
- Проверьте админку Django

## 🔍 Дополнительная диагностика

### Проверка циклических импортов:
```python
# Добавьте в начало passenger_wsgi.py
import sys
sys.setrecursionlimit(10000)
```

### Проверка путей:
```python
import os
print("Current directory:", os.getcwd())
print("Script directory:", os.path.dirname(__file__))
```

### Проверка Django настроек:
```python
import django
from django.conf import settings
print("Django version:", django.get_version())
print("Settings module:", settings.SETTINGS_MODULE)
```

## ✅ После исправления

Когда ошибка будет исправлена:

1. **Сайт должен загружаться** без ошибок
2. **Админка Django** должна работать
3. **Статические файлы** должны загружаться
4. **Логи сервера** должны быть чистыми

## 📞 Поддержка

Если проблема не решается:

1. **Проверьте логи сервера** для дополнительной информации
2. **Обратитесь к хостинг-провайдеру** за помощью
3. **Используйте альтернативные WSGI файлы** из репозитория
4. **Проверьте версию Python** на сервере

## 🎯 Рекомендации

- ✅ **Используйте исправленную версию** `passenger_wsgi_fixed.py`
- ✅ **Проверяйте пути** перед развертыванием
- ✅ **Тестируйте локально** перед загрузкой на сервер
- ✅ **Создавайте резервные копии** перед изменениями
