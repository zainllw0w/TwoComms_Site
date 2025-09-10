#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')

django.setup()

import openai
from django.conf import settings

print("=== Testing OpenAI API ===")

# Get API key
api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("No API key found!")
    sys.exit(1)

print(f"API Key: {api_key[:10]}...{api_key[-4:]}")

# Test with different models
models_to_test = ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo']

for model in models_to_test:
    try:
        print(f"\nTesting model: {model}")
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ви - генератор SEO ключових слів."},
                {"role": "user", "content": "Створіть 5 SEO ключових слів для футболки. Виведіть через кому."}
            ],
            max_tokens=50
        )
        
        content = response.choices[0].message.content
        print(f"✅ {model} works! Response: {content}")
        
    except Exception as e:
        print(f"❌ {model} failed: {str(e)}")

print("\n=== Testing AI generation function ===")
try:
    from storefront.seo_utils import SEOKeywordGenerator
    from storefront.models import Product
    
    # Get first product
    product = Product.objects.first()
    if product:
        print(f"Testing with product: {product.title}")
        keywords = SEOKeywordGenerator.generate_product_keywords_ai(product)
        print(f"Generated keywords: {keywords}")
    else:
        print("No products found")
        
except Exception as e:
    print(f"Error testing AI generation: {str(e)}")
    import traceback
    traceback.print_exc()
