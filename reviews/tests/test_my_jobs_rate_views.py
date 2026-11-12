"""Integration tests: "Rate the workers" on the employer's "My jobs" (#38).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/reviews.md, iteration 2 (R11a, R12, D15), acceptance criteria AC9a and
AC10.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

DAY = datetime.timedelta(days=1)
BUTTON = "Rate the workers"


@pytest.fixture
def employer():
    """Anna, the employer of the jobs."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as Anna."""
    client.force_login(employer)
    return client


def done_job(employer, done_ago=DAY, workers=("ivan@example.com",)):
    """A job two days ago, done `done_ago` before now, with these workers accepted."""
    job = make_job(
        employer,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - done_ago,
    )
    for email in workers:
        Application.objects.create(
            job=job, worker=make_worker(email), workers_accepted=1, status="accepted"
        )
    return job


def applications_url(job):
    """The job page's list of applications, where the employer rates each worker."""
    return reverse("job_detail", args=[job.pk]) + "#applications"


def test_done_job_with_a_worker_to_rate_has_the_button(employer_client, employer):
    """A worker left to rate: the button, to the job's applications (R11a, D15).

    1. Save a job done yesterday with Ivan accepted, not rated
    2. Open "My jobs" as Anna
    3. Expect: "Rate the workers", a link to the job page's #applications
    """
    job = done_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, BUTTON)
    assertContains(response, f'href="{applications_url(job)}" class="btn')


def test_button_stays_while_one_of_two_is_not_rated(employer_client, employer):
    """One of two rated: still someone to rate (R11a).

    1. Save a done job with Ivan and Olga accepted; Anna rated Ivan only
    2. Open "My jobs" as Anna
    3. Expect: "Rate the workers"
    """
    job = done_job(employer, workers=("ivan@example.com", "olga@example.com"))
    ivan = job.applications.get(worker__email="ivan@example.com")
    Review.objects.create(application=ivan, author=employer, rating=5)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, BUTTON)


def test_no_button_when_every_worker_is_rated(employer_client, employer):
    """All rated: the button would ask for reviews already given (D15, option B rejected).

    1. Save a done job with Ivan accepted and Anna's review of him; Ivan's review of
       Anna does not count
    2. Open "My jobs" as Anna
    3. Expect: no "Rate the workers"
    """
    job = done_job(employer)
    ivan = job.applications.get()
    Review.objects.create(application=ivan, author=employer, rating=4)
    Review.objects.create(application=ivan, author=ivan.worker, rating=4)

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, BUTTON)


def test_no_button_after_the_deadline(employer_client, employer):
    """The 14 days are over: nothing to do any more (R11a, D3).

    1. Save a job done 15 days ago with Ivan accepted, not rated
    2. Open "My jobs" as Anna
    3. Expect: no "Rate the workers"
    """
    done_job(employer, done_ago=15 * DAY)

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, BUTTON)


def test_no_button_on_a_job_that_is_not_done(employer_client, employer):
    """Filled and over, not done: "Mark as done" comes first (R11a, D1).

    1. Save a filled job two days ago with Ivan accepted
    2. Open "My jobs" as Anna
    3. Expect: no "Rate the workers"
    """
    job = make_job(
        employer, date=timezone.localdate() - 2 * DAY, status=Job.Status.FILLED
    )
    Application.objects.create(
        job=job, worker=make_worker("ivan@example.com"), status="accepted"
    )

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, BUTTON)


def test_buttons_cost_no_query_per_job(employer_client, employer):
    """The same queries for 1 and for 3 done jobs (R12, D15).

    1. Save one done job with a worker to rate, open "My jobs" and count the queries
    2. Save two more, one of them with two workers; open it again and count
    3. Expect: the same number; three buttons on the second page
    """
    done_job(employer, workers=("w1@example.com",))
    with CaptureQueriesContext(connection) as one:
        employer_client.get(reverse("my_jobs"))
    done_job(employer, workers=("w2@example.com",))
    done_job(employer, workers=("w3@example.com", "w4@example.com"))

    with CaptureQueriesContext(connection) as three:
        response = employer_client.get(reverse("my_jobs"))

    assert len(three) == len(one)
    assertContains(response, BUTTON, count=3)
