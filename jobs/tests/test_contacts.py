"""Unit tests: when an application shows contacts; cancelling a job cancels its workers (#25).

Spec: docs/specs/contacts.md (R1, R2, D2-D4, D9), acceptance criteria AC1 and AC2. The job
page and the profile forms are in test_contacts_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobs.models import Application, Job, JobStateError

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(25)]

# A fixed "now": 3 November 2026, 10:00 in Munich, as in test_models.py.
MUNICH_NOW = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
TODAY = MUNICH_NOW.date()
DAY = datetime.timedelta(days=1)


@pytest.fixture
def frozen_now(monkeypatch):
    """Fix the clock at MUNICH_NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: MUNICH_NOW)
    return MUNICH_NOW


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def apply(job, email, **fields):
    """Save an application of one worker to `job`."""
    return Application.objects.create(job=job, worker=make_worker(email), **fields)


def accepted(job, email="a@example.com"):
    """Save an accepted application of one worker to `job`."""
    return apply(job, email, status="accepted", workers_accepted=1)


def refreshed(*objects):
    """Read every object again from the database: what the methods really saved."""
    for obj in objects:
        obj.refresh_from_db()


# When contacts are shown (R1, D2, D4; AC1)


@pytest.mark.parametrize("status", ["pending", "rejected", "closed", "cancelled"])
def test_only_an_accepted_application_shows_contacts(job, status):
    """Pending, rejected, closed and cancelled applications show no contacts (R1, D2).

    1. Save an application with this status to a job next week
    2. Expect: shows_contacts is False
    """
    application = apply(job, "a@example.com", status=status)

    assert application.shows_contacts is False


def test_accepted_application_of_a_coming_job_shows_contacts(job):
    """An accepted worker and the employer can reach each other before the job (R1).

    1. Save an accepted application to a job next week
    2. Expect: shows_contacts is True
    """
    assert accepted(job).shows_contacts is True


@pytest.mark.parametrize(
    ("date", "start_hour", "hours", "expected"),
    [
        (TODAY, 8, 6, True),  # started at 08:00, still the day of the job
        (TODAY - DAY, 8, 6, False),  # ended yesterday at 14:00
        (TODAY - DAY, 22, 8, True),  # a night shift that ended today at 06:00
        (TODAY - 2 * DAY, 22, 8, False),  # the night shift ended yesterday morning
    ],
    ids=[
        "today",
        "yesterday",
        "night shift ending today",
        "night shift ending yesterday",
    ],
)
def test_contacts_are_shown_until_the_day_the_job_ends_is_over(
    employer, frozen_now, date, start_hour, hours, expected
):
    """The day the job ends is the last day with contacts, Munich time (R1, D4).

    1. Fix the clock at 3 November 2026, 10:00 in Munich
    2. Save an accepted application to a job on that date, start and hours
    3. Expect: shows_contacts is True until the day the job ends is over, then False
    """
    job = make_job(
        employer, date=date, start_time=datetime.time(start_hour, 0), hours=hours
    )

    assert accepted(job).shows_contacts is expected


# Cancelling a job (R2, D3, D9; AC2)


def test_cancelling_a_job_cancels_its_accepted_workers(job):
    """The accepted workers of a cancelled job are cancelled; the others stay (D3, D9).

    1. On an open job, save an accepted, a pending, a closed and a rejected application
    2. Cancel the job
    3. Expect: the job is cancelled; the accepted application is cancelled and shows no
       contacts; the pending, closed and rejected ones are unchanged
    """
    worker = accepted(job, "a@example.com")
    pending = apply(job, "b@example.com")
    closed = apply(job, "c@example.com", status="closed")
    rejected = apply(job, "d@example.com", status="rejected")

    job.cancel()

    refreshed(job, worker, pending, closed, rejected)
    assert job.status == Job.Status.CANCELLED
    assert worker.status == Application.Status.CANCELLED
    assert worker.shows_contacts is False
    assert pending.status == Application.Status.PENDING
    assert closed.status == Application.Status.CLOSED
    assert rejected.status == Application.Status.REJECTED


def test_cancelling_a_job_does_not_touch_other_jobs(employer, job):
    """Only this job's workers are cancelled.

    1. Save an accepted application to the job and one to another job of the employer
    2. Cancel the first job
    3. Expect: the other job is open and its application still accepted
    """
    accepted(job, "a@example.com")
    other_job = make_job(employer)
    other = accepted(other_job, "b@example.com")

    job.cancel()

    refreshed(other_job, other)
    assert other_job.status == Job.Status.OPEN
    assert other.status == Application.Status.ACCEPTED


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_only_an_open_job_can_be_cancelled(job, status):
    """A filled, done or cancelled job is refused and nothing changes (R2).

    1. Save an accepted application, then set the job filled, done or cancelled
    2. Cancel the job
    3. Expect: JobStateError; the job and the application are unchanged
    """
    worker = accepted(job)
    Job.objects.filter(pk=job.pk).update(status=status)

    with pytest.raises(JobStateError):
        job.cancel()

    refreshed(job, worker)
    assert job.status == status
    assert worker.status == Application.Status.ACCEPTED


def test_cancel_reads_the_job_again_and_locks_it(job):
    """A second click with an old copy changes nothing; the job row is locked (R2).

    1. Load the same open job twice (two tabs)
    2. Cancel it through the first copy, recording the SQL; then through the second
    3. Expect: one SELECT … FOR UPDATE on the job; the second cancel raises JobStateError
    """
    first_tab = Job.objects.get(pk=job.pk)
    second_tab = Job.objects.get(pk=job.pk)

    with CaptureQueriesContext(connection) as queries:
        first_tab.cancel()
    with pytest.raises(JobStateError):
        second_tab.cancel()

    locks = [
        q["sql"]
        for q in queries
        if 'FROM "jobs_job"' in q["sql"] and "FOR UPDATE" in q["sql"]
    ]
    assert len(locks) == 1
