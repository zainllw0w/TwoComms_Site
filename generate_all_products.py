#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
os.environ['DJANGO_SKIP_SYSTEM_CHECKS'] = '1'

django.setup()

from storefront.models import Product, Category
from django.conf import settings
import openai

def generate_ai_keywords(product):
    """Генерирует AI ключевые слова для товара"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        color_names = []
        try:
            from productcolors.models import ProductColorVariant
            for variant in ProductColorVariant.objects.filter(product=product):
                if variant.color and getattr(variant.color, 'name', None):
                    color_names.append(variant.color.name)
        except Exception:
            color_names = []
        
        prompt = (
            f"Створіть до 20 SEO ключових слів для товару. Назва: {product.title}. "
            f"Категорія: {product.category.name if product.category else 'N/A'}. "
            f"Опис: {product.description or ''}. "
            f"Кольори: {', '.join(color_names) if color_names else 'N/A'}. "
            "Виведіть ключові слова через кому."
        )
        
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "Ви - генератор SEO ключових слів."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=200
        )
        
        content = response.choices[0].message.content
        if content:
            keywords = [kw.strip() for kw in content.split(',') if kw.strip()]
            return keywords[:20]
        return []
        
    except Exception as e:
        print(f"Error generating keywords for {product.title}: {e}")
        return []

def generate_ai_description(product):
    """Генерирует AI описание для товара"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        prompt = (
            f"Напишіть стислий SEO-дружній опис товару '{product.title}'. "
            f"Категорія: {product.category.name if product.category else 'N/A'}. "
            f"Ціна: {product.final_price} грн."
        )
        
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "Ви - SEO-копірайтер."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=150
        )
        
        content = response.choices[0].message.content
        return content.strip() if content else ""
        
    except Exception as e:
        print(f"Error generating description for {product.title}: {e}")
        return ""

def generate_category_keywords(category):
    """Генерирует AI ключевые слова для категории"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        prompt = (
            f"Створіть до 20 SEO ключових слів для категорії '{category.name}'. "
            f"Опис: {category.description or ''}."
        )
        
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "Ви - генератор SEO ключових слів."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=200
        )
        
        content = response.choices[0].message.content
        if content:
            keywords = [kw.strip() for kw in content.split(',') if kw.strip()]
            return keywords[:20]
        return []
        
    except Exception as e:
        print(f"Error generating keywords for category {category.name}: {e}")
        return []

def generate_category_description(category):
    """Генерирует AI описание для категории"""
    try:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        client = openai.OpenAI(api_key=api_key)
        
        prompt = (
            f"Напишіть стислий SEO-дружній опис категорії '{category.name}'. "
        )
        if category.description:
            prompt += f" Опис: {category.description}."
        
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "Ви - SEO-копірайтер."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=150
        )
        
        content = response.choices[0].message.content
        return content.strip() if content else ""
        
    except Exception as e:
        print(f"Error generating description for category {category.name}: {e}")
        return ""

def main():
    print("=== AI Content Generator for All Products ===")
    
    # Обрабатываем товары
    products = Product.objects.all()
    print(f"Processing {products.count()} products...")
    
    processed = 0
    for product in products:
        try:
            processed += 1
            print(f"Product {processed}/{products.count()}: {product.title}")
            
            # Генерируем ключевые слова
            keywords = generate_ai_keywords(product)
            if keywords:
                product.ai_keywords = ', '.join(keywords)
                print(f"  Keywords: {len(keywords)} words")
            
            # Генерируем описание
            description = generate_ai_description(product)
            if description:
                product.ai_description = description
                print(f"  Description: {len(description)} chars")
            
            # Сохраняем
            if keywords or description:
                product.ai_content_generated = True
                product.save()
                print(f"  ✅ Saved")
            else:
                print(f"  ⚠️ No content generated")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Обрабатываем категории
    categories = Category.objects.all()
    print(f"\nProcessing {categories.count()} categories...")
    
    for category in categories:
        try:
            print(f"Category: {category.name}")
            
            # Генерируем ключевые слова
            keywords = generate_category_keywords(category)
            if keywords:
                category.ai_keywords = ', '.join(keywords)
                print(f"  Keywords: {len(keywords)} words")
            
            # Генерируем описание
            description = generate_category_description(category)
            if description:
                category.ai_description = description
                print(f"  Description: {len(description)} chars")
            
            # Сохраняем
            if keywords or description:
                category.ai_content_generated = True
                category.save()
                print(f"  ✅ Saved")
            else:
                print(f"  ⚠️ No content generated")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print(f"\n=== Generation completed! ===")
    print(f"Processed {processed} products and {categories.count()} categories")

if __name__ == "__main__":
    main()
