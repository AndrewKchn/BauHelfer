"""Unit tests: JobPhotosForm, several photos for one job in one go (#64).

Spec: docs/specs/job-photos.md, iteration 2 (R16, AC23, D12, D17). The form needs the
database only to count the photos a job already has.
"""

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict
from PIL import Image

from jobs.forms import JobPhotosForm
from jobs.models import Job, JobPhoto
from jobs.tests.images import camera_exif, make_upload

pytestmark = [pytest.mark.django_db, pytest.mark.story(64)]

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


def photos_form(job, uploads):
    """The form bound to `uploads` as the browser sends them: several files, one name."""
    return JobPhotosForm(files=MultiValueDict({"photos": uploads}), job=job)


def add_existing_photos(job, count):
    """Give `job` `count` stored photos."""
    for _ in range(count):
        JobPhoto.objects.create(
            job=job, image=ContentFile(make_upload().read(), name="old.jpg")
        )


def test_several_valid_photos_are_prepared(job):
    """Every chosen file comes out checked and prepared: JPEG without EXIF.

    1. Bind the form to a JPEG with GPS EXIF, a PNG and a WebP
    2. Expect: the form is valid; cleaned_data["photos"] holds 3 JPEGs without EXIF
    """
    uploads = [
        make_upload(exif=camera_exif()),
        make_upload("PNG", name="b.png"),
        make_upload("WEBP", name="c.webp"),
    ]

    form = photos_form(job, uploads)

    assert form.is_valid(), form.errors
    assert len(form.cleaned_data["photos"]) == 3
    for photo in form.cleaned_data["photos"]:
        photo.seek(0)
        image = Image.open(photo)
        assert image.format == "JPEG"
        assert dict(image.getexif()) == {}


def test_save_stores_the_photos_for_the_job(job):
    """save() stores one JobPhoto per file, all for this job.

    1. Bind the form to two valid photos and save it
    2. Expect: save() returns 2 photos; the job has those 2 photos
    """
    form = photos_form(job, [make_upload(), make_upload(name="b.jpg")])
    assert form.is_valid(), form.errors

    saved = form.save()

    assert len(saved) == 2
    assert list(job.photos.all()) == saved


def test_one_bad_file_makes_the_whole_form_invalid(job):
    """One bad file refuses the whole batch, and the error names that file (D17).

    1. Bind the form to two valid JPEGs and a GIF named plan.gif
    2. Expect: the form is invalid; the error starts with "plan.gif: "
    """
    uploads = [make_upload(), make_upload("GIF", name="plan.gif"), make_upload()]

    form = photos_form(job, uploads)

    assert not form.is_valid()
    assert form.errors["photos"] == [
        "plan.gif: Upload a photo in JPEG, PNG or WebP format."
    ]


def test_fake_photo_is_refused(job):
    """A text file named .jpg is refused like in the admin.

    1. Bind the form to a text file named notes.jpg
    2. Expect: the form is invalid; the error names notes.jpg
    """
    fake = SimpleUploadedFile("notes.jpg", b"this is not a picture")

    form = photos_form(job, [fake])

    assert not form.is_valid()
    assert form.errors["photos"][0].startswith("notes.jpg: ")


def test_count_includes_photos_already_there(job):
    """The limit counts the photos the job already has (R16, AC18).

    1. Give the job 4 photos
    2. Bind the form to 2 more
    3. Expect: invalid, "You can add 1 more photo."
    """
    add_existing_photos(job, 4)

    form = photos_form(job, [make_upload(), make_upload(name="b.jpg")])

    assert not form.is_valid()
    assert form.errors["photos"] == ["You can add 1 more photo."]


def test_up_to_the_limit_is_fine(job):
    """Filling the job up to exactly 5 photos is allowed.

    1. Give the job 3 photos
    2. Bind the form to 2 more
    3. Expect: valid
    """
    add_existing_photos(job, 3)

    form = photos_form(job, [make_upload(), make_upload(name="b.jpg")])

    assert form.is_valid(), form.errors


def test_more_than_5_at_once_is_refused(job):
    """Six photos for an empty job are refused in plural words.

    1. Bind the form of a job without photos to 6 files
    2. Expect: invalid, "You can add 5 more photos."
    """
    uploads = [make_upload(name=f"{number}.jpg") for number in range(6)]

    form = photos_form(job, uploads)

    assert not form.is_valid()
    assert form.errors["photos"] == ["You can add 5 more photos."]


def test_no_file_is_refused(job):
    """Pressing "Add photos" without choosing a file gives a clear error.

    1. Bind the form to no files
    2. Expect: invalid, "Choose at least one photo."
    """
    form = JobPhotosForm(files=MultiValueDict(), job=job)

    assert not form.is_valid()
    assert form.errors["photos"] == ["Choose at least one photo."]


def test_file_field_takes_several_files(job):
    """The browser lets the employer pick several files and only photos (R15).

    1. Render the form's photos field
    2. Expect: a file input with "multiple" and an accept list of the three formats
    """
    html = str(JobPhotosForm(job=job)["photos"])

    assert 'type="file"' in html
    assert "multiple" in html
    assert 'accept="image/jpeg,image/png,image/webp"' in html
