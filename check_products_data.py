#!/usr/bin/env python3
"""
Скрипт для проверки данных товаров
"""

import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
sys.path.append('/Users/zainllw0w/PycharmProjects/TwoComms/twocomms')

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
django.setup()

from storefront.models import Product

def check_products_data():
    """Проверяем данные товаров"""
    print("=== ПРОВЕРКА ДАННЫХ ТОВАРОВ ===\n")
    
    # Получаем первые 10 товаров
    products = Product.objects.all()[:10]
    
    for i, product in enumerate(products, 1):
        print(f"Товар {i}: {product.title}")
        print(f"ID: {product.id}")
        print(f"Display image: {product.display_image}")
        print(f"Main image: {product.main_image}")
        
        if product.display_image:
            print(f"  Display image URL: {product.display_image.url}")
            print(f"  Display image путь: {product.display_image.path}")
            print(f"  Файл существует: {os.path.exists(product.display_image.path)}")
        elif product.main_image:
            print(f"  Main image URL: {product.main_image.url}")
            print(f"  Main image путь: {product.main_image.path}")
            print(f"  Файл существует: {os.path.exists(product.main_image.path)}")
        else:
            print("  НЕТ ИЗОБРАЖЕНИЙ!")
        
        print("-" * 50)

if __name__ == "__main__":
    try:
        check_products_data()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
