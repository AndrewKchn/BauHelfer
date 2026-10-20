"""Settings for development on your own machine."""

import os

from .base import *
from .base import INSTALLED_APPS, LOGGING, MIDDLEWARE, env

DEBUG = env.bool("DEBUG", default=True)

# Django Debug Toolbar (#135): a panel on every runserver page with the view, templates,
# SQL queries and signals. pytest uses these settings too and sets PYTEST_VERSION at start,
# so the tests run without it (the toolbar's docs recommend this). It shows only with
# DEBUG on and for INTERNAL_IPS; it is a dev package, never installed on Render.
TESTING = "PYTEST_VERSION" in os.environ
if not TESTING:
    INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
    # First, as its docs ask: it adds the panel to the page the other middleware return.
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
    INTERNAL_IPS = ["127.0.0.1"]

# Our apps log everything here, DEBUG included (#124). A new dict, not an edit of base's:
# production.py imports the same base.LOGGING and must keep INFO.
# With the time first: Render adds it on the server, the terminal does not.
LOGGING = {
    **LOGGING,
    "formatters": {
        "simple": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "datefmt": "%d/%b/%Y %H:%M:%S",  # as runserver printed it before
            "style": "{",
        },
    },
    "loggers": {
        **LOGGING["loggers"],
        "accounts": {"level": "DEBUG"},
        "jobs": {"level": "DEBUG"},
    },
}

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Look for static files on each request instead of scanning staticfiles/ at startup:
# that folder only exists on the server, after collectstatic.
WHITENOISE_AUTOREFRESH = True
# Serve files straight from static/ folders. WhiteNoise does this only when DEBUG is on,
# but pytest always runs with DEBUG off, so the tests would get 404 without this line.
WHITENOISE_USE_FINDERS = True
