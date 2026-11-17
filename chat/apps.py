"""Django app configuration for chat."""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Registers the chat app with Django (#35)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"
