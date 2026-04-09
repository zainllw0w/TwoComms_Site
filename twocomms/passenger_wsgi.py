import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from django.core.wsgi import get_wsgi_application
from twocomms.runtime import configure_django

configure_django(base_dir=Path(__file__).resolve().parent)
application = get_wsgi_application()
