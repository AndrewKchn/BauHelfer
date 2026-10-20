"""Unit tests: the Application model and the apply form (#22).

Spec: docs/specs/application.md (R1-R4, D3-D5), acceptance criteria AC1-AC3. The view and
the job page are in test_application_views.py.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import DataError, IntegrityError, transaction
from django.utils import timezone

from accounts.models import WorkerProfile
from jobs.forms import ApplicationForm
from jobs.models import Application

from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(22)]

User = get_user_model()


def make_worker(email="ivan@example.com", team_size=3, profile=True, permit=True):
    """A worker; by default one who can apply: profile and work-permit confirmation."""
    user = User.objects.create_user(
        email=email,
        password="x",
        role="worker",
        work_permit_confirmed_at=timezone.now() if permit else None,
    )
    if profile:
        WorkerProfile.objects.create(
            user=user,
            team_size=team_size,
            skills=["demolition"],
            languages=["de"],
            legal_status="minijob",
        )
    return user


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


@pytest.fixture
def job(employer):
    """An open job next week for 2 workers."""
    return make_job(employer)


@pytest.fixture
def worker():
    """A crew of 3 that can apply."""
    return make_worker()


# The model (spec R1, R2, D2, D3, D5; AC1, AC2)


def test_new_application_is_pending(job, worker):
    """A saved application starts as pending (spec R1, D2).

    1. Save an application of a worker to a job, without a status
    2. Expect: status pending, created_at is set
    """
    application = Application.objects.create(job=job, worker=worker, workers_offered=2)

    assert application.status == Application.Status.PENDING
    assert application.created_at is not None


def test_database_refuses_a_second_application_to_the_same_job(employer, job, worker):
    """One application per worker and job, enforced by the database (spec R2, D5).

    1. Save an application of a worker to a job
    2. Save a second one of the same worker to the same job
    3. Expect: IntegrityError
    4. Save one of the same worker to another job
    5. Expect: saved, the worker has 2 applications
    """
    Application.objects.create(job=job, worker=worker, workers_offered=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(job=job, worker=worker, workers_offered=1)

    Application.objects.create(job=make_job(employer), worker=worker, workers_offered=1)
    assert Application.objects.filter(worker=worker).count() == 2


@pytest.mark.parametrize("workers_offered", [0, 11])
def test_database_refuses_workers_offered_outside_1_to_10(job, worker, workers_offered):
    """The database keeps workers_offered between 1 and 10 (spec R3).

    1. Save an application with 0 or 11 workers, without the form
    2. Expect: IntegrityError
    """
    with pytest.raises(IntegrityError):
        Application.objects.create(
            job=job, worker=worker, workers_offered=workers_offered
        )


def test_database_refuses_a_message_over_500_characters(job, worker):
    """The message column is varchar(500): code without the form cannot save more (D3).

    1. Save an application with a message of 501 characters, without the form
    2. Expect: DataError from PostgreSQL
    """
    with pytest.raises(DataError):
        Application.objects.create(
            job=job, worker=worker, workers_offered=1, message="x" * 501
        )


# The form (spec R3, R4, D3, D4; AC2, AC3)


def make_form(job, worker, **data):
    """The apply form of `worker` for `job`; with `data` it is bound (sent)."""
    return ApplicationForm(data or None, job=job, worker=worker)


@pytest.mark.parametrize(
    ("team_size", "workers_needed", "limit"),
    [(3, 2, 2), (2, 5, 2)],
    ids=["job needs fewer", "team is smaller"],
)
def test_form_allows_up_to_team_size_and_workers_needed(
    employer, team_size, workers_needed, limit
):
    """Workers I bring: at most the team size and at most the workers needed (spec D4).

    1. A crew of 3 for a job for 2, or a crew of 2 for a job for 5: the limit is 2
    2. Send the form with 2, then with 3
    3. Expect: 2 is valid, 3 has an error on workers_offered
    """
    job = make_job(employer, workers_needed=workers_needed)
    worker = make_worker(team_size=team_size)

    assert make_form(job, worker, workers_offered=limit).is_valid()
    too_many = make_form(job, worker, workers_offered=limit + 1)
    assert not too_many.is_valid()
    assert "workers_offered" in too_many.errors


def test_form_starts_at_the_limit_and_tells_the_browser(job, worker):
    """The number field starts at the largest allowed value, which is also its max (R4).

    1. A crew of 3 opens the form of a job for 2 workers
    2. Expect: the field's value is 2; the HTML input has min="1" and max="2"
    """
    form = make_form(job, worker)

    assert form["workers_offered"].value() == 2
    html = str(form["workers_offered"])
    assert 'min="1"' in html
    assert 'max="2"' in html


@pytest.mark.parametrize(
    ("team_size", "workers_needed"),
    [(1, 2), (3, 1)],
    ids=["worker alone", "job needs one"],
)
def test_form_without_number_field_when_the_limit_is_one(
    employer, team_size, workers_needed
):
    """Nothing to choose when only 1 is possible: no field, 1 is saved (spec R4, D4).

    1. A worker alone applies to a job for 2, or a crew of 3 to a job for 1
    2. Expect: the form has no workers_offered field
    3. Send the form with only a message and save it
    4. Expect: the application has workers_offered 1, this job and this worker
    """
    job = make_job(employer, workers_needed=workers_needed)
    worker = make_worker(team_size=team_size)

    form = make_form(job, worker, message="Hello")
    assert "workers_offered" not in form.fields
    assert form.is_valid(), form.errors
    application = form.save()

    assert application.workers_offered == 1
    assert application.job == job
    assert application.worker == worker


def test_form_message_is_optional(job, worker):
    """An empty message is fine: not every worker writes German or English (spec D3).

    1. Send the form with 2 workers and an empty message
    2. Expect: valid
    """
    assert make_form(job, worker, workers_offered=2, message="").is_valid()


def test_form_refuses_a_message_over_500_characters(job, worker):
    """A message of 501 characters sent around the browser is refused (spec D3).

    1. Send the form with a message of 500 characters, then of 501
    2. Expect: 500 is valid, 501 has an error on message
    """
    assert make_form(job, worker, workers_offered=2, message="x" * 500).is_valid()
    too_long = make_form(job, worker, workers_offered=2, message="x" * 501)
    assert "message" in too_long.errors


def test_form_message_is_a_textarea_limited_in_the_browser(job, worker):
    """The browser stops typing at 500 characters (spec D3).

    1. Render the message field of an empty form
    2. Expect: a textarea with maxlength="500"
    """
    html = str(make_form(job, worker)["message"])

    assert html.startswith("<textarea")
    assert 'maxlength="500"' in html


def test_form_saves_the_application_for_this_job_and_worker(job, worker):
    """Saving the form stores the application with the job and the worker (spec R1).

    1. Send the form with 2 workers and a message, save it
    2. Expect: one application of this worker to this job, 2 workers, the message, pending
    """
    form = make_form(job, worker, workers_offered=2, message="We are two.")
    assert form.is_valid(), form.errors

    application = form.save()

    assert Application.objects.get() == application
    assert (application.job, application.worker) == (job, worker)
    assert application.workers_offered == 2
    assert application.message == "We are two."
    assert application.status == Application.Status.PENDING
