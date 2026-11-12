"""Integration tests: marking a job done emails each accepted worker to rate (#38).

Each test goes through the whole stack: middleware, URL, view, model, notification,
template and database. Spec: docs/specs/reviews.md, iteration 2 (R13, D5, D14),
acceptance criterion AC11.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_notifications import confirmed
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

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
    """A filled job for 2 that ended yesterday."""
    return make_job(
        employer,
        date=timezone.localdate() - DAY,
        workers_needed=2,
        status=Job.Status.FILLED,
    )


def accept(job, email, language="en"):
    """Save an accepted application of one new confirmed worker in `language`."""
    worker = confirmed(make_worker(email))
    worker.preferred_language = language
    worker.save()
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status="accepted"
    )


def mark_done(client, job):
    """POST the "Mark as done" button of `job`."""
    return client.post(reverse("job_done", args=[job.pk]))


def test_done_emails_each_accepted_worker(employer_client, job, mailoutbox):
    """One email per accepted worker, each in their language (R13, D5).

    1. Accept Ivan (English) and Olga (Polish); a third worker is only pending
    2. As Anna, mark the job done
    3. Expect: two emails, to Ivan and Olga; Ivan's subject "Rate the employer: …",
       Olga's not in English; none to the pending worker
    """
    accept(job, "ivan@example.com")
    accept(job, "olga@example.com", language="pl")
    Application.objects.create(job=job, worker=confirmed(make_worker("p@example.com")))

    mark_done(employer_client, job)

    emails = {email.to[0]: email for email in mailoutbox}
    assert sorted(emails) == ["ivan@example.com", "olga@example.com"]
    assert emails["ivan@example.com"].subject.startswith("Rate the employer: ")
    assert not emails["olga@example.com"].subject.startswith("Rate the employer: ")


def test_email_links_to_the_review_page(employer_client, job, mailoutbox):
    """The body names the deadline and links to the worker's own review page (R13).

    1. Accept Ivan
    2. As Anna, mark the job done
    3. Expect: the body has the full address of Ivan's review page and the deadline date,
       14 days from today
    """
    ivan = accept(job, "ivan@example.com")

    mark_done(employer_client, job)

    [email] = mailoutbox
    review = reverse("review_create", args=[ivan.pk])
    assert f"http://testserver{review}" in email.body
    # As the email writes it: the deadline in the date format of English.
    deadline = date_format(timezone.localdate() + 14 * DAY, "DATE_FORMAT")
    assert deadline in email.body


def test_worker_who_turned_them_off_gets_no_email(employer_client, job, mailoutbox):
    """The checkbox of #27 works for this email too (R13).

    1. Accept Ivan with emails off, and Olga
    2. As Anna, mark the job done
    3. Expect: one email, to Olga
    """
    ivan = accept(job, "ivan@example.com")
    ivan.worker.email_notifications = False
    ivan.worker.save()
    accept(job, "olga@example.com")

    mark_done(employer_client, job)

    assert [email.to for email in mailoutbox] == [["olga@example.com"]]


def test_failed_email_still_marks_done(employer_client, job, settings, caplog):
    """A provider that is down never undoes "done" (R13, D14).

    1. Use an email backend that raises; accept Ivan
    2. As Anna, mark the job done
    3. Expect: the job is done; an ERROR line "Notification failed: kind=review_request …"
    """
    settings.EMAIL_BACKEND = FAILING_BACKEND
    accept(job, "ivan@example.com")

    mark_done(employer_client, job)

    job.refresh_from_db()
    assert job.status == Job.Status.DONE
    assert "Notification failed: kind=review_request" in caplog.text
