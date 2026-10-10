"""Unit tests: the Job admin configuration (#15).

Spec: docs/specs/job.md (R5). The admin pages themselves are Django's; integration tests for
job pages come with #16 (D6).
"""

import pytest
from django.contrib import admin

from jobs.models import Job

pytestmark = [pytest.mark.story(15)]


def test_job_is_registered_in_admin():
    """Job has pages in /admin/.

    1. Ask the admin site whether Job is registered
    2. Expect: yes
    """
    assert admin.site.is_registered(Job)


def test_job_admin_list_columns():
    """The admin job list shows the main facts of each job.

    1. Read list_display of the Job admin
    2. Expect: the job (type and date), district, workers, rate and status
    """
    job_admin = admin.site.get_model_admin(Job)

    assert job_admin.list_display == (
        "__str__",
        "district",
        "workers_needed",
        "hourly_rate",
        "status",
    )


def test_job_admin_filters():
    """The admin job list can be filtered by status, district and job type.

    1. Read list_filter of the Job admin
    2. Expect: status, district, job_type
    """
    job_admin = admin.site.get_model_admin(Job)

    assert job_admin.list_filter == ("status", "district", "job_type")
