#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
os.environ['DJANGO_SKIP_SYSTEM_CHECKS'] = '1'

django.setup()

from storefront.models import Product, ProductImage
from productcolors.models import ProductColorVariant, ProductColorImage
from django.conf import settings
import openai

def generate_alt_text_for_product_image(product, image_type="main"):
    """Генерирует SEO-оптимизированный alt-текст для изображения товара"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        # Создаем промпт для генерации alt-текста
        prompt = (
            f"Створіть SEO-оптимізований alt-текст для зображення товару. "
            f"Назва товару: {product.title}. "
            f"Категорія: {product.category.name if product.category else 'одяг'}. "
            f"Тип зображення: {image_type}. "
            f"Обов'язково включіть назву товару та бренд 'TwoComms'. "
            f"Alt-текст повинен бути коротким (до 125 символів), описовим та SEO-дружнім. "
            f"Використовуйте українську мову. "
            f"Приклад формату: 'Футболка класична TwoComms - якісний одяг з ексклюзивним дизайном'"
        )
        
        response = client.chat.completions.create(
            model='gpt-5',
            messages=[
                {"role": "system", "content": "Ви - SEO-спеціаліст, який створює оптимізовані alt-тексти для зображень товарів."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=100
        )
        
        content = response.choices[0].message.content
        if content:
            # Очищаем и ограничиваем длину
            alt_text = content.strip()
            if len(alt_text) > 125:
                alt_text = alt_text[:122] + "..."
            return alt_text
        return ""
        
    except Exception as e:
        print(f"Error generating alt text for {product.title}: {e}")
        return ""

def generate_alt_text_for_color_image(product, color_name, image_type="color"):
    """Генерирует alt-текст для изображения цветового варианта"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        prompt = (
            f"Створіть SEO-оптимізований alt-текст для зображення кольорового варіанту товару. "
            f"Назва товару: {product.title}. "
            f"Колір: {color_name}. "
            f"Категорія: {product.category.name if product.category else 'одяг'}. "
            f"Обов'язково включіть назву товару, колір та бренд 'TwoComms'. "
            f"Alt-текст повинен бути коротким (до 125 символів), описовим та SEO-дружнім. "
            f"Використовуйте українську мову."
        )
        
        response = client.chat.completions.create(
            model='gpt-5',
            messages=[
                {"role": "system", "content": "Ви - SEO-спеціаліст, який створює оптимізовані alt-тексти для зображень товарів."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=100
        )
        
        content = response.choices[0].message.content
        if content:
            alt_text = content.strip()
            if len(alt_text) > 125:
                alt_text = alt_text[:122] + "..."
            return alt_text
        return ""
        
    except Exception as e:
        print(f"Error generating alt text for {product.title} color {color_name}: {e}")
        return ""

def main():
    print("=== AI Alt Text Generator for Product Images ===")
    
    # Обрабатываем основные изображения товаров
    products = Product.objects.all()
    print(f"Processing {products.count()} products for main images...")
    
    processed_main_images = 0
    for product in products:
        try:
            if product.main_image:
                alt_text = generate_alt_text_for_product_image(product, "головне зображення")
                if alt_text:
                    product.main_image_alt = alt_text
                    product.save()
                    processed_main_images += 1
                    print(f"  ✅ Main image alt text generated for: {product.title}")
                    print(f"    Alt text: {alt_text}")
                else:
                    print(f"  ⚠️ Failed to generate alt text for: {product.title}")
        except Exception as e:
            print(f"  ❌ Error processing {product.title}: {e}")
    
    # Обрабатываем дополнительные изображения товаров
    print(f"\nProcessing additional product images...")
    additional_images = ProductImage.objects.all()
    processed_additional = 0
    
    for img in additional_images:
        try:
            alt_text = generate_alt_text_for_product_image(img.product, "додаткове зображення")
            if alt_text:
                img.alt_text = alt_text
                img.save()
                processed_additional += 1
                print(f"  ✅ Additional image alt text generated for: {img.product.title}")
                print(f"    Alt text: {alt_text}")
            else:
                print(f"  ⚠️ Failed to generate alt text for additional image: {img.product.title}")
        except Exception as e:
            print(f"  ❌ Error processing additional image for {img.product.title}: {e}")
    
    # Обрабатываем изображения цветовых вариантов
    print(f"\nProcessing color variant images...")
    try:
        color_variants = ProductColorVariant.objects.all()
        processed_color_images = 0
        
        for variant in color_variants:
            try:
                color_images = ProductColorImage.objects.filter(color_variant=variant)
                for img in color_images:
                    color_name = variant.color.name if variant.color and variant.color.name else "невідомий колір"
                    alt_text = generate_alt_text_for_color_image(variant.product, color_name)
                    if alt_text:
                        img.alt_text = alt_text
                        img.save()
                        processed_color_images += 1
                        print(f"  ✅ Color image alt text generated for: {variant.product.title} ({color_name})")
                        print(f"    Alt text: {alt_text}")
                    else:
                        print(f"  ⚠️ Failed to generate alt text for color image: {variant.product.title} ({color_name})")
            except Exception as e:
                print(f"  ❌ Error processing color variant for {variant.product.title}: {e}")
                
    except ImportError:
        print("  ⚠️ ProductColorVariant model not found, skipping color images")
    
    print(f"\n=== Alt Text Generation Completed! ===")
    print(f"Processed {processed_main_images} main product images")
    print(f"Processed {processed_additional} additional product images")
    print(f"Processed {processed_color_images if 'processed_color_images' in locals() else 0} color variant images")
    print(f"Total: {processed_main_images + processed_additional + (processed_color_images if 'processed_color_images' in locals() else 0)} images")

if __name__ == "__main__":
    main()
