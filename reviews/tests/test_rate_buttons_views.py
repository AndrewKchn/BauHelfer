"""Integration tests: the "Rate" buttons on "My applications" and on the job page (#38).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/reviews.md, iteration 2 (R10-R12, D4, D11), acceptance criteria AC8-AC10.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna, the employer of the jobs."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """Ivan, who worked for Anna."""
    return make_worker("ivan@example.com")


def done_job(employer, done_ago=DAY):
    """A job two days ago, marked done `done_ago` before now."""
    return make_job(
        employer,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - done_ago,
    )


def accepted(job, worker):
    """An accepted application of `worker` to `job`."""
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )


def review_url(application):
    """The review page of `application`."""
    return reverse("review_create", args=[application.pk])


def job_url(job):
    """The job page."""
    return reverse("job_detail", args=[job.pk])


# "My applications", the worker's "Done" tab (R10, D11; AC8)


def test_done_card_has_rate_the_employer(client, employer, worker):
    """A done job the worker can still rate: the button to its review page (R10).

    1. Save Ivan's accepted application of a job done yesterday
    2. Open "My applications" as Ivan
    3. Expect: a link to its review page, "Rate the employer"
    """
    application = accepted(done_job(employer), worker)
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertContains(response, f'href="{review_url(application)}"')
    assertContains(response, "Rate the employer")


def test_card_shows_the_own_rating_after_the_review(client, employer, worker):
    """After the review: "Rated ★4" instead of the button (D11).

    1. Save Ivan's application of a done job and his 4-star review of it
    2. Open "My applications" as Ivan
    3. Expect: "Rated ★4"; no link to the review page
    """
    application = accepted(done_job(employer), worker)
    Review.objects.create(application=application, author=worker, rating=4)
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertContains(response, "Rated ★4")
    assertNotContains(response, review_url(application))


def test_card_has_no_button_after_the_deadline(client, employer, worker):
    """The 14 days are over: no button, no rating (D3, D11).

    1. Save Ivan's application of a job done 15 days ago, without a review
    2. Open "My applications" as Ivan
    3. Expect: no link to the review page, no "Rate the employer"
    """
    application = accepted(done_job(employer, done_ago=15 * DAY), worker)
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertNotContains(response, review_url(application))
    assertNotContains(response, "Rate the employer")


def test_card_hides_the_own_rating_after_the_deadline(client, employer, worker):
    """Nothing after the 14 days, also no "Rated" (D11).

    1. Save Ivan's application of a job done 15 days ago and his 4-star review of it
    2. Open "My applications" as Ivan
    3. Expect: no "Rated ★4"
    """
    application = accepted(done_job(employer, done_ago=15 * DAY), worker)
    Review.objects.create(application=application, author=worker, rating=4)
    client.force_login(worker)

    response = client.get(reverse("my_applications"))

    assertNotContains(response, "Rated ★4")


def test_my_applications_buttons_cost_no_query_per_card(client, employer, worker):
    """The same queries for 1 and for 3 done cards (R12).

    1. Save one done application of Ivan, open "My applications" and count the queries
    2. Save two more, one of them reviewed; open it again and count
    3. Expect: the same number; two buttons and one "Rated" on the second page
    """
    accepted(done_job(employer), worker)
    client.force_login(worker)
    with CaptureQueriesContext(connection) as one:
        client.get(reverse("my_applications"))
    accepted(done_job(employer), worker)
    reviewed = accepted(done_job(employer), worker)
    Review.objects.create(application=reviewed, author=worker, rating=5)

    with CaptureQueriesContext(connection) as three:
        response = client.get(reverse("my_applications"))

    assert len(three) == len(one)
    assertContains(response, "Rate the employer", count=2)
    assertContains(response, "Rated ★5", count=1)


# The job page, the employer's list of workers (R11, D4, D11; AC9)


def test_owner_sees_rate_next_to_an_accepted_worker(client, employer, worker):
    """A done job: "Rate" next to the worker, to the review page (R11).

    1. Save Ivan's accepted application of Anna's job done yesterday
    2. Open the job page as Anna
    3. Expect: a link to the review page
    """
    application = accepted(done_job(employer), worker)
    client.force_login(employer)

    response = client.get(job_url(application.job))

    assertContains(response, f'href="{review_url(application)}"')


def test_owner_sees_the_own_rating_after_the_review(client, employer, worker):
    """After Anna's review: "Rated ★3" instead of "Rate" (D11).

    1. Save Ivan's application of a done job and Anna's 3-star review of it
    2. Open the job page as Anna
    3. Expect: "Rated ★3"; no link to the review page
    """
    application = accepted(done_job(employer), worker)
    Review.objects.create(application=application, author=employer, rating=3)
    client.force_login(employer)

    response = client.get(job_url(application.job))

    assertContains(response, "Rated ★3")
    assertNotContains(response, review_url(application))


def test_worker_review_does_not_count_as_the_owner_s(client, employer, worker):
    """Ivan's review of Anna does not hide Anna's button (R11).

    1. Save Ivan's application of a done job and his review of Anna
    2. Open the job page as Anna
    3. Expect: the link to the review page; no "Rated"
    """
    application = accepted(done_job(employer), worker)
    Review.objects.create(application=application, author=worker, rating=2)
    client.force_login(employer)

    response = client.get(job_url(application.job))

    assertContains(response, f'href="{review_url(application)}"')
    assertNotContains(response, "Rated ★")


def test_no_rate_on_a_job_that_is_not_done(client, employer, worker):
    """Filled and over, but not marked done: nothing to rate yet (R11, D1).

    1. Save Ivan's accepted application of a filled job two days ago
    2. Open the job page as Anna
    3. Expect: no link to the review page
    """
    job = make_job(
        employer, date=timezone.localdate() - 2 * DAY, status=Job.Status.FILLED
    )
    application = accepted(job, worker)
    client.force_login(employer)

    response = client.get(job_url(job))

    assertNotContains(response, review_url(application))


def test_job_page_buttons_cost_no_query_per_worker(client, employer):
    """The same queries for 1 and for 3 accepted workers (R12).

    1. Save a done job with one accepted worker, open it as Anna and count the queries
    2. Accept two more workers; open it again and count
    3. Expect: the same number; three review links on the second page
    """
    job = done_job(employer)
    accepted(job, make_worker("w1@example.com"))
    client.force_login(employer)
    with CaptureQueriesContext(connection) as one:
        client.get(job_url(job))
    accepted(job, make_worker("w2@example.com"))
    accepted(job, make_worker("w3@example.com"))

    with CaptureQueriesContext(connection) as three:
        response = client.get(job_url(job))

    assert len(three) == len(one)
    assert response.content.decode().count("/review/") == 3
