from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# The Vite dev server proxies the API and passes the browser's host on, so a phone reaching Leon
# through an HTTPS tunnel signs in and refreshes like localhost does.
USE_X_FORWARDED_HOST = True
