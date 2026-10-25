"""Integration tests: the applications to a job, on the job page of its employer (#23).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/applications-list.md, iteration 2 (R3, R4, R8, R10-R17, D5, D7, D11, D12,
D15-D18), acceptance criteria AC10 and AC12-AC18, AC20. Iteration 1's separate page was
replaced (D15); its access rules became "only the owner sees the list" (AC15). The worker
page is in accounts/tests/test_worker_detail_views.py.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains

from accounts.models import WorkerProfile
from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(23)]

# The section's heading: on the page only while the list is shown.
LIST = 'id="applications"'


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
    """An open demolition job next week for 2 workers."""
    return make_job(employer)


def apply(job, email, name, **fields):
    """Save an application to `job` from a new crew of 3 called `name`."""
    worker = make_worker(email)
    worker.name = name
    worker.save()
    return Application.objects.create(job=job, worker=worker, **fields)


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


# What the owner sees (R3, R10, R13, D5, D16; AC14, AC16)


def test_owner_sees_each_application_with_the_workers_details(employer_client, job):
    """Every application shows who applied, what they offer and what they wrote.

    1. Save an application from Ivan, a crew of 3 (Gewerbe, work permit confirmed)
       bringing 2, with a message
    2. Open the job's page as its employer
    3. Expect: the list instead of the employer card, with the name, "Crew of 3",
       "brings 2 workers", the legal status, "Work permit confirmed", the message in
       quotes, "Pending" and the day it was sent
    """
    application = apply(
        job, "ivan@example.com", "Ivan Petrenko", workers_offered=2, message="We are 3."
    )
    WorkerProfile.objects.filter(user=application.worker).update(legal_status="gewerbe")

    response = employer_client.get(detail_url(job))

    assertContains(response, LIST)
    assertNotContains(response, "Huber Bau GmbH")  # the employer card
    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Crew of 3")
    assertContains(response, "brings 2 workers")
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
    2. Open the first job's page
    3. Expect: Ivan and "Applications (1)", not Olga
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    apply(make_job(employer), "olga@example.com", "Olga Popescu")

    response = employer_client.get(detail_url(job))

    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Applications (1)")
    assertNotContains(response, "Olga Popescu")


def test_newest_application_comes_first(employer_client, job):
    """The employer sees what is new at the top (spec D5).

    1. Save an application from Ivan, then a newer one from Olga
    2. Open the job's page
    3. Expect: "Applications (2)"; Olga comes before Ivan
    """
    older = apply(job, "ivan@example.com", "Ivan Petrenko")
    Application.objects.filter(pk=older.pk).update(
        created_at=timezone.now() - datetime.timedelta(hours=1)
    )
    apply(job, "olga@example.com", "Olga Popescu")

    response = employer_client.get(detail_url(job))

    content = response.content.decode()
    assertContains(response, "Applications (2)")
    assert content.index("Olga Popescu") < content.index("Ivan Petrenko")


def test_page_without_applications_says_so(employer_client, job):
    """A job nobody applied to yet gets a short line instead of an empty list.

    1. Open the page of a job without applications as its employer
    2. Expect: "Applications (0)" and "No applications yet."
    """
    response = employer_client.get(detail_url(job))

    assertContains(response, "Applications (0)")
    assertContains(response, "No applications yet.")


def test_unconfirmed_work_permit_is_shown(employer_client, job):
    """The employer sees when a worker has not confirmed the work permit.

    1. Save an application from a worker without the work-permit confirmation (possible
       when the admin removes it after applying)
    2. Open the job's page
    3. Expect: "Work permit not confirmed", not "Work permit confirmed"
    """
    worker = make_worker("ivan@example.com", permit=False)
    Application.objects.create(job=job, worker=worker)

    response = employer_client.get(detail_url(job))

    assertContains(response, "Work permit not confirmed")
    assertNotContains(response, "Work permit confirmed")


def test_page_shows_no_contact_details(employer_client, job):
    """Phone and email stay hidden until the employer accepts the worker (#25).

    1. Save an application from Ivan, who has a phone number
    2. Open the job's page as its employer
    3. Expect: neither Ivan's email nor his phone is on the page
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    application.worker.phone = "+49 151 2345678"
    application.worker.save()

    response = employer_client.get(detail_url(job))

    assertContains(response, "Ivan Petrenko")
    assertNotContains(response, "ivan@example.com")
    assertNotContains(response, "2345678")


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_owner_sees_the_applications_in_every_job_status(
    employer_client, employer, status
):
    """A job that is no longer open still shows its applications (spec D3).

    1. Save a filled / done / cancelled job with an application from Ivan
    2. Open its page as its employer
    3. Expect: Ivan's application
    """
    closed_job = make_job(employer, status=status)
    apply(closed_job, "ivan@example.com", "Ivan Petrenko")

    response = employer_client.get(detail_url(closed_job))

    assertContains(response, "Ivan Petrenko")


# Only the owner sees the list (R14, D16; AC15)


def test_guest_sees_the_employer_card_and_no_list(client, job):
    """A guest sees the job page as before #23.

    1. Save an application from Ivan
    2. Open the job's page without logging in
    3. Expect: the employer card; no list and not Ivan's name
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")

    response = client.get(detail_url(job))

    assertContains(response, "Huber Bau GmbH")
    assertNotContains(response, LIST)
    assertNotContains(response, "Ivan Petrenko")


def test_worker_who_applied_does_not_see_the_other_applicants(client, job):
    """A worker sees their own application, never who else applied (spec D16).

    1. Save applications from Ivan and Olga; log in as Ivan
    2. Open the job's page
    3. Expect: the employer card and "You applied"; no list and not Olga's name
    """
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko").worker
    apply(job, "olga@example.com", "Olga Popescu")
    client.force_login(ivan)

    response = client.get(detail_url(job))

    assertContains(response, "Huber Bau GmbH")
    assertContains(response, "You applied")
    assertNotContains(response, LIST)
    assertNotContains(response, "Olga Popescu")


def test_other_employer_does_not_see_the_list(client, job):
    """Another employer sees the job as everyone does, without its applications.

    1. Save an application from Ivan to Anna's job
    2. Log in as Boris, another employer, and open the job's page
    3. Expect: the employer card; no list and not Ivan's name
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    client.force_login(make_employer("boris@example.com"))

    response = client.get(detail_url(job))

    assertContains(response, "Huber Bau GmbH")
    assertNotContains(response, LIST)
    assertNotContains(response, "Ivan Petrenko")


# Queries (R16, D7; AC17)


def count_page_queries(client, job):
    """How many SQL queries the job's page makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(detail_url(job))
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_applications(employer_client, job):
    """The page loads all applications with their workers at once, not one query each.

    1. Save 1 application; count the owner's page's queries
    2. Save 2 more; count again
    3. Expect: the same number of queries (no "N+1")
    """
    apply(job, "ivan@example.com", "Ivan Petrenko")
    with_one = count_page_queries(employer_client, job)

    apply(job, "olga@example.com", "Olga Popescu")
    apply(job, "mehmet@example.com", "Mehmet Kaya")
    with_three = count_page_queries(employer_client, job)

    assert with_three == with_one


# The link to the worker page (R8; AC10)


def test_each_name_links_to_the_workers_page(employer_client, job):
    """The employer opens a worker's profile by tapping the name.

    1. Save applications from Ivan and Olga
    2. Open the job's page as its employer
    3. Expect: a link to each worker's page, with the worker's name as its text
    """
    ivan = apply(job, "ivan@example.com", "Ivan Petrenko").worker
    olga = apply(job, "olga@example.com", "Olga Popescu").worker

    response = employer_client.get(detail_url(job))

    for worker in (ivan, olga):
        url = reverse("worker_detail", args=[worker.pk])
        assertContains(response, f'href="{url}"')
        assertContains(response, f">{worker.name}</a>")


# The mockup's look (R11, R12, D11-D13; AC12, AC13)


def test_each_application_has_an_avatar_with_initials(employer_client, job):
    """The avatar shows the worker's initials, as on the mockup.

    1. Save an application from Andrii Petrenko
    2. Open the job's page as its employer
    3. Expect: "AP" inside the avatar
    """
    apply(job, "andrii@example.com", "Andrii Petrenko")

    response = employer_client.get(detail_url(job))

    assertContains(response, '<span aria-hidden="true">AP</span>')


def test_card_shows_only_the_jobs_skill(employer_client, job):
    """Only the skill this job needs is shown, not the worker's other skills (spec D12).

    1. Save an application from Ivan, who can do demolition and carrying, to a demolition
       job
    2. Open the job's page as its employer
    3. Expect: "✓ Demolition"; "Carrying materials" is not on the page
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    WorkerProfile.objects.filter(user=application.worker).update(
        skills=["demolition", "carrying"]
    )

    response = employer_client.get(detail_url(job))

    assertContains(response, "✓ Demolition")
    assertNotContains(response, "Carrying materials")
    assertNotContains(response, "No skill:")


# The grey badge: "−" for the eye, hidden words for a screen reader (D12).
MISSING_SKILL = (
    '<span class="sr-only">No skill:</span><span aria-hidden="true">−</span> Demolition'
)


def test_card_says_when_the_worker_lacks_the_jobs_skill(employer_client, job):
    """A worker without the job's skill gets the same badge, grey with "−" (spec D12).

    1. Save an application from Ivan, who can only carry, to a demolition job
    2. Open the job's page as its employer
    3. Expect: "− Demolition" with the hidden words "No skill:", and no "✓ Demolition"
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko")
    WorkerProfile.objects.filter(user=application.worker).update(skills=["carrying"])

    response = employer_client.get(detail_url(job))

    assertContains(response, MISSING_SKILL)
    assertNotContains(response, "✓ Demolition")


# Navigation (R15, R17, D17, D18; AC18, AC20)


def test_top_link_goes_back_to_my_jobs_for_the_owner(client, employer_client, job):
    """The owner goes back to "My jobs", everyone else to the job list (spec D17).

    1. Open the job's page as its employer, then as a guest
    2. Expect: "← My jobs" to "My jobs" for the employer; "← Jobs" to the job list for
       the guest
    """
    owner_page = employer_client.get(detail_url(job))
    client.logout()
    guest_page = client.get(detail_url(job))

    assertContains(owner_page, f'href="{reverse("my_jobs")}" class="link link-hover')
    assertContains(owner_page, "← My jobs")
    assertContains(guest_page, f'href="{reverse("home")}" class="link link-hover')
    assertContains(guest_page, "← Jobs")


def test_separate_applications_page_is_gone(employer_client, job):
    """The list lives on the job page only; the old page and its link are removed (D15).

    1. Open /jobs/<pk>/applications/ as the job's employer, then "My jobs"
    2. Expect: 404 for the old page; no "Applications" link on "My jobs"
    """
    old_page = employer_client.get(f"/jobs/{job.pk}/applications/")
    my_jobs = employer_client.get(reverse("my_jobs"))

    assert old_page.status_code == 404
    assertNotContains(my_jobs, ">Applications</a>")
