"""Integration tests: the employer's public page and the way to it from the job page (#39).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/ratings.md, iteration 3 (R11-R13, D4, D11).
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import EmployerTag, Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(39)]

User = get_user_model()
DAY = datetime.timedelta(days=1)


@pytest.fixture
def employer():
    """Anna Huber of Huber Bau GmbH, with a phone number."""
    return make_employer("anna@example.com", name="Anna Huber", phone="+49 151 1111111")


@pytest.fixture
def worker():
    """Ivan Petrenko, a crew of 3, who worked for Anna."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.save()
    return user


def rated(employer, worker, stars=4, tags=()):
    """A done work: Ivan rates Anna `stars` with `tags`, Anna rates him back."""
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
        application=application, author=worker, rating=stars, tags=list(tags)
    )
    Review.objects.create(application=application, author=employer, rating=5)


def employer_url(user):
    """The public page of employer `user`."""
    return reverse("employer_detail", args=[user.pk])


def test_guest_sees_the_employers_page(client, employer, worker):
    """Anyone can open it: card, rating, tags and reviews (R11, D4, D11).

    1. Ivan rates Anna 4 with Paid in full and on time
    2. Open Anna's page as a guest
    3. Expect: 200, "Employer profile", "Huber Bau GmbH", "★ 4.0 (1 review)",
       "Paid in full and on time · 1 of 1", the "Reviews" list signed "Crew of 3"
    """
    rated(employer, worker, 4, [EmployerTag.PAID_ON_TIME])

    response = client.get(employer_url(employer))

    assert response.status_code == 200
    assertContains(response, ">Employer profile</h1>")
    assertContains(response, "Huber Bau GmbH")
    assertContains(response, "★ 4.0 (1 review)")
    assertContains(response, "Paid in full and on time · 1 of 1")
    assertContains(response, ">Reviews</h2>")
    assertContains(response, "Crew of 3")


def test_page_has_no_contact_details(client, employer):
    """The public page shows what the job page card shows, no phone or email (D11).

    1. Anna has a phone number
    2. Open her page as a guest
    3. Expect: no phone, no email
    """
    response = client.get(employer_url(employer))

    assertNotContains(response, "+49 151 1111111")
    assertNotContains(response, "anna@example.com")


@pytest.mark.parametrize("who", ["worker", "unknown", "no profile"])
def test_page_of_someone_else_is_404(client, worker, who):
    """Only an employer with a profile has a page (R11).

    1. Take a worker's id, an id nobody has, or an employer who has no profile yet
    2. Open the employer page with it
    3. Expect: 404
    """
    ids = {
        "worker": worker.pk,
        "unknown": 999999,
        "no profile": User.objects.create_user(
            email="new@example.com", password="x", role="employer"
        ).pk,
    }

    response = client.get(reverse("employer_detail", args=[ids[who]]))

    assert response.status_code == 404


def test_job_page_links_to_the_reviews(client, employer, worker):
    """The job page's employer card: "2 reviews →" to her page (R12).

    1. Ivan rates Anna twice
    2. Open a new job of Anna's as a guest
    3. Expect: a link to her page with "2 reviews →"
    """
    rated(employer, worker)
    rated(employer, worker)

    response = client.get(reverse("job_detail", args=[make_job(employer).pk]))

    assertContains(response, f'href="{employer_url(employer)}"')
    assertContains(response, "2 reviews →")


def test_job_page_without_reviews_has_no_link(client, employer):
    """No review yet: nothing to read on her page, so no link (R12).

    1. Anna has no review
    2. Open her job as a guest
    3. Expect: "No reviews yet", no link to her page
    """
    response = client.get(reverse("job_detail", args=[make_job(employer).pk]))

    assertContains(response, "No reviews yet")
    assertNotContains(response, f'href="{employer_url(employer)}"')


def test_own_page_has_no_link_to_itself(client, employer, worker):
    """ "My company" shows the reviews itself; no link to the public page (R13).

    1. Ivan rates Anna
    2. Open "My company" as Anna
    3. Expect: the reviews, no "1 review →"
    """
    rated(employer, worker)
    client.force_login(employer)

    response = client.get(reverse("employer_profile"))

    assertContains(response, ">Reviews</h2>")
    assertNotContains(response, "1 review →")
