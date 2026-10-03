"""Settings for development on your own machine."""

from .base import *
from .base import env

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Look for static files on each request instead of scanning staticfiles/ at startup:
# that folder only exists on the server, after collectstatic.
WHITENOISE_AUTOREFRESH = True
