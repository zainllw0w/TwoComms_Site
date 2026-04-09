"""
WSGI config for twocomms project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

from django.core.wsgi import get_wsgi_application
from twocomms.runtime import configure_django

configure_django()

application = get_wsgi_application()
