"""Integration tests: the employer's page with the applications to one job (#23).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/applications-list.md, iteration 1 (R1-R5, D3-D8), acceptance criteria
AC1-AC7, and from iteration 2 the link to the worker page (R8, AC10).
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from accounts.models import WorkerProfile
from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(23)]


@pytest.fixture
def employer():
    """The employer who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the job's employer."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """An open job next week for 2 workers."""
    return make_job(employer)


def apply(job, email, name, **fields):
    """Save an application to `job` from a new crew of 3 called `name`."""
    worker = make_worker(email)
    worker.name = name
    worker.save()
    return Application.objects.create(job=job, worker=worker, **fields)


def applications_url(job):
    """The job's applications page."""
    return reverse("job_applications", args=[job.pk])


# What the owner sees (R2, R3; AC1, AC2, AC5)


def test_owner_sees_each_application_with_the_workers_details(employer_client, job):
    """Every application shows who applied, what they offer and what they wrote.

    1. Save an application from Ivan, a crew of 3 (carrying, Gewerbe, work permit
       confirmed) bringing 2, with a message
    2. Open the job's applications page as its employer
    3. Expect: the name, "Crew of 3", "brings 2 workers", the skill, the legal status,
       "Work permit confirmed", the message in quotes, "Pending" and the day it was sent
    """
    application = apply(
        job, "ivan@example.com", "Ivan Petrenko", workers_offered=2, message="We are 3."
    )
    WorkerProfile.objects.filter(user=application.worker).update(
        skills=["carrying"], legal_status="gewerbe"
    )

    response = employer_client.get(applications_url(job))

    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Crew of 3")
    assertContains(response, "brings 2 workers")
    assertContains(response, "Carrying materials")
    assertContains(response, "Self-employed (Gewerbe)")
    assertContains(response, "Work permit confirmed")
    assertContains(response, "“We are 3.”")
    assertContains(response, "Pending")
    sent = dateformat.format(timezone.localdate(), "j M")
    assertContains(response, f"Sent {sent}")


def test_page_shows_only_this_jobs_applications(employer_client, employer, job):
    """An application to another job of the same employer is not on the page.

    1. Save an application from Ivan to the job and one from Olga to another job of the
       same employer
    2. Open the first job's applications page
    3. Expect: Ivan and "Applications (1)", not Olga
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    apply(make_job(employer), "olga@example.com", "Olga Popescu")

    response = employer_client.get(applications_url(job))

    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Applications (1)")
    assertNotContains(response, "Olga Popescu")


def test_newest_application_comes_first(employer_client, job):
    """The employer sees what is new at the top (spec D5).

    1. Save an application from Ivan, then a newer one from Olga
    2. Open the job's applications page
    3. Expect: "Applications (2)"; Olga comes before Ivan
    """
    older = apply(job, "ivan@example.com", "Ivan Petrenko")
    Application.objects.filter(pk=older.pk).update(
        created_at=timezone.now() - datetime.timedelta(hours=1)
    )
    apply(job, "olga@example.com", "Olga Popescu")

    response = employer_client.get(applications_url(job))

    content = response.content.decode()
    assertContains(response, "Applications (2)")
    assert content.index("Olga Popescu") < content.index("Ivan Petrenko")


def test_page_without_applications_says_so(employer_client, job):
    """A job nobody applied to yet gets a short line instead of an empty list.

    1. Open the applications page of a job without applications
    2. Expect: the job's title, "Applications (0)", "No applications yet." and a link back
       to "My jobs"
    """
    response = employer_client.get(applications_url(job))

    assertContains(response, "Demolition")
    assertContains(response, "Applications (0)")
    assertContains(response, "No applications yet.")
    assertContains(response, f'href="{reverse("my_jobs")}"')


def test_unconfirmed_work_permit_is_shown(employer_client, job):
    """The employer sees when a worker has not confirmed the work permit.

    1. Save an application from a worker without the work-permit confirmation (possible
       when the admin removes it after applying)
    2. Open the job's applications page
    3. Expect: "Work permit not confirmed", not "Work permit confirmed"
    """
    worker = make_worker("ivan@example.com", permit=False)
    Application.objects.create(job=job, worker=worker)

    response = employer_client.get(applications_url(job))

    assertContains(response, "Work permit not confirmed")
    assertNotContains(response, "Work permit confirmed")


def test_page_shows_no_contact_details(employer_client, job):
    """Phone and email stay hidden until the employer accepts the worker (#25).

    1. Save an application from Ivan, who has a phone number
    2. Open the job's applications page
    3. Expect: neither Ivan's email nor his phone is on the page
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    application.worker.phone = "+49 151 2345678"
    application.worker.save()

    response = employer_client.get(applications_url(job))

    assertContains(response, "Ivan Petrenko")
    assertNotContains(response, "ivan@example.com")
    assertNotContains(response, "2345678")


# Who may open the page (R1, D3, D4; AC3, AC4)


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_owner_sees_the_applications_in_every_job_status(
    employer_client, employer, status
):
    """A job that is no longer open still shows its applications (spec D3).

    1. Save a filled / done / cancelled job with an application from Ivan
    2. Open its applications page as its employer
    3. Expect: status 200 with Ivan's application
    """
    closed_job = make_job(employer, status=status)
    apply(closed_job, "ivan@example.com", "Ivan Petrenko")

    response = employer_client.get(applications_url(closed_job))

    assertContains(response, "Ivan Petrenko")


def test_guest_is_sent_to_login(client, job):
    """A guest opening the applications page is sent to the login page.

    1. Open the job's applications page without logging in
    2. Expect: a redirect to login, which brings the guest back afterwards
    """
    url = applications_url(job)

    response = client.get(url)

    assertRedirects(response, f"{reverse('login')}?next={url}")


def test_worker_gets_403(client, job):
    """A worker gets "403 Forbidden", even one who applied to the job.

    1. Save an application from Ivan to the job; log in as Ivan
    2. Open the job's applications page
    3. Expect: status 403
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    client.force_login(application.worker)

    assert client.get(applications_url(job)).status_code == 403


def test_other_employer_gets_404(client, job):
    """For another employer the job's applications do not exist (spec D4).

    1. Save an application from Ivan to Anna's job
    2. Log in as Boris, another employer, and open the job's applications page
    3. Expect: 404, and Ivan's name is not shown
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    client.force_login(make_employer("boris@example.com"))

    response = client.get(applications_url(job))

    assert response.status_code == 404
    assertNotContains(response, "Ivan Petrenko", status_code=404)


def test_unknown_job_gives_404(employer_client):
    """A job id that does not exist gives 404.

    1. Open the applications page of job id 999999 as an employer
    2. Expect: 404
    """
    response = employer_client.get(reverse("job_applications", args=[999999]))

    assert response.status_code == 404


# Queries (R4, D7; AC6)


def count_page_queries(client, job):
    """How many SQL queries the applications page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(applications_url(job))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_applications(employer_client, job):
    """The page loads all applications with their workers at once, not one query each.

    1. Save 1 application; count the page's queries
    2. Save 2 more; count again
    3. Expect: the same number of queries (no "N+1")
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    with_one = count_page_queries(employer_client, job)

    apply(job, "olga@example.com", "Olga Popescu")
    apply(job, "mehmet@example.com", "Mehmet Kaya")
    with_three = count_page_queries(employer_client, job)

    assert with_three == with_one


# The link to the worker page (iteration 2: R8; AC10)


def test_each_name_links_to_the_workers_page(employer_client, job):
    """The employer opens a worker's profile by tapping the name.

    1. Save applications from Ivan and Olga
    2. Open the job's applications page
    3. Expect: a link to each worker's page, with the worker's name as its text
    """
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko").worker
    olga = apply(job, "olga@example.com", "Olga Popescu").worker

    response = employer_client.get(applications_url(job))

    for worker in (ivan, olga):
        url = reverse("worker_detail", args=[worker.pk])
        assertContains(response, f'href="{url}"')
        assertContains(response, f">{worker.name}</a>")


# The link from "My jobs" (R5, D8; AC7)


def test_my_jobs_links_to_the_applications_of_every_job(employer_client, employer):
    """Every card on "My jobs" leads to its applications, also a cancelled job's.

    1. Save an open and a cancelled job of the employer
    2. Open "My jobs"
    3. Expect: an "Applications" link to each job's applications page
    """
    open_job = make_job(employer)
    cancelled_job = make_job(employer, status=Job.Status.CANCELLED)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'href="{applications_url(open_job)}"')
    assertContains(response, f'href="{applications_url(cancelled_job)}"')
    assertContains(response, ">Applications</a>")
