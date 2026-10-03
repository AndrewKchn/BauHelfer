"""Settings for development on your own machine."""

from .base import *
from .base import env

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
