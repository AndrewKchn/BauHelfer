"""Integration tests: the review page of an application (#38).

Each test goes through the whole stack: middleware, URL, view, form, template and database.
Spec: docs/specs/reviews.md, iteration 1 (R7-R9, D2-D4, D6, D10), acceptance criteria
AC5-AC7. Who may review and when a review is shown are in test_models.py.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job
from reviews.models import Review

pytestmark = [pytest.mark.django_db, pytest.mark.story(38)]

DAY = datetime.timedelta(days=1)

# One tag of each list, as the page shows it.
WORKER_TAG = "Followed safety rules"
EMPLOYER_TAG = "Paid in full and on time"


@pytest.fixture
def employer():
    """Anna, the employer of the job."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """Ivan, the worker who was accepted and worked."""
    return make_worker("ivan@example.com")


@pytest.fixture
def application(employer, worker):
    """Ivan's accepted application to Anna's job, done yesterday."""
    job = make_job(
        employer,
        date=timezone.localdate() - 2 * DAY,
        status=Job.Status.DONE,
        done_at=timezone.now() - DAY,
    )
    return Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status=Application.Status.ACCEPTED
    )


def review_url(application):
    """The review page of `application`."""
    return reverse("review_create", args=[application.pk])


def messages_of(response):
    """The texts of the messages shown on the page after the redirect."""
    return [str(message) for message in response.context["messages"]]


# Who gets the page (R7, D10; AC5)


def test_worker_gets_the_employer_tags(client, application, worker):
    """The worker rates the employer: the employer's tags, not the worker's (R2, R8).

    1. Open the review page as Ivan
    2. Expect: 200; the stars, an employer tag, the hint that it cannot be changed; no
       worker tag
    """
    client.force_login(worker)

    response = client.get(review_url(application))

    assertContains(response, 'name="rating"')
    assertContains(response, EMPLOYER_TAG)
    assertContains(response, "It cannot be changed.")
    assertNotContains(response, WORKER_TAG)


def test_employer_gets_the_worker_tags(client, application, employer):
    """The employer rates the worker: the worker's tags (R2, R8).

    1. Open the review page as Anna
    2. Expect: 200; a worker tag; no employer tag
    """
    client.force_login(employer)

    response = client.get(review_url(application))

    assertContains(response, WORKER_TAG)
    assertNotContains(response, EMPLOYER_TAG)


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_stranger_gets_404(client, application, role):
    """Another worker or employer cannot tell the application exists (R7, D10).

    1. Log in as another worker / another employer
    2. GET and POST the review page
    3. Expect: 404 both times; no review saved
    """
    if role == "worker":
        stranger = make_worker("olga@example.com")
    else:
        stranger = make_employer("bob@example.com")
    client.force_login(stranger)

    get = client.get(review_url(application))
    post = client.post(review_url(application), {"rating": "5"})

    assert (get.status_code, post.status_code) == (404, 404)
    assert not Review.objects.exists()


def test_job_that_is_not_done_gets_404(client, employer, worker):
    """can_review says no: 404, as for a stranger (R7, D1, D10).

    1. Save Ivan's accepted application of a filled job next week
    2. Open its review page as Ivan
    3. Expect: 404
    """
    job = make_job(employer, status=Job.Status.FILLED)
    application = Application.objects.create(
        job=job, worker=worker, workers_accepted=1, status="accepted"
    )
    client.force_login(worker)

    assert client.get(review_url(application)).status_code == 404


def test_guest_is_sent_to_login(client, application):
    """Logged in only (R7).

    1. Open the review page without logging in
    2. Expect: a redirect to the login page
    """
    response = client.get(review_url(application))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


# Publishing a review (R8; AC6)


def test_worker_publishes_a_review(client, application, worker):
    """Stars and tags saved; back to "My applications", "Done" tab (R8, D4).

    1. POST 4 stars and two employer tags as Ivan, following the redirect
    2. Expect: one review by Ivan with them; "My applications" at #tab-done; the message
       "Review published."
    """
    client.force_login(worker)

    response = client.post(
        review_url(application),
        {"rating": "4", "tags": ["paid_on_time", "respectful"]},
        follow=True,
    )

    saved = Review.objects.get()
    assert (saved.application, saved.author) == (application, worker)
    assert (saved.rating, saved.tags) == (4, ["paid_on_time", "respectful"])
    assert response.redirect_chain == [(reverse("my_applications") + "#tab-done", 302)]
    assert messages_of(response) == ["Review published."]


def test_employer_publishes_a_review(client, application, employer):
    """The employer goes back to the job page (R8, D4).

    1. POST 5 stars without tags as Anna, following the redirect
    2. Expect: one review by Anna with 5 stars and no tags; the job page; the message
    """
    client.force_login(employer)

    response = client.post(review_url(application), {"rating": "5"}, follow=True)

    saved = Review.objects.get()
    assert (saved.author, saved.rating, saved.tags) == (employer, 5, [])
    job_url = reverse("job_detail", args=[application.job.pk])
    assert response.redirect_chain == [(job_url, 302)]
    assert messages_of(response) == ["Review published."]


def test_stars_are_required(client, application, worker):
    """Without stars: the form again, nothing saved (R8, D2).

    1. POST only a tag as Ivan
    2. Expect: 200 with a form error on rating; no review
    """
    client.force_login(worker)

    response = client.post(review_url(application), {"tags": ["paid_on_time"]})

    assert response.status_code == 200
    assert "rating" in response.context["form"].errors
    assert not Review.objects.exists()


def test_tag_of_the_other_list_is_refused(client, application, worker):
    """A worker cannot give the employer a worker tag (R2).

    1. POST 4 stars and the worker tag "on_time" as Ivan
    2. Expect: 200 with a form error on tags; no review
    """
    client.force_login(worker)

    response = client.post(
        review_url(application), {"rating": "4", "tags": ["on_time"]}
    )

    assert response.status_code == 200
    assert "tags" in response.context["form"].errors
    assert not Review.objects.exists()


# Only one review per side (R9, D6, D8; AC7)


def test_second_review_gets_404(client, application, worker):
    """After the review the page is gone for its author (R9, D6).

    1. POST a review as Ivan
    2. GET and POST the page again
    3. Expect: 404 both times; still one review, with the first rating
    """
    client.force_login(worker)
    client.post(review_url(application), {"rating": "4"})

    get = client.get(review_url(application))
    post = client.post(review_url(application), {"rating": "1"})

    assert (get.status_code, post.status_code) == (404, 404)
    assert Review.objects.get().rating == 4


def test_review_saved_by_another_tab_meanwhile_gives_404(
    client, application, worker, monkeypatch
):
    """Two tabs at the same moment: the database refuses the second, the page says 404 (R9,
    D8).

    1. Save Ivan's review; make can_review say yes anyway, as for a tab that checked a
       moment before the other one saved
    2. POST a second review as Ivan
    3. Expect: 404, not an error 500; still one review
    """
    Review.objects.create(application=application, author=worker, rating=4)
    monkeypatch.setattr(Application, "can_review", lambda self, user: True)
    client.force_login(worker)

    response = client.post(review_url(application), {"rating": "1"})

    assert response.status_code == 404
    assert Review.objects.get().rating == 4
