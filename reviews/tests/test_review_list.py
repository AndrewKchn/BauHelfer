"""Unit tests: the tag summary, the latest reviews and who is named over a review (#39).

Spec: docs/specs/ratings.md, iteration 2 (R7-R10, D1, D3, D5). The pages are in
test_review_list_views.py.
"""

import datetime

import pytest
from django.utils import timezone

from accounts.models import EmployerProfile
from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import EmployerTag, Review, WorkerTag

pytestmark = [pytest.mark.django_db, pytest.mark.story(39)]

DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna of Huber Bau GmbH."""
    return make_employer("anna@example.com", name="Anna Huber")


@pytest.fixture
def worker():
    """Ivan, a crew of 3."""
    return make_worker("ivan@example.com")


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


def rated(employer, worker, worker_tags=(), employer_tags=(), stars=4):
    """One work rated by both sides, so both reviews are visible; Anna's review back."""
    application = work(employer, worker)
    annas = Review.objects.create(
        application=application, author=employer, rating=stars, tags=list(worker_tags)
    )
    Review.objects.create(
        application=application, author=worker, rating=4, tags=list(employer_tags)
    )
    return annas


# The tag summary (R7, D1)


def test_tags_are_counted_most_often_first(employer, worker):
    """Three reviews: "On time" twice, "Careful work" once (R7, D1).

    1. Anna rates Ivan three times: On time + Careful work, On time, and no tag
    2. Expect: tags [("On time", 2), ("Careful work", 1)] out of 3 reviews
    """
    rated(employer, worker, [WorkerTag.ON_TIME, WorkerTag.CAREFUL_WORK])
    rated(employer, worker, [WorkerTag.ON_TIME])
    rated(employer, worker, [])

    rating = Review.objects.rating_of(worker)

    assert rating.count == 3
    assert rating.tags == [("On time", 2), ("Careful work", 1)]


def test_tags_with_the_same_count_keep_the_list_order(employer, worker):
    """A tie is shown in the order of the tag list, so the page does not shuffle (R7).

    1. Anna rates Ivan once with Followed safety rules and On time
    2. Expect: On time first, as in WorkerTag
    """
    rated(employer, worker, [WorkerTag.SAFETY_RULES, WorkerTag.ON_TIME])

    labels = [label for label, _ in Review.objects.rating_of(worker).tags]

    assert labels == ["On time", "Followed safety rules"]


def test_hidden_reviews_tags_are_not_counted(employer, worker):
    """A hidden review gives away nothing, not even its tags (D2).

    1. Anna rates Ivan with On time for one work; Ivan has not rated her back
    2. Expect: no tags
    """
    Review.objects.create(
        application=work(employer, worker),
        author=employer,
        rating=5,
        tags=[WorkerTag.ON_TIME],
    )

    assert Review.objects.rating_of(worker).tags == []


def test_employer_gets_the_workers_tags(employer, worker):
    """The employer's summary counts what workers ticked about them (R7).

    1. Ivan rates Anna with Paid in full and on time
    2. Expect: Anna's tags [("Paid in full and on time", 1)]
    """
    rated(employer, worker, employer_tags=[EmployerTag.PAID_ON_TIME])

    assert Review.objects.rating_of(employer).tags == [("Paid in full and on time", 1)]


# The latest reviews (R8, R10, D5)


def test_latest_are_the_five_newest_visible(employer, worker):
    """Six visible reviews and a hidden one: the five newest visible, newest first (D5).

    1. Anna rates Ivan six times (both sides), then once more without Ivan's review
    2. Expect: latest_about(Ivan) is the 6th to the 2nd, in that order
    """
    reviews = [rated(employer, worker) for _ in range(6)]
    Review.objects.create(application=work(employer, worker), author=employer, rating=1)

    latest = list(Review.objects.latest_about(worker))

    assert latest == reviews[:0:-1]


# Who is named over a review (R9, D3)


def test_employers_review_is_signed_with_the_company(employer, worker):
    """An employer's review: the company (R9).

    1. Anna (Huber Bau GmbH) rates Ivan
    2. Expect: author_label "Huber Bau GmbH"
    """
    assert rated(employer, worker).author_label == "Huber Bau GmbH"


def test_private_employers_review_is_signed_with_the_name(worker):
    """An employer without a company: their name (R9).

    1. Petra, a private person (no company), rates Ivan
    2. Expect: author_label "Petra Klein"
    """
    petra = make_employer("petra@example.com", name="Petra Klein")
    EmployerProfile.objects.filter(user=petra).update(company_name="")

    assert rated(petra, worker).author_label == "Petra Klein"


def test_crews_review_is_signed_crew_of_n(employer, worker):
    """A worker's review never shows the name: "Crew of 3" (D3).

    1. Ivan (crew of 3) rates Anna
    2. Expect: author_label "Crew of 3"
    """
    rated(employer, worker)
    ivans = Review.objects.get(author=worker)

    assert ivans.author_label == "Crew of 3"


def test_single_workers_review_is_signed_worker(employer):
    """A worker on their own: "Worker" (D3).

    1. Olga (team of 1) rates Anna
    2. Expect: author_label "Worker"
    """
    olga = make_worker("olga@example.com", team_size=1)
    rated(employer, olga)

    assert Review.objects.get(author=olga).author_label == "Worker"


def test_review_tag_names(employer, worker):
    """A review's tags as names, for its card (R9).

    1. Anna rates Ivan with On time and Left the site clean
    2. Expect: tag_names ["On time", "Left the site clean"]
    """
    review = rated(employer, worker, [WorkerTag.ON_TIME, WorkerTag.CLEAN_SITE])

    assert review.tag_names == ["On time", "Left the site clean"]
