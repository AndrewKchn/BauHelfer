"""Django app configuration for accounts."""

from typing import override

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Registers the accounts app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    @override
    def ready(self):
        """Connect the signal receivers once all apps are loaded (#124).

        Nothing imports signals.py otherwise, so its @receiver lines would never run.
        """
        from . import signals  # noqa: F401
