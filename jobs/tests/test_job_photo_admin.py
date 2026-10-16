"""Integration tests: job photos on the admin job page (#64).

Spec: docs/specs/job-photos.md, iteration 1 (R10, AC11, D6, D9). Django test client: the
admin view, the inline formset with prepare_photo(), the database and the (in-memory) storage.
"""

import datetime
import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.urls import reverse
from PIL import Image

from jobs.models import Job, JobPhoto
from jobs.tests.images import camera_exif, make_upload

pytestmark = [pytest.mark.django_db, pytest.mark.story(64)]

User = get_user_model()


@pytest.fixture
def job():
    """A saved open job of an employer."""
    employer = User.objects.create_user(
        email="employer@example.com", password="x", role="employer"
    )
    return Job.objects.create(
        employer=employer,
        job_type="demolition",
        description="Tear down a garden shed.",
        original_language="de",
        address="Lindwurmstraße 1",
        district="sendling",
        date=datetime.date(2030, 11, 3),
        start_time=datetime.time(8, 0),
        hours=6,
        workers_needed=2,
        hourly_rate=Decimal("18.00"),
    )


@pytest.fixture
def admin_client(client):
    """The test client logged in as a superuser."""
    admin = User.objects.create_superuser(email="admin@example.com", password="x")
    client.force_login(admin)
    return client


def change_page_post(job, uploads):
    """What the browser sends when the job's admin page is saved with `uploads` as new photos.

    The job's own fields stay as they are; "photos-…" is the inline formset of its photos.
    """
    data = {
        "employer": job.employer_id,
        "job_type": job.job_type,
        "description": job.description,
        "original_language": job.original_language,
        "address": job.address,
        "district": job.district,
        "date": job.date.isoformat(),
        "start_time": "08:00",
        "hours": job.hours,
        "workers_needed": job.workers_needed,
        "hourly_rate": job.hourly_rate,
        "status": job.status,
        # The formset's management form: how many rows, how many of them already exist.
        "photos-TOTAL_FORMS": len(uploads),
        "photos-INITIAL_FORMS": 0,
    }
    for number, upload in enumerate(uploads):
        data[f"photos-{number}-image"] = upload
    return data


def test_photo_added_in_admin_is_stored_without_exif(admin_client, job):
    """A photo added on the admin job page is stored under a random name, without EXIF.

    1. As a superuser, save the job's admin page with one new JPEG that has GPS EXIF
    2. Expect: a redirect (saved), one JobPhoto, its file under job_photos/ with a random
       name, a JPEG with no EXIF
    """
    url = reverse("admin:jobs_job_change", args=[job.pk])
    upload = make_upload(exif=camera_exif(), name="Familie_Maier.jpg")

    response = admin_client.post(url, change_page_post(job, [upload]))

    assert response.status_code == 302
    photo = JobPhoto.objects.get(job=job)
    assert re.fullmatch(r"job_photos/[0-9a-f]{32}\.jpg", photo.image.name)
    with default_storage.open(photo.image.name) as stored:
        assert dict(Image.open(stored).getexif()) == {}


def test_admin_refuses_a_sixth_photo(admin_client, job):
    """Six photos in one save are refused, even if the request is made by hand.

    The page shows at most 5 rows, but a browser can send more; the formset must check.

    1. As a superuser, save the job's admin page with 6 new photos at once
    2. Expect: the page comes back (200) with an error, and no photo is saved
    """
    url = reverse("admin:jobs_job_change", args=[job.pk])
    uploads = [make_upload(name=f"photo{number}.jpg") for number in range(6)]

    response = admin_client.post(url, change_page_post(job, uploads))

    assert response.status_code == 200
    assert "Please submit at most 5 forms." in response.content.decode()
    assert not JobPhoto.objects.exists()
