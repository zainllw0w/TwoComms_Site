#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/qlknpodo/TWC/TwoComms_Site/twocomms')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.settings')

django.setup()

from django.conf import settings

print("=== AI Settings Check ===")
print(f"OPENAI_API_KEY: {getattr(settings, 'OPENAI_API_KEY', 'NOT_SET')}")
print(f"USE_AI_KEYWORDS: {getattr(settings, 'USE_AI_KEYWORDS', 'NOT_SET')}")
print(f"USE_AI_DESCRIPTIONS: {getattr(settings, 'USE_AI_DESCRIPTIONS', 'NOT_SET')}")
print(f"OPENAI_MODEL: {getattr(settings, 'OPENAI_MODEL', 'NOT_SET')}")

print("\n=== Environment Variables ===")
print(f"OPENAI_API_KEY env: {os.environ.get('OPENAI_API_KEY', 'NOT_SET')}")
print(f"OPEN_API_KEY env: {os.environ.get('OPEN_API_KEY', 'NOT_SET')}")

print("\n=== Test OpenAI Import ===")
try:
    import openai
    print("OpenAI library imported successfully")
    print(f"OpenAI version: {openai.__version__}")
except ImportError as e:
    print(f"Failed to import OpenAI: {e}")

print("\n=== Test API Key ===")
api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY') or os.environ.get('OPEN_API_KEY')
if api_key:
    print(f"API Key found: {api_key[:10]}...{api_key[-4:]}")
else:
    print("No API key found!")
