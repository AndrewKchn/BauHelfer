"""Integration tests: the job pages through the Django test client (#16).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/job-form.md (R5, R10-R15), acceptance criteria AC8-AC18.
"""

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from accounts.models import EmployerProfile
from jobs.models import Job

pytestmark = [pytest.mark.django_db, pytest.mark.story(16)]

User = get_user_model()

NEXT_WEEK = timezone.localdate() + datetime.timedelta(days=7)


def make_employer(email, **fields):
    """An employer with a filled company profile (#12), ready to post jobs."""
    user = User.objects.create_user(
        email=email, password="x", role="employer", **fields
    )
    EmployerProfile.objects.create(
        user=user, company_name="Huber Bau GmbH", trades=["demolition"]
    )
    return user


def make_job(employer, **fields):
    """A saved open job of `employer`; `fields` replace the defaults."""
    values = {
        "job_type": "demolition",
        "description": "Tear down a garden shed.",
        "original_language": "de",
        "address": "Lindwurmstraße 1",
        "district": "sendling",
        "date": NEXT_WEEK,
        "start_time": datetime.time(8, 0),
        "hours": 6,
        "workers_needed": 2,
        "hourly_rate": Decimal("20.00"),
        **fields,
    }
    return Job.objects.create(employer=employer, **values)


def form_data(**fields):
    """What the browser sends for a correctly filled job form."""
    return {
        "job_type": "carrying",
        "description": "Carry tiles to the third floor.",
        "address": "Leopoldstraße 50",
        "district": "schwabing_west",
        "date": NEXT_WEEK.isoformat(),
        "start_time": "07:30",
        "hours": "4",
        "workers_needed": "3",
        "hourly_rate": "20.00",
        **fields,
    }


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com", preferred_language="ru")


@pytest.fixture
def other_employer():
    """A second employer, who must not touch Anna's jobs."""
    return make_employer("boris@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """An open job of the employer."""
    return make_job(employer)


def page_urls(job):
    """The four job pages; edit and cancel point at `job`."""
    return [
        reverse("job_create"),
        reverse("my_jobs"),
        reverse("job_edit", args=[job.pk]),
        reverse("job_cancel", args=[job.pk]),
    ]


# Who may open the pages (R10, AC8)


def test_guest_is_sent_to_login(client, job):
    """A guest opening any job page is sent to the login page.

    1. Open each of the four job pages without logging in
    2. Expect: a redirect to login, which brings the guest back afterwards
    """
    for url in page_urls(job):
        response = client.get(url)

        assertRedirects(response, f"{reverse('login')}?next={url}")


def test_worker_gets_403(client, job):
    """A worker opening any job page gets "403 Forbidden".

    1. Log in as a worker
    2. Open each of the four job pages
    3. Expect: status 403 on every page
    """
    worker = User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )
    client.force_login(worker)

    for url in page_urls(job):
        assert client.get(url).status_code == 403, url


# Create (R11, AC9-AC12)


def test_employer_without_profile_is_sent_to_the_profile_form(client):
    """An employer without a company profile must fill it in before posting.

    1. Log in as an employer without a profile
    2. Open "Post a job"
    3. Expect: a redirect to the company profile form, with a message saying why
    """
    newcomer = User.objects.create_user(
        email="clara@example.com", password="x", role="employer"
    )
    client.force_login(newcomer)

    response = client.get(reverse("job_create"), follow=True)

    assertRedirects(response, reverse("employer_profile_edit"))
    assertContains(response, "company profile")


def test_job_gets_the_employers_language(employer_client):
    """A posted job is written in the employer's own language; the form does not ask.

    1. Log in as an employer whose preferred language is Russian
    2. Open "Post a job": no language field
    3. Send a correctly filled job form
    4. Expect: the job's original language is Russian
    """
    # Translation (#32) starts from this language and corrects it if Claude finds another.
    response = employer_client.get(reverse("job_create"))
    assertNotContains(response, 'name="original_language"')

    employer_client.post(reverse("job_create"), form_data())

    assert Job.objects.get().original_language == "ru"


def test_employer_posts_a_job(employer_client, employer):
    """An employer posts a job; it is saved as theirs and open, and listed in "My jobs".

    1. Log in as an employer with a profile
    2. Send a correctly filled job form
    3. Expect: one job, owned by the employer, status open
    4. Expect: the employer lands on "My jobs" with "Job posted." and sees the job
    """
    response = employer_client.post(reverse("job_create"), form_data(), follow=True)

    job = Job.objects.get()
    assert job.employer == employer
    assert job.status == Job.Status.OPEN
    assert job.address == "Leopoldstraße 50"
    assertRedirects(response, reverse("my_jobs"))
    assertContains(response, "Job posted.")
    assertContains(response, "Carrying materials")


def test_posted_fields_for_owner_and_status_are_ignored(
    employer_client, employer, other_employer
):
    """Extra fields in the request cannot change the owner or the status.

    1. Log in as an employer
    2. Send a job form with employer = another user and status = filled added
    3. Expect: the job belongs to the logged-in employer and is open
    """
    data = form_data(employer=other_employer.pk, status="filled")

    employer_client.post(reverse("job_create"), data)

    job = Job.objects.get()
    assert job.employer == employer
    assert job.status == Job.Status.OPEN


def test_invalid_job_is_not_saved(employer_client):
    """A job below the minimum wage is not saved, and the form says why.

    1. Log in as an employer
    2. Send a job form with an hourly rate of 5.00 €
    3. Expect: no job saved, the form is shown again with the minimum wage error
    """
    response = employer_client.post(
        reverse("job_create"), form_data(hourly_rate="5.00")
    )

    assert response.status_code == 200
    assert not Job.objects.exists()
    assert "hourly_rate" in response.context["form"].errors


# Edit (R12, AC13-AC15)


def test_owner_edits_an_open_job(employer_client, employer, job):
    """The owner changes an open job; the change is saved and the owner stays.

    1. Log in as the employer who posted the job
    2. Open "Edit": the form shows the saved address
    3. Send the form with a new address
    4. Expect: the job has the new address, the same owner and language, and is still open
    """
    url = reverse("job_edit", args=[job.pk])
    assertContains(employer_client.get(url), "Lindwurmstraße 1")

    response = employer_client.post(url, form_data(address="Marienplatz 8"))

    assertRedirects(response, reverse("my_jobs"))
    job.refresh_from_db()
    assert job.address == "Marienplatz 8"
    assert job.employer == employer
    assert job.status == Job.Status.OPEN
    assert job.original_language == "de"  # kept, not replaced by the employer's "ru"


@pytest.mark.parametrize("name", ["job_edit", "job_cancel"])
def test_other_employer_gets_404(client, other_employer, job, name):
    """Another employer cannot see, edit or cancel the job: for them it does not exist.

    1. Log in as a different employer
    2. Open the edit / cancel page of Anna's job, then send the form there
    3. Expect: 404 both times, and the job is unchanged
    """
    client.force_login(other_employer)
    url = reverse(name, args=[job.pk])

    assert client.get(url).status_code == 404
    assert client.post(url, form_data(address="Marienplatz 8")).status_code == 404
    job.refresh_from_db()
    assert job.address == "Lindwurmstraße 1"
    assert job.status == Job.Status.OPEN


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
@pytest.mark.parametrize("name", ["job_edit", "job_cancel"])
def test_job_that_is_not_open_gives_404(employer_client, employer, status, name):
    """Only open jobs can be edited or cancelled, even by their owner.

    1. Log in as the employer
    2. Open edit / cancel of their own filled / done / cancelled job
    3. Expect: 404
    """
    closed_job = make_job(employer, status=status)

    response = employer_client.get(reverse(name, args=[closed_job.pk]))

    assert response.status_code == 404


# Cancel (R13, AC16)


def test_cancel_page_asks_first(employer_client, job):
    """Opening "Cancel" only asks; the job is still open.

    1. Log in as the owner
    2. Open the cancel page of an open job
    3. Expect: a confirmation page naming the job, the job is still open
    """
    response = employer_client.get(reverse("job_cancel", args=[job.pk]))

    assertContains(response, "Demolition")
    assertContains(response, 'method="post"')
    job.refresh_from_db()
    assert job.status == Job.Status.OPEN


def test_owner_cancels_a_job(employer_client, job):
    """Confirming the cancel marks the job cancelled and keeps it in the database.

    1. Log in as the owner
    2. Confirm the cancel (POST)
    3. Expect: back on "My jobs" with a message; the job is cancelled, not deleted
    """
    response = employer_client.post(reverse("job_cancel", args=[job.pk]), follow=True)

    assertRedirects(response, reverse("my_jobs"))
    assertContains(response, "Job cancelled.")
    job.refresh_from_db()
    assert job.status == Job.Status.CANCELLED


# My jobs (R14, AC17)


def test_my_jobs_lists_only_own_jobs(employer_client, employer, other_employer):
    """ "My jobs" shows the employer's own jobs and no one else's.

    1. Save an open and a cancelled job of the employer and a job of another employer
    2. Open "My jobs"
    3. Expect: both own jobs with their status, not the other employer's job
    """
    make_job(employer, job_type="demolition")
    make_job(employer, job_type="carrying", status=Job.Status.CANCELLED)
    make_job(other_employer, job_type="painting")

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, "Demolition")
    assertContains(response, "Carrying materials")
    assertContains(response, "Cancelled")
    assertNotContains(response, "Painting helper")


def test_my_jobs_offers_edit_and_cancel_for_open_jobs_only(employer_client, employer):
    """ "Edit" and "Cancel" links are shown for open jobs only.

    1. Save an open and a cancelled job of the employer
    2. Open "My jobs"
    3. Expect: edit and cancel links for the open job, none for the cancelled one
    """
    open_job = make_job(employer)
    cancelled_job = make_job(employer, status=Job.Status.CANCELLED)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'href="{reverse("job_edit", args=[open_job.pk])}"')
    assertContains(response, f'href="{reverse("job_cancel", args=[open_job.pk])}"')
    assertNotContains(response, reverse("job_edit", args=[cancelled_job.pk]))
    assertNotContains(response, reverse("job_cancel", args=[cancelled_job.pk]))


def test_my_jobs_card_follows_the_mockup(employer_client, employer):
    """A job card in "My jobs" looks like the UI mockup.

    1. Save an open demolition job next week, 08:00, 6 hours, 2 workers, 20.00 €
    2. Open "My jobs"
    3. Expect: the title "Demolition · <weekday> <day> <month>"; time, hours, workers and
       rate in one line that wraps only between its parts; the district in a line of its
       own; the links "Edit" and "Cancel job"
    """
    make_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f"Demolition · {dateformat.format(NEXT_WEEK, 'D j M')}")
    # The short parts share one line; on a phone it may wrap only between them, never
    # inside one ("2 / workers"), so each is a no-wrap span.
    for part in ["08:00", "6 h", "2 workers", "20.00 €/h"]:
        assertContains(response, f'<span class="whitespace-nowrap">{part}')
    # The district has a line of its own and may wrap: the longest one has 52 characters
    # and would run out of the card if it could not.
    assertContains(response, ">Sendling</p>")
    assertNotContains(response, 'whitespace-nowrap">Sendling')
    assertContains(response, "Cancel job")


def test_post_form_follows_the_mockup(employer_client):
    """The "Post a job" form is sent with the "Publish job" button of the UI mockup.

    1. Log in as an employer
    2. Open "Post a job"
    3. Expect: a "Publish job" button
    """
    response = employer_client.get(reverse("job_create"))

    assertContains(response, "Publish job")


def test_empty_my_jobs_invites_to_post(employer_client):
    """Without jobs, "My jobs" leads to "Post a job".

    1. Log in as an employer without jobs
    2. Open "My jobs"
    3. Expect: a link to the "Post a job" form
    """
    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'href="{reverse("job_create")}"')


# CSRF (spec R13: changes only through POST forms of our own pages)


@pytest.mark.parametrize("name", ["job_create", "job_edit", "job_cancel"])
def test_job_forms_need_the_csrf_token(employer, job, name):
    """Posting, editing and cancelling a job only work with the CSRF token of our page.

    1. Log in with a client that checks CSRF like a real browser
    2. Send the post / edit / cancel form without the token
    3. Expect: 403 Forbidden; no new job, the job is unchanged and still open
    """
    # The default test client skips the CSRF check, so the other tests cannot see it.
    # Without it, another site could post, change or cancel jobs of a logged-in visitor.
    client = Client(enforce_csrf_checks=True)
    client.force_login(employer)
    url = reverse(name) if name == "job_create" else reverse(name, args=[job.pk])

    response = client.post(url, form_data(address="Marienplatz 8"))

    assert response.status_code == 403
    job.refresh_from_db()
    assert Job.objects.count() == 1
    assert job.address == "Lindwurmstraße 1"
    assert job.status == Job.Status.OPEN


@pytest.mark.parametrize("name", ["job_create", "job_edit", "job_cancel"])
def test_job_form_pages_carry_the_csrf_token(employer_client, job, name):
    """Every job page with a form puts the CSRF token into it.

    1. Log in as the employer
    2. Open the post / edit / cancel page
    3. Expect: the hidden csrfmiddlewaretoken field in the page
    """
    # Catches a forgotten {% csrf_token %}: real browsers would then get 403 on submit.
    url = reverse(name) if name == "job_create" else reverse(name, args=[job.pk])

    response = employer_client.get(url)

    # Two tokens: one in the logout form of the header menu, one in this page's form.
    assertContains(response, 'name="csrfmiddlewaretoken"', count=2)


# Menu (R15, AC18)


def test_employer_menu_has_the_job_links(employer_client):
    """An employer's menu links to "Post a job" and "My jobs".

    1. Log in as an employer
    2. Open the home page
    3. Expect: both links in the menu
    """
    response = employer_client.get(reverse("home"))

    assertContains(response, f'href="{reverse("job_create")}"')
    assertContains(response, f'href="{reverse("my_jobs")}"')


def test_worker_menu_has_no_job_links(client):
    """A worker's menu has no employer job links.

    1. Log in as a worker
    2. Open the home page
    3. Expect: no "Post a job" and no "My jobs" link
    """
    worker = User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )
    client.force_login(worker)

    response = client.get(reverse("home"))

    assertNotContains(response, "Post a job")
    assertNotContains(response, "My jobs")
