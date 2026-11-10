"""Django app configuration for translations."""

from django.apps import AppConfig


class TranslationsConfig(AppConfig):
    """Registers the translations app (translation service and its cache) with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "translations"
