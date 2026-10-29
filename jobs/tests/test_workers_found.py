"""Unit tests: the workers found with the jobs, the places left and the apply form (#24).

Spec: docs/specs/accept-reject.md, iteration 2 (R14-R16, D12), acceptance criteria AC13 and
AC14. The pages are in test_workers_found_views.py.
"""

import pytest

from jobs.forms import ApplicationForm
from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(24)]


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def accept(job, email, taken):
    """Save an accepted application to `job` with `taken` workers taken."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        workers_offered=taken,
        workers_accepted=taken,
        status=Application.Status.ACCEPTED,
    )


# Found with the jobs (R16, D12)


def test_with_workers_found_adds_the_sum_of_accepted_workers(employer):
    """Each job comes with its accepted workers, from the same query (spec D12).

    1. Save a job for 4 with accepted crews of 2 and 1 and a pending application, and a
       job without applications
    2. Load both with Job.objects.with_workers_found()
    3. Expect: accepted_workers is 3 for the first, 0 (not None) for the second
    """
    busy = make_job(employer, workers_needed=4)
    accept(busy, "a@example.com", 2)
    accept(busy, "b@example.com", 1)
    Application.objects.create(job=busy, worker=make_worker("c@example.com"))
    empty = make_job(employer)

    jobs = {job.pk: job for job in Job.objects.with_workers_found()}

    assert jobs[busy.pk].accepted_workers == 3
    assert jobs[empty.pk].accepted_workers == 0


def test_places_left_uses_the_number_loaded_with_the_job(
    employer, django_assert_num_queries
):
    """A job loaded with with_workers_found() needs no query for its places left.

    1. Save a job for 3 with an accepted crew of 2
    2. Load it with with_workers_found()
    3. Expect: places_left is 1, read without any database query
    """
    job = make_job(employer, workers_needed=3)
    accept(job, "a@example.com", 2)
    loaded = Job.objects.with_workers_found().get(pk=job.pk)

    with django_assert_num_queries(0):
        assert loaded.places_left == 1


def test_places_left_counts_for_a_job_loaded_without_it(employer):
    """A job loaded the plain way still gets the right number, with a query.

    1. Save a job for 3 with an accepted crew of 2
    2. Load it with Job.objects.get()
    3. Expect: places_left is 1
    """
    job = make_job(employer, workers_needed=3)
    accept(job, "a@example.com", 2)

    assert Job.objects.get(pk=job.pk).places_left == 1


# The apply form (R15; AC13)


def make_form(job, worker, **data):
    """The apply form of `worker` for `job`, sent with `data`."""
    return ApplicationForm(data, job=job, worker=worker)


def test_form_allows_at_most_the_places_left(employer):
    """Workers I bring: at most the places still free (spec R15).

    1. A job for 5 with 3 workers found; a crew of 3 opens the form
    2. Expect: max="2" on the field; 2 is valid, 3 has an error on workers_offered
    """
    job = make_job(employer, workers_needed=5)
    accept(job, "a@example.com", 3)
    worker = make_worker("ivan@example.com", team_size=3)

    assert 'max="2"' in str(make_form(job, worker)["workers_offered"])
    assert make_form(job, worker, workers_offered=2).is_valid()
    too_many = make_form(job, worker, workers_offered=3)
    assert "workers_offered" in too_many.errors


def test_form_without_number_field_when_one_place_is_left(employer):
    """Only 1 place left: nothing to choose, 1 is saved (spec R15, application.md D4).

    1. A job for 3 with 2 workers found; a crew of 3 opens the form
    2. Expect: no workers_offered field
    """
    job = make_job(employer, workers_needed=3)
    accept(job, "a@example.com", 2)
    worker = make_worker("ivan@example.com", team_size=3)

    assert "workers_offered" not in make_form(job, worker).fields
