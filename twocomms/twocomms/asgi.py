"""
ASGI config for twocomms project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os
from pathlib import Path

from django.core.asgi import get_asgi_application

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    base_dir = Path(__file__).resolve().parent.parent
    for candidate in (base_dir / '.env.production', base_dir.parent / '.env.production'):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            break

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'twocomms.production_settings')

application = get_asgi_application()
