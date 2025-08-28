# 🔧 Исправление загрузки картинок на PythonAnywhere

## 🚨 **Проблема:** Картинки не загружаются на сервер

## 📋 **Пошаговое решение:**

### **1. Обновите код:**
```bash
cd /home/twocomms/TwoComms_Site
git stash
git pull origin main
git stash pop
```

### **2. Создайте все необходимые папки:**
```bash
# Основная папка медиа
mkdir -p /home/twocomms/TwoComms_Site/media

# Папки для разных типов файлов
mkdir -p /home/twocomms/TwoComms_Site/media/products
mkdir -p /home/twocomms/TwoComms_Site/media/avatars
mkdir -p /home/twocomms/TwoComms_Site/media/category_covers
mkdir -p /home/twocomms/TwoComms_Site/media/category_icons
mkdir -p /home/twocomms/TwoComms_Site/media/product_colors
mkdir -p /home/twocomms/TwoComms_Site/media/ubd_docs
```

### **3. Установите правильные права доступа:**
```bash
# Права на папки
chmod -R 755 /home/twocomms/TwoComms_Site/media

# Права на файлы (если они есть)
find /home/twocomms/TwoComms_Site/media -type f -exec chmod 644 {} \;
```

### **4. Проверьте владельца файлов:**
```bash
# Убедитесь, что файлы принадлежат вашему пользователю
chown -R twocomms:twocomms /home/twocomms/TwoComms_Site/media
```

### **5. Настройте веб-сервер для медиа-файлов:**
В разделе **Web → Static files** добавьте:

**URL:** `/media/`
**Directory:** `/home/twocomms/TwoComms_Site/media`

### **6. Обновите WSGI файл:**
В разделе **Web → WSGI configuration file** замените содержимое на:

```python
import os
import sys

# Добавьте путь к проекту
path = '/home/twocomms/TwoComms_Site'
if path not in sys.path:
    sys.path.append(path)

# Добавьте путь к виртуальному окружению
path = '/home/twocomms/TwoComms_Site/.venv/lib/python3.13/site-packages'
if path not in sys.path:
    sys.path.append(path)

# Настройте переменные окружения
os.environ['DJANGO_SETTINGS_MODULE'] = 'twocomms.settings'

# Импортируйте Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### **7. Перезагрузите приложение:**
Нажмите **"Reload"** в разделе Web

### **8. Проверьте настройки Django:**
```bash
cd /home/twocomms/TwoComms_Site
python manage.py shell
```

В Python shell выполните:
```python
from django.conf import settings
print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"DEBUG: {settings.DEBUG}")
```

### **9. Создайте тестовый файл:**
```bash
# Создайте тестовый файл для проверки прав доступа
echo "test" > /home/twocomms/TwoComms_Site/media/test.txt
chmod 644 /home/twocomms/TwoComms_Site/media/test.txt
```

### **10. Проверьте доступность файла:**
Откройте в браузере: `https://twocomms.pythonanywhere.com/media/test.txt`

## 🔍 **Диагностика проблем:**

### **Проверьте логи ошибок:**
В разделе **Web → Log files → Error log**

### **Проверьте права доступа:**
```bash
ls -la /home/twocomms/TwoComms_Site/media/
```

### **Проверьте настройки статических файлов:**
В разделе **Web → Static files** должно быть:
- URL: `/static/` → Directory: `/home/twocomms/TwoComms_Site/staticfiles`
- URL: `/media/` → Directory: `/home/twocomms/TwoComms_Site/media`

## 🎯 **Тестирование загрузки:**

### **1. Попробуйте загрузить изображение:**
- Откройте админ-панель
- Создайте новый товар
- Загрузите изображение
- Проверьте, создался ли файл: `ls -la /home/twocomms/TwoComms_Site/media/products/`

### **2. Проверьте отображение:**
- Откройте страницу товара
- Проверьте, отображается ли изображение
- Откройте инспектор браузера (F12) и проверьте URL изображения

## ✅ **Ожидаемый результат:**

После выполнения всех шагов:
- ✅ **Файлы загружаются** в папку `/media/`
- ✅ **Изображения отображаются** на сайте
- ✅ **URL медиа-файлов** работают правильно
- ✅ **Права доступа** настроены корректно

## 🚨 **Если проблемы остаются:**

1. **Проверьте логи ошибок** в разделе Web
2. **Убедитесь, что все папки созданы** и имеют правильные права
3. **Проверьте настройки** в Static files
4. **Попробуйте перезапустить** веб-приложение
