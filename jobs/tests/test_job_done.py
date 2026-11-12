"""Unit tests: when a job can be marked done, and marking it done (#37).

Spec: docs/specs/job-done.md, iteration 1 (R1, R2, R7, D1, D2, D6), acceptance criteria AC1,
AC2 and the model part of AC6. The button, the view and the tabs are in
test_job_done_views.py.
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

pytestmark = [pytest.mark.django_db, pytest.mark.story(37)]

# A fixed "now": 3 November 2026, 10:00 in Munich, as in test_models.py.
MUNICH = ZoneInfo("Europe/Berlin")
MUNICH_NOW = datetime.datetime(2026, 11, 3, 10, 0, tzinfo=MUNICH)
TODAY = MUNICH_NOW.date()
DAY = datetime.timedelta(days=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at MUNICH_NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: MUNICH_NOW)
    return MUNICH_NOW


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def ended_job(employer, **fields):
    """A job today 07:59-09:59: over a minute ago; `fields` replace the defaults."""
    values = {"date": TODAY, "start_time": datetime.time(7, 59), "hours": 2, **fields}
    return make_job(employer, **values)


def accept(job, email="ivan@example.com", taken=1):
    """Save an accepted application to `job` with `taken` workers taken."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        workers_offered=taken,
        workers_accepted=taken,
        status=Application.Status.ACCEPTED,
    )


# When a job can be marked done (R1, D1, D2; AC1)


def test_filled_job_can_be_marked_done_after_the_work_ends(employer):
    """A minute after the end: yes (R1, D1).

    1. Save a filled job today 07:59-09:59 with an accepted worker; it is 10:00
    2. Expect: can_mark_done is True
    """
    job = ended_job(employer, status=Job.Status.FILLED)
    accept(job)

    assert job.can_mark_done is True


def test_job_cannot_be_marked_done_before_the_work_ends(employer):
    """A minute before the end: not yet; the work is still going on (D1).

    1. Save a filled job today 08:01-10:01 with an accepted worker; it is 10:00
    2. Expect: can_mark_done is False
    """
    job = ended_job(employer, start_time=datetime.time(8, 1), status=Job.Status.FILLED)
    accept(job)

    assert job.can_mark_done is False


def test_open_job_with_an_accepted_worker_can_be_marked_done(employer):
    """2 of 3 found and worked: the job happened (D2).

    1. Save an open job for 3 that ended, with one accepted worker
    2. Expect: can_mark_done is True
    """
    job = ended_job(employer, workers_needed=3)
    accept(job)

    assert job.can_mark_done is True


def test_open_job_without_accepted_workers_cannot_be_marked_done(employer):
    """Nobody worked, so there is nobody to rate (D2).

    1. Save an open job that ended, with a pending and a cancelled application
    2. Expect: can_mark_done is False
    """
    job = ended_job(employer)
    Application.objects.create(job=job, worker=make_worker("a@example.com"))
    Application.objects.create(
        job=job, worker=make_worker("b@example.com"), status="cancelled"
    )

    assert job.can_mark_done is False


@pytest.mark.parametrize("status", [Job.Status.DONE, Job.Status.CANCELLED])
def test_done_or_cancelled_job_cannot_be_marked_done(employer, status):
    """Only open and filled jobs (R1).

    1. Save a done / cancelled job that ended, with an accepted application
    2. Expect: can_mark_done is False
    """
    job = ended_job(employer, status=status)
    accept(job)

    assert job.can_mark_done is False


def test_night_shift_can_be_marked_done_only_after_its_morning_end(
    employer, monkeypatch
):
    """A job past midnight ends the next morning (R1, Job.ends_at).

    1. Save a filled job yesterday 23:00 for 10 hours: it ends today 09:00
    2. Set the clock to today 08:59, then 09:01
    3. Expect: can_mark_done False, then True
    """
    job = make_job(
        employer,
        date=TODAY - DAY,
        start_time=datetime.time(23, 0),
        hours=10,
        status=Job.Status.FILLED,
    )
    accept(job)

    monkeypatch.setattr(
        timezone, "now", lambda: datetime.datetime(2026, 11, 3, 8, 59, tzinfo=MUNICH)
    )
    assert job.can_mark_done is False
    monkeypatch.setattr(
        timezone, "now", lambda: datetime.datetime(2026, 11, 3, 9, 1, tzinfo=MUNICH)
    )
    assert job.can_mark_done is True


def test_can_mark_done_uses_the_annotation_without_a_query(employer):
    """With with_workers_found() the answer is the same and costs no query (R1, R5).

    1. Save an ended open job with one accepted worker and one without
    2. Load both with with_workers_found()
    3. Expect: True and False, as without the annotation; no query while asking
    """
    worked = ended_job(employer)
    accept(worked)
    empty = ended_job(employer)
    loaded = {job.pk: job for job in Job.objects.with_workers_found()}

    with CaptureQueriesContext(connection) as queries:
        answers = (loaded[worked.pk].can_mark_done, loaded[empty.pk].can_mark_done)

    assert answers == (True, False)
    assert len(queries) == 0


# Marking a job done (R2; AC2)


def test_mark_done_sets_done_and_leaves_the_applications(employer):
    """The job is done; the accepted worker stays accepted for #38 (R2).

    1. Save a filled job that ended, with an accepted and a closed application
    2. mark_done()
    3. Expect: the job is "done" in the database; the applications keep their statuses
    """
    job = ended_job(employer, status=Job.Status.FILLED)
    accepted = accept(job)
    closed = Application.objects.create(
        job=job, worker=make_worker("c@example.com"), status="closed"
    )

    job.mark_done()

    job.refresh_from_db()
    accepted.refresh_from_db()
    closed.refresh_from_db()
    assert job.status == Job.Status.DONE
    assert accepted.status == Application.Status.ACCEPTED
    assert closed.status == Application.Status.CLOSED


@pytest.mark.parametrize(
    ("fields", "with_worker"),
    [
        ({"start_time": datetime.time(8, 1), "status": "filled"}, True),  # not over
        ({}, False),  # open, nobody accepted
        ({"status": "done"}, True),
        ({"status": "cancelled"}, True),
    ],
    ids=["before-the-end", "nobody-accepted", "done", "cancelled"],
)
def test_mark_done_refuses_a_job_that_cannot_be_marked_done(
    employer, fields, with_worker
):
    """Every case of R1 that says no (R2).

    1. Save a job that cannot be marked done: before its end, open with nobody accepted,
       done, cancelled
    2. mark_done()
    3. Expect: JobStateError; the status in the database is unchanged
    """
    job = ended_job(employer, **fields)
    if with_worker:
        accept(job)
    before = job.status

    with pytest.raises(JobStateError):
        job.mark_done()

    job.refresh_from_db()
    assert job.status == before


def test_mark_done_reads_the_job_again(employer):
    """An old copy does not win: the locked row is read again (R2, as Job.cancel).

    1. Load a filled job that ended, with an accepted worker
    2. Cancel it in the database behind the copy's back (another tab)
    3. mark_done() on the old copy
    4. Expect: JobStateError; the job stays cancelled
    """
    job = ended_job(employer, status=Job.Status.FILLED)
    accept(job)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CANCELLED)

    with pytest.raises(JobStateError):
        job.mark_done()

    job.refresh_from_db()
    assert job.status == Job.Status.CANCELLED


# The worker's "Done" tab (R7, D6; AC6)


def test_accepted_application_of_a_done_job_is_in_the_done_tab(employer):
    """Done is the next step of an accepted application (D6).

    1. Save an accepted application of a done job, and a rejected one of the same job
    2. Expect: the accepted one's tab is "done"; the rejected one stays "rejected"
    """
    job = ended_job(employer, status=Job.Status.DONE)
    accepted = accept(job)
    rejected = Application.objects.create(
        job=job, worker=make_worker("r@example.com"), status="rejected"
    )

    assert accepted.tab == "done"
    assert rejected.tab == Application.Status.REJECTED
