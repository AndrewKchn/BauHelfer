"""Integration tests: applying to a job through the Django test client (#22).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/application.md (R4-R6, D1, D5-D8), acceptance criteria AC4-AC10. Who may
post at all (GET 405, guest, employer, unknown job: AC9) stays in test_job_detail_views.py;
the log line (R7) is in test_logging.py.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateUsed,
)

from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(22)]

# The form's text field: on the page only while the form is shown.
MESSAGE_FIELD = 'name="message"'


@pytest.fixture
def employer():
    """The employer who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 2 workers."""
    return make_job(employer)


@pytest.fixture
def worker():
    """A crew of 3 with profile and work-permit confirmation: can apply."""
    return make_worker()


@pytest.fixture
def worker_client(client, worker):
    """A browser logged in as the worker who can apply."""
    client.force_login(worker)
    return client


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


def apply_url(job):
    """Where the apply form posts to."""
    return reverse("job_apply", args=[job.pk])


# Sending the form (spec R5, D1; AC4, AC5)


def test_worker_applies_and_comes_back_to_the_job(worker_client, job, worker):
    """A valid form saves the application and goes back to the job with a message.

    1. Log in as a crew of 3 who can apply
    2. POST 2 workers and a message to the job's apply URL, following the redirect
    3. Expect: one pending application with the message and 2 workers
    4. Expect: redirected to the job's page, "Application sent." is shown
    """
    response = worker_client.post(
        apply_url(job), {"workers_offered": 2, "message": "We are two."}, follow=True
    )

    application = Application.objects.get()
    assert (application.job, application.worker) == (job, worker)
    assert application.workers_offered == 2
    assert application.message == "We are two."
    assert application.status == Application.Status.PENDING
    assertRedirects(response, detail_url(job))
    assertContains(response, "Application sent.")


def test_invalid_form_shows_the_job_page_again_with_the_error(worker_client, job):
    """Too many workers: nothing is saved, the same page comes back with the error (D1).

    1. Log in as a crew of 3; the job needs 2
    2. POST 3 workers to the job's apply URL
    3. Expect: no application; status 200 with the job page (no redirect)
    4. Expect: the form in the context has an error on workers_offered, the page shows the
       job and the form again
    """
    response = worker_client.post(apply_url(job), {"workers_offered": 3})

    assert not Application.objects.exists()
    assert response.status_code == 200
    assertTemplateUsed(response, "jobs/job_detail.html")
    assert "workers_offered" in response.context["apply_form"].errors
    assertContains(response, "Demolition")
    assertContains(response, MESSAGE_FIELD)


# What the view refuses (spec R5, D5, D6, D8; AC6, AC7, AC8)


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "cancelled"},
        {"date": timezone.localdate() - datetime.timedelta(days=1)},
    ],
    ids=["cancelled", "started"],
)
def test_job_that_takes_no_applications_refuses_the_post(
    worker_client, employer, fields
):
    """A cancelled job, or one that has started, takes no application (spec D8).

    1. Save a cancelled job next week, or an open job yesterday
    2. Log in as a worker who can apply and POST a valid form to its apply URL
    3. Expect: no application; back on the job page with
       "This job no longer takes applications."
    """
    job = make_job(employer, **fields)

    response = worker_client.post(apply_url(job), {"workers_offered": 1}, follow=True)

    assert not Application.objects.exists()
    assertRedirects(response, detail_url(job))
    assertContains(response, "This job no longer takes applications.")


@pytest.mark.parametrize(
    "who",
    [{"profile": False}, {"permit": False}],
    ids=["no profile", "no work permit"],
)
def test_worker_who_cannot_apply_is_refused(client, job, who):
    """Without a profile or the work-permit confirmation, no application (spec D6).

    1. Log in as a worker without a profile, or without the work-permit confirmation
    2. POST a valid form to the job's apply URL
    3. Expect: no application; back on the job page with "Complete your profile to apply."
    """
    client.force_login(make_worker(**who))

    response = client.post(apply_url(job), {"workers_offered": 1}, follow=True)

    assert not Application.objects.exists()
    assertRedirects(response, detail_url(job))
    assertContains(response, "Complete your profile to apply.")


def test_second_application_to_the_same_job_is_refused(worker_client, job):
    """Applying twice keeps one application and says so (spec D5).

    1. Log in as a worker who can apply and POST a valid form
    2. POST another valid form to the same job, following the redirect
    3. Expect: still one application, with the first message
    4. Expect: back on the job page with "You have already applied to this job."
    """
    worker_client.post(apply_url(job), {"workers_offered": 2, "message": "First"})

    response = worker_client.post(
        apply_url(job), {"workers_offered": 1, "message": "Second"}, follow=True
    )

    assert Application.objects.get().message == "First"
    assertRedirects(response, detail_url(job))
    assertContains(response, "You have already applied to this job.")


# The job page by state (spec R6, D6, D7; AC10)


def test_worker_who_can_apply_sees_the_form(worker_client, job):
    """The form is on the job page and scrolls to itself after an error (spec R4, D1).

    1. Log in as a crew of 3 who can apply; the job needs 2
    2. Open the job's page
    3. Expect: a form posting to the apply URL with #apply, an element with id "apply",
       the message field, "Workers I bring" with max 2, "Send application"
    """
    response = worker_client.get(detail_url(job))

    assertContains(response, f'action="{apply_url(job)}#apply"')
    assertContains(response, 'id="apply"')
    assertContains(response, MESSAGE_FIELD)
    assertContains(response, "Workers I bring")
    assertContains(response, 'max="2"')
    assertContains(response, "Send application")


@pytest.mark.parametrize(
    "who",
    [{"profile": False}, {"permit": False}],
    ids=["no profile", "no work permit"],
)
def test_worker_who_cannot_apply_sees_a_link_to_the_profile(client, job, who):
    """A worker who cannot apply sees why and where to fix it, not the form (spec D6).

    1. Log in as a worker without a profile, or without the work-permit confirmation
    2. Open the job's page
    3. Expect: "Complete your profile to apply" links to the worker profile form;
       no message field
    """
    client.force_login(make_worker(**who))

    response = client.get(detail_url(job))

    assertContains(response, "Complete your profile to apply")
    assertContains(response, f'href="{reverse("worker_profile_edit")}"')
    assertNotContains(response, MESSAGE_FIELD)


@pytest.mark.parametrize(
    ("status", "badge"), [("open", "Pending"), ("cancelled", "Job cancelled")]
)
def test_worker_who_applied_sees_the_application_not_the_form(
    worker_client, job, worker, status, badge
):
    """After applying the page shows what was sent, also when the job closed (spec D7).

    Since #26 (my-applications.md R10, D9) a pending application of a cancelled job says
    "Job cancelled".

    1. Save a pending application of the worker with 2 workers
    2. Leave the job open, or cancel it
    3. Open the job's page as the worker
    4. Expect: "You applied", "2 workers", "Pending" / "Job cancelled"; no message field
    """
    Application.objects.create(job=job, worker=worker, workers_offered=2)
    job.status = status
    job.save()

    response = worker_client.get(detail_url(job))

    assertContains(response, "You applied")
    assertContains(response, "2 workers")
    assertContains(response, badge)
    assertNotContains(response, MESSAGE_FIELD)


@pytest.mark.parametrize("who", ["guest", "owner"])
def test_guest_and_employer_see_no_form(client, job, employer, who):
    """Only workers get the form (spec R6).

    1. Open the job's page as a guest, or as the employer who posted it
    2. Expect: no message field, no "Send application"
    """
    if who == "owner":
        client.force_login(employer)

    response = client.get(detail_url(job))

    assertNotContains(response, MESSAGE_FIELD)
    assertNotContains(response, "Send application")
