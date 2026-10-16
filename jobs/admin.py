"""Admin pages for jobs."""

from django.contrib import admin

from .forms import JobPhotoForm
from .models import Job, JobPhoto


class JobPhotoInline(admin.TabularInline):
    """The job's photos on its admin page: see, add, delete (#64, job-photos.md D9).

    The form runs prepare_photo(), so a photo added here is checked and stripped like any
    other. Django's formset offers no more than max_num rows (D6).
    """

    model = JobPhoto
    form = JobPhotoForm
    max_num = Job.MAX_PHOTOS
    extra = 1  # one empty row for a new photo


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """The job list, add, change and delete pages in /admin/ (#15), with photos (#64)."""

    list_display = ("__str__", "district", "workers_needed", "hourly_rate", "status")
    list_filter = ("status", "district", "job_type")
    inlines = (JobPhotoInline,)
