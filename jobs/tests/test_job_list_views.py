"""Integration tests: the job list on the home page through the Django test client (#18).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/job-list.md (R1-R10), acceptance criteria AC3-AC10. AC1 and AC2 are unit
tests in test_models.py; AC11 is test_onboarding.py (a user without a role is still sent to
the role choice from the home page).
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Job

# The same helpers as the employer job pages: an employer with a profile, a job next week.
from .test_views import NEXT_WEEK, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(18)]

User = get_user_model()


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def jobs_on_page(response):
    """The jobs the page shows, in the order it shows them."""
    return list(response.context["jobs"])


# Which jobs are shown (R2, R3, R4; AC3, AC4, AC7)


def test_home_page_shows_an_open_upcoming_job(client, employer):
    """The home page lists an open job that has not started yet.

    1. Save an open job next week
    2. Open the home page as a guest
    3. Expect: status 200, the job is in the list, the job list template is used
    """
    job = make_job(employer)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert jobs_on_page(response) == [job]
    assert "jobs/job_list.html" in [t.name for t in response.templates]


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_home_page_hides_jobs_that_are_not_open(client, employer, status):
    """Filled, done and cancelled jobs are not on the list.

    1. Save a job with status filled / done / cancelled, next week
    2. Open the home page
    3. Expect: the list is empty
    """
    make_job(employer, status=status)

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == []


def test_home_page_hides_a_job_that_was_yesterday(client, employer):
    """A job whose day has passed is not on the list, though its status is still open.

    1. Save an open job yesterday
    2. Open the home page
    3. Expect: the list is empty; the job itself is still "open" (spec D2)
    """
    job = make_job(employer, date=timezone.localdate() - datetime.timedelta(days=1))

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == []
    job.refresh_from_db()
    assert job.status == Job.Status.OPEN


def test_jobs_are_listed_soonest_first(client, employer):
    """The list is ordered by date, then start time, not by when the job was posted.

    1. Post a job in two weeks, then one next week at 10:00, then one next week at 07:00
    2. Open the home page
    3. Expect: next week 07:00, next week 10:00, in two weeks
    """
    later = make_job(employer, date=NEXT_WEEK + datetime.timedelta(days=7))
    ten = make_job(employer, start_time=datetime.time(10, 0))
    seven = make_job(employer, start_time=datetime.time(7, 0))

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == [seven, ten, later]


@pytest.mark.parametrize(
    "role", [None, "worker", "employer"], ids=["guest", "worker", "employer"]
)
def test_everyone_sees_the_list(client, employer, role):
    """Guests, workers and employers all see the same list (spec D1).

    1. Save an open job next week
    2. Open the home page as a guest, a worker or another employer
    3. Expect: status 200 and the job is in the list
    """
    job = make_job(employer)
    if role:
        user = User.objects.create_user(
            email="ivan@example.com", password="x", role=role
        )
        client.force_login(user)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert jobs_on_page(response) == [job]


# Pages (R5, R6; AC5, AC6)


def test_21_jobs_make_two_pages(client, employer):
    """20 jobs per page; the count shows all jobs found, on every page.

    1. Save 21 open jobs next week
    2. Open the home page, then ?page=2
    3. Expect: 20 jobs and a "Next" link on page 1, 1 job and a "Previous" link on page 2,
       "Page 1 of 2" / "Page 2 of 2", and "21 open" on both
    """
    for _ in range(21):
        make_job(employer)

    first = client.get(reverse("home"))
    second = client.get(reverse("home"), {"page": 2})

    assert len(jobs_on_page(first)) == 20
    assert len(jobs_on_page(second)) == 1
    assertContains(first, "21 open")
    assertContains(second, "21 open")
    assertContains(first, "Page 1 of 2")
    assertContains(second, "Page 2 of 2")
    assertContains(first, 'href="?page=2"')
    assertNotContains(first, "Previous")
    assertContains(second, 'href="?page=1"')
    # "Next →", not "Next": the date filter has "Next 7 days" (#18 iteration 2).
    assertNotContains(second, "Next →")


def test_one_page_has_no_page_links(client, employer):
    """With all jobs on one page there is no page navigation.

    1. Save one open job
    2. Open the home page
    3. Expect: "1 open", no "Page 1 of 1", no page navigation
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertContains(response, "1 open")
    assertNotContains(response, "Page 1 of")
    assertNotContains(response, 'aria-label="Pages"')


def test_a_page_that_does_not_exist_gives_404(client, employer):
    """A page number past the last page is "not found".

    1. Save one open job (one page)
    2. Open the home page with ?page=99
    3. Expect: status 404
    """
    make_job(employer)

    response = client.get(reverse("home"), {"page": 99})

    assert response.status_code == 404


# The card (R7, R8; AC8)


def test_card_shows_what_a_worker_needs_and_no_address(client, employer):
    """The card shows type, rate, district, date, start-end time and the workers needed.

    1. Save a demolition job in Sendling next week, 08:00 for 6 hours, 2 workers, 20.00 €/h
    2. Open the home page
    3. Expect: "Demolition", "20.00 €/h", "Sendling", the date, "08:00–14:00",
       "Needs 2 workers"; not the address and not the description
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertContains(response, "Demolition")
    assertContains(response, "20.00 €/h")
    assertContains(response, "Sendling")
    assertContains(response, dateformat.format(NEXT_WEEK, "D j M"))
    assertContains(response, "08:00–14:00")
    assertContains(response, "Needs 2 workers")
    assertNotContains(response, "Lindwurmstraße 1")
    assertNotContains(response, "Tear down a garden shed.")


def test_card_says_one_worker_in_the_singular(client, employer):
    """One worker is "Needs 1 worker", not "workers".

    1. Save a job for one worker
    2. Open the home page
    3. Expect: "Needs 1 worker<", the singular form
    """
    make_job(employer, workers_needed=1)

    response = client.get(reverse("home"))

    assertContains(response, "Needs 1 worker<")


# Guests and the empty list (R9, R10; AC9, AC10)


def test_guest_sees_the_post_a_job_line(client):
    """A guest sees "Need workers? Post a job", and the link goes to signup.

    1. Open the home page as a guest
    2. Expect: "Need workers?" and a link to the signup page
    """
    response = client.get(reverse("home"))

    assertContains(response, "Need workers?")
    assertContains(response, f'href="{reverse("register")}" class="link font-semibold"')


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_logged_in_users_do_not_see_the_post_a_job_line(client, role):
    """Logged-in users do not see the line for guests.

    1. Log in as a worker or an employer
    2. Open the home page
    3. Expect: no "Need workers?"
    """
    user = User.objects.create_user(email="ivan@example.com", password="x", role=role)
    client.force_login(user)

    response = client.get(reverse("home"))

    assertNotContains(response, "Need workers?")


def test_empty_list_says_there_are_no_jobs(client):
    """Without any open upcoming job the page says so.

    1. Open the home page with no jobs in the database
    2. Expect: "No open jobs right now." and "0 open"
    """
    response = client.get(reverse("home"))

    assertContains(response, "No open jobs right now.")
    assertContains(response, "0 open")
