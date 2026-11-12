"""Unit tests: cancelling a filled job, and the cancellation email (#37).

Spec: docs/specs/job-done.md, iteration 2 (R10, R12-R14, D10-D13), acceptance criteria
AC8, AC10, AC12 and the email part of AC11. The views that cancel and send are in
test_job_cancel_filled_views.py. `mailoutbox` (pytest-django) is the list of emails
Django's in-memory backend "sent".
"""

import datetime

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation

from jobs import notifications
from jobs.models import Application, Job, JobStateError

from .test_application import make_worker
from .test_notifications import confirmed
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(37)]

# A fixed date, so the month name in the subject can be checked in each language.
MARCH_15 = datetime.date(2027, 3, 15)
MY_APPLICATIONS = f"http://testserver{reverse('my_applications')}"


@pytest.fixture
def request_():
    """A request as the views get it; links are built from its host, http://testserver."""
    return RequestFactory().get("/")


@pytest.fixture
def job():
    """A filled demolition job on 15 March 2027 at 08:00 for 2 workers."""
    employer = confirmed(make_employer("anna@example.com"))
    return make_job(employer, date=MARCH_15, workers_needed=2, status=Job.Status.FILLED)


def apply(job, email, status, taken=0):
    """Save an application of a new confirmed worker with this status."""
    return Application.objects.create(
        job=job,
        worker=confirmed(make_worker(email)),
        workers_offered=max(taken, 1),
        workers_accepted=taken,
        status=status,
    )


# Cancelling a filled job (R10, D10; AC8)


def test_filled_job_can_be_cancelled(job):
    """The job and its accepted workers are cancelled; the others stay (R10, D13).

    1. On a filled job: two accepted workers, a "Job filled" and a rejected application
    2. Cancel the job
    3. Expect: the job and both accepted applications "cancelled"; the closed and the
       rejected one unchanged; cancel() returns the two it cancelled
    """
    first = apply(job, "a@example.com", "accepted", taken=1)
    second = apply(job, "b@example.com", "accepted", taken=1)
    closed = apply(job, "c@example.com", "closed")
    rejected = apply(job, "d@example.com", "rejected")

    cancelled = job.cancel()

    for obj in (job, first, second, closed, rejected):
        obj.refresh_from_db()
    assert job.status == Job.Status.CANCELLED
    assert (first.status, second.status) == ("cancelled", "cancelled")
    assert (closed.status, rejected.status) == ("closed", "rejected")
    assert sorted(a.pk for a in cancelled) == sorted([first.pk, second.pk])


@pytest.mark.parametrize("status", [Job.Status.DONE, Job.Status.CANCELLED])
def test_done_or_cancelled_job_cannot_be_cancelled(job, status):
    """Only open and filled jobs (R10).

    1. Save an accepted application, then set the job done or cancelled
    2. Cancel the job
    3. Expect: JobStateError; the job and the application are unchanged
    """
    worker = apply(job, "a@example.com", "accepted", taken=1)
    Job.objects.filter(pk=job.pk).update(status=status)

    with pytest.raises(JobStateError):
        job.cancel()

    job.refresh_from_db()
    worker.refresh_from_db()
    assert job.status == status
    assert worker.status == Application.Status.ACCEPTED


# The worker's tab (R12, D13; AC10)


@pytest.mark.parametrize("status", ["pending", "closed"])
def test_waiting_application_of_a_cancelled_job_is_in_cancelled(job, status):
    """Nobody will answer it any more (D13).

    1. Save a pending / "Job filled" application; cancel the job
    2. Expect: its tab is "cancelled"; its own status is unchanged
    """
    application = apply(job, "c@example.com", status)
    job.cancel()

    application.refresh_from_db()
    assert application.tab == Application.Status.CANCELLED
    assert application.status == status


# The email (R13, R14, D11, D12; AC11, AC12)


def test_cancelled_job_email(request_, job, mailoutbox):
    """The job is cancelled: the worker is told so, with nothing to do (R14, D11).

    1. Cancel the job with Ivan accepted; call notify_cancelled for his application
    2. Expect: one email, to Ivan; subject "Cancelled: Demolition, March 15, 2027"
    3. Expect: the body says the employer cancelled the job, start at 8 a.m., that he
       has nothing to do, and links to "My applications"
    """
    ivan = apply(job, "ivan@example.com", "accepted", taken=1)
    job.cancel()
    ivan.refresh_from_db()

    notifications.notify_cancelled(request_, ivan)

    [email] = mailoutbox
    assert email.to == ["ivan@example.com"]
    assert email.subject == "Cancelled: Demolition, March 15, 2027"
    assert "The employer cancelled the job: Demolition, March 15, 2027" in email.body
    assert "8 a.m." in email.body
    assert "You have nothing to do." in email.body
    assert MY_APPLICATIONS in email.body


def test_cancelled_place_email(request_, job, mailoutbox):
    """Only Ivan's place is cancelled; the job goes on (R14, D12).

    1. Cancel Ivan's accepted application (the job opens again); call notify_cancelled
    2. Expect: the same subject; the body says the employer cancelled his place, not the
       job
    """
    ivan = apply(job, "ivan@example.com", "accepted", taken=1)
    ivan.cancel()

    notifications.notify_cancelled(request_, ivan)

    [email] = mailoutbox
    assert email.subject == "Cancelled: Demolition, March 15, 2027"
    assert "The employer cancelled your place: Demolition, March 15, 2027" in email.body
    assert "cancelled the job" not in email.body


def test_cancelled_email_is_in_the_workers_language(request_, job, mailoutbox):
    """A Polish worker gets Polish, though the employer clicked in German (R13).

    1. Set Ivan's language to Polish; cancel the job
    2. With German active, call notify_cancelled
    3. Expect: the subject has "15 marca 2027" and not "Cancelled"
    """
    ivan = apply(job, "ivan@example.com", "accepted", taken=1)
    ivan.worker.preferred_language = "pl"
    ivan.worker.save()
    job.cancel()

    with translation.override("de"):
        notifications.notify_cancelled(request_, ivan)

    [email] = mailoutbox
    assert "15 marca 2027" in email.subject
    assert "Cancelled" not in email.subject


def test_no_cancelled_email_when_the_worker_turned_them_off(request_, job, mailoutbox):
    """The checkbox of #27 counts for this email too (R13).

    1. Ivan turned the emails off; cancel the job; call notify_cancelled
    2. Expect: no email
    """
    ivan = apply(job, "ivan@example.com", "accepted", taken=1)
    ivan.worker.email_notifications = False
    ivan.worker.save()
    job.cancel()

    notifications.notify_cancelled(request_, ivan)

    assert mailoutbox == []
