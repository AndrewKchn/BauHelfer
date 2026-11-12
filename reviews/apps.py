"""Django app configuration for reviews."""

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Registers the reviews app with Django (#38)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"
