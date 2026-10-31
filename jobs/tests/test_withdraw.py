"""Unit tests: the worker withdraws their own application; a filled job opens again (#26).

Spec: docs/specs/my-applications.md, iteration 2 (R14-R17, D4, D5, D17, D18), acceptance
criteria AC13 and AC14. The button, the view and the pages are in test_withdraw_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobs.models import Application, ApplicationStateError, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(26)]

# A fixed "now": 3 November 2026, 10:00 in Munich, as in test_my_applications.py.
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
def job(employer, frozen_now):
    """An open job for 3 workers in a week, with the clock fixed."""
    return make_job(employer, date=TODAY + 7 * DAY, workers_needed=3)


def apply(job, email, status="pending", taken=0):
    """Save an application of a new worker to `job` with `taken` workers taken."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        status=status,
        workers_offered=max(taken, 1),
        workers_accepted=taken,
    )


def refreshed(*objects):
    """Read every object again from the database: what the methods really saved."""
    for obj in objects:
        obj.refresh_from_db()


# When a job has started (#26, docs/specs/my-applications.md R15)


@pytest.mark.parametrize(
    ("date", "start_hour", "expected"),
    [
        (TODAY + DAY, 8, False),
        (TODAY, 11, False),  # starts at 11:00, now is 10:00
        (TODAY, 10, True),  # starts right now
        (TODAY, 8, True),
        (TODAY - DAY, 8, True),
    ],
    ids=["tomorrow", "later today", "now", "earlier today", "yesterday"],
)
def test_a_job_has_started_from_its_start_time(
    employer, frozen_now, date, start_hour, expected
):
    """A job has started from its date and start time on, Munich time (R15).

    1. Fix the clock at 3 November 2026, 10:00 in Munich
    2. Save a job on that date and start time
    3. Expect: has_started is True from the start time on; accepts_applications is its
       opposite for an open job
    """
    job = make_job(employer, date=date, start_time=datetime.time(start_hour, 0))

    assert job.has_started is expected
    assert job.accepts_applications is not expected


# Who can withdraw (R16, D5, D17; AC13)


@pytest.mark.parametrize(
    ("status", "job_status"),
    [
        ("pending", "open"),
        ("accepted", "open"),
        ("accepted", "filled"),
        ("closed", "filled"),
    ],
)
def test_application_still_in_play_can_be_withdrawn(job, status, job_status):
    """Pending, "Job filled" and accepted applications of an open or filled job (D5).

    1. Save an application in this status; set the job open or filled
    2. Expect: can_withdraw is True
    """
    application = apply(job, "a@example.com", status)
    Job.objects.filter(pk=job.pk).update(status=job_status)
    application.job.refresh_from_db()

    assert application.can_withdraw is True


@pytest.mark.parametrize("status", ["rejected", "cancelled", "withdrawn"])
def test_closed_application_cannot_be_withdrawn(job, status):
    """Rejected, cancelled and withdrawn applications are over (D5).

    1. Save an application in this status to an open job
    2. Expect: can_withdraw is False
    """
    assert apply(job, "a@example.com", status).can_withdraw is False


@pytest.mark.parametrize("job_status", ["done", "cancelled"])
def test_application_of_a_done_or_cancelled_job_cannot_be_withdrawn(job, job_status):
    """There is nothing to leave when the job is done or cancelled (R16).

    1. Save a pending application; set the job done / cancelled
    2. Expect: can_withdraw is False
    """
    application = apply(job, "a@example.com")
    Job.objects.filter(pk=job.pk).update(status=job_status)
    application.job.refresh_from_db()

    assert application.can_withdraw is False


def test_application_cannot_be_withdrawn_after_the_start(employer, frozen_now):
    """Once the work has started, leaving is not withdrawing (D17).

    1. Fix the clock at 10:00; save an accepted application to a job that started at 08:00
    2. Expect: can_withdraw is False
    """
    job = make_job(employer, date=TODAY, start_time=datetime.time(8, 0))

    assert apply(job, "a@example.com", "accepted", 1).can_withdraw is False


# Withdrawing (R14, R17, D4, D18; AC14)


def test_withdrawing_a_pending_application(job):
    """It becomes "Withdrawn"; the job does not change (R14, R17).

    1. Save a pending application to an open job
    2. Withdraw it
    3. Expect: it is "withdrawn", shown as "Withdrawn"; withdraw() returns False; the job
       is still open
    """
    application = apply(job, "a@example.com")

    assert application.withdraw() is False

    refreshed(application, job)
    assert application.status == Application.Status.WITHDRAWN
    assert application.get_status_display() == "Withdrawn"
    assert job.status == Job.Status.OPEN


def test_withdrawing_a_job_filled_application_keeps_the_job_filled(job):
    """A "Job filled" application took no place: the job stays filled (R17).

    1. On a filled job, save an accepted crew of 3 and a closed application
    2. Withdraw the closed one
    3. Expect: it is "withdrawn"; the job is still filled; the crew still accepted
    """
    crew = apply(job, "a@example.com", "accepted", 3)
    closed = apply(job, "b@example.com", "closed")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    assert closed.withdraw() is False

    refreshed(closed, crew, job)
    assert closed.status == Application.Status.WITHDRAWN
    assert job.status == Job.Status.FILLED
    assert crew.status == Application.Status.ACCEPTED


def test_withdrawing_an_accepted_worker_frees_the_places(job):
    """An accepted worker who leaves no longer counts (R17, D18).

    1. On an open job for 3, save accepted crews of 2 and 1 (the job stays open)
    2. Withdraw the crew of 2
    3. Expect: it is "withdrawn"; workers found are 1; the job is still open
    """
    crew = apply(job, "a@example.com", "accepted", 2)
    apply(job, "b@example.com", "accepted", 1)

    assert crew.withdraw() is False

    refreshed(crew, job)
    assert crew.status == Application.Status.WITHDRAWN
    assert job.workers_found() == 1
    assert job.status == Job.Status.OPEN


def test_withdrawing_from_a_filled_job_opens_it_and_brings_back_the_closed(job):
    """As the employer's "Cancel": the job opens, closed ones are pending again (D18).

    1. On a job for 3, save accepted crews of 2 and 1, a closed and a rejected
       application, and set the job filled
    2. Withdraw the single worker
    3. Expect: withdraw() returns True; the job is open; the closed one is pending; the
       rejected one is still rejected; the crew of 2 is still accepted
    """
    crew = apply(job, "a@example.com", "accepted", 2)
    single = apply(job, "b@example.com", "accepted", 1)
    closed = apply(job, "c@example.com", "closed")
    rejected = apply(job, "d@example.com", "rejected")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    assert single.withdraw() is True

    refreshed(job, crew, single, closed, rejected)
    assert job.status == Job.Status.OPEN
    assert single.status == Application.Status.WITHDRAWN
    assert closed.status == Application.Status.PENDING
    assert rejected.status == Application.Status.REJECTED
    assert crew.status == Application.Status.ACCEPTED


@pytest.mark.parametrize("status", ["rejected", "cancelled", "withdrawn"])
def test_withdrawing_a_closed_application_is_refused(job, status):
    """Only what can_withdraw allows; nothing changes otherwise (R17).

    1. Save an application in this status
    2. Withdraw it
    3. Expect: ApplicationStateError; the status is unchanged
    """
    application = apply(job, "a@example.com", status)

    with pytest.raises(ApplicationStateError):
        application.withdraw()

    refreshed(application)
    assert application.status == status


def test_withdrawing_after_the_start_is_refused(employer, frozen_now):
    """After the start the worker cannot withdraw any more (D17).

    1. Fix the clock at 10:00; save an accepted application to a job that started at 08:00
    2. Withdraw it
    3. Expect: ApplicationStateError; it is still accepted
    """
    job = make_job(employer, date=TODAY, start_time=datetime.time(8, 0))
    application = apply(job, "a@example.com", "accepted", 1)

    with pytest.raises(ApplicationStateError):
        application.withdraw()

    refreshed(application)
    assert application.status == Application.Status.ACCEPTED


def test_withdraw_reads_the_state_again_and_locks_the_job(job):
    """A second tap with an old copy changes nothing; the job row is locked (R17).

    1. Load the same pending application twice (two tabs)
    2. Withdraw it through the first copy, recording the SQL; then through the second
    3. Expect: one SELECT … FOR UPDATE on the job; the second withdraw raises
       ApplicationStateError
    """
    application = apply(job, "a@example.com")
    first_tab = Application.objects.get(pk=application.pk)
    second_tab = Application.objects.get(pk=application.pk)

    with CaptureQueriesContext(connection) as queries:
        first_tab.withdraw()
    with pytest.raises(ApplicationStateError):
        second_tab.withdraw()

    locks = [
        q["sql"]
        for q in queries
        if 'FROM "jobs_job"' in q["sql"] and "FOR UPDATE" in q["sql"]
    ]
    assert len(locks) == 1


def test_application_that_was_accepted_meanwhile_is_withdrawn_as_accepted(job):
    """The employer accepted in another tab: withdrawing frees the place it took (D18).

    1. Load a pending application, then accept it through another copy so it fills the
       job (a job for 1)
    2. Withdraw it through the old copy
    3. Expect: it is "withdrawn"; the job is open again
    """
    Job.objects.filter(pk=job.pk).update(workers_needed=1)
    old_copy = apply(job, "a@example.com")
    Application.objects.get(pk=old_copy.pk).accept()

    assert old_copy.withdraw() is True

    refreshed(old_copy, job)
    assert old_copy.status == Application.Status.WITHDRAWN
    assert job.status == Job.Status.OPEN
