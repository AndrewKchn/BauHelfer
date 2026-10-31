"""Integration tests: the employer dashboard "My jobs" (#20).

Spec: docs/specs/my-jobs.md, iteration 1 (R1-R10, AC1-AC7). Django test client on
`my_jobs`; photo files in the in-memory storage. The swipe and the filled badge are
JavaScript, checked by the E2E tests (AC8).
"""

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import dateformat
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job, JobPhoto
from jobs.tests.images import make_upload
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(20)]


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


def add_applications(job, count, first=0, status=Application.Status.PENDING):
    """Give `job` `count` applications, each from a new worker (w<first>@…, w<first+1>@…)."""
    for number in range(first, first + count):
        Application.objects.create(
            job=job, worker=make_worker(f"w{number}@example.com"), status=status
        )


def add_photo(job):
    """Give `job` one stored photo and return it."""
    return JobPhoto.objects.create(
        job=job, image=ContentFile(make_upload().read(), name="photo.jpg")
    )


# Groups by status (R2, R3, AC1, AC2)


def test_jobs_are_grouped_by_status_in_order(employer_client, employer):
    """The jobs come in groups, Open, Filled, Done, Cancelled, each with its own jobs.

    1. Save a cancelled, a done, a filled and an open job of the employer, in that order
    2. Open "My jobs"
    3. Expect: four groups in the order open, filled, done, cancelled, each with its job
    """
    cancelled = make_job(employer, status=Job.Status.CANCELLED)
    done = make_job(employer, status=Job.Status.DONE)
    filled = make_job(employer, status=Job.Status.FILLED)
    open_job = make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    groups = [(group["status"], group["items"]) for group in response.context["groups"]]
    assert groups == [
        ("open", [open_job]),
        ("filled", [filled]),
        ("done", [done]),
        ("cancelled", [cancelled]),
    ]


def test_badges_show_each_status_with_its_number_of_jobs(employer_client, employer):
    """Above the groups one badge per status with its number of jobs, in status order.

    1. Save two open jobs and one cancelled job
    2. Open "My jobs"
    3. Expect: the badges "Open 2" before "Cancelled 1", each a link to its group
    """
    make_job(employer)
    make_job(employer)
    make_job(employer, status=Job.Status.CANCELLED)

    response = employer_client.get(reverse("my_jobs"))

    html = response.content.decode()
    assertContains(response, 'href="#tab-open"')
    assertContains(response, 'href="#tab-cancelled"')
    assertContains(response, 'id="tab-open"')
    assertContains(response, 'id="tab-cancelled"')
    assert html.index(">Open 2</a>") < html.index(">Cancelled 1</a>")


def test_a_status_without_jobs_has_no_group(employer_client, employer):
    """A status without jobs gets no group and no badge (D10).

    1. Save only an open job
    2. Open "My jobs"
    3. Expect: only the "open" group; no badge for Filled, Done or Cancelled
    """
    make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assert [group["status"] for group in response.context["groups"]] == ["open"]
    for status in ["filled", "done", "cancelled"]:
        assertNotContains(response, f'href="#tab-{status}"')


@pytest.mark.parametrize(
    ("status", "colour"),
    [
        (Job.Status.OPEN, "badge-success"),
        (Job.Status.FILLED, "badge-info"),
        (Job.Status.DONE, "badge-secondary"),
        (Job.Status.CANCELLED, "badge-error"),
    ],
)
def test_each_badge_knows_its_status_colour(employer_client, employer, status, colour):
    """Each badge carries the colour it is filled with while active (D7).

    1. Save a job in the given status
    2. Open "My jobs"
    3. Expect: its badge has data-colour with the status colour
    """
    make_job(employer, status=status)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'data-colour="{colour}"')


# The number of applications (R6, R7, AC3, AC4)


def test_card_links_the_number_of_applications(employer_client, employer):
    """A job with 3 applications shows "3 applications", a link to them on the job page.

    1. Give an open job 3 applications
    2. Open "My jobs"
    3. Expect: a link "3 applications" to the job page's #applications
    """
    job = make_job(employer)
    add_applications(job, 3)

    response = employer_client.get(reverse("my_jobs"))

    link = reverse("job_detail", args=[job.pk]) + "#applications"
    assertContains(response, f'href="{link}"')
    assertContains(response, ">3 applications</a>")


def test_one_application_in_singular(employer_client, employer):
    """One application is counted in the singular.

    1. Give an open job 1 application
    2. Open "My jobs"
    3. Expect: "1 application", not "1 applications"
    """
    add_applications(make_job(employer), 1)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, ">1 application</a>")
    assertNotContains(response, "1 applications")


def test_job_without_applications_has_no_link(employer_client, employer):
    """A job without applications says so, with no link to an empty list (D14).

    1. Save an open job without applications
    2. Open "My jobs"
    3. Expect: "No applications yet" and no link to #applications
    """
    make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, "No applications yet")
    assertNotContains(response, "#applications")


def test_count_includes_every_application_status(employer_client, employer):
    """Accepted and rejected applications are counted too (D15).

    1. Give a filled job a pending, an accepted and a rejected application
    2. Open "My jobs"
    3. Expect: "3 applications"
    """
    job = make_job(employer, status=Job.Status.FILLED)
    add_applications(job, 1)
    add_applications(job, 1, first=1, status=Application.Status.ACCEPTED)
    add_applications(job, 1, first=2, status=Application.Status.REJECTED)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, ">3 applications</a>")


def test_each_job_counts_only_its_own_applications(employer_client, employer):
    """Applications to another job, also another employer's, are not counted (AC4).

    1. Give the employer's job 1 application, a second own job 2, and another employer's
       job 4
    2. Open "My jobs"
    3. Expect: "1 application" and "2 applications"; no "4 applications" and not the other
       employer's job
    """
    add_applications(make_job(employer, job_type="demolition"), 1)
    add_applications(make_job(employer, job_type="carrying"), 2, first=1)
    other = make_job(make_employer("boris@example.com"), job_type="painting")
    add_applications(other, 4, first=3)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, ">1 application</a>")
    assertContains(response, ">2 applications</a>")
    assertNotContains(response, "4 applications")
    assertNotContains(response, "Painting helper")


# The card: photo, address, district (R5, R9, AC5)


def test_card_shows_the_address_and_the_district(employer_client, employer):
    """The employer's own card shows the job's address and, below it, the district (D3).

    1. Save an open job at "Belgradstraße 9" in Schwabing-West
    2. Open "My jobs"
    3. Expect: the address before the district
    """
    make_job(employer, address="Belgradstraße 9", district="schwabing_west")

    response = employer_client.get(reverse("my_jobs"))

    html = response.content.decode()
    assert html.index("Belgradstraße 9") < html.index("Schwabing-West")


def test_card_shows_the_photo_or_the_placeholder(employer_client, employer):
    """A job with a photo shows its thumbnail; a job without one the placeholder.

    1. Save one open job with a photo and one without
    2. Open "My jobs"
    3. Expect: the photo's thumbnail (not the big photo) and "No photo"
    """
    photo = add_photo(make_job(employer))
    make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, photo.thumbnail.url)
    assertNotContains(response, photo.image.url)
    assertContains(response, "No photo")


def test_card_puts_the_date_on_a_line_of_its_own(employer_client, employer):
    """The date is under the job type, not after a "·" on the same line (D9).

    1. Save an open demolition job
    2. Open "My jobs"
    3. Expect: "Demolition" followed by the date in its own block, no "Demolition ·"
    """
    job = make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    date = dateformat.format(job.date, "D j M")
    assertContains(response, f'Demolition<span class="block">{date}</span>')
    assertNotContains(response, "Demolition ·")


# Queries (R8, AC7)


def count_my_jobs_queries(client):
    """How many database queries "My jobs" makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("my_jobs"))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_jobs(employer_client, employer):
    """The counts and photos of all jobs come at once, not one query per card.

    1. Save 1 job with a photo and 2 applications; count the page's queries
    2. Add 2 more such jobs; count again
    3. Expect: the same number of queries (no "N+1")
    """
    job = make_job(employer)
    add_photo(job)
    add_applications(job, 2)
    with_one = count_my_jobs_queries(employer_client)

    for first in (2, 4):
        job = make_job(employer)
        add_photo(job)
        add_applications(job, 2, first=first)
    with_three = count_my_jobs_queries(employer_client)

    assert with_three == with_one
