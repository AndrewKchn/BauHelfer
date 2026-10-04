"""Settings for development on your own machine."""

from .base import *
from .base import env

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Look for static files on each request instead of scanning staticfiles/ at startup:
# that folder only exists on the server, after collectstatic.
WHITENOISE_AUTOREFRESH = True
# Serve files straight from static/ folders. WhiteNoise does this only when DEBUG is on,
# but pytest always runs with DEBUG off, so the tests would get 404 without this line.
WHITENOISE_USE_FINDERS = True
