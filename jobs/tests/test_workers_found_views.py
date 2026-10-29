"""Integration tests: "1 of 3 workers found" on the pages and the places left (#24).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/accept-reject.md, iteration 2 (R12-R16, D10-D12), acceptance criteria
AC10-AC14. The numbers themselves are in test_workers_found.py.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(24)]


@pytest.fixture
def employer():
    """The employer who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def accept(job, email, taken):
    """Save an accepted application to `job` with `taken` workers taken."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        workers_offered=taken,
        workers_accepted=taken,
        status=Application.Status.ACCEPTED,
    )


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


# The job page (R12, R13, D10, D11; AC10, AC11)


def test_job_page_shows_the_workers_found(client, job):
    """Once someone is accepted, everyone sees how many are found (spec R12).

    1. Accept a crew of 2 on a job for 3
    2. Open the job's page as a guest
    3. Expect: "2 of 3 workers found", no "Needs 3 workers"
    """
    accept(job, "a@example.com", 2)

    response = client.get(detail_url(job))

    assertContains(response, "2 of 3 workers found")
    assertNotContains(response, "Needs 3 workers")


def test_job_page_says_needs_while_nobody_is_found(client, job):
    """A fresh job keeps "Needs 3 workers", not "0 of 3 found" (spec D10).

    1. Open the page of a job for 3 without accepted workers as a guest
    2. Expect: "Needs 3 workers", no "workers found"
    """
    response = client.get(detail_url(job))

    assertContains(response, "Needs 3 workers")
    assertNotContains(response, "workers found")


def test_owner_sees_the_workers_found_bar(client, employer, job):
    """The owner gets "Workers found 2 / 3" with a bar above the list (spec R13, D11).

    1. Accept a crew of 2 on a job for 3
    2. Open the job's page as its employer
    3. Expect: "Workers found", "2 / 3" and a <progress> with value 2 and max 3
    """
    accept(job, "a@example.com", 2)
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, "Workers found")
    assertContains(response, "2 / 3")
    assertContains(response, 'value="2" max="3"')


def test_guest_sees_no_workers_found_bar(client, job):
    """The bar is the owner's (spec D11).

    1. Accept a crew of 2 on a job for 3
    2. Open the job's page as a guest
    3. Expect: no <progress>
    """
    accept(job, "a@example.com", 2)

    response = client.get(detail_url(job))

    assertNotContains(response, "<progress")


# The job list (R14, R16; AC12, AC14)


def test_job_list_card_says_how_many_are_still_needed(client, job):
    """The card counts only the free places (spec R14).

    1. Accept a crew of 2 on a job for 3
    2. Open the home page
    3. Expect: "Needs 1 worker", no "Needs 3 workers"
    """
    accept(job, "a@example.com", 2)

    response = client.get(reverse("home"))

    assertContains(response, "Needs 1 worker")
    assertNotContains(response, "Needs 3 workers")


def count_home_queries(client):
    """How many database queries the home page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("home"))
    assert response.status_code == 200
    return len(queries)


def test_job_list_queries_do_not_grow_with_accepted_workers(client, employer, job):
    """The workers found come with the jobs, not one query per card (spec R16, D12).

    1. One job with an accepted worker; count the home page's queries
    2. Add 3 more jobs, each with an accepted worker; count again
    3. Expect: the same number
    """
    accept(job, "a@example.com", 1)
    one = count_home_queries(client)

    for number in range(3):
        accept(make_job(employer, workers_needed=3), f"w{number}@example.com", 1)

    assert count_home_queries(client) == one


# The apply view (R15; AC13)


def test_apply_with_more_than_the_places_left_is_refused(client, employer):
    """A POST with more workers than places left saves nothing (spec R15).

    1. A job for 4 with 2 workers found; log in as a crew of 3
    2. POST 3 workers to the job's apply URL
    3. Expect: the page again with an error on workers_offered, no new application
    """
    job = make_job(employer, workers_needed=4)
    accept(job, "a@example.com", 2)
    worker = make_worker("ivan@example.com", team_size=3)
    client.force_login(worker)

    response = client.post(reverse("job_apply", args=[job.pk]), {"workers_offered": 3})

    assert response.status_code == 200
    assert "workers_offered" in response.context["apply_form"].errors
    assert not Application.objects.filter(worker=worker).exists()
