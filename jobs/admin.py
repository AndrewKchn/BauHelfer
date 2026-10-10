"""Admin pages for jobs."""

from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """The job list, add, change and delete pages in /admin/ (#15)."""

    list_display = ("__str__", "district", "workers_needed", "hourly_rate", "status")
    list_filter = ("status", "district", "job_type")
