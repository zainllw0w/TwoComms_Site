import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twocomms.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()



#import importlib.machinery
#import importlib.util
#import os
#import sys


#sys.path.insert(0, os.path.dirname(__file__))

#def load_source(modname, filename):
 #   loader = importlib.machinery.SourceFileLoader(modname, filename)
 #   spec = importlib.util.spec_from_file_location(modname, filename, loader=loader)
  #  module = importlib.util.module_from_spec(spec)
   # loader.exec_module(module)
   # return module

#wsgi = load_source('wsgi', 'passenger_wsgi.py')
#application = wsgi.application