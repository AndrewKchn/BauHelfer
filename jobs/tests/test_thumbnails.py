"""Unit tests: small copies of job photos for the job list (#64).

Spec: docs/specs/job-photos.md, iteration 3 (R24-R28, AC29-AC32, D25, D29). Files go to the
in-memory storage (root conftest.py).
"""

import datetime
import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

from jobs.models import Job, JobPhoto
from jobs.photos import make_thumbnail
from jobs.tests.images import camera_exif, make_upload

pytestmark = [pytest.mark.story(64)]

User = get_user_model()


@pytest.fixture
def job():
    """A saved open job without photos."""
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


def add_photo(job, size=(300, 200)):
    """Save a JobPhoto of `job` with a JPEG of `size`."""
    upload = make_upload(size=size)
    return JobPhoto.objects.create(
        job=job, image=ContentFile(upload.read(), name="photo.jpg")
    )


def open_image(file):
    """The picture inside a file or a stored FieldFile."""
    file.seek(0)
    return Image.open(file)


# make_thumbnail() (R25, AC29)


@pytest.mark.parametrize("size", [(4000, 3000), (3000, 4000)])
def test_thumbnail_is_a_300_square(size):
    """A landscape and a portrait picture both become a 300 × 300 square.

    1. Make a thumbnail of a picture of the given size
    2. Expect: a 300 × 300 JPEG
    """
    thumbnail = make_thumbnail(make_upload(size=size))

    image = open_image(thumbnail)
    assert image.format == "JPEG"
    assert image.size == (300, 300)


def test_thumbnail_has_no_exif():
    """The small copy carries no EXIF either.

    1. Make a thumbnail of a JPEG with GPS and camera EXIF
    2. Expect: no EXIF at all
    """
    thumbnail = make_thumbnail(make_upload(exif=camera_exif()))

    assert dict(open_image(thumbnail).getexif()) == {}


# Made when a photo is saved (R24, R26, AC30)


@pytest.mark.django_db
def test_saving_a_photo_makes_its_thumbnail(job):
    """A new photo gets its thumbnail stored under job_photos/thumbs/.

    1. Save a JobPhoto with a 4000 × 3000 picture
    2. Expect: a thumbnail named job_photos/thumbs/<32 hex>.jpg, 300 × 300, in storage
    """
    photo = add_photo(job, size=(4000, 3000))

    assert re.fullmatch(r"job_photos/thumbs/[0-9a-f]{32}\.jpg", photo.thumbnail.name)
    assert default_storage.exists(photo.thumbnail.name)
    with default_storage.open(photo.thumbnail.name) as stored:
        assert Image.open(stored).size == (300, 300)


@pytest.mark.django_db
def test_saving_again_keeps_the_thumbnail(job):
    """Saving a photo again does not make a second thumbnail.

    1. Save a photo; remember its thumbnail name
    2. Save it again
    3. Expect: the same thumbnail name
    """
    photo = add_photo(job)
    name = photo.thumbnail.name

    photo.save()

    photo.refresh_from_db()
    assert photo.thumbnail.name == name


# Deleting (R28, AC31)


@pytest.mark.django_db
def test_deleting_a_photo_deletes_both_files(job, django_capture_on_commit_callbacks):
    """The photo file and its thumbnail file both go with the row.

    1. Save a photo; remember both file names
    2. Delete it and run the after-commit callbacks
    3. Expect: neither file exists
    """
    photo = add_photo(job)
    names = [photo.image.name, photo.thumbnail.name]

    with django_capture_on_commit_callbacks(execute=True):
        photo.delete()

    assert not any(default_storage.exists(name) for name in names)


# thumbnail_url (R27, AC32)


@pytest.mark.django_db
def test_thumbnail_url(job):
    """The list uses the thumbnail, or the big photo when there is none.

    1. Save a photo
    2. Expect: thumbnail_url is the thumbnail's address
    3. Clear the thumbnail (as for a photo saved before iteration 3)
    4. Expect: thumbnail_url is the photo's address
    """
    photo = add_photo(job)
    assert photo.thumbnail_url == photo.thumbnail.url

    photo.thumbnail = ""

    assert photo.thumbnail_url == photo.image.url
