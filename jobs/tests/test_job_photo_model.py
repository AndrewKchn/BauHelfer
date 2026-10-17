"""Unit tests: the JobPhoto model, its file name and deleting its file (#64).

Spec: docs/specs/job-photos.md, iteration 1 (R2, R3, R6, R7, AC8-AC10, D7, D8). Files go to
Django's in-memory storage (root conftest.py, R9), never to the disk.
"""

import datetime
import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from jobs.models import Job, JobPhoto
from jobs.tests.images import make_upload

pytestmark = [pytest.mark.django_db, pytest.mark.story(64)]

User = get_user_model()


@pytest.fixture
def employer():
    """A user with the employer role."""
    return User.objects.create_user(
        email="employer@example.com", password="x", role="employer"
    )


@pytest.fixture
def job(employer):
    """A saved open job."""
    return Job.objects.create(
        employer=employer,
        job_type="demolition",
        description="Tear down a garden shed.",
        original_language="de",
        address="Lindwurmstraße 1",
        district="sendling",
        date=datetime.date(2026, 11, 3),
        start_time=datetime.time(8, 0),
        hours=6,
        workers_needed=2,
        hourly_rate=Decimal("18.00"),
    )


def add_photo(job, name="photo.jpg"):
    """Save a JobPhoto of `job` with a small JPEG named `name`."""
    upload = make_upload(name=name)
    return JobPhoto.objects.create(job=job, image=ContentFile(upload.read(), name=name))


def test_max_photos_is_5():
    """A job has at most 5 photos; the limit lives in one place.

    1. Read Job.MAX_PHOTOS
    2. Expect: 5
    """
    assert Job.MAX_PHOTOS == 5


# File name (R6, AC8, D7)


def test_stored_name_is_random(job):
    """The stored file gets a random name; the original name is not kept.

    1. Save a photo named "Familie_Maier_Bad.jpg"
    2. Expect: the name is job_photos/<32 hex characters>.jpg, without "Maier"
    """
    photo = add_photo(job, name="Familie_Maier_Bad.jpg")

    assert re.fullmatch(r"job_photos/[0-9a-f]{32}\.jpg", photo.image.name)
    assert "Maier" not in photo.image.name


def test_two_photos_get_different_names(job):
    """Two files with the same original name do not clash.

    1. Save two photos, both named photo.jpg
    2. Expect: two different stored names, both files exist
    """
    first = add_photo(job)
    second = add_photo(job)

    assert first.image.name != second.image.name
    assert default_storage.exists(first.image.name)
    assert default_storage.exists(second.image.name)


# Order (R2, AC10)


def test_photos_oldest_first(job):
    """job.photos lists the photos by upload time, oldest first.

    1. Save photo A, then photo B
    2. Move A's upload time one hour after B's
    3. Expect: job.photos returns B, then A
    """
    photo_a = add_photo(job)
    photo_b = add_photo(job)
    JobPhoto.objects.filter(pk=photo_a.pk).update(
        uploaded_at=photo_b.uploaded_at + datetime.timedelta(hours=1)
    )

    assert list(job.photos.all()) == [photo_b, photo_a]


def test_uploaded_at_is_set(job):
    """The upload time is filled in automatically.

    1. Save a photo
    2. Expect: uploaded_at is within the last minute
    """
    photo = add_photo(job)

    assert timezone.now() - photo.uploaded_at < datetime.timedelta(minutes=1)


# Deleting the file with its row (R7, AC9, D8)


def test_deleting_photo_deletes_file(job, django_capture_on_commit_callbacks):
    """Deleting a photo removes its file from storage, after the commit.

    1. Save a photo; remember its file name
    2. Delete the photo and run the after-commit callbacks
    3. Expect: the file no longer exists
    """
    photo = add_photo(job)
    name = photo.image.name

    with django_capture_on_commit_callbacks(execute=True):
        photo.delete()

    assert not default_storage.exists(name)


def test_file_stays_until_commit(job, django_capture_on_commit_callbacks):
    """The file is not deleted before the database change is committed.

    1. Save a photo; remember its file name
    2. Delete the photo, but do not run the after-commit callbacks
    3. Expect: the file still exists (a rolled-back delete would not lose it)
    """
    photo = add_photo(job)
    name = photo.image.name

    with django_capture_on_commit_callbacks(execute=False):
        photo.delete()

    assert default_storage.exists(name)


def test_deleting_job_deletes_files(job, django_capture_on_commit_callbacks):
    """Deleting a job deletes the files of all its photos (cascade).

    1. Save two photos of the job; remember their file names
    2. Delete the job and run the after-commit callbacks
    3. Expect: neither file exists
    """
    names = [add_photo(job).image.name, add_photo(job).image.name]

    with django_capture_on_commit_callbacks(execute=True):
        job.delete()

    assert not any(default_storage.exists(name) for name in names)


def test_deleting_employer_deletes_files(
    employer, job, django_capture_on_commit_callbacks
):
    """Deleting the employer's account deletes the files of their job photos.

    1. Save a photo of the employer's job; remember its file name
    2. Delete the employer and run the after-commit callbacks
    3. Expect: the file no longer exists
    """
    name = add_photo(job).image.name

    with django_capture_on_commit_callbacks(execute=True):
        employer.delete()

    assert not default_storage.exists(name)


def test_queryset_delete_deletes_files(job, django_capture_on_commit_callbacks):
    """Deleting photos in bulk (a queryset, as the admin's "delete selected" does) works too.

    1. Save a photo; remember its file name
    2. Delete job.photos.all() and run the after-commit callbacks
    3. Expect: the file no longer exists
    """
    name = add_photo(job).image.name

    with django_capture_on_commit_callbacks(execute=True):
        job.photos.all().delete()

    assert not default_storage.exists(name)
