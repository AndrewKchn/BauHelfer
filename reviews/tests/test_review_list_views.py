"""Integration tests: the tag summary and the latest reviews on the profiles (#39).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/ratings.md, iteration 2 (R7-R10, D1, D3, D5).
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import EmployerTag, Review, WorkerTag

pytestmark = [pytest.mark.django_db, pytest.mark.story(39)]

DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna Huber of Huber Bau GmbH."""
    return make_employer("anna@example.com", name="Anna Huber")


@pytest.fixture
def worker():
    """Ivan Petrenko, a crew of 3."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.save()
    return user


def rated(employer, worker, worker_tags=(), employer_tags=(), job_type="demolition"):
    """One done work, rated by both sides with these tags; returns the application."""
    job = make_job(
        employer,
        job_type=job_type,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - DAY,
    )
    application = Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )
    Review.objects.create(
        application=application, author=employer, rating=5, tags=list(worker_tags)
    )
    Review.objects.create(
        application=application, author=worker, rating=3, tags=list(employer_tags)
    )
    return application


def test_worker_sees_the_tag_summary(client, employer, worker):
    """ "On time · 2 of 3" in the worker's card (R7, D1).

    1. Anna rates Ivan three times, twice with On time
    2. Open "My profile" as Ivan
    3. Expect: "What went well", "On time · 2 of 3"
    """
    rated(employer, worker, [WorkerTag.ON_TIME])
    rated(employer, worker, [WorkerTag.ON_TIME])
    rated(employer, worker)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "What went well")
    assertContains(response, "On time · 2 of 3")


def test_no_tags_no_summary(client, employer, worker):
    """Reviews without tags: no "What went well" at all (R7).

    1. Anna rates Ivan once, without tags
    2. Open "My profile" as Ivan
    3. Expect: no "What went well"
    """
    rated(employer, worker)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertNotContains(response, "What went well")


def test_employer_sees_the_workers_reviews(client, employer, worker):
    """The worker page lists the reviews: company, stars, tags, job and date (R8, R9).

    1. Anna rates Ivan 5 with Careful work for a demolition; Ivan applied to her new job
    2. Open Ivan's worker page as Anna
    3. Expect: "Reviews", "Huber Bau GmbH", "★ 5", "Careful work" and
       "Demolition · <job date>"
    """
    application = rated(employer, worker, [WorkerTag.CAREFUL_WORK])
    Application.objects.create(job=make_job(employer), worker=worker)
    client.force_login(employer)

    response = client.get(reverse("worker_detail", args=[worker.pk]))

    when = date_format(application.job.date, "j M")
    assertContains(response, ">Reviews</h2>")
    assertContains(response, "Huber Bau GmbH")
    assertContains(response, "★ 5")
    assertContains(response, "Careful work")
    assertContains(response, f"Demolition · {when}")


def test_employers_page_lists_reviews_without_workers_names(client, employer, worker):
    """Anna sees Ivan's review of her signed "Crew of 3", never his name (R9, D3).

    1. Ivan rates Anna 3 with Paid in full and on time
    2. Open "My company" as Anna
    3. Expect: "Crew of 3", "★ 3", "Paid in full and on time"; no "Ivan Petrenko"
    """
    rated(employer, worker, employer_tags=[EmployerTag.PAID_ON_TIME])
    client.force_login(employer)

    response = client.get(reverse("employer_profile"))

    assertContains(response, ">Reviews</h2>")
    assertContains(response, "Crew of 3")
    assertContains(response, "★ 3")
    assertContains(response, "Paid in full and on time")
    assertNotContains(response, "Ivan Petrenko")


def test_hidden_review_is_not_listed(client, employer, worker):
    """Anna's review waits for Ivan's: not in his list (R10, D2).

    1. Anna rates Ivan with Hard-working; Ivan has not rated her back
    2. Open "My profile" as Ivan
    3. Expect: no "Reviews" section, no "Hard-working"
    """
    job = make_job(
        employer,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - DAY,
    )
    application = Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )
    Review.objects.create(
        application=application,
        author=employer,
        rating=2,
        tags=[WorkerTag.HARD_WORKING],
    )
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertNotContains(response, ">Reviews</h2>")
    assertNotContains(response, "Hard-working")


def test_only_five_reviews_are_listed(client, employer, worker):
    """Six reviews: the list shows five (D5).

    1. Anna rates Ivan six times, the oldest for a site cleaning, the rest demolitions
    2. Open "My profile" as Ivan
    3. Expect: five "Demolition ·" lines, no "Site cleaning ·"
    """
    rated(employer, worker, job_type="site_cleaning")
    for _ in range(5):
        rated(employer, worker)
    client.force_login(worker)

    response = client.get(reverse("worker_profile"))

    assertContains(response, "Demolition · ", count=5)
    assertNotContains(response, "Site cleaning · ")


def test_job_page_card_has_the_tag_summary(client, employer, worker):
    """The employer card on the public job page shows the summary (R7, D4).

    1. Ivan rates Anna with Paid in full and on time
    2. Open a new job of Anna's as a guest
    3. Expect: "Paid in full and on time · 1 of 1"
    """
    rated(employer, worker, employer_tags=[EmployerTag.PAID_ON_TIME])

    response = client.get(reverse("job_detail", args=[make_job(employer).pk]))

    assertContains(response, "Paid in full and on time · 1 of 1")
