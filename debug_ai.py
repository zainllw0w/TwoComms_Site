#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')

django.setup()

from storefront.seo_utils import SEOKeywordGenerator, SEOContentOptimizer
from storefront.models import Product, Category
from django.conf import settings
import openai

print("=== Debug AI Generation ===")

# Get first product
product = Product.objects.first()
if not product:
    print("No products found!")
    sys.exit(1)

print(f"Testing with product: {product.title}")
print(f"Product category: {product.category.name if product.category else 'None'}")
print(f"Product description: {product.description[:100] if product.description else 'None'}...")

# Test API key
api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
print(f"API Key: {api_key[:10]}...{api_key[-4:] if api_key else 'None'}")

# Test OpenAI client
try:
    client = openai.OpenAI(api_key=api_key)
    print("OpenAI client created successfully")
except Exception as e:
    print(f"Failed to create OpenAI client: {e}")
    sys.exit(1)

# Test direct API call
try:
    print("\n=== Testing direct API call ===")
    response = client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {"role": "system", "content": "Ви - генератор SEO ключових слів."},
            {"role": "user", "content": f"Створіть до 20 SEO ключових слів для товару. Назва: {product.title}. Категорія: {product.category.name if product.category else 'N/A'}. Виведіть ключові слова через кому."}
        ],
        max_tokens=200
    )
    
    content = response.choices[0].message.content
    print(f"Direct API response: {content}")
    
except Exception as e:
    print(f"Direct API call failed: {e}")
    import traceback
    traceback.print_exc()

# Test our function
try:
    print("\n=== Testing our function ===")
    keywords = SEOKeywordGenerator.generate_product_keywords_ai(product)
    print(f"Our function result: {keywords}")
    
except Exception as e:
    print(f"Our function failed: {e}")
    import traceback
    traceback.print_exc()

# Test description generation
try:
    print("\n=== Testing description generation ===")
    description = SEOContentOptimizer.generate_ai_product_description(product)
    print(f"Description result: {description}")
    
except Exception as e:
    print(f"Description generation failed: {e}")
    import traceback
    traceback.print_exc()
