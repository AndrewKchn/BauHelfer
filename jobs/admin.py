"""Admin pages for jobs."""

from typing import override

from django.contrib import admin

from .forms import JobPhotoForm
from .models import Job, JobPhoto


class JobPhotoInline(admin.TabularInline):
    """The job's photos on its admin page: see, add, delete (#64, job-photos.md D9).

    The form runs prepare_photo(), so a photo added here is checked and stripped like any
    other. At most Job.MAX_PHOTOS photos per job (D6).
    """

    model = JobPhoto
    form = JobPhotoForm
    max_num = Job.MAX_PHOTOS  # the page shows no more rows than this
    extra = 1  # one empty row for a new photo

    @override
    def get_formset(self, request, obj=None, **kwargs):
        """Also refuse more than max_num photos when the form is sent, not only hide rows.

        max_num alone only limits the rows on the page; a request made by hand could still
        send more (found by test_admin_refuses_a_sixth_photo).
        """
        return super().get_formset(request, obj, validate_max=True, **kwargs)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """The job list, add, change and delete pages in /admin/ (#15), with photos (#64)."""

    list_display = ("__str__", "district", "workers_needed", "hourly_rate", "status")
    list_filter = ("status", "district", "job_type")
    inlines = (JobPhotoInline,)
