"""Unit tests: the review, who may write one and when it is shown (#38).

Spec: docs/specs/reviews.md, iteration 1 (R1-R6, D1, D3, D6-D9), acceptance criteria
AC1-AC4. The review page is in test_views.py.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import EmployerTag, Review, WorkerTag

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

# A fixed "now": 12 November 2026, 10:00 in Munich.
MUNICH = ZoneInfo("Europe/Berlin")
NOW = datetime.datetime(2026, 11, 12, 10, 0, tzinfo=MUNICH)
DAY = datetime.timedelta(days=1)
MINUTE = datetime.timedelta(minutes=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """Fix the clock at NOW, so the test does not depend on when it runs."""
    monkeypatch.setattr(timezone, "now", lambda: NOW)


@pytest.fixture
def employer():
    """The employer of the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """The worker who was accepted and worked."""
    return make_worker("ivan@example.com")


def done_job(employer, done_at=NOW - DAY, **fields):
    """A job that ended two days ago and was marked done `done_at` (yesterday)."""
    values = {"date": (NOW - 2 * DAY).date(), "status": Job.Status.DONE, **fields}
    return make_job(employer, done_at=done_at, **values)


def accepted(job, worker, **fields):
    """An accepted application of `worker` to `job`."""
    values = {"workers_accepted": 1, "status": Application.Status.ACCEPTED, **fields}
    return Application.objects.create(job=job, worker=worker, **values)


@pytest.fixture
def application(employer, worker):
    """Ivan's accepted application to Anna's job, done yesterday."""
    return accepted(done_job(employer), worker)


def review(application, author, rating=4, tags=()):
    """Save a review of `application` by `author`."""
    return Review.objects.create(
        application=application, author=author, rating=rating, tags=list(tags)
    )


# The model and its database rules (R1, R2, D8; AC1)


def test_both_sides_can_review_one_application(application, employer, worker):
    """One review per side: the worker's and the employer's of the same work (R1).

    1. Save Ivan's review of Anna with an employer tag, and Anna's of Ivan with a worker tag
    2. Expect: two reviews of the application, with their ratings and tags
    """
    review(application, worker, rating=5, tags=[EmployerTag.PAID_ON_TIME])
    review(application, employer, rating=3, tags=[WorkerTag.ON_TIME])

    saved = {r.author: (r.rating, r.tags) for r in application.reviews.all()}
    assert saved == {
        worker: (5, ["paid_on_time"]),
        employer: (3, ["on_time"]),
    }


def test_second_review_by_the_same_author_is_refused(application, worker):
    """The database itself allows one review per author and application (R1, D8).

    1. Save Ivan's review of the application
    2. Save a second one by Ivan
    3. Expect: IntegrityError; still one review
    """
    review(application, worker)

    with pytest.raises(IntegrityError), transaction.atomic():
        review(application, worker, rating=1)

    assert application.reviews.count() == 1


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_outside_one_to_five_is_refused(application, worker, rating):
    """1-5 stars, checked by the database too (R1).

    1. Save a review with 0 / 6 stars
    2. Expect: IntegrityError
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        review(application, worker, rating=rating)


def test_tags_are_optional(application, worker):
    """Only the stars are required (D2).

    1. Save a review without tags
    2. Expect: saved, with an empty list of tags
    """
    saved = review(application, worker)

    saved.refresh_from_db()
    assert saved.tags == []


def test_tag_lists():
    """Five positive tags per side (R2, D2).

    1. Read the values of WorkerTag and EmployerTag
    2. Expect: the five values of each list in the spec
    """
    assert list(WorkerTag.values) == [
        "on_time",
        "careful_work",
        "hard_working",
        "clean_site",
        "safety_rules",
    ]
    assert list(EmployerTag.values) == [
        "paid_on_time",
        "as_described",
        "safe_workplace",
        "clear_instructions",
        "respectful",
    ]


# When the job was done (R3, D9; AC2)


def test_mark_done_saves_when(employer, worker):
    """The 14 days count from "done", so it is saved (R3, D9).

    1. Save a filled job that ended yesterday, with an accepted worker
    2. mark_done()
    3. Expect: done_at in the database is now
    """
    job = make_job(employer, date=(NOW - DAY).date(), status=Job.Status.FILLED)
    accepted(job, worker)

    job.mark_done()

    job.refresh_from_db()
    assert job.done_at == NOW


def test_cancel_does_not_set_done_at(employer, worker):
    """Only "done" has a done_at (R3).

    1. Save a filled job next week with an accepted worker
    2. cancel()
    3. Expect: done_at is still empty
    """
    job = make_job(employer, status=Job.Status.FILLED)
    accepted(job, worker)

    job.cancel()

    job.refresh_from_db()
    assert job.done_at is None


def test_review_deadline_is_14_days_after_done(application):
    """Done yesterday: the reviews close in 13 days (R4, D3).

    1. Take an application of a job done yesterday at 10:00
    2. Expect: review_deadline is 14 days after done_at
    """
    assert application.review_deadline == NOW - DAY + 14 * DAY


def test_no_deadline_before_the_job_is_done(employer, worker):
    """No reviews of a job that is not done (R4, D1).

    1. Take an accepted application of a filled job next week
    2. Expect: review_deadline is None
    """
    job = make_job(employer, status=Job.Status.FILLED)

    assert accepted(job, worker).review_deadline is None


# Who may review (R5; AC3)


def test_worker_and_employer_can_review(application, employer, worker):
    """Both participants of a done job (R5).

    1. Take Ivan's accepted application of Anna's done job
    2. Expect: can_review is True for Ivan and for Anna
    """
    assert application.can_review(worker) is True
    assert application.can_review(employer) is True


def test_strangers_cannot_review(application, employer):
    """Only the two sides: not another worker, another employer (R5).

    1. Accept another worker on the same job; make another employer
    2. Expect: can_review of Ivan's application is False for both
    """
    other_worker = make_worker("olga@example.com")
    accepted(application.job, other_worker)
    other_employer = make_employer("bob@example.com")

    assert application.can_review(other_worker) is False
    assert application.can_review(other_employer) is False


@pytest.mark.parametrize(
    "status",
    [
        Application.Status.PENDING,
        Application.Status.CLOSED,
        Application.Status.REJECTED,
        Application.Status.CANCELLED,
        Application.Status.WITHDRAWN,
    ],
)
def test_application_that_was_not_accepted_cannot_be_reviewed(employer, worker, status):
    """Only work that happened: an accepted application (R5, D1).

    1. Save a pending / closed / rejected / cancelled / withdrawn application of a done job
    2. Expect: can_review is False for the worker and the employer
    """
    application = accepted(done_job(employer), worker, status=status)

    assert application.can_review(worker) is False
    assert application.can_review(employer) is False


@pytest.mark.parametrize("status", [Job.Status.FILLED, Job.Status.CANCELLED])
def test_job_that_is_not_done_cannot_be_reviewed(employer, worker, status):
    """A filled job that is over but not done, or a cancelled one: no (R5, D1).

    1. Save an accepted application of a filled / cancelled job two days ago
    2. Expect: can_review is False for both sides
    """
    job = done_job(employer, status=status, done_at=None)
    application = accepted(job, worker)

    assert application.can_review(worker) is False
    assert application.can_review(employer) is False


def test_reviews_close_after_the_deadline(employer, worker, monkeypatch):
    """A minute before the 14 days end: yes; a minute after: no (R5, D3).

    1. Take an application done yesterday
    2. Set the clock a minute before, then a minute after its deadline
    3. Expect: can_review True, then False
    """
    application = accepted(done_job(employer), worker)
    deadline = application.review_deadline

    monkeypatch.setattr(timezone, "now", lambda: deadline - MINUTE)
    assert application.can_review(worker) is True
    monkeypatch.setattr(timezone, "now", lambda: deadline + MINUTE)
    assert application.can_review(worker) is False


def test_one_review_per_side(application, employer, worker):
    """After their own review a side cannot review again; the other still can (R5, D6).

    1. Save Ivan's review of the application
    2. Expect: can_review False for Ivan, True for Anna
    """
    review(application, worker)

    assert application.can_review(worker) is False
    assert application.can_review(employer) is True


# When a review is shown (R6, D3; AC4)


def test_review_is_hidden_until_the_other_side_rates(application, employer, worker):
    """One side only: hidden, so the other side cannot rate in revenge (D3).

    1. Save Ivan's review of the application
    2. Expect: is_visible is False
    """
    assert review(application, worker).is_visible is False


def test_both_reviews_are_shown_when_both_sides_rated(application, employer, worker):
    """The second review opens both (R6).

    1. Save Ivan's review, then Anna's
    2. Expect: is_visible is True for both
    """
    first = review(application, worker)
    second = review(application, employer)

    assert first.is_visible is True
    assert second.is_visible is True


def test_review_of_another_application_does_not_open_it(application, employer):
    """Only the same work counts: Anna's review of another worker does not (R6).

    1. Accept Olga on the same job; save Ivan's review of his application and Anna's of
       Olga's
    2. Expect: Ivan's review is still hidden
    """
    olga = accepted(application.job, make_worker("olga@example.com"))
    ivans = review(application, application.worker)
    review(olga, employer)

    assert ivans.is_visible is False


def test_one_sided_review_is_shown_after_the_deadline(application, worker, monkeypatch):
    """The other side did not rate in 14 days: shown anyway (R6, D3).

    1. Save Ivan's review
    2. Set the clock a minute before, then a minute after the deadline
    3. Expect: is_visible False, then True
    """
    saved = review(application, worker)
    deadline = application.review_deadline

    monkeypatch.setattr(timezone, "now", lambda: deadline - MINUTE)
    assert saved.is_visible is False
    monkeypatch.setattr(timezone, "now", lambda: deadline + MINUTE)
    assert saved.is_visible is True
