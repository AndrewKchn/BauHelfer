"""Unit tests: accepting and rejecting an application, the job fills itself (#24).

Spec: docs/specs/accept-reject.md, iteration 1 (R0-R4, D1, D4-D7, D15), acceptance criteria
AC1-AC5 and AC9. The buttons, the views and the job page are in
test_accept_reject_views.py.
"""

import pytest
from django.db import IntegrityError, connection, transaction
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
    worker = make_worker(email)
    return Application.objects.create(
        job=job, worker=worker, workers_offered=workers_offered, **fields
    )


def refreshed(*objects):
    """Read every object again from the database: what the methods really saved."""
    for obj in objects:
        obj.refresh_from_db()


# Workers found (R2, D4; AC1)


def test_workers_found_sums_the_accepted_workers(employer, job):
    """Workers found count the people taken, not the applications (spec D4).

    1. Save, on a job, an accepted crew with 2 workers taken, an accepted single worker, a
       pending, a rejected and a closed application; and an accepted one on another job
    2. Expect: workers_found() is 3
    """
    apply(job, "a@example.com", 2, status="accepted", workers_accepted=2)
    apply(job, "b@example.com", 1, status="accepted", workers_accepted=1)
    apply(job, "c@example.com", 2)
    apply(job, "d@example.com", 2, status="rejected")
    apply(job, "e@example.com", 2, status="closed")
    other = make_job(employer, workers_needed=3)
    apply(other, "f@example.com", 2, status="accepted", workers_accepted=2)

    assert job.workers_found() == 3


def test_workers_found_is_zero_without_accepted_applications(job):
    """A fresh job has found nobody.

    1. Save a pending application to a job
    2. Expect: workers_found() is 0, not None
    """
    apply(job, "a@example.com", 2)

    assert job.workers_found() == 0


# Accept (R3, D1, D6, D15; AC2-AC5)


def test_accepting_a_crew_takes_all_of_it(job):
    """A crew that fits is taken whole; the job stays open while places are left.

    1. On a job for 3, save a crew offering 2 and another pending application
    2. Accept the crew
    3. Expect: the crew is accepted with 2 workers taken; the job is still open; the other
       application is still pending
    """
    crew = apply(job, "a@example.com", 2)
    other = apply(job, "b@example.com", 1)

    crew.accept()

    refreshed(crew, other, job)
    assert crew.status == Application.Status.ACCEPTED
    assert crew.workers_accepted == 2
    assert job.status == Job.Status.OPEN
    assert other.status == Application.Status.PENDING


def test_accepting_the_last_places_fills_the_job_and_closes_the_rest(employer, job):
    """When enough workers are found, the job is filled and the others are closed (D15).

    1. On a job for 3, save an accepted crew of 2, a rejected, two pending applications
       and a pending one on another job
    2. Accept one pending single worker
    3. Expect: the job is filled; the other pending one is closed ("Job filled"); the
       accepted and the rejected ones are unchanged; the other job's one is still pending
    """
    first = apply(job, "a@example.com", 2, status="accepted", workers_accepted=2)
    rejected = apply(job, "b@example.com", 1, status="rejected")
    last = apply(job, "c@example.com", 1)
    extra = apply(job, "d@example.com", 1)
    elsewhere = apply(make_job(employer), "e@example.com", 1)

    last.accept()

    refreshed(job, first, rejected, last, extra, elsewhere)
    assert job.status == Job.Status.FILLED
    assert last.status == Application.Status.ACCEPTED
    assert extra.status == Application.Status.CLOSED
    assert extra.get_status_display() == "Job filled"
    assert first.status == Application.Status.ACCEPTED
    assert rejected.status == Application.Status.REJECTED
    assert elsewhere.status == Application.Status.PENDING


def test_accepting_a_crew_bigger_than_the_places_left_takes_part_of_it(job):
    """Only as many of a crew as places are left are taken (spec D1).

    1. On a job for 3, save an accepted crew of 2 and a pending crew offering 2
    2. Accept the second crew
    3. Expect: it is accepted with 1 of its 2 workers taken; the job is filled with 3
    """
    apply(job, "a@example.com", 2, status="accepted", workers_accepted=2)
    crew = apply(job, "b@example.com", 2)

    crew.accept()

    refreshed(crew, job)
    assert crew.workers_accepted == 1
    assert crew.workers_offered == 2
    assert job.status == Job.Status.FILLED
    assert job.workers_found() == 3


@pytest.mark.parametrize("status", ["accepted", "rejected", "closed"])
def test_accepting_a_decided_application_is_refused(job, status):
    """Only a pending application can be accepted (spec R3; AC5).

    1. Save an application that is already accepted, rejected or closed
    2. Accept it
    3. Expect: ApplicationStateError; the status and workers taken are unchanged
    """
    taken = 1 if status == "accepted" else 0
    application = apply(job, "a@example.com", 1, status=status, workers_accepted=taken)

    with pytest.raises(ApplicationStateError):
        application.accept()

    refreshed(application)
    assert application.status == status
    assert application.workers_accepted == taken


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_accepting_on_a_job_that_is_not_open_is_refused(job, status):
    """Decisions only on an open job (spec D5; AC5).

    1. Save a pending application, then set the job filled, done or cancelled
    2. Accept the application
    3. Expect: ApplicationStateError; the application is still pending
    """
    application = apply(job, "a@example.com", 1)
    Job.objects.filter(pk=job.pk).update(status=status)

    with pytest.raises(ApplicationStateError):
        application.accept()

    refreshed(application)
    assert application.status == Application.Status.PENDING


def test_accept_reads_the_state_again_from_the_database(job):
    """A second click with an old copy of the application changes nothing (spec D6).

    1. Load the same pending application twice (two tabs)
    2. Accept it through the first copy, then through the second one
    3. Expect: the second accept raises ApplicationStateError; workers found stay 1
    """
    application = apply(job, "a@example.com", 1)
    first_tab = Application.objects.get(pk=application.pk)
    second_tab = Application.objects.get(pk=application.pk)

    first_tab.accept()
    with pytest.raises(ApplicationStateError):
        second_tab.accept()

    assert job.workers_found() == 1


def test_accept_locks_the_job_row(job):
    """Two accepts at the same instant wait for each other on the job row (spec D6).

    1. Save a pending application
    2. Accept it and record the SQL queries
    3. Expect: one query reads the job with SELECT … FOR UPDATE
    """
    application = apply(job, "a@example.com", 1)

    with CaptureQueriesContext(connection) as queries:
        application.accept()

    locks = [
        q["sql"]
        for q in queries
        if 'FROM "jobs_job"' in q["sql"] and "FOR UPDATE" in q["sql"]
    ]
    assert len(locks) == 1


# Reject (R4; AC5)


def test_rejecting_a_pending_application(job):
    """Reject changes only this application.

    1. Save two pending applications
    2. Reject the first
    3. Expect: it is rejected with no workers taken; the other is still pending; the job is
       still open
    """
    application = apply(job, "a@example.com", 2)
    other = apply(job, "b@example.com", 1)

    application.reject()

    refreshed(application, other, job)
    assert application.status == Application.Status.REJECTED
    assert application.workers_accepted == 0
    assert other.status == Application.Status.PENDING
    assert job.status == Job.Status.OPEN


@pytest.mark.parametrize("status", ["accepted", "rejected", "closed"])
def test_rejecting_a_decided_application_is_refused(job, status):
    """Only a pending application can be rejected (spec R4; AC5).

    1. Save an application that is already accepted, rejected or closed
    2. Reject it
    3. Expect: ApplicationStateError; the status is unchanged
    """
    application = apply(job, "a@example.com", 1, status=status)

    with pytest.raises(ApplicationStateError):
        application.reject()

    refreshed(application)
    assert application.status == status


def test_rejecting_on_a_job_that_is_not_open_is_refused(job):
    """Decisions only on an open job (spec D5; AC5).

    1. Save a pending application, then cancel the job
    2. Reject the application
    3. Expect: ApplicationStateError; the application is still pending
    """
    application = apply(job, "a@example.com", 1)
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CANCELLED)

    with pytest.raises(ApplicationStateError):
        application.reject()

    refreshed(application)
    assert application.status == Application.Status.PENDING


# The database (R1; AC9)


def test_database_refuses_more_workers_taken_than_offered(job):
    """workers_accepted can never be above workers_offered, even outside the methods.

    1. Save an application offering 2 workers with 3 taken
    2. Expect: IntegrityError
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        apply(job, "a@example.com", 2, status="accepted", workers_accepted=3)


def test_new_application_has_no_workers_taken(job):
    """Nobody is taken before the employer accepts (spec R1).

    1. Save an application offering 2 workers
    2. Expect: workers_accepted is 0
    """
    assert apply(job, "a@example.com", 2).workers_accepted == 0
