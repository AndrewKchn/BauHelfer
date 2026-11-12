"""Integration tests: the employer cancels a filled job; workers get an email (#37).

Each test goes through the whole stack: middleware, URL, view, model, notification,
template and database. Spec: docs/specs/job-done.md, iteration 2 (R10, R11, R13, D10,
D12), acceptance criteria AC9 and AC11. What the email says is in test_job_cancel_filled.py.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job

from .test_application import make_worker
from .test_notifications import confirmed
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(37)]

FAILING_BACKEND = "jobs.tests.test_notifications.FailingBackend"
DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna, who posted the job."""
    return confirmed(make_employer("anna@example.com"))


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as Anna."""
    client.force_login(employer)
    return client


@pytest.fixture
def job(employer):
    """A filled job next week for 2 workers."""
    return make_job(employer, workers_needed=2, status=Job.Status.FILLED)


def accept(job, email, language="en"):
    """Save an accepted application of one new confirmed worker in `language`."""
    worker = confirmed(make_worker(email))
    worker.preferred_language = language
    worker.save()
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status="accepted"
    )


def cancel_url(job):
    """The job's cancel page: GET asks, POST cancels."""
    return reverse("job_cancel", args=[job.pk])


# Cancelling a filled job (R10, R11, D10; AC9)


def test_owner_cancels_a_filled_job(employer_client, job):
    """The cancel page asks; POST cancels the job and its workers (R10, R11).

    1. Save a filled job with an accepted worker
    2. GET its cancel page, then POST to it as Anna
    3. Expect: 200, then a redirect to "My jobs"; the job and the application cancelled
    """
    application = accept(job, "ivan@example.com")

    page = employer_client.get(cancel_url(job))
    response = employer_client.post(cancel_url(job))

    job.refresh_from_db()
    application.refresh_from_db()
    assert page.status_code == 200
    assert response.url == reverse("my_jobs")
    assert job.status == Job.Status.CANCELLED
    assert application.status == Application.Status.CANCELLED


def test_filled_card_has_cancel_but_not_edit(employer_client, job):
    """A filled job can be cancelled, not edited: its workers were taken for it (R11).

    1. Save a filled job next week
    2. Open "My jobs"
    3. Expect: its cancel link; no edit link
    """
    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'href="{cancel_url(job)}"')
    assertNotContains(response, reverse("job_edit", args=[job.pk]))


def test_filled_job_that_is_over_cannot_be_cancelled(employer_client, employer):
    """Over is over (D9): no link, and the page gives 404.

    1. Save a filled job that ended yesterday
    2. Open "My jobs" and its cancel page
    3. Expect: no cancel link; 404
    """
    job = make_job(employer, date=timezone.localdate() - DAY, status=Job.Status.FILLED)

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, cancel_url(job))
    assert employer_client.get(cancel_url(job)).status_code == 404


# The emails (R13, D10, D12; AC11)


def test_cancelling_a_job_emails_each_accepted_worker(employer_client, job, mailoutbox):
    """One email per worker who loses their place, each in their language (R13).

    1. Accept Ivan (English) and Olga (Polish); a "Job filled" application of Petr
    2. As Anna, cancel the job
    3. Expect: two emails, to Ivan and Olga; Olga's subject in Polish; none to Petr
    """
    accept(job, "ivan@example.com")
    accept(job, "olga@example.com", language="pl")
    Application.objects.create(
        job=job, worker=confirmed(make_worker("petr@example.com")), status="closed"
    )

    employer_client.post(cancel_url(job))

    emails = {email.to[0]: email for email in mailoutbox}
    assert sorted(emails) == ["ivan@example.com", "olga@example.com"]
    assert emails["ivan@example.com"].subject.startswith("Cancelled: ")
    assert not emails["olga@example.com"].subject.startswith("Cancelled: ")


def test_cancelling_one_worker_emails_that_worker(employer_client, job, mailoutbox):
    """Taking one worker off sends them the email too (D12; changes notifications D6).

    1. Accept Ivan and Olga
    2. As Anna, cancel Ivan's application
    3. Expect: one email, to Ivan, saying his place was cancelled
    """
    ivan = accept(job, "ivan@example.com")
    accept(job, "olga@example.com")

    employer_client.post(reverse("application_cancel", args=[ivan.pk]))

    [email] = mailoutbox
    assert email.to == ["ivan@example.com"]
    assert "cancelled your place" in email.body


def test_worker_who_turned_them_off_gets_no_email(employer_client, job, mailoutbox):
    """The checkbox of #27 counts (R13).

    1. Accept Ivan with emails off, and Olga
    2. As Anna, cancel the job
    3. Expect: one email, to Olga
    """
    ivan = accept(job, "ivan@example.com")
    ivan.worker.email_notifications = False
    ivan.worker.save()
    accept(job, "olga@example.com")

    employer_client.post(cancel_url(job))

    assert [email.to for email in mailoutbox] == [["olga@example.com"]]


@pytest.mark.parametrize("what", ["job", "place"])
def test_failed_email_still_cancels(employer_client, job, settings, caplog, what):
    """A provider that is down never undoes the cancel (R13).

    1. Use an email backend that raises; accept Ivan
    2. As Anna, cancel the job / Ivan's place
    3. Expect: the application is cancelled; an ERROR line "Notification failed:
       kind=application_cancelled …"
    """
    settings.EMAIL_BACKEND = FAILING_BACKEND
    ivan = accept(job, "ivan@example.com")
    url = (
        cancel_url(job)
        if what == "job"
        else reverse("application_cancel", args=[ivan.pk])
    )

    employer_client.post(url)

    ivan.refresh_from_db()
    assert ivan.status == Application.Status.CANCELLED
    assert "Notification failed: kind=application_cancelled" in caplog.text
