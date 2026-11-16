"""Unit tests: which reviews count and the rating made of them (#39).

Spec: docs/specs/ratings.md, iteration 1 (R1-R3, R6, D2, D8). The pages are in
test_rating_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Rating, Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(39)]

# A fixed "now": 16 November 2026, 10:00 in Munich.
MUNICH = ZoneInfo("Europe/Berlin")
NOW = datetime.datetime(2026, 11, 16, 10, 0, tzinfo=MUNICH)
DAY = datetime.timedelta(days=1)
MINUTE = datetime.timedelta(minutes=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def employer():
    """Anna, who hires."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """Ivan, who works for Anna."""
    return make_worker("ivan@example.com")


def work(employer, worker, done_at=NOW - DAY):
    """Ivan's accepted application to a job of Anna's, marked done `done_at`."""
    job = make_job(
        employer,
        date=(done_at - DAY).date(),
        status=Job.Status.DONE,
        done_at=done_at,
    )
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )


def review(application, author, rating=4, tags=()):
    """Save a review of `application` by `author`."""
    return Review.objects.create(
        application=application, author=author, rating=rating, tags=list(tags)
    )


def both_rated(application, worker_gets, employer_gets):
    """Both sides rate each other, so both reviews are visible (reviews.md D3)."""
    review(application, application.job.employer, rating=worker_gets)
    review(application, application.worker, rating=employer_gets)


# visible(): the rule of Review.is_visible, in the database (R1, D2)


def test_visible_keeps_the_reviews_is_visible_lets_through(employer, worker):
    """visible() and is_visible agree on every kind of review (R1).

    1. Save four reviews: one-sided and fresh; both sides of one work; one-sided whose
       14 days are over; one-sided while the employer rated another worker of the job
    2. Expect: visible() returns exactly the reviews whose is_visible is True, and these
       are the two of the rated-both work and the late one-sided one
    """
    fresh = review(work(employer, worker), worker)
    both = work(employer, worker)
    both_rated(both, 5, 4)
    late = review(work(employer, worker, done_at=NOW - 15 * DAY), worker)
    shared = work(employer, worker)
    olga = Application.objects.create(
        job=shared.job,
        worker=make_worker("olga@example.com"),
        workers_accepted=1,
        status=Application.Status.ACCEPTED,
    )
    alone = review(shared, worker)
    review(olga, employer)

    shown = set(Review.objects.visible())

    assert shown == {r for r in Review.objects.all() if r.is_visible}
    assert fresh not in shown
    assert alone not in shown
    assert late in shown
    assert set(both.reviews.all()) <= shown


def test_visible_opens_a_one_sided_review_at_the_deadline(
    employer, worker, monkeypatch
):
    """The 14 days end: visible() lets it through, as is_visible does (R1, D2).

    1. Save Ivan's review; nobody rates back
    2. Set the clock a minute before, then exactly at the deadline
    3. Expect: not visible, then visible
    """
    application = work(employer, worker)
    saved = review(application, worker)
    deadline = application.review_deadline

    monkeypatch.setattr(timezone, "now", lambda: deadline - MINUTE)
    assert saved not in Review.objects.visible()
    monkeypatch.setattr(timezone, "now", lambda: deadline)
    assert saved in Review.objects.visible()


# about(): the reviews of a user, not by them (R2)


def test_about_a_worker_is_what_employers_wrote(employer, worker):
    """Ivan's reviews are the ones about him, not the one he wrote (R2).

    1. Anna and Ivan rate each other for one work
    2. Expect: about(Ivan) is Anna's review; about(Anna) is Ivan's
    """
    application = work(employer, worker)
    annas = review(application, employer, rating=5)
    ivans = review(application, worker, rating=2)

    assert list(Review.objects.about(worker)) == [annas]
    assert list(Review.objects.about(employer)) == [ivans]


# rating_of(): the average and the count (R3, D2)


def test_rating_is_the_average_and_count_of_visible_reviews(employer, worker):
    """Three rated works: 5, 4 and 5 stars give 4.67 from 3 (R3).

    1. Anna rates Ivan 5, 4 and 5 for three works; Ivan rates her back each time
    2. Expect: Ivan's rating is 14/3 from 3 reviews
    """
    for stars in (5, 4, 5):
        both_rated(work(employer, worker), worker_gets=stars, employer_gets=3)

    rating = Review.objects.rating_of(worker)

    assert rating.average == pytest.approx(14 / 3)
    assert rating.count == 3


def test_hidden_review_is_not_in_the_rating(employer, worker):
    """Anna's 1★ waits for Ivan's review: his rating does not move (D2).

    1. Anna rates Ivan 5 for one work (both rated) and 1 for a second (only she)
    2. Expect: Ivan's rating is 5 from 1 review
    """
    both_rated(work(employer, worker), worker_gets=5, employer_gets=5)
    review(work(employer, worker), employer, rating=1)

    assert Review.objects.rating_of(worker) == Rating(average=5, count=1)


def test_rating_without_reviews_is_empty(worker):
    """Nobody rated Ivan yet: no average, count 0 (R3, D7).

    1. Ivan has no review
    2. Expect: Rating(None, 0)
    """
    assert Review.objects.rating_of(worker) == Rating(average=None, count=0)


# worker_ratings(): all workers of a list at once (R6, D8)


def test_worker_ratings_gives_each_worker_theirs_in_one_query(employer, worker):
    """The applications list asks for every worker's rating in one query (D8).

    1. Anna rates Ivan 5 and 3, Olga 4 (all rated back); Petro has no review
    2. Ask for the ratings of Ivan, Olga and Petro, counting the queries
    3. Expect: one query; Ivan 4 from 2, Olga 4 from 1, Petro missing
    """
    olga = make_worker("olga@example.com")
    petro = make_worker("petro@example.com")
    both_rated(work(employer, worker), worker_gets=5, employer_gets=5)
    both_rated(work(employer, worker), worker_gets=3, employer_gets=5)
    both_rated(work(employer, olga), worker_gets=4, employer_gets=5)

    with CaptureQueriesContext(connection) as queries:
        ratings = Review.objects.worker_ratings([worker.pk, olga.pk, petro.pk])

    assert len(queries) == 1
    assert ratings == {
        worker.pk: Rating(average=4, count=2),
        olga.pk: Rating(average=4, count=1),
    }


def test_worker_ratings_skip_hidden_and_own_reviews(employer, worker):
    """Only visible reviews about the worker, as rating_of (R2, D2).

    1. Ivan rates Anna 1 (only he, hidden) and Anna rates Ivan 2 for another work (only
       she, hidden)
    2. Expect: no rating for Ivan
    """
    review(work(employer, worker), worker, rating=1)
    review(work(employer, worker), employer, rating=2)

    assert Review.objects.worker_ratings([worker.pk]) == {}
