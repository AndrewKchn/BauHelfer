"""Integration tests: applying, accepting and rejecting send their emails (#27).

Each test goes through the whole stack: middleware, URL, view, model, notification,
template and database. Spec: docs/specs/notifications.md, iteration 1 (R1-R3, R7, D5, D6,
D10), acceptance criteria AC1-AC4, AC7, AC8. What each email says is in
test_notifications.py.
"""

import pytest
from django.urls import reverse
from django.utils import translation
from django.utils.formats import date_format
from pytest_django.asserts import assertContains

from jobs.models import Application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

FAILING_BACKEND = "jobs.tests.test_notifications.FailingBackend"


@pytest.fixture
def employer():
    """Anna, who posted the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open demolition job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


@pytest.fixture
def ivan():
    """Ivan, a worker with a crew of 3 who can apply."""
    return make_worker("ivan@example.com")


def apply(job, email, workers_offered=1, **fields):
    """Save an application to `job` from a new worker with this email."""
    return Application.objects.create(
        job=job, worker=make_worker(email), workers_offered=workers_offered, **fields
    )


def post_as(client, user, name, pk, data=None):
    """Log in as `user` and POST to the URL `name` with `pk`; follow the redirect."""
    client.force_login(user)
    return client.post(reverse(name, args=[pk]), data or {}, follow=True)


# Applying (R1, R2; AC1, AC3)


def test_applying_emails_the_employer(client, ivan, job, mailoutbox):
    """Sending the apply form emails the job's employer once.

    1. Log in as Ivan and send the apply form with 2 workers
    2. Expect: the application is saved
    3. Expect: one email, to Anna, with the subject "New application: …"
    """
    post_as(client, ivan, "job_apply", job.pk, {"workers_offered": 2})

    assert Application.objects.filter(worker=ivan).exists()
    [email] = mailoutbox
    assert email.to == ["anna@example.com"]
    assert email.subject.startswith("New application: ")


def test_apply_form_with_errors_sends_nothing(client, job, mailoutbox):
    """A form with errors saves nothing, so nobody is emailed.

    1. Log in as a crew of 3 and send the apply form with 4 workers to a job for 3
    2. Expect: no application, no email
    """
    post_as(
        client,
        make_worker("ivan@example.com"),
        "job_apply",
        job.pk,
        {"workers_offered": 4},
    )

    assert not Application.objects.exists()
    assert mailoutbox == []


def test_applying_twice_sends_one_email(client, ivan, job, mailoutbox):
    """The second apply is refused, so the employer gets one email, not two.

    1. Log in as Ivan and send the apply form twice
    2. Expect: one application and one email
    """
    post_as(client, ivan, "job_apply", job.pk, {"workers_offered": 1})
    post_as(client, ivan, "job_apply", job.pk, {"workers_offered": 1})

    assert Application.objects.count() == 1
    assert len(mailoutbox) == 1


# Accepting and rejecting (R1, R2; AC2, AC3)


@pytest.mark.parametrize(
    ("name", "subject"),
    [
        ("application_accept", "You are accepted: "),
        ("application_reject", "Application not accepted: "),
    ],
)
def test_deciding_emails_the_worker(client, employer, job, mailoutbox, name, subject):
    """Accept and Reject each email the worker once with their outcome.

    1. Save Ivan's pending application
    2. Log in as Anna and press Accept (or Reject)
    3. Expect: one email, to Ivan, whose subject starts with the outcome
    """
    application = apply(job, "ivan@example.com")

    post_as(client, employer, name, application.pk)

    [email] = mailoutbox
    assert email.to == ["ivan@example.com"]
    assert email.subject.startswith(subject)


def test_deciding_twice_sends_one_email(client, employer, job, mailoutbox):
    """A second click on an application already decided sends nothing more.

    1. Save Ivan's pending application
    2. As Anna, press Accept, then Reject on the same application
    3. Expect: the application stays accepted; one email, the accepted one
    """
    application = apply(job, "ivan@example.com")

    post_as(client, employer, "application_accept", application.pk)
    post_as(client, employer, "application_reject", application.pk)

    application.refresh_from_db()
    assert application.status == Application.Status.ACCEPTED
    [email] = mailoutbox
    assert email.subject.startswith("You are accepted: ")


# What sends nothing (D6; AC8)


def test_filling_the_job_emails_only_the_accepted_worker(
    client, employer, job, mailoutbox
):
    """Olga's application is closed when the job fills, but she gets no email (D6).

    1. On a job for 3, save an accepted crew of 2, a pending Ivan and a pending Olga
    2. As Anna, accept Ivan: the job is filled and Olga's application closed
    3. Expect: one email, to Ivan only
    """
    apply(job, "crew@example.com", 2, status="accepted", workers_accepted=2)
    ivan = apply(job, "ivan@example.com")
    olga = apply(job, "olga@example.com")

    post_as(client, employer, "application_accept", ivan.pk)

    olga.refresh_from_db()
    assert olga.status == Application.Status.CLOSED
    assert [email.to for email in mailoutbox] == [["ivan@example.com"]]


def test_cancelling_an_accepted_worker_sends_nothing(client, employer, job, mailoutbox):
    """Taking an accepted worker off the job sends no email (D6).

    1. Save Ivan's accepted application
    2. As Anna, cancel it
    3. Expect: it is cancelled; no email
    """
    application = apply(job, "ivan@example.com", status="accepted", workers_accepted=1)

    post_as(client, employer, "application_cancel", application.pk)

    application.refresh_from_db()
    assert application.status == Application.Status.CANCELLED
    assert mailoutbox == []


def test_withdrawing_sends_nothing(client, ivan, job, mailoutbox):
    """A worker withdrawing their application sends no email (D6).

    1. Save Ivan's pending application
    2. As Ivan, withdraw it
    3. Expect: it is withdrawn; no email
    """
    application = Application.objects.create(job=job, worker=ivan)

    post_as(client, ivan, "application_withdraw", application.pk)

    application.refresh_from_db()
    assert application.status == Application.Status.WITHDRAWN
    assert mailoutbox == []


# The recipient's language (R3, D8; AC4)


def test_worker_gets_the_decision_in_their_language(client, employer, job, mailoutbox):
    """Ivan reads Polish, so his email has the job's date in Polish.

    1. Save Ivan's pending application; set his language to Polish
    2. As Anna (English), press Accept
    3. Expect: the subject has the job's date as Django writes it in Polish
    """
    application = apply(job, "ivan@example.com")
    application.worker.preferred_language = "pl"
    application.worker.save()

    post_as(client, employer, "application_accept", application.pk)

    with translation.override("pl"):
        polish_date = date_format(job.date, "DATE_FORMAT")
    [email] = mailoutbox
    assert polish_date in email.subject


# A failed email (R7, D10; AC7)


def test_failed_email_still_saves_the_application(client, ivan, job, settings):
    """When the provider is down, the application is saved and the worker told so.

    1. Use an email backend that raises
    2. Log in as Ivan and send the apply form
    3. Expect: the application is saved; the page says "Application sent."
    """
    settings.EMAIL_BACKEND = FAILING_BACKEND

    response = post_as(client, ivan, "job_apply", job.pk, {"workers_offered": 1})

    assert Application.objects.filter(worker=ivan).exists()
    assertContains(response, "Application sent.")


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("application_accept", Application.Status.ACCEPTED),
        ("application_reject", Application.Status.REJECTED),
    ],
)
def test_failed_email_still_records_the_decision(
    client, employer, job, settings, name, status
):
    """When the provider is down, the decision is saved anyway.

    1. Use an email backend that raises; save Ivan's pending application
    2. As Anna, press Accept (or Reject)
    3. Expect: the application has the new status
    """
    settings.EMAIL_BACKEND = FAILING_BACKEND
    application = apply(job, "ivan@example.com")

    post_as(client, employer, name, application.pk)

    application.refresh_from_db()
    assert application.status == status
