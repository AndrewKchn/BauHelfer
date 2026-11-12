"""Integration tests: the employer marks a job done on "My jobs" (#37).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/job-done.md, iteration 1 (R3-R7, R9, D3-D6, D9), acceptance criteria
AC3-AC7. The rule itself (when a job can be marked done) is in test_job_done.py.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job

from .test_application import make_worker
from .test_my_jobs_views import add_photo
from .test_views import form_data, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(37)]

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
CONFIRM = "Mark this job as done? This cannot be undone."


@pytest.fixture
def employer():
    """The employer who posted the jobs."""
    return make_employer("anna@example.com")


@pytest.fixture
def employer_client(client, employer):
    """A browser logged in as the employer."""
    client.force_login(employer)
    return client


def accept(job, email="ivan@example.com"):
    """Save an accepted application of one worker to `job`."""
    return Application.objects.create(
        job=job,
        worker=make_worker(email),
        workers_accepted=1,
        status=Application.Status.ACCEPTED,
    )


def finished_job(employer, **fields):
    """A filled job that ended yesterday, with one accepted worker."""
    job = make_job(employer, date=TODAY - DAY, status=Job.Status.FILLED, **fields)
    accept(job, f"worker{Job.objects.count()}@example.com")
    return job


def done_url(job):
    """Where the "Mark as done" button posts to."""
    return reverse("job_done", args=[job.pk])


def groups(response):
    """The tabs on the page: (status, items) in order."""
    return [(group["status"], group["items"]) for group in response.context["groups"]]


# The view (R3; AC3)


def test_owner_marks_a_finished_job_done(employer_client, employer):
    """POST marks it done and goes back to "My jobs", where it is in "Done" (R3, R6).

    1. Save a filled job that ended yesterday, with an accepted worker
    2. POST to its done URL as its employer, following the redirect
    3. Expect: the job is done; the page is "My jobs" with "Job marked as done."; the job
       is in the "done" tab
    """
    job = finished_job(employer)

    response = employer_client.post(done_url(job), follow=True)

    job.refresh_from_db()
    assert job.status == Job.Status.DONE
    assert response.redirect_chain == [(reverse("my_jobs"), 302)]
    assertContains(response, "Job marked as done.")
    assert groups(response) == [("done", [job])]


def test_job_that_is_not_over_gives_404(employer_client, employer):
    """Before the end the view refuses, as the model (R3, D1).

    1. Save a filled job next week with an accepted worker
    2. POST to its done URL as its employer
    3. Expect: 404; the job is still filled
    """
    job = make_job(employer, status=Job.Status.FILLED)
    accept(job)

    response = employer_client.post(done_url(job))

    job.refresh_from_db()
    assert response.status_code == 404
    assert job.status == Job.Status.FILLED


def test_other_employer_gets_404(client, employer):
    """Another employer cannot even tell the job exists (R3).

    1. Save a finished job of Anna
    2. POST to its done URL as another employer
    3. Expect: 404; the job is still filled
    """
    job = finished_job(employer)
    client.force_login(make_employer("bob@example.com"))

    response = client.post(done_url(job))

    job.refresh_from_db()
    assert response.status_code == 404
    assert job.status == Job.Status.FILLED


def test_worker_gets_403(client, employer):
    """Employers only, as the other employer pages (R3).

    1. Save a finished job
    2. POST to its done URL as a worker
    3. Expect: 403
    """
    job = finished_job(employer)
    client.force_login(make_worker("w@example.com"))

    assert client.post(done_url(job)).status_code == 403


def test_get_is_not_allowed(employer_client, employer):
    """A link must not change anything: only POST (R3).

    1. Save a finished job
    2. GET its done URL as its employer
    3. Expect: 405; the job is still filled
    """
    job = finished_job(employer)

    response = employer_client.get(done_url(job))

    job.refresh_from_db()
    assert response.status_code == 405
    assert job.status == Job.Status.FILLED


# The button on "My jobs" (R4-R6, D3-D5; AC4, AC5)


def test_finished_job_shows_the_button_with_a_question(employer_client, employer):
    """A form to the done URL that asks first (R4, D4).

    1. Save a filled job that ended yesterday, with an accepted worker
    2. Open "My jobs"
    3. Expect: a form posting to its done URL, "Mark as done", the confirm question
    """
    job = finished_job(employer)

    response = employer_client.get(reverse("my_jobs"))

    assertContains(response, f'action="{done_url(job)}"')
    assertContains(response, "Mark as done")
    assertContains(response, CONFIRM)


def test_open_past_job_with_a_worker_shows_the_button_in_past(
    employer_client, employer
):
    """2 of 3 found and worked: in "Past", with the button (R6, D2, D5).

    1. Save an open job for 3 that ended yesterday, with one accepted worker
    2. Open "My jobs"
    3. Expect: the job in the "past" tab; the button to its done URL
    """
    job = make_job(employer, date=TODAY - DAY, workers_needed=3)
    accept(job)

    response = employer_client.get(reverse("my_jobs"))

    assert groups(response) == [("past", [job])]
    assertContains(response, f'action="{done_url(job)}"')


@pytest.mark.parametrize(
    ("fields", "with_worker"),
    [
        ({"status": "filled"}, True),  # next week: not over yet
        ({"date": TODAY - DAY}, False),  # over, but nobody accepted
    ],
    ids=["not-over", "nobody-accepted"],
)
def test_no_button_for_a_job_that_cannot_be_marked_done(
    employer_client, employer, fields, with_worker
):
    """The button only when the model says yes (R4).

    1. Save a filled job next week with a worker / an open job yesterday without one
    2. Open "My jobs"
    3. Expect: no done URL and no "Mark as done" on the page
    """
    job = make_job(employer, **fields)
    if with_worker:
        accept(job)

    response = employer_client.get(reverse("my_jobs"))

    assertNotContains(response, done_url(job))
    assertNotContains(response, "Mark as done")


def test_buttons_cost_no_query_per_job(employer_client, employer):
    """with_workers_found(): the same queries for 1 and for 3 finished jobs (R5).

    1. Save one finished job, open "My jobs" and count the queries
    2. Save two more, open it again and count
    3. Expect: the same number; three buttons on the second page
    """
    finished_job(employer)
    with CaptureQueriesContext(connection) as one:
        employer_client.get(reverse("my_jobs"))
    finished_job(employer)
    finished_job(employer)

    with CaptureQueriesContext(connection) as three:
        response = employer_client.get(reverse("my_jobs"))

    assert len(three) == len(one)
    assertContains(response, CONFIRM, count=3)


# The worker's "Done" tab (R7, D6; AC6)


def test_worker_sees_a_done_tab_after_accepted(client, employer):
    """The "Done" tab right after "Accepted", in the done jobs' colour (R7, D6).

    1. Save Ivan's accepted application of a done job, and of an open job next week
    2. Open "My applications" as Ivan
    3. Expect: the tabs accepted, done; the badge "Done 1" with data-colour
       badge-secondary
    """
    ivan = make_worker("ivan@example.com")
    done = make_job(employer, date=TODAY - DAY, status=Job.Status.DONE)
    upcoming = make_job(employer, status=Job.Status.FILLED)
    done_application = Application.objects.create(
        job=done, worker=ivan, workers_accepted=1, status="accepted"
    )
    upcoming_application = Application.objects.create(
        job=upcoming, worker=ivan, workers_accepted=1, status="accepted"
    )
    client.force_login(ivan)

    response = client.get(reverse("my_applications"))

    assert groups(response) == [
        ("accepted", [upcoming_application]),
        ("done", [done_application]),
    ]
    assertContains(response, 'data-colour="badge-secondary">Done 1')


# Edit, cancel and photos refuse a job that is over (R9, D9; AC7)


def past_open_job(employer):
    """An open job that ended yesterday, with one photo."""
    job = make_job(employer, date=TODAY - DAY)
    add_photo(job)
    return job


def test_edit_of_a_job_that_is_over_gives_404(employer_client, employer):
    """#26 hid the links; now the page refuses too (D9).

    1. Save an open job that ended yesterday
    2. GET and POST its edit page
    3. Expect: 404 both times; the job is unchanged
    """
    job = past_open_job(employer)
    url = reverse("job_edit", args=[job.pk])

    get = employer_client.get(url)
    post = employer_client.post(url, form_data())

    job.refresh_from_db()
    assert (get.status_code, post.status_code) == (404, 404)
    assert job.job_type == "demolition"


def test_cancel_of_a_job_that_is_over_gives_404(employer_client, employer):
    """No cancelling work that is already over (D9).

    1. Save an open job that ended yesterday
    2. GET and POST its cancel page
    3. Expect: 404 both times; the job is still open
    """
    job = past_open_job(employer)
    url = reverse("job_cancel", args=[job.pk])

    get = employer_client.get(url)
    post = employer_client.post(url)

    job.refresh_from_db()
    assert (get.status_code, post.status_code) == (404, 404)
    assert job.status == Job.Status.OPEN


def test_photos_of_a_job_that_is_over_cannot_change(employer_client, employer):
    """Adding and deleting a photo refuse too (R9).

    1. Save an open job that ended yesterday, with one photo
    2. POST to add a photo, and to delete the one it has
    3. Expect: 404 both times; the job still has exactly its photo
    """
    job = past_open_job(employer)
    photo = job.photos.get()

    add = employer_client.post(reverse("job_photo_add", args=[job.pk]))
    delete = employer_client.post(reverse("job_photo_delete", args=[photo.pk]))

    assert (add.status_code, delete.status_code) == (404, 404)
    assert list(job.photos.all()) == [photo]


def test_job_on_its_day_can_still_be_edited_and_cancelled(employer_client, employer):
    """On the day itself nothing changes: the same rule as the "Past" tab (D9).

    1. Save an open job today at 00:00 for 1 hour, with a photo (already ended, but its
       day is not over)
    2. GET its edit and cancel pages
    3. Expect: 200 both times
    """
    job = make_job(employer, date=TODAY, start_time=datetime.time(0, 0), hours=1)
    add_photo(job)

    edit = employer_client.get(reverse("job_edit", args=[job.pk]))
    cancel = employer_client.get(reverse("job_cancel", args=[job.pk]))

    assert (edit.status_code, cancel.status_code) == (200, 200)
