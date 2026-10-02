"""Settings for the live server (Render). DEBUG is always off here."""

from .base import *  # noqa: F403

DEBUG = False

# Render terminates HTTPS in front of the app and tells Django via this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600  # raise once HTTPS is confirmed working
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
