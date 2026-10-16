"""Unit tests: the Job admin configuration (#15) and its photos (#64).

Spec: docs/specs/job.md (R5); docs/specs/job-photos.md (R10, AC11, D9). The admin pages
themselves are Django's; integration tests for job pages come with #16 (D6).
"""

import pytest
from django.contrib import admin
from PIL import Image

from jobs.models import Job, JobPhoto
from jobs.tests.images import camera_exif, make_upload

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


def photo_inline():
    """The inline class that shows JobPhoto rows on the admin job page."""
    job_admin = admin.site.get_model_admin(Job)
    return next(inline for inline in job_admin.inlines if inline.model is JobPhoto)


@pytest.mark.story(64)
def test_job_admin_shows_at_most_5_photos():
    """The admin job page lists the job's photos and offers at most 5.

    1. Find the JobPhoto inline of the Job admin
    2. Expect: it exists and its max_num is Job.MAX_PHOTOS
    """
    assert photo_inline().max_num == Job.MAX_PHOTOS


@pytest.mark.story(64)
def test_admin_photo_upload_is_prepared():
    """A photo uploaded in the admin is checked and stripped like any other.

    1. Fill the inline's form with a JPEG that has GPS and camera EXIF
    2. Expect: the form is valid and the cleaned image has no EXIF
    """
    form = photo_inline().form(files={"image": make_upload(exif=camera_exif())})

    assert form.is_valid(), form.errors
    image = form.cleaned_data["image"]
    image.seek(0)
    assert dict(Image.open(image).getexif()) == {}


@pytest.mark.story(64)
def test_admin_refuses_a_fake_photo():
    """A text file named .jpg is refused in the admin too.

    1. Fill the inline's form with a text file named photo.jpg
    2. Expect: the form is invalid, with an error on the image field
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    fake = SimpleUploadedFile("photo.jpg", b"this is not a picture")
    form = photo_inline().form(files={"image": fake})

    assert not form.is_valid()
    assert "image" in form.errors
