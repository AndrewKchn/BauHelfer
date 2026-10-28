"""Unit tests: removing an accepted worker; a filled job opens again (#24).

Spec: docs/specs/accept-reject.md, iteration 3 (R17, R18, D13-D15), acceptance criteria
AC15-AC17. The button, the view and the job page are in test_remove_views.py.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from jobs.models import Application, ApplicationStateError, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(24)]


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 3 workers."""
    return make_job(employer, workers_needed=3)


def apply(job, email, workers_offered=1, **fields):
    """Save an application to `job` from a new crew of 3 bringing `workers_offered`."""
    return Application.objects.create(
        job=job, worker=make_worker(email), workers_offered=workers_offered, **fields
    )


def accepted(job, email, taken):
    """Save an accepted application to `job` with `taken` workers taken."""
    return apply(job, email, taken, status="accepted", workers_accepted=taken)


def refreshed(*objects):
    """Read every object again from the database: what the methods really saved."""
    for obj in objects:
        obj.refresh_from_db()


def test_removing_cancels_the_application_and_frees_its_places(job):
    """A removed worker no longer counts (spec R18, D13; AC15).

    1. On a job for 3, save accepted crews of 2 and 1 (the job stays open)
    2. Remove the crew of 2
    3. Expect: it is "cancelled", shown as "Cancelled"; workers found are 1, both by
       workers_found() and by with_workers_found(); the job is still open
    """
    crew = accepted(job, "a@example.com", 2)
    accepted(job, "b@example.com", 1)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.OPEN)

    crew.remove()

    refreshed(crew, job)
    assert crew.status == Application.Status.CANCELLED
    assert crew.get_status_display() == "Cancelled"
    assert job.workers_found() == 1
    assert Job.objects.with_workers_found().get(pk=job.pk).accepted_workers == 1
    assert job.status == Job.Status.OPEN


def test_removing_from_a_filled_job_opens_it_and_brings_back_the_closed(job):
    """The job opens again; the closed applications are pending again (D14, D15; AC16).

    1. On a job for 3, save accepted crews of 2 and 1, a closed and a rejected
       application, and set the job filled
    2. Remove the single worker
    3. Expect: the job is open; the closed one is pending; the rejected one is still
       rejected; the crew of 2 is still accepted
    """
    crew = accepted(job, "a@example.com", 2)
    single = accepted(job, "b@example.com", 1)
    closed = apply(job, "c@example.com", status="closed")
    rejected = apply(job, "d@example.com", status="rejected")
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)

    single.remove()

    refreshed(job, crew, closed, rejected)
    assert job.status == Job.Status.OPEN
    assert closed.status == Application.Status.PENDING
    assert rejected.status == Application.Status.REJECTED
    assert crew.status == Application.Status.ACCEPTED


def test_removing_does_not_touch_other_jobs(employer, job):
    """Only this job's closed applications come back.

    1. Fill two jobs, each with a closed application
    2. Remove an accepted worker of the first job
    3. Expect: the second job is still filled and its closed application still closed
    """
    worker = accepted(job, "a@example.com", 1)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.FILLED)
    other = make_job(employer, status=Job.Status.FILLED)
    other_closed = apply(other, "b@example.com", status="closed")

    worker.remove()

    refreshed(other, other_closed)
    assert other.status == Job.Status.FILLED
    assert other_closed.status == Application.Status.CLOSED


@pytest.mark.parametrize("status", ["pending", "rejected", "closed", "cancelled"])
def test_removing_an_application_that_is_not_accepted_is_refused(job, status):
    """Only an accepted application can be removed (spec R18; AC17).

    1. Save a pending, rejected, closed or cancelled application
    2. Remove it
    3. Expect: ApplicationStateError; the status is unchanged
    """
    application = apply(job, "a@example.com", status=status)

    with pytest.raises(ApplicationStateError):
        application.remove()

    refreshed(application)
    assert application.status == status


@pytest.mark.parametrize("status", ["done", "cancelled"])
def test_removing_on_a_done_or_cancelled_job_is_refused(job, status):
    """A done or cancelled job is history (spec R18; AC17).

    1. Save an accepted application, then set the job done or cancelled
    2. Remove it
    3. Expect: ApplicationStateError; it is still accepted, the job unchanged
    """
    application = accepted(job, "a@example.com", 1)
    Job.objects.filter(pk=job.pk).update(status=status)

    with pytest.raises(ApplicationStateError):
        application.remove()

    refreshed(application, job)
    assert application.status == Application.Status.ACCEPTED
    assert job.status == status


def test_remove_reads_the_state_again_and_locks_the_job(job):
    """A second click with an old copy changes nothing; the job row is locked (D6).

    1. Load the same accepted application twice (two tabs)
    2. Remove it through the first copy, recording the SQL; then through the second
    3. Expect: one SELECT … FOR UPDATE on the job; the second remove raises
       ApplicationStateError
    """
    application = accepted(job, "a@example.com", 1)
    first_tab = Application.objects.get(pk=application.pk)
    second_tab = Application.objects.get(pk=application.pk)

    with CaptureQueriesContext(connection) as queries:
        first_tab.remove()
    with pytest.raises(ApplicationStateError):
        second_tab.remove()

    locks = [
        q["sql"]
        for q in queries
        if 'FROM "jobs_job"' in q["sql"] and "FOR UPDATE" in q["sql"]
    ]
    assert len(locks) == 1
