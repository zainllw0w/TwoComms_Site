# 🚀 Git Workflow и Деплой для TwoComms

## 📋 Процесс разработки

### 1. Работа локально

```bash
# Получить последние изменения
git pull origin main

# Внести изменения в коде
# ... редактируем файлы ...

# Проверить изменения
git status
git diff

# Добавить файлы
git add .

# Закоммитить
git commit -m "Описание изменений"

# Отправить в GitHub
git push origin main
```

### 2. Автоматический деплой

Используем скрипт `deploy.sh` для автоматического деплоя:

```bash
./deploy.sh "Описание изменений"
```

**Что делает скрипт:**
1. ✅ Добавляет все файлы в git
2. ✅ Коммитит изменения
3. ✅ Пушит в GitHub
4. ✅ Подключается к серверу
5. ✅ Делает git pull на сервере
6. ✅ Собирает статику
7. ✅ Перезапускает сервер

### 3. Ручной деплой (если нужно)

```bash
# Подключиться к серверу
ssh qlknpodo@195.191.24.169

# Перейти в директорию проекта
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms

# Получить изменения
git pull origin main

# Активировать виртуальное окружение
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate

# Применить миграции (если есть)
python manage.py migrate

# Собрать статику
python manage.py collectstatic --noinput

# Перезапустить сервер
touch twocomms/wsgi.py
```

---

## 🔧 Синхронизация изменений с сервера

Если на сервере были сделаны изменения напрямую:

```bash
# На сервере: закоммитить изменения
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git add -A
git commit -m "Server changes"
# Нужно настроить git credentials для push

# Локально: получить изменения
git pull origin main
```

---

## 📝 Лучшие практики

### ✅ Делать:
- Всегда работать локально
- Тестировать изменения локально
- Коммитить часто с понятными сообщениями
- Использовать deploy.sh для деплоя
- Проверять сайт после деплоя

### ❌ Не делать:
- Редактировать файлы напрямую на сервере
- Делать git push с сервера (нет credentials)
- Забывать собирать статику
- Коммитить временные файлы

---

## 🎯 Типичные сценарии

### Сценарий 1: Исправление CSS

```bash
# 1. Редактируем CSS локально
nano twocomms/twocomms_django_theme/static/css/styles.css

# 2. Деплоим
./deploy.sh "Fix CSS animations for CLS"

# 3. Проверяем на сайте
open https://twocomms.shop
```

### Сценарий 2: Обновление Django views

```bash
# 1. Редактируем views
nano twocomms/storefront/views.py

# 2. Деплоим
./deploy.sh "Optimize database queries"

# 3. Проверяем работоспособность
```

### Сценарий 3: Добавление новых файлов

```bash
# 1. Создаем файл
nano twocomms/storefront/utils.py

# 2. Деплоим
./deploy.sh "Add new utility functions"
```

### Сценарий 4: Изменения в базе данных

```bash
# 1. Создаем миграцию локально
cd twocomms
python manage.py makemigrations

# 2. Коммитим
git add .
git commit -m "Add new Product fields"
git push origin main

# 3. На сервере применяем миграцию
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git pull origin main
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/activate
python manage.py migrate
touch twocomms/wsgi.py
```

---

## 🔐 Безопасность

### Файлы, которые НЕ должны быть в git:

- `.env` - переменные окружения
- `*.pyc` - скомпилированные файлы Python
- `__pycache__/` - кэш Python
- `media/` - загруженные пользователями файлы
- `staticfiles/` - собранная статика
- `db.sqlite3` - база данных (если используется SQLite)
- Временные отчеты и логи

Все это уже добавлено в `.gitignore`

---

## 📊 Мониторинг

После деплоя проверять:

```bash
# Проверить статус сервера
ssh qlknpodo@195.191.24.169
systemctl status your-wsgi-service

# Проверить логи
tail -f /var/log/your-app/error.log

# Проверить Redis
/home/qlknpodo/redis/bin/redis-cli info stats
```

---

## 🆘 Откат изменений

Если что-то пошло не так:

```bash
# Локально: откатить последний коммит
git reset --soft HEAD~1

# На сервере: откатить к предыдущей версии
ssh qlknpodo@195.191.24.169
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git log  # посмотреть историю
git reset --hard HEAD~1  # откатить на 1 коммит назад
python manage.py collectstatic --noinput
touch twocomms/wsgi.py
```

---

## 📞 Полезные команды

```bash
# Статус git
git status

# История коммитов
git log --oneline -10

# Посмотреть изменения
git diff

# Посмотреть изменения конкретного файла
git diff path/to/file.py

# Отменить изменения в файле (до коммита)
git checkout -- path/to/file.py

# Удалить неотслеживаемые файлы
git clean -fd

# Обновить .gitignore
git rm -r --cached .
git add .
git commit -m "Update .gitignore"
```

---

## 🎉 Готово!

Теперь у вас полноценный Git workflow:
1. ✅ Работа локально
2. ✅ Автоматический деплой одной командой
3. ✅ Синхронизация через GitHub
4. ✅ Безопасность и откат изменений

**Используйте:** `./deploy.sh "Ваше сообщение"` для деплоя!
