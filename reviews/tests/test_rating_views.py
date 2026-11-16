"""Integration tests: the rating on the profiles, the job page and the applications (#39).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/ratings.md, iteration 1 (R4-R6, D2, D6-D10, D12).
"""

import datetime

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(39)]

DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna of Huber Bau GmbH, who hires."""
    user = make_employer("anna@example.com")
    user.name = "Anna Huber"
    user.save()
    return user


@pytest.fixture
def worker():
    """Ivan Petrenko, a crew of 3 on a Minijob, with a work-permit confirmation."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.save()
    return user


def work(employer, worker):
    """Ivan's accepted application to a job of Anna's, done yesterday."""
    job = make_job(
        employer,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - DAY,
    )
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )


def rate(application, worker_gets=None, employer_gets=None):
    """Save the reviews given; with both, both are visible (reviews.md D3)."""
    if worker_gets is not None:
        Review.objects.create(
            application=application,
            author=application.job.employer,
            rating=worker_gets,
        )
    if employer_gets is not None:
        Review.objects.create(
            application=application, author=application.worker, rating=employer_gets
        )


def rated_worker(employer, worker, *stars):
    """Anna rates Ivan with each of `stars` for a work of its own, Ivan rates back 4."""
    for each in stars:
        rate(work(employer, worker), worker_gets=each, employer_gets=4)


def job_url(job):
    """The job page."""
    return reverse("job_detail", args=[job.pk])


# The worker's card: own page and the employer's view (R4, D6, D7, D9, D10)


def test_own_profile_shows_the_average_and_count(client, employer, worker):
    """Ivan sees his rating in his card's head (R4, D6, D10).

    1. Anna rates Ivan 5, 4 and 5 for three works, both sides rated
    2. Open "My profile" as Ivan
    3. Expect: "★ 4.7 (3 reviews)"
    """
    rated_worker(employer, worker, 5, 4, 5)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "★ 4.7 (3 reviews)")


def test_one_review_is_singular(client, employer, worker):
    """One review: "(1 review)", not "(1 reviews)" (R4).

    1. Anna rates Ivan 5 once, both sides rated
    2. Open "My profile" as Ivan
    3. Expect: "★ 5.0 (1 review)"
    """
    rated_worker(employer, worker, 5)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "★ 5.0 (1 review)")


def test_average_uses_the_page_language(client, employer, worker):
    """German pages write the average with a comma (D6).

    1. Anna rates Ivan 5, 4 and 5; Ivan reads in German
    2. Open "My profile"
    3. Expect: "★ 4,7", not "★ 4.7"
    """
    rated_worker(employer, worker, 5, 4, 5)
    worker.preferred_language = "de"
    worker.save()
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "★ 4,7")
    assertNotContains(response, "★ 4.7")


def test_no_reviews_yet(client, worker):
    """Nobody rated Ivan: "No reviews yet" instead of a rating (D7).

    1. Ivan has no review
    2. Open "My profile" as Ivan
    3. Expect: "No reviews yet", no "★"
    """
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "No reviews yet")
    assertNotContains(response, "★")


def test_hidden_review_is_not_on_the_own_page(client, employer, worker):
    """Anna's 1★ waits for Ivan's own review: his page does not show it (D2).

    1. Anna rates Ivan 1; Ivan has not rated her
    2. Open "My profile" as Ivan
    3. Expect: "No reviews yet"
    """
    rate(work(employer, worker), worker_gets=1)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "No reviews yet")


def test_employer_sees_the_workers_rating(client, employer, worker):
    """The worker page for an employer shows the same rating (R4).

    1. Anna rates Ivan 4 and 5 (both rated); Ivan applied to her open job
    2. Open Ivan's worker page as Anna
    3. Expect: "★ 4.5 (2 reviews)"
    """
    rated_worker(employer, worker, 4, 5)
    Application.objects.create(job=make_job(employer), worker=worker)
    client.force_login(employer)

    response = client.get(reverse("worker_detail", args=[worker.pk]))

    assertContains(response, "★ 4.5 (2 reviews)")


def test_worker_card_head(client, employer, worker):
    """The head of the mockup: initials, name, crew and legal status (D9).

    1. Ivan (crew of 3, Minijob) applied to Anna's job
    2. Open Ivan's worker page as Anna
    3. Expect: "IP", "Ivan Petrenko" and "Crew of 3 · Minijob"
    """
    Application.objects.create(job=make_job(employer), worker=worker)
    client.force_login(employer)

    response = client.get(reverse("worker_detail", args=[worker.pk]))

    assertContains(response, ">IP<")
    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Crew of 3 · Minijob")


def test_permit_line_says_who_confirmed(client, employer, worker):
    """A green line that says the worker confirmed it, not the site (D12).

    1. Ivan confirmed the work permit and applied to Anna's job
    2. Open Ivan's worker page as Anna
    3. Expect: "Allowed to work in Germany (confirmed by the worker)" in green
    """
    Application.objects.create(job=make_job(employer), worker=worker)
    client.force_login(employer)

    response = client.get(reverse("worker_detail", args=[worker.pk]))

    assertContains(response, "Allowed to work in Germany (confirmed by the worker)")
    assertContains(response, "text-success")


def test_permit_line_without_confirmation(client, employer):
    """No confirmation: "Work permit not confirmed" (D12).

    1. Olga has a profile but no work-permit confirmation; an admin added her
       application to Anna's job
    2. Open Olga's worker page as Anna
    3. Expect: "Work permit not confirmed", not "Allowed to work in Germany"
    """
    olga = make_worker("olga@example.com", permit=False)
    Application.objects.create(job=make_job(employer), worker=olga)
    client.force_login(employer)

    response = client.get(reverse("worker_detail", args=[olga.pk]))

    assertContains(response, "Work permit not confirmed")
    assertNotContains(response, "Allowed to work in Germany")


# The employer's card: own page and the job page (R5)


def test_employer_rating_on_the_job_page_for_a_guest(client, employer, worker):
    """Anyone who opens Anna's job sees her rating (R5).

    1. Ivan rates Anna 4 and 5 for two works, Anna rates back
    2. Open a new job of Anna's as a guest
    3. Expect: "★ 4.5 (2 reviews)" and her initials "AH"
    """
    for stars in (4, 5):
        rate(work(employer, worker), worker_gets=4, employer_gets=stars)

    response = client.get(job_url(make_job(employer)))

    assertContains(response, "★ 4.5 (2 reviews)")
    assertContains(response, ">AH<")


def test_employer_sees_own_rating(client, employer, worker):
    """Anna sees her rating on "My company" (R5).

    1. Ivan rates Anna 3, Anna rates back
    2. Open "My company" as Anna
    3. Expect: "★ 3.0 (1 review)"
    """
    rate(work(employer, worker), worker_gets=4, employer_gets=3)
    client.force_login(employer)

    response = client.get(reverse("employer_profile"))

    assertContains(response, "★ 3.0 (1 review)")


# The applications list on the owner's job page (R6, D8)


def test_applications_list_shows_each_workers_rating(client, employer, worker):
    """Short ratings in the list, as on the mockup: "★ 4.7 (3)" (R6, D7).

    1. Anna rates Ivan 5, 4 and 5; Ivan and Olga (no reviews) apply to her new job
    2. Open the job as Anna
    3. Expect: "★ 4.7 (3)" and "No reviews yet"
    """
    rated_worker(employer, worker, 5, 4, 5)
    job = make_job(employer)
    Application.objects.create(job=job, worker=worker)
    Application.objects.create(job=job, worker=make_worker("olga@example.com"))
    client.force_login(employer)

    response = client.get(job_url(job))

    assertContains(response, "★ 4.7 (3)")
    assertContains(response, "No reviews yet")


def test_applications_list_ratings_do_not_cost_a_query_each(client, employer):
    """Four applications cost as many queries as one (D8).

    1. Anna's job with one application, each worker rated once; count the queries of
       the page
    2. Add three more applications of rated workers; count again
    3. Expect: the same number
    """
    job = make_job(employer)

    def add_rated_applicant(n):
        applicant = make_worker(f"w{n}@example.com")
        rated_worker(employer, applicant, 4)
        Application.objects.create(job=job, worker=applicant)

    client.force_login(employer)
    add_rated_applicant(0)
    with CaptureQueriesContext(connection) as one:
        client.get(job_url(job))
    for n in (1, 2, 3):
        add_rated_applicant(n)
    with CaptureQueriesContext(connection) as four:
        response = client.get(job_url(job))

    assertContains(response, "★ 4.0 (1)", count=4)
    assert len(four) == len(one)
