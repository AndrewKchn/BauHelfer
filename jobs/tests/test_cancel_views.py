"""Integration tests: the employer cancels an accepted worker on the job page (#24).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/accept-reject.md, iteration 3 (R19-R21, D13, D16), acceptance criteria
AC18 and AC19. The model's rules are in test_cancel.py.
"""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(24)]


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
    """An open demolition job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def apply(job, email, name, workers_offered=1, **fields):
    """Save an application to `job` from a new crew of 3 called `name`."""
    worker = make_worker(email)
    worker.name = name
    worker.save()
    return Application.objects.create(
        job=job, worker=worker, workers_offered=workers_offered, **fields
    )


def accepted(job, email="ivan@example.com", name="Ivan Petrenko", taken=1):
    """Save an accepted application to `job` with `taken` workers taken."""
    return apply(job, email, name, taken, status="accepted", workers_accepted=taken)


def cancel_url(application):
    """The cancel URL of one application."""
    return reverse("application_cancel", args=[application.pk])


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


# Cancel (R19, R20; AC18)


def test_owner_cancels_a_worker_and_comes_back_to_them(employer_client, job):
    """Cancel marks the application cancelled and goes back to it with a message (R20).

    1. Save an accepted application of Ivan on an open job
    2. POST to its cancel URL as the job's employer
    3. Expect: the application is cancelled; a redirect to the job's page at
       #application-<id>
    4. Expect: the page says "Cancelled: Ivan Petrenko." and not "open again"
    """
    application = accepted(job)

    response = employer_client.post(cancel_url(application))

    application.refresh_from_db()
    assert application.status == Application.Status.CANCELLED
    assert response.url == f"{detail_url(job)}#application-{application.pk}"
    page = employer_client.get(detail_url(job))
    assertContains(page, "Cancelled: Ivan Petrenko.")
    assertNotContains(page, "The job is open again.")


def test_cancelling_from_a_filled_job_says_it_is_open_again(employer_client, job):
    """The employer is told the job takes applications again (spec R20).

    1. Save an accepted application of Ivan, set the job filled
    2. POST to its cancel URL as the job's employer
    3. Expect: the job is open; the page says "Cancelled: Ivan Petrenko. The job is open
       again."
    """
    application = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    employer_client.post(cancel_url(application))

    job.refresh_from_db()
    assert job.status == Job.Status.OPEN
    page = employer_client.get(detail_url(job))
    assertContains(page, "Cancelled: Ivan Petrenko. The job is open again.")


def test_guest_is_sent_to_login(client, job):
    """A guest's POST changes nothing and goes to the login page.

    1. Save an accepted application
    2. POST to its cancel URL without logging in
    3. Expect: a redirect to login; the application is still accepted
    """
    application = accepted(job)

    response = client.post(cancel_url(application))

    assert response.url.startswith(reverse("login"))
    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED


def test_worker_gets_403(client, job):
    """A worker, even the one accepted, cannot cancel.

    1. Save an accepted application of Ivan
    2. Log in as Ivan and POST to its cancel URL
    3. Expect: 403; the application is still accepted
    """
    application = accepted(job)
    client.force_login(application.worker)

    response = client.post(cancel_url(application))

    assert response.status_code == 403
    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED


def test_other_employer_gets_404(client, job):
    """Another employer cannot even tell that the application exists.

    1. Save an accepted application to Anna's job
    2. Log in as another employer and POST to its cancel URL
    3. Expect: 404; the application is still accepted
    """
    application = accepted(job)
    client.force_login(make_employer("bob@example.com"))

    response = client.post(cancel_url(application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED


@pytest.mark.parametrize("status", ["pending", "rejected", "closed", "cancelled"])
def test_application_that_is_not_accepted_gets_404(employer_client, job, status):
    """Only an accepted application can be cancelled (spec R19).

    1. Save a pending, rejected, closed or cancelled application
    2. POST to its cancel URL as the job's employer
    3. Expect: 404; the status is unchanged
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", status=status)

    response = employer_client.post(cancel_url(application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == status


@pytest.mark.parametrize("status", ["done", "cancelled"])
def test_done_or_cancelled_job_gets_404(employer_client, job, status):
    """A done or cancelled job is history (spec R19).

    1. Save an accepted application, set the job done or cancelled
    2. POST to its cancel URL as the job's employer
    3. Expect: 404; the application is still accepted
    """
    application = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=status)

    response = employer_client.post(cancel_url(application))

    assert response.status_code == 404
    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED


def test_unknown_application_gets_404(employer_client):
    """An id that does not exist gives 404.

    1. POST to the cancel URL of application 999999 as an employer
    2. Expect: 404
    """
    response = employer_client.post(reverse("application_cancel", args=[999999]))

    assert response.status_code == 404


def test_get_is_not_allowed(employer_client, job):
    """A link must not cancel: only POST.

    1. Save an accepted application
    2. GET its cancel URL as the job's employer
    3. Expect: 405; the application is still accepted
    """
    application = accepted(job)

    response = employer_client.get(cancel_url(application))

    assert response.status_code == 405
    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED


# The button and the badge (R20, R21, D13; AC19)


@pytest.mark.parametrize("status", ["open", "filled"])
def test_accepted_application_has_a_cancel_button(employer_client, job, status):
    """An accepted application of an open or filled job can be cancelled (spec R20).

    1. Save an accepted application, set the job open or filled
    2. Open the job's page as its employer
    3. Expect: a form posting to its cancel URL with a "Cancel" button (D26)
    """
    application = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=status)

    response = employer_client.get(detail_url(job))

    assertContains(response, f'action="{cancel_url(application)}"')
    assertContains(response, ">Cancel</button>")


def test_cancel_asks_the_browser_first(employer_client, job):
    """A tap by mistake is caught by the browser's own dialog (spec D16).

    1. Save an accepted application of Ivan O'Brien
    2. Open the job's page as its employer
    3. Expect: the cancel form has onsubmit="return confirm(…)" with "Cancel Ivan
       O'Brien? This cannot be undone.", the apostrophe escaped for JavaScript only
    """
    accepted(job, name="Ivan O'Brien")

    response = employer_client.get(detail_url(job))

    assertContains(
        response,
        "onsubmit=\"return confirm('Cancel Ivan O\\u0027Brien? "
        "This cannot be undone.')\"",
    )


@pytest.mark.parametrize("status", ["pending", "rejected", "closed", "cancelled"])
def test_application_that_is_not_accepted_has_no_cancel_button(
    employer_client, job, status
):
    """Cancel only on accepted applications (spec AC19).

    1. Save a pending, rejected, closed or cancelled application
    2. Open the job's page as its employer
    3. Expect: no form posting to its cancel URL
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", status=status)

    response = employer_client.get(detail_url(job))

    assertNotContains(response, cancel_url(application))


def test_cancelled_job_has_no_cancel_button(employer_client, job):
    """A cancelled job's workers are history (spec AC19).

    1. Save an accepted application, cancel the job
    2. Open the job's page as its employer
    3. Expect: no form posting to its cancel URL
    """
    application = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CANCELLED)

    response = employer_client.get(detail_url(job))

    assertNotContains(response, cancel_url(application))


def test_worker_sees_cancelled_on_their_application(client, job):
    """The cancelled worker sees "Cancelled", in its own colour (spec R21, D13).

    1. Save a cancelled application of Ivan
    2. Open the job's page as Ivan
    3. Expect: "Cancelled" in slate (badge-secondary), not red like "Rejected"
    """
    application = apply(job, "ivan@example.com", "Ivan Petrenko", status="cancelled")
    client.force_login(application.worker)

    response = client.get(detail_url(job))

    assertContains(response, 'badge-secondary">Cancelled</span>')


# Log lines (#124)


def jobs_records(caplog):
    """The records our jobs app wrote, without Django's own ones."""
    return [r.getMessage() for r in caplog.records if r.name.startswith("jobs")]


def test_cancelling_and_reopening_are_logged_with_ids_only(
    employer_client, employer, job, caplog
):
    """Cancel and the reopened job each write one INFO line with ids.

    1. Save an accepted application of Ivan, set the job filled
    2. Cancel it as the job's employer
    3. Expect: "Application cancelled: application_id=… job_id=… employer_id=…" and
       "Job reopened: job_id=… employer_id=…"; Ivan's email is in no line
    """
    application = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    with caplog.at_level("INFO"):
        employer_client.post(cancel_url(application))

    records = jobs_records(caplog)
    assert (
        f"Application cancelled: application_id={application.pk} job_id={job.pk} "
        f"employer_id={employer.pk}"
    ) in records
    assert f"Job reopened: job_id={job.pk} employer_id={employer.pk}" in records
    assert not any("ivan@example.com" in r for r in records)
