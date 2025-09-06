#!/usr/bin/env python3
"""
Скрипт для проверки прав доступа к MySQL базе данных
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

def check_mysql_permissions():
    """Проверяет права доступа к MySQL базе данных"""
    
    print("🔍 Проверка прав доступа к MySQL базе данных...")
    print("=" * 60)
    
    # Загружаем переменные окружения
    env_file = BASE_DIR / 'db_config.env'
    if env_file.exists():
        print("📄 Загружаем переменные из db_config.env...")
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        print("⚠️  Файл db_config.env не найден!")
        return False
    
    # Настройка Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
    
    try:
        django.setup()
        print("✅ Django настроен успешно")
    except Exception as e:
        print(f"❌ Ошибка настройки Django: {e}")
        return False
    
    # Проверка подключения к базе данных
    try:
        from django.db import connection
        from django.conf import settings
        
        print(f"📊 Настройки базы данных:")
        print(f"   Тип: {settings.DATABASES['default']['ENGINE']}")
        print(f"   База: {settings.DATABASES['default']['NAME']}")
        print(f"   Пользователь: {settings.DATABASES['default']['USER']}")
        print(f"   Хост: {settings.DATABASES['default']['HOST']}")
        print(f"   Порт: {settings.DATABASES['default']['PORT']}")
        
        with connection.cursor() as cursor:
            # Проверяем подключение
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            print("✅ Подключение к базе данных успешно!")
            
            # Проверяем текущую базу данных
            cursor.execute("SELECT DATABASE()")
            current_db = cursor.fetchone()[0]
            print(f"   Текущая база данных: {current_db}")
            
            # Проверяем права на создание таблиц
            try:
                cursor.execute("CREATE TEMPORARY TABLE test_permissions (id INT)")
                cursor.execute("DROP TEMPORARY TABLE test_permissions")
                print("✅ Права на создание/удаление таблиц: OK")
            except Exception as e:
                print(f"❌ Права на создание/удаление таблиц: {e}")
            
            # Проверяем права на вставку данных
            try:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"✅ Права на чтение таблиц: OK ({len(tables)} таблиц)")
            except Exception as e:
                print(f"❌ Права на чтение таблиц: {e}")
            
            # Проверяем существующие таблицы
            if tables:
                print("   Существующие таблицы:")
                for table in tables[:5]:
                    print(f"     - {table[0]}")
                if len(tables) > 5:
                    print(f"     ... и еще {len(tables) - 5} таблиц")
            
            # Проверяем права на миграции
            try:
                cursor.execute("SHOW TABLES LIKE 'django_migrations'")
                migrations_table = cursor.fetchone()
                if migrations_table:
                    print("✅ Таблица миграций существует")
                    cursor.execute("SELECT COUNT(*) FROM django_migrations")
                    count = cursor.fetchone()[0]
                    print(f"   Количество примененных миграций: {count}")
                else:
                    print("ℹ️  Таблица миграций не существует (это нормально для новой БД)")
            except Exception as e:
                print(f"❌ Ошибка проверки миграций: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        
        # Анализируем тип ошибки
        error_str = str(e)
        if "Access denied" in error_str:
            if "to database" in error_str:
                print("\n🔧 Проблема: Нет прав доступа к базе данных")
                print("   Решение: Назначьте права пользователю на базу данных")
            elif "using password" in error_str:
                print("\n🔧 Проблема: Неправильный пароль")
                print("   Решение: Проверьте пароль в db_config.env")
            else:
                print("\n🔧 Проблема: Нет прав доступа")
                print("   Решение: Проверьте настройки пользователя MySQL")
        elif "Unknown database" in error_str:
            print("\n🔧 Проблема: База данных не существует")
            print("   Решение: Создайте базу данных через панель управления")
        elif "Can't connect" in error_str:
            print("\n🔧 Проблема: MySQL сервер недоступен")
            print("   Решение: Проверьте, что MySQL сервер запущен")
        
        print("\n📋 Дополнительные шаги:")
        print("   1. Проверьте настройки в панели управления хостинга")
        print("   2. Убедитесь, что пользователь имеет права на базу данных")
        print("   3. Проверьте правильность пароля")
        print("   4. Обратитесь к хостинг-провайдеру при необходимости")
        
        return False

def main():
    """Основная функция"""
    print("🗄️  Проверка прав доступа к MySQL базе данных")
    print("=" * 60)
    
    success = check_mysql_permissions()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Проверка завершена успешно!")
        print("   Теперь вы можете выполнить миграции:")
        print("   python manage.py makemigrations")
        print("   python manage.py migrate")
    else:
        print("💥 Проверка завершена с ошибками!")
        print("   Исправьте проблемы и повторите проверку")
        print("   См. файл MYSQL_ACCESS_FIX.md для подробных инструкций")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
