import os

from django.core.wsgi import get_wsgi_application

from config.env import load_dotenv_file

load_dotenv_file()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
application = get_wsgi_application()
