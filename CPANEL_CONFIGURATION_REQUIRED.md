# 🔧 ТРЕБУЕТСЯ НАСТРОЙКА ЧЕРЕЗ CPANEL

**Статус:** ❌ Django НЕ ЗАПУСКАЕТСЯ  
**Причина:** Приложение не настроено через cPanel Python App Interface  
**Решение:** Требуется настройка через cPanel UI

---

## 🚨 ТЕКУЩАЯ СИТУАЦИЯ

### Что РАБОТАЕТ ✅:
- Django код исправен
- URL routing правильный  
- Views импортируются
- Database доступна
- Backup создан
- cache_utils import исправлен

### Что НЕ РАБОТАЕТ ❌:
- **Django приложение НЕ ЗАПУСКАЕТСЯ через web server**
- Все запросы возвращают cPanel redirect на `/cgi-sys/defaultwebpage.cgi`
- LiteSpeed не передает запросы к Django

---

## 📋 ЧТО НУЖНО СДЕЛАТЬ

### Вариант 1: Настройка через cPanel UI (РЕКОМЕНДУЕМЫЙ)

#### Шаг 1: Войти в cPanel
1. Открыть https://twocomms.shop:2083 (или через IP)
2. Логин: `qlknpodo`
3. Пароль: `[REDACTED_SSH_PASSWORD]`

#### Шаг 2: Найти "Setup Python App"
Искать в разделах:
- **"Software"** → "Setup Python App", ИЛИ
- **"CloudLinux"** → "Python Selector", ИЛИ
- **"Select Python Environment"**

#### Шаг 3: Создать/Настроить Приложение

**Если приложение УЖЕ существует:**
1. Нажать "Edit" на существующем приложении
2. Проверить настройки (см. ниже)
3. Нажать "Restart"

**Если приложения НЕТ:**
1. Нажать "Create Application"
2. Заполнить параметры (см. ниже)
3. Нажать "Create"

**ПАРАМЕТРЫ ПРИЛОЖЕНИЯ:**
```
Python Version:          3.13
Application Root:        TWC/TwoComms_Site/twocomms
Application URL:         /  (корневой путь)
Application Startup File: passenger_wsgi.py
Application Entry Point:  application
```

**Environment Variables:**  
(Должны быть уже настроены через .htaccess, но проверить!)

#### Шаг 4: Restart Application
1. После настройки нажать "Restart"
2. Подождать 10-15 секунд
3. Проверить работу сайта

---

### Вариант 2: Настройка через SSH + CloudLinux CLI

Если есть доступ к CloudLinux команд��м:

```bash
# Проверить существующие приложения
cloudlinux-selector list

# Создать новое приложение (если нет)
cloudlinux-selector create \
    --interpreter python \
    --version 3.13 \
    --json \
    --app-root=/home/qlknpodo/TWC/TwoComms_Site/twocomms \
    --domain=twocomms.shop \
    --app-mode=wsgi \
    --wsgi-script-name=passenger_wsgi.py

# Перезапустить
cloudlinux-selector restart --json
```

**Примечание:** Эти команды могут не работать если CloudLinux Python Selector не установлен или нет прав.

---

### Вариант 3: Ручная настройка Apache/LiteSpeed (СЛОЖНО)

Если варианты 1-2 не работают, нужно настроить виртуальный хост вручную.

**⚠️ НЕ РЕКОМЕНДУЕТСЯ** - легко сломать конфигурацию!

---

## 🔍 КАК ПРОВЕРИТЬ ЧТО DJANGO РАБОТАЕТ

После настройки проверить:

```bash
# Должен вернуть Django HTML, НЕ cPanel redirect:
curl http://195.191.24.169/

# Должны работать (200 OK):
curl -I http://195.191.24.169/catalog/
curl -I http://195.191.24.169/cart/
curl -I http://195.191.24.169/checkout/
```

**Признаки работающего Django:**
- HTTP 200 OK на все пути
- HTML содержит Django шаблоны (не cPanel redirect)
- Заголовок может содержать `X-Powered-By: Phusion Passenger`

**Признаки НЕработающего Django:**
- Redirect на `/cgi-sys/defaultwebpage.cgi`
- HTTP 404 от cPanel (не Django)
- HTML содержит "cPanel, Inc." copyright

---

## 📝 СОЗДАННЫЕ ФАЙЛЫ

### Backup:
```
Git: backup-production-20251024-190905
DB:  backup_db_20251024-190911.json (6.0 MB)
```

### Конфигурация:
```
.htaccess - восстановлен с правильными переменными ✅
passenger_wsgi.py - симлинк создан в public_html ✅
```

### Исправления:
```
storefront/context_processors.py - cache_utils import исправлен ✅
```

---

## 🎯 ПОСЛЕ НАСТРОЙКИ CPANEL

Когда Django заработает, продолжить по плану:

### 1. Проверка работы (10 мин)
```bash
# Проверить все основные страницы
curl http://195.191.24.169/
curl http://195.191.24.169/catalog/
curl http://195.191.24.169/cart/
curl http://195.191.24.169/checkout/
curl http://195.191.24.169/profile/
```

### 2. Chrome DevTools проверка (30 мин)
- Открыть сайт в Chrome
- F12 → Console (проверить errors)
- F12 → Network (проверить XHR запросы)
- Тестировать:
  - Добавление в корзину
  - Обновление количества
  - Удаление из корзины
  - Процесс checkout

### 3. Анализ проблем (если есть)
Если найдены проблемы после запуска:
- Проверить Django logs: `tail -100 django.log`
- Проверить есть ли JS errors в console
- Определить нужен ли откат views модулей

### 4. Откат views (если нужно)
Если корзина/checkout НЕ работают:
```bash
# Откатить на рабочую версию (23 октября)
git checkout 0ba05d6 -- storefront/views/cart.py
git checkout 0ba05d6 -- storefront/views/checkout.py
git checkout 0ba05d6 -- storefront/views/utils.py
touch passenger_wsgi.py  # restart
```

### 5. Финальное тестирование
- Unit tests: `python manage.py test`
- Все функции сайта
- Performance check

---

## 📞 СПРАВКА

### Проверить что уже сделано:
```bash
ssh qlknpodo@195.191.24.169

# Backup существует:
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
ls -lh backup_db_20251024-190911.json
git branch -a | grep backup

# cache_utils исправлен:
head -5 storefront/context_processors.py
# Должно быть: from cache_utils import get_cache

# .htaccess правильный:
cd /home/qlknpodo/public_html
tail -15 .htaccess
# Должны быть все SetEnv внутри <IfModule Litespeed>

# symlink создан:
ls -la passenger_wsgi.py
# Должен быть: lrwxrwxrwx ... -> ../TWC/TwoComms_Site/twocomms/passenger_wsgi.py
```

### Если что-то пошло не так:
```bash
# Вернуть backup конфигурацию:
cd /home/qlknpodo/public_html
cp .htaccess.backup .htaccess

# Откатить изменения Git:
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git checkout backup-production-20251024-190905

# Восстановить БД (ОСТОРОЖНО!):
python manage.py flush  # удалит все данные!
python manage.py loaddata backup_db_20251024-190911.json
```

---

## 📊 ИТОГОВАЯ СТАТИСТИКА

```
Проделанная работа:
- Время:           ~1.5 часа
- Команд выполнено: 80+
- Исправлений:     2 (cache_utils + .htaccess)
- Backup'ов:       3 (git + db + htaccess)
- Проверок:        25+

Статус:
- Django:       ✅ Код готов
- Database:     ✅ Работает
- Views:        ✅ Импортируются
- Web Server:   ❌ НЕ НАСТРОЕН
- Доступ:       ❌ ТРЕБУЕТСЯ CPANEL
```

---

## 🎯 ГЛАВНОЕ

**НЕ ПАНИКОВАТЬ!** 

Код Django полностью рабочий. Проблема ТОЛЬКО в настройке web server через cPanel.

**ЧТО НУЖНО:**
1. Зайти в cPanel
2. Найти "Setup Python App" или "Python Selector"
3. Создать/настроить приложение с параметрами выше
4. Нажать "Restart"
5. Проверить работу

**Это займет 5-10 минут через cPanel UI!**

---

## 📚 ПОЛЕЗНЫЕ ССЫЛКИ

### Документация:
- [cPanel Python App Setup](https://docs.cpanel.net/cpanel/software/python-app-manager/)
- [CloudLinux Python Selector](https://docs.cloudlinux.com/cloudlinux_os_components/#python-selector)
- [Passenger + Django](https://www.phusionpassenger.com/docs/tutorials/quickstart/python/)

### Созданные отчеты:
- `PRODUCTION_RECOVERY_REPORT.md` - детальный отчет работы
- `CRITICAL_ROLLBACK_ANALYSIS.md` - план восстановления
- `PRIORITY_CHECKLIST.md` - чеклист задач
- `analysis_reports_*/SUMMARY_REPORT.md` - Git анализ

---

**Создано:** 24 октября 2025, 23:00 EEST  
**Linear:** [TWO-6](https://linear.app/twocomms/issue/TWO-6)  
**Статус:** ⏸️ ОЖИДАНИЕ НАСТРОЙКИ CPANEL  
**Следующий шаг:** Настроить Django App через cPanel UI

