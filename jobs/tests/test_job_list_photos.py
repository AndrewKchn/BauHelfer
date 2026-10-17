"""Integration tests: photo thumbnails on the job list (#64).

Spec: docs/specs/job-photos.md, iteration 3 (R29, R30, AC33-AC35, D26-D28). Django test
client on the home page; files in the in-memory storage.
"""

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertTemplateUsed,
)

from jobs.models import JobPhoto
from jobs.tests.images import make_upload
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(64)]


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def add_photos(job, count):
    """Give `job` `count` stored photos; returns them, oldest first."""
    return [
        JobPhoto.objects.create(
            job=job, image=ContentFile(make_upload().read(), name="photo.jpg")
        )
        for _ in range(count)
    ]


def test_card_shows_the_first_thumbnail_and_the_count(client, employer):
    """A job with 3 photos shows its first photo's thumbnail and "3 photos".

    1. Give an open job 3 photos
    2. Open the home page as a guest
    3. Expect: the first photo's thumbnail address and "3 photos"; not the big photo
    """
    first, *_ = add_photos(make_job(employer), 3)

    response = client.get(reverse("home"))

    assertContains(response, first.thumbnail.url)
    assertNotContains(response, first.image.url)
    assertContains(response, "3 photos")


def test_one_photo_in_singular(client, employer):
    """One photo is counted in the singular.

    1. Give an open job 1 photo
    2. Open the home page
    3. Expect: "1 photo", not "1 photos"
    """
    add_photos(make_job(employer), 1)

    response = client.get(reverse("home"))

    assertContains(response, "1 photo<")
    assertNotContains(response, "1 photos")


def test_card_without_photos_shows_the_placeholder(client, employer):
    """A job without photos shows the hard-hat placeholder with "No photo".

    1. Create an open job without photos
    2. Open the home page
    3. Expect: "No photo", rendered by the placeholder template
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertContains(response, "No photo")
    assertTemplateUsed(response, "jobs/_photo_placeholder.html")


def count_home_queries(client):
    """How many database queries the home page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("home"))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_jobs(client, employer):
    """The list loads the photos of all its jobs at once, not one query per card.

    1. Create 2 open jobs with 2 photos each; count the home page's queries
    2. Add 3 more such jobs; count again
    3. Expect: the same number of queries (no "N+1")
    """
    for _ in range(2):
        add_photos(make_job(employer), 2)
    with_two = count_home_queries(client)

    for _ in range(3):
        add_photos(make_job(employer), 2)
    with_five = count_home_queries(client)

    assert with_five == with_two
