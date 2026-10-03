"""Settings for the live server (Render). DEBUG is always off here."""

from .base import *
from .base import env

DEBUG = False

# Render sets this to the service's own address, e.g. bauhelfer.onrender.com.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_EXTERNAL_HOSTNAME]

# Compressed copies and a content hash in each file name (style.3f9a1c.css), so browsers can
# cache static files for a long time. Needs collectstatic, which only runs on the server.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Render terminates HTTPS in front of the app and tells Django via this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600  # raise once HTTPS is confirmed working
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
