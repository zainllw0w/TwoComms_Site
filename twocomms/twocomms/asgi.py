"""
ASGI config for twocomms project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

from django.core.asgi import get_asgi_application
from twocomms.runtime import configure_django

configure_django()

application = get_asgi_application()
