# 🔧 Исправления ошибок консоли для сервера

## Критические ошибки, которые нужно исправить:

### 1. **404 ошибки - отсутствующие файлы**

#### **Проблема:**
- `performance.css` и `performance.js` - не найдены
- `sw.js` - ServiceWorker не найден
- `inter-var.woff2` - шрифт не найден

#### **Решение:**
```bash
# На сервере выполните:
cd /home/your_username/TwoComms_Site/twocomms

# Соберите статические файлы
python manage.py collectstatic --noinput --settings=twocomms.production_settings

# Проверьте, что файлы собрались
ls -la staticfiles/css/performance.css
ls -la staticfiles/js/performance.js
ls -la staticfiles/sw.js
```

### 2. **JavaScript ошибки - аналитика**

#### **Проблема:**
- `YANDEX_METRICA_ID is not defined`
- Facebook events заблокированы

#### **Решение:**
✅ **УЖЕ ИСПРАВЛЕНО** - Facebook Pixel ID добавлен: `1101270515449298`
✅ **УЖЕ ИСПРАВЛЕНО** - Yandex Metrica отключен до настройки
✅ **УЖЕ ИСПРАВЛЕНО** - Google Analytics отключен до настройки

### 3. **ServiceWorker ошибка**

#### **Проблема:**
- `sw.js` возвращает 404

#### **Решение:**
```bash
# Проверьте, что sw.js существует
ls -la static/sw.js

# Если файл есть, но не собирается:
python manage.py collectstatic --noinput --settings=twocomms.production_settings

# Проверьте настройки STATIC_URL в production_settings.py
```

### 4. **Шрифты (404 ошибки)**

#### **Проблема:**
- `inter-var.woff2` не найден

#### **Решение:**
✅ **УЖЕ ИСПРАВЛЕНО** - Создан fallback CSS для шрифтов

## 📋 Пошаговая инструкция для сервера:

### **Шаг 1: Обновите код**
```bash
cd /home/your_username/TwoComms_Site/twocomms
git pull origin main
```

### **Шаг 2: Соберите статические файлы**
```bash
python manage.py collectstatic --noinput --settings=twocomms.production_settings
```

### **Шаг 3: Проверьте файлы**
```bash
# Проверьте, что все файлы на месте
ls -la staticfiles/css/performance.css
ls -la staticfiles/js/performance.js
ls -la staticfiles/sw.js
ls -la staticfiles/fonts/fonts.css
```

### **Шаг 4: Перезапустите веб-приложение**
```bash
# В PythonAnywhere:
# 1. Перейдите в Web tab
# 2. Нажмите "Reload" для вашего домена
```

### **Шаг 5: Проверьте результат**
- Откройте сайт в браузере
- Откройте Developer Tools (F12)
- Проверьте Console - ошибки должны исчезнуть
- Проверьте Network - файлы должны загружаться с 200 статусом

## 🎯 Ожидаемый результат:

### **До исправления:**
```
❌ GET performance.css?v=2025.01.07.001:1 404 (Not Found)
❌ GET performance.js?v=2025.01.07.001:130 404 (Not Found)
❌ GET sw.js 404 (Not Found)
❌ Uncaught ReferenceError: YANDEX_METRICA_ID is not defined
❌ GET inter-var.woff2 404 (Not Found)
```

### **После исправления:**
```
✅ GET performance.css?v=2025.01.07.001:1 200 OK
✅ GET performance.js?v=2025.01.07.001:130 200 OK
✅ GET sw.js 200 OK
✅ Facebook Pixel загружается корректно
✅ Шрифты загружаются с fallback
```

## 🔍 Дополнительные проверки:

### **Проверьте настройки STATIC_URL:**
```python
# В production_settings.py должно быть:
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

### **Проверьте веб-сервер:**
```bash
# Убедитесь, что веб-сервер настроен на обслуживание статических файлов
# В PythonAnywhere это настраивается автоматически
```

### **Проверьте права доступа:**
```bash
# Убедитесь, что файлы доступны для чтения
chmod 644 staticfiles/css/performance.css
chmod 644 staticfiles/js/performance.js
chmod 644 staticfiles/sw.js
```

## 🚨 Если проблемы остаются:

### **1. Очистите кэш браузера:**
- Нажмите Ctrl+F5 (или Cmd+Shift+R на Mac)
- Или откройте в режиме инкогнито

### **2. Проверьте логи веб-сервера:**
```bash
# В PythonAnywhere: Web tab -> Log files
tail -f /var/log/nginx/error.log
```

### **3. Проверьте настройки Django:**
```bash
python manage.py check --settings=twocomms.production_settings
```

## ✅ После исправления:

- ✅ Все статические файлы загружаются
- ✅ Facebook Pixel работает корректно
- ✅ ServiceWorker регистрируется
- ✅ Шрифты загружаются с fallback
- ✅ Консоль чистая от ошибок
- ✅ Производительность оптимизирована

**Готово! Ваш сайт будет работать без ошибок в консоли!** 🎉
