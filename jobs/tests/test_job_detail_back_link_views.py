"""Integration tests: the link back at the top of the job page (#38).

Each test goes through the whole stack: middleware, URL, view and template. Spec:
docs/specs/reviews.md, iteration 3 (R16, D17), acceptance criterion AC13; the owner's
link is #23 (applications-list.md D17).
"""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

TO_APPLICATIONS = (
    f'href="{reverse("my_applications")}" class="link link-hover text-sm">'
)
TO_JOBS = f'href="{reverse("home")}" class="link link-hover text-sm">'
TO_MY_JOBS = f'href="{reverse("my_jobs")}" class="link link-hover text-sm">'


@pytest.fixture
def job():
    """Anna's open job next week."""
    return make_job(make_employer("anna@example.com"))


def job_page(client, job):
    """GET the job page."""
    return client.get(reverse("job_detail", args=[job.pk]))


def test_worker_who_applied_goes_back_to_my_applications(client, job):
    """The job is on their own page, so the arrow leads there (R16, D17).

    1. Save Ivan's application to the job
    2. Open the job page as Ivan
    3. Expect: "← My applications" to "My applications"; no "← Jobs"
    """
    ivan = make_worker("ivan@example.com")
    Application.objects.create(job=job, worker=ivan)
    client.force_login(ivan)

    response = job_page(client, job)

    assertContains(response, TO_APPLICATIONS + "← My applications")
    assertNotContains(response, TO_JOBS)


def test_worker_without_an_application_goes_back_to_the_jobs(client, job):
    """Nothing of theirs here: back to the job list, as before (R16).

    1. Open the job page as a worker who did not apply
    2. Expect: "← Jobs"; no link back to "My applications"
    """
    client.force_login(make_worker("olga@example.com"))

    response = job_page(client, job)

    assertContains(response, TO_JOBS + "← Jobs")
    assertNotContains(response, TO_APPLICATIONS)


def test_guest_goes_back_to_the_jobs(client, job):
    """A guest has no page of their own (R16).

    1. Open the job page without logging in
    2. Expect: "← Jobs"
    """
    assertContains(job_page(client, job), TO_JOBS + "← Jobs")


def test_owner_still_goes_back_to_my_jobs(client, job):
    """Unchanged for the employer (applications-list.md D17).

    1. Open the job page as Anna, its owner
    2. Expect: "← My jobs"
    """
    client.force_login(job.employer)

    assertContains(job_page(client, job), TO_MY_JOBS + "← My jobs")
