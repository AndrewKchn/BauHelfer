"""Django app configuration for jobs."""

from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Registers the jobs app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs"
