# 🛠️ Инструкции по исправлению ошибки на сервере

## 🔍 Диагностика проблемы

Из логов видно, что ошибка все еще возникает:
```
RecursionError: maximum recursion depth exceeded
File "passenger_wsgi.py", line 12, in load_source
```

Это означает, что на сервере все еще старая версия `passenger_wsgi.py`.

## 🚀 Пошаговое исправление

### 1. Подключитесь к серверу
```bash
ssh qlknpodo@195.191.24.169
# Пароль: [REDACTED_SSH_PASSWORD]
```

### 2. Активируйте виртуальное окружение и перейдите в директорию
```bash
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
```

### 3. Проверьте текущий файл passenger_wsgi.py
```bash
cat passenger_wsgi.py
```

### 4. Создайте резервную копию
```bash
cp passenger_wsgi.py passenger_wsgi.py.backup
```

### 5. Создайте исправленный файл passenger_wsgi.py
```bash
cat > passenger_wsgi.py << 'EOF'
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
EOF
```

### 6. Проверьте созданный файл
```bash
cat passenger_wsgi.py
```

### 7. Установите правильные права доступа
```bash
chmod 644 passenger_wsgi.py
```

### 8. Перезапустите веб-сервер
```bash
# Для большинства хостингов
touch tmp/restart.txt

# Или перезапустите через панель управления
```

### 9. Проверьте логи
```bash
tail -f stderr.log
```

## 🔧 Альтернативные решения

### Если файл не создается через cat:

1. **Используйте nano:**
```bash
nano passenger_wsgi.py
```

2. **Скопируйте и вставьте содержимое:**
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

3. **Сохраните файл:** `Ctrl+X`, затем `Y`, затем `Enter`

### Если проблема с правами доступа:

```bash
# Проверьте владельца файла
ls -la passenger_wsgi.py

# Измените владельца если нужно
chown qlknpodo:qlknpodo passenger_wsgi.py

# Установите права
chmod 644 passenger_wsgi.py
```

## 🔍 Проверка после исправления

### 1. Проверьте синтаксис Python
```bash
python -m py_compile passenger_wsgi.py
```

### 2. Проверьте Django
```bash
python manage.py check
```

### 3. Проверьте логи в реальном времени
```bash
tail -f stderr.log
```

### 4. Откройте сайт в браузере
- Проверьте, что сайт загружается
- Убедитесь, что ошибка RecursionError исчезла

## 🚨 Если проблема не решается

### 1. Проверьте версию Python
```bash
python --version
```

### 2. Проверьте Django
```bash
python -c "import django; print(django.get_version())"
```

### 3. Проверьте пути
```bash
python -c "import sys; print(sys.path)"
```

### 4. Проверьте переменные окружения
```bash
python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"
```

## 📋 Чек-лист

- [ ] Подключились к серверу
- [ ] Активировали виртуальное окружение
- [ ] Перешли в правильную директорию
- [ ] Создали резервную копию
- [ ] Создали исправленный passenger_wsgi.py
- [ ] Установили правильные права доступа
- [ ] Перезапустили веб-сервер
- [ ] Проверили логи
- [ ] Протестировали сайт

## ✅ Ожидаемый результат

После исправления:
- ✅ Сайт должен загружаться без ошибок
- ✅ Логи должны быть чистыми
- ✅ Ошибка RecursionError должна исчезнуть
- ✅ Все страницы должны работать корректно

## 📞 Поддержка

Если проблема не решается:
1. Проверьте логи сервера
2. Обратитесь к хостинг-провайдеру
3. Используйте альтернативные WSGI файлы
4. Проверьте настройки веб-сервера
