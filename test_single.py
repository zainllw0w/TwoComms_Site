#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')
os.environ['DJANGO_SKIP_SYSTEM_CHECKS'] = '1'

django.setup()

from storefront.models import Product
from django.conf import settings
import openai

print('=== Test GPT-4o ===')
product = Product.objects.first()
print(f'Product: {product.title}')

api_key = getattr(settings, 'OPENAI_API_KEY', None)
client = openai.OpenAI(api_key=api_key)

try:
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {'role': 'system', 'content': 'Ви - генератор SEO ключових слів.'},
            {'role': 'user', 'content': f'Створіть до 20 SEO ключових слів для товару. Назва: {product.title}. Категорія: {product.category.name if product.category else "N/A"}. Виведіть ключові слова через кому.'}
        ],
        max_completion_tokens=200
    )
    
    content = response.choices[0].message.content
    print(f'GPT-4o response: {content}')
    
    if content:
        keywords = [kw.strip() for kw in content.split(',') if kw.strip()]
        print(f'Keywords: {keywords}')
        print(f'Number of keywords: {len(keywords)}')
        
        # Сохраняем в базу данных
        product.ai_keywords = ', '.join(keywords)
        product.ai_content_generated = True
        product.save()
        print('✅ Saved to database!')
    else:
        print('❌ Empty response')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
