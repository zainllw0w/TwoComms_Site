#!/usr/bin/env python3
"""
Скрипт для проверки подключения к MySQL базе данных
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

def test_database_connection():
    """Тестирует подключение к базе данных"""
    
    print("🔍 Проверка подключения к базе данных...")
    print("=" * 50)
    
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
        print("   Создайте файл с переменными окружения")
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
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            
        print("✅ Подключение к базе данных успешно!")
        print(f"   Результат тестового запроса: {result}")
        
        # Проверяем существование базы данных
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()[0]
        print(f"   Текущая база данных: {current_db}")
        
        # Проверяем таблицы
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"   Количество таблиц: {len(tables)}")
        
        if tables:
            print("   Существующие таблицы:")
            for table in tables[:5]:  # Показываем первые 5 таблиц
                print(f"     - {table[0]}")
            if len(tables) > 5:
                print(f"     ... и еще {len(tables) - 5} таблиц")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        print("\n🔧 Возможные решения:")
        print("   1. Проверьте, что MySQL сервер запущен")
        print("   2. Убедитесь, что база данных существует")
        print("   3. Проверьте правильность пароля")
        print("   4. Убедитесь, что пользователь имеет права на базу данных")
        return False

def main():
    """Основная функция"""
    print("🗄️  Тестирование подключения к MySQL базе данных")
    print("=" * 60)
    
    success = test_database_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Тест завершен успешно!")
        print("   Теперь вы можете выполнить миграции:")
        print("   python manage.py makemigrations")
        print("   python manage.py migrate")
    else:
        print("💥 Тест завершен с ошибками!")
        print("   Исправьте проблемы и повторите тест")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
