#!/usr/bin/env python3
"""
Скрипт для отладки данных корзины
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
from productcolors.models import ProductColorVariant
from django.conf import settings

def debug_cart_data():
    """Отлаживаем данные корзины"""
    print("=== ОТЛАДКА ДАННЫХ КОРЗИНЫ ===\n")
    
    # Получаем несколько товаров для тестирования
    products = Product.objects.filter(main_image__isnull=False)[:3]
    
    for product in products:
        print(f"Товар: {product.title}")
        print(f"ID: {product.id}")
        
        # Проверяем основное изображение
        if product.main_image:
            print(f"  Основное изображение URL: {product.main_image.url}")
            print(f"  Основное изображение путь: {product.main_image.path}")
            print(f"  Файл существует: {os.path.exists(product.main_image.path)}")
        
        # Проверяем display_image
        if product.display_image:
            print(f"  Display изображение URL: {product.display_image.url}")
            print(f"  Display изображение путь: {product.display_image.path}")
            print(f"  Файл существует: {os.path.exists(product.display_image.path)}")
        
        # Проверяем цветовые варианты
        color_variants = ProductColorVariant.objects.filter(product=product)
        if color_variants.exists():
            print(f"  Цветовые варианты: {color_variants.count()}")
            for variant in color_variants[:2]:
                if variant.images.exists():
                    first_image = variant.images.first()
                    print(f"    Цвет {variant.color.name}:")
                    print(f"      URL: {first_image.image.url}")
                    print(f"      Путь: {first_image.image.path}")
                    print(f"      Файл существует: {os.path.exists(first_image.image.path)}")
        
        print("-" * 50)

def test_optimized_image_tag():
    """Тестируем тег optimized_image с реальными данными"""
    print("\n=== ТЕСТ ТЕГА OPTIMIZED_IMAGE ===\n")
    
    from storefront.templatetags.responsive_images import optimized_image
    
    # Получаем товар с изображением
    product = Product.objects.filter(main_image__isnull=False).first()
    if not product:
        print("Нет товаров с изображениями для тестирования")
        return
    
    print(f"Тестируем товар: {product.title}")
    print(f"Изображение: {product.main_image.url}")
    
    # Тестируем тег для мини-корзины (48x48)
    result = optimized_image(
        image_path=product.main_image.url,
        alt_text=product.title,
        class_name="w-100 h-100 object-fit-cover",
        width=48,
        height=48
    )
    
    print("Результат тега optimized_image для мини-корзины:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    # Тестируем тег без фиксированных размеров
    result2 = optimized_image(
        image_path=product.main_image.url,
        alt_text=product.title,
        class_name="w-100 h-100 object-fit-cover"
    )
    
    print("\nРезультат тега optimized_image без фиксированных размеров:")
    for key, value in result2.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    try:
        debug_cart_data()
        test_optimized_image_tag()
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
