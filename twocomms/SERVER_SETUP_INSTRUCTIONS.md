# 🖥️ Инструкции по настройке сервера для миграции к MySQL

## 📋 Требования

Для выполнения миграций на сервере вам понадобится:

1. **Доступ к серверу** (SSH или панель управления)
2. **Python 3.8+** установлен на сервере
3. **MySQL сервер** запущен и доступен
4. **База данных** создана через панель управления

## 🗄️ Настройка базы данных

### 1. Создание базы данных через панель управления

Если база данных еще не создана:

1. **Войдите в панель управления** (cPanel, Plesk, или другая)
2. **Найдите раздел "Базы данных MySQL"**
3. **Создайте новую базу данных:**
   - Имя: `qlknpodo_MySQL_DB`
   - Кодировка: `utf8mb4_unicode_ci`

4. **Создайте пользователя базы данных:**
   - Имя пользователя: `qlknpodo_zainllw0w`
   - Пароль: `[REDACTED_SSH_PASSWORD]`

5. **Назначьте права доступа:**
   - Выберите базу данных `qlknpodo_MySQL_DB`
   - Выберите пользователя `qlknpodo_zainllw0w`
   - Назначьте **ВСЕ ПРАВА** (ALL PRIVILEGES)

### 2. Проверка подключения к базе данных

Выполните на сервере:

```bash
# Подключение к MySQL через командную строку
mysql -h localhost -u qlknpodo_zainllw0w -p qlknpodo_MySQL_DB

# Введите пароль: [REDACTED_SSH_PASSWORD]
# Если подключение успешно, вы увидите приглашение MySQL
```

## 🐍 Настройка Python окружения

### 1. Установка зависимостей

```bash
# Установка PyMySQL (альтернатива mysqlclient)
pip install PyMySQL

# Или если доступен mysqlclient:
pip install mysqlclient

# Установка Django зависимостей
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` на сервере:

```bash
# Создание файла с переменными окружения
cat > .env << 'EOF'
DB_ENGINE=mysql
DB_NAME=qlknpodo_MySQL_DB
DB_USER=qlknpodo_zainllw0w
DB_PASSWORD=[REDACTED_SSH_PASSWORD]
DB_HOST=localhost
DB_PORT=3306
SECRET_KEY=django-insecure-!t*_^p60d-88kvjs%*&!czbes-q8-#$r!-d_0%o495rfed6i*
DEBUG=False
ALLOWED_HOSTS=twocomms.shop,www.twocomms.shop,twocomms.pythonanywhere.com
EOF
```

## 🚀 Выполнение миграций

### 1. Загрузка переменных окружения

```bash
# Загрузка переменных окружения
export $(cat .env | grep -v '^#' | xargs)
```

### 2. Проверка подключения

```bash
# Проверка подключения к базе данных
python manage.py dbshell
# Если подключение успешно, вы увидите приглашение MySQL
# Выйдите командой: exit
```

### 3. Выполнение миграций

```bash
# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser
# Логин: zainllw0w
# Email: admin@twocomms.shop
# Пароль: 123

# Сбор статических файлов
python manage.py collectstatic --noinput
```

## 🔧 Альтернативные способы

### 1. Использование готовых скриптов

Если у вас есть файлы `migrate_to_mysql.sh` и `db_config.env`:

```bash
# Сделать скрипт исполняемым
chmod +x migrate_to_mysql.sh

# Выполнить миграцию
./migrate_to_mysql.sh
```

### 2. Ручное выполнение команд

```bash
# Пошаговое выполнение
python manage.py makemigrations storefront
python manage.py makemigrations accounts
python manage.py makemigrations orders
python manage.py makemigrations productcolors

python manage.py migrate

python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## 🐛 Устранение проблем

### Ошибка "Access denied"

```
(1045, "Access denied for user 'qlknpodo_zainllw0w'@'localhost'")
```

**Решение:**
1. Проверьте пароль в панели управления
2. Убедитесь, что пользователь имеет права на базу данных
3. Проверьте, что база данных существует

### Ошибка "Unknown database"

```
(1049, "Unknown database 'qlknpodo_MySQL_DB'")
```

**Решение:**
1. Создайте базу данных через панель управления
2. Проверьте правильность имени базы данных

### Ошибка "ModuleNotFoundError: No module named 'MySQLdb'"

**Решение:**
```bash
# Установите PyMySQL
pip install PyMySQL

# Или mysqlclient (если доступен)
pip install mysqlclient
```

## ✅ Проверка успешной миграции

После выполнения миграций:

1. **Проверьте таблицы в базе данных:**
   ```sql
   USE qlknpodo_MySQL_DB;
   SHOW TABLES;
   ```

2. **Запустите сервер:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

3. **Откройте админку:**
   - URL: `http://your-server:8000/admin/`
   - Логин: `zainllw0w`
   - Пароль: `123`

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи Django: `python manage.py check`
2. Проверьте подключение к базе: `python manage.py dbshell`
3. Убедитесь, что все переменные окружения загружены: `env | grep DB_`
