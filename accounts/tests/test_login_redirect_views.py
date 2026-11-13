"""Integration tests: where a user lands after logging in (#20).

Spec: docs/specs/my-jobs.md, iteration 2 (R11-R13, AC9-AC11, D4), and since #38
docs/specs/reviews.md, iteration 3 (R15, AC12, D16). An employer lands on
"My jobs", a worker on "My applications", a user without a role on the home page; a
`?next=` address still wins.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from pytest_django.asserts import assertRedirects

pytestmark = [pytest.mark.django_db, pytest.mark.story(20)]

User = get_user_model()

PASSWORD = "Gerüst-2026-Munich"


def make_user(role):
    """A user with the given role ("" = not chosen yet) and the test password."""
    return User.objects.create_user(
        email="anna@example.com", password=PASSWORD, role=role
    )


def log_in(client, url=None):
    """Send the login form as anna@example.com, to `url` or the plain login page."""
    return client.post(
        url or reverse("login"),
        {"username": "anna@example.com", "password": PASSWORD},
    )


def test_employer_lands_on_my_jobs(client):
    """After logging in, an employer goes to "My jobs" (AC9).

    1. Create an employer
    2. Log in on the login page
    3. Expect: a redirect to "My jobs"
    """
    make_user(User.Role.EMPLOYER)

    response = log_in(client)

    assertRedirects(response, reverse("my_jobs"))


@pytest.mark.story(38)
def test_worker_lands_on_my_applications(client):
    """After logging in, a worker goes to "My applications" (#38, reviews.md R15, D16).

    Changed by #38: until then the home page, the job list (AC10 of #20).

    1. Create a worker
    2. Log in on the login page
    3. Expect: a redirect to "My applications"
    """
    make_user(User.Role.WORKER)

    response = log_in(client)

    assertRedirects(response, reverse("my_applications"))


@pytest.mark.story(38)
def test_next_address_wins_for_a_worker(client):
    """A worker sent to login from another page goes back there (#38, R15).

    1. Create a worker
    2. Log in on the login page with ?next= their profile page
    3. Expect: a redirect to the profile page, not to "My applications"
    """
    make_user(User.Role.WORKER)

    profile = reverse("worker_profile")
    response = log_in(client, reverse("login") + "?next=" + profile)

    assertRedirects(response, profile, fetch_redirect_response=False)


@pytest.mark.story(38)
def test_logged_in_worker_opening_login_goes_to_my_applications(client):
    """A logged-in worker who opens the login page goes to "My applications" (#38, R15).

    1. Log in as a worker
    2. Open the login page
    3. Expect: a redirect to "My applications"
    """
    client.force_login(make_user(User.Role.WORKER))

    response = client.get(reverse("login"))

    assertRedirects(response, reverse("my_applications"))


def test_user_without_a_role_lands_on_the_home_page(client):
    """A user who has not chosen a role yet goes to the home page, as before (R11).

    1. Create a user without a role
    2. Log in on the login page
    3. Expect: a redirect to the home page (from there the onboarding middleware sends
       them on to the role choice)
    """
    make_user("")

    response = log_in(client)

    assertRedirects(response, reverse("home"), fetch_redirect_response=False)


def test_next_address_wins_for_an_employer(client):
    """An employer sent to login from another page goes back there (AC11).

    1. Create an employer
    2. Log in on the login page with ?next=/jobs/new/
    3. Expect: a redirect to /jobs/new/, not to "My jobs"
    """
    make_user(User.Role.EMPLOYER)

    response = log_in(client, reverse("login") + "?next=" + reverse("job_create"))

    assertRedirects(response, reverse("job_create"), fetch_redirect_response=False)


def test_logged_in_employer_opening_login_goes_to_my_jobs(client):
    """A logged-in employer who opens the login page goes to "My jobs" too (R13).

    1. Log in as an employer
    2. Open the login page
    3. Expect: a redirect to "My jobs"
    """
    client.force_login(make_user(User.Role.EMPLOYER))

    response = client.get(reverse("login"))

    assertRedirects(response, reverse("my_jobs"))
