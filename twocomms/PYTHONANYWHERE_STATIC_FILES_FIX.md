# Исправление статических файлов на PythonAnywhere

## Проблема:
Статические файлы (CSS, JS, изображения) не загружаются на сайте.

## ✅ РЕШЕНО: Настройки исправлены

### Что было исправлено:
1. **Порядок настроек** в `production_settings.py`
2. **STATIC_URL** теперь правильно определен
3. **STATICFILES_DIRS** настроен корректно

## Что нужно сделать на PythonAnywhere:

### 1. Обновите проект
```bash
cd /home/twocomms/TwoComms_Site
git pull origin main
```

### 2. Соберите статические файлы
```bash
python manage.py collectstatic --noinput
```

### 3. Проверьте права доступа
```bash
chmod -R 755 staticfiles/
chmod -R 755 media/
```

### 4. Перезапустите веб-приложение
- В разделе "Web" на PythonAnywhere нажмите "Reload"

## Если статические файлы все еще не загружаются:

### Проверьте настройки веб-приложения в PythonAnywhere:

1. **Перейдите в раздел "Web"**
2. **Найдите ваш домен** (twocomms.pythonanywhere.com)
3. **Нажмите на ссылку "Files"** рядом с вашим доменом
4. **Проверьте настройки статических файлов:**

```
Static files:
URL: /static/
Directory: /home/twocomms/TwoComms_Site/staticfiles

Media files:
URL: /media/
Directory: /home/twocomms/TwoComms_Site/media
```

### Если настройки неправильные:

1. **Измените URL статических файлов** на `/static/`
2. **Измените Directory статических файлов** на `/home/twocomms/TwoComms_Site/staticfiles`
3. **Измените URL медиа файлов** на `/media/`
4. **Измените Directory медиа файлов** на `/home/twocomms/TwoComms_Site/media`
5. **Нажмите "Save"**
6. **Нажмите "Reload"**

## Проверки:

### Проверьте структуру файлов:
```bash
cd /home/twocomms/TwoComms_Site
ls -la staticfiles/
ls -la media/
```

### Проверьте настройки Django:
```bash
python manage.py shell
```
```python
from django.conf import settings
print(settings.STATIC_URL)
print(settings.STATIC_ROOT)
print(settings.STATICFILES_DIRS)
```

### Проверьте логи:
- В разделе "Web" на PythonAnywhere проверьте логи ошибок

## Альтернативное решение:

Если ничего не помогает, можно временно использовать CDN или внешние ссылки для статических файлов.

## Проверка после исправления:

1. **Откройте сайт** https://twocomms.pythonanywhere.com/
2. **Проверьте в DevTools** (F12) вкладку "Network"
3. **Убедитесь, что CSS и JS файлы загружаются** без ошибок 404
4. **Проверьте стили** - сайт должен выглядеть правильно
