"""Unit tests: the three notification emails, called directly with a made-up request (#27).

Spec: docs/specs/notifications.md, iteration 1 (R1-R7, D8-D10), acceptance criteria
AC4-AC7. The views that call these functions are in test_notifications_views.py.
`mailoutbox` (pytest-django) is the list of emails Django's in-memory backend "sent".
"""

import datetime

import pytest
from django.core.mail.backends.base import BaseEmailBackend
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation

from jobs.models import Application
from jobs.notifications import notify_decision, notify_new_application

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(27)]

# A fixed date, so the month name in the subject can be checked in each language.
MARCH_15 = datetime.date(2027, 3, 15)


@pytest.fixture
def request_():
    """A request as the views get it; links are built from its host, http://testserver."""
    return RequestFactory().get("/")


@pytest.fixture
def employer():
    """Anna, an employer with a phone; she posted the job."""
    return make_employer("anna@example.com", name="Anna Huber", phone="+49 89 1234567")


@pytest.fixture
def worker():
    """Ivan, a worker with a crew of 3 and a phone."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.phone = "+49 176 7654321"
    user.save()
    return user


@pytest.fixture
def application(employer, worker):
    """Ivan's pending application with 2 workers and a message with a phone number."""
    job = make_job(employer, date=MARCH_15, address="Lindwurmstraße 1")
    return Application.objects.create(
        job=job, worker=worker, workers_offered=2, message="Call me on 0176 1234567"
    )


def absolute(name, *args):
    """The full URL of a page, as a link in an email has it: http://testserver/…."""
    return f"http://testserver{reverse(name, args=args)}"


def decide(application, status):
    """Save `application` as accepted (with 2 workers) or rejected."""
    application.status = status
    if status == Application.Status.ACCEPTED:
        application.workers_accepted = 2
    application.save()
    return application


class FailingBackend(BaseEmailBackend):
    """An email backend that fails like a provider that is down, naming the address."""

    def send_messages(self, email_messages):
        raise ConnectionError("Brevo refused the email to ivan@example.com")


# What each email says and to whom (R2, R5, R6; AC5)


def test_new_application_email_goes_to_the_employer(request_, application, mailoutbox):
    """The employer gets one email about the new application, with a link to it.

    1. Call notify_new_application for Ivan's application with 2 workers
    2. Expect: one email, to Anna only
    3. Expect: subject "New application: Demolition, March 15, 2027"
    4. Expect: the body names Ivan and "2 workers" and links to the job page at the
       application, as an absolute URL
    """
    notify_new_application(request_, application)

    [email] = mailoutbox
    assert email.to == ["anna@example.com"]
    assert email.subject == "New application: Demolition, March 15, 2027"
    assert "Ivan Petrenko" in email.body
    assert "2 workers" in email.body
    job_page = absolute("job_detail", application.job_id)
    assert f"{job_page}#application-{application.pk}" in email.body


def test_accepted_email_goes_to_the_worker(request_, application, mailoutbox):
    """The worker gets one email saying they are accepted, with a link to their list.

    1. Accept Ivan's application with 2 workers and call notify_decision
    2. Expect: one email, to Ivan only
    3. Expect: subject "You are accepted: Demolition, March 15, 2027"
    4. Expect: the body says "2 workers" and links to "My applications" (absolute URL)
    """
    notify_decision(request_, decide(application, Application.Status.ACCEPTED))

    [email] = mailoutbox
    assert email.to == ["ivan@example.com"]
    assert email.subject == "You are accepted: Demolition, March 15, 2027"
    assert "2 workers" in email.body
    assert absolute("my_applications") in email.body


def test_rejected_email_goes_to_the_worker(request_, application, mailoutbox):
    """The worker gets one email saying they are not accepted, with a link to other jobs.

    1. Reject Ivan's application and call notify_decision
    2. Expect: one email, to Ivan only
    3. Expect: subject "Application not accepted: Demolition, March 15, 2027"
    4. Expect: the body links to the job list (absolute URL)
    """
    notify_decision(request_, decide(application, Application.Status.REJECTED))

    [email] = mailoutbox
    assert email.to == ["ivan@example.com"]
    assert email.subject == "Application not accepted: Demolition, March 15, 2027"
    assert absolute("home") in email.body


@pytest.mark.parametrize(
    "status", [Application.Status.ACCEPTED, Application.Status.REJECTED]
)
def test_decision_emails_hold_no_contact_data(
    request_, application, mailoutbox, status
):
    """The worker's email has no contact data: that stays on the site (D9).

    1. Accept, or reject, Ivan's application and call notify_decision
    2. Expect: neither Anna's phone, email nor the job's address is in the email
    """
    notify_decision(request_, decide(application, status))

    [email] = mailoutbox
    text = email.subject + email.body
    for private in ("+49 89 1234567", "anna@example.com", "Lindwurmstraße"):
        assert private not in text


def test_new_application_email_holds_no_contact_data(request_, application, mailoutbox):
    """The employer's email has Ivan's name, but no phone, email or message (D9).

    1. Call notify_new_application for Ivan's application with a message
    2. Expect: neither Ivan's phone, his email, nor the message text is in the email
    """
    notify_new_application(request_, application)

    [email] = mailoutbox
    text = email.subject + email.body
    for private in ("+49 176 7654321", "ivan@example.com", "0176 1234567"):
        assert private not in text


def test_subjects_are_one_line(request_, application, mailoutbox):
    """Every subject is one line: Django refuses a header with a line break (R4; AC6).

    1. Send the new application email, then the accepted one
    2. Expect: no subject has a line break
    """
    notify_new_application(request_, application)
    notify_decision(request_, decide(application, Application.Status.ACCEPTED))

    assert len(mailoutbox) == 2
    assert not any("\n" in email.subject for email in mailoutbox)


def test_emails_greet_the_recipient_by_name(request_, application, mailoutbox):
    """Each email starts with "Hello <recipient's name>," (R5).

    1. Send the new application email (to Anna), then the accepted one (to Ivan)
    2. Expect: Anna's starts "Hello Anna Huber,", Ivan's "Hello Ivan Petrenko,"
    """
    notify_new_application(request_, application)
    notify_decision(request_, decide(application, Application.Status.ACCEPTED))

    to_anna, to_ivan = mailoutbox
    assert to_anna.body.startswith("Hello Anna Huber,\n")
    assert to_ivan.body.startswith("Hello Ivan Petrenko,\n")


def test_email_without_a_name_says_hello(request_, application, mailoutbox):
    """A recipient without a name (e.g. made in Django admin) gets a plain "Hello,".

    1. Empty Ivan's name; reject his application and call notify_decision
    2. Expect: the body starts "Hello,"
    """
    application.worker.name = ""
    application.worker.save()

    notify_decision(request_, decide(application, Application.Status.REJECTED))

    [email] = mailoutbox
    assert email.body.startswith("Hello,\n")


def test_names_are_not_html_escaped(request_, application, mailoutbox):
    """A plain-text email shows O'Brien, not O&#x27;Brien as an HTML page would (D7).

    1. Name Ivan "Seán O'Brien"; send the new application email, then the rejected one
    2. Expect: both bodies have "Seán O'Brien" as typed
    """
    application.worker.name = "Seán O'Brien"
    application.worker.save()

    notify_new_application(request_, application)
    notify_decision(request_, decide(application, Application.Status.REJECTED))

    assert all("Seán O'Brien" in email.body for email in mailoutbox)


# The recipient's language (R3, D8; AC4)


def test_email_is_in_the_recipients_language_not_the_clickers(
    request_, application, mailoutbox
):
    """A Polish worker gets Polish, even when the employer clicked in German.

    Our own strings are translated only in M5; Django's month names already are, so the
    date shows the language: "15 marca 2027" in Polish, "15. März 2027" in German.

    1. Set Ivan's language to Polish; accept his application
    2. With German active (the employer's request), call notify_decision
    3. Expect: the subject has "15 marca 2027" and not "März"
    4. Expect: German is still active afterwards
    """
    application.worker.preferred_language = "pl"
    application.worker.save()
    decide(application, Application.Status.ACCEPTED)

    with translation.override("de"):
        notify_decision(request_, application)
        language_after = translation.get_language()

    [email] = mailoutbox
    assert "15 marca 2027" in email.subject
    assert "März" not in email.subject
    assert language_after == "de"


def test_employer_email_is_in_the_employers_language(request_, application, mailoutbox):
    """The employer's email is in the employer's language, not the worker's.

    1. Set Anna's language to German; call notify_new_application with Polish active
    2. Expect: the subject has "15. März 2027"
    """
    application.job.employer.preferred_language = "de"
    application.job.employer.save()

    with translation.override("pl"):
        notify_new_application(request_, application)

    [email] = mailoutbox
    assert "15. März 2027" in email.subject


# Log lines and a failed email (R7, D10; AC7)


def jobs_records(caplog):
    """The (level, message) of the records our jobs app wrote."""
    return [
        (r.levelname, r.getMessage())
        for r in caplog.records
        if r.name.startswith("jobs")
    ]


def test_sent_email_is_logged_with_ids_only(request_, application, mailoutbox, caplog):
    """A sent email writes one INFO line with its kind and the application id.

    1. Call notify_new_application, then accept and call notify_decision
    2. Expect: "Notification sent: kind=new_application application_id=<id>" and
       "Notification sent: kind=application_accepted application_id=<id>"
    3. Expect: no email address in any line
    """
    with caplog.at_level("INFO"):
        notify_new_application(request_, application)
        notify_decision(request_, decide(application, Application.Status.ACCEPTED))

    pk = application.pk
    assert jobs_records(caplog) == [
        ("INFO", f"Notification sent: kind=new_application application_id={pk}"),
        ("INFO", f"Notification sent: kind=application_accepted application_id={pk}"),
    ]
    assert "@example.com" not in caplog.text


def test_failed_email_is_logged_and_not_raised(request_, application, settings, caplog):
    """When the provider fails, the error is logged with ids and the class only (D10).

    1. Use an email backend that raises ConnectionError naming Ivan's address
    2. Reject the application and call notify_decision
    3. Expect: no exception
    4. Expect: one ERROR line "Notification failed: kind=application_rejected
       application_id=<id> error=ConnectionError"
    5. Expect: Ivan's address from the error text is in no line
    """
    settings.EMAIL_BACKEND = "jobs.tests.test_notifications.FailingBackend"

    notify_decision(request_, decide(application, Application.Status.REJECTED))

    message = (
        "Notification failed: kind=application_rejected "
        f"application_id={application.pk} error=ConnectionError"
    )
    assert jobs_records(caplog) == [("ERROR", message)]
    assert "ivan@example.com" not in caplog.text
