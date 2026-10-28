"""Integration tests: a worker's profile as an employer sees it (#23).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/applications-list.md, iteration 2 (R7, D2, D4, D9, D10, D14), acceptance
criteria AC8, AC9 and AC19. The link from the list on the job page (AC10) is in
jobs/tests/test_applications_list_views.py.
"""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from jobs.models import Application, Job
from jobs.tests.test_application import make_worker
from jobs.tests.test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(23)]


@pytest.fixture
def employer():
    """Anna, who posted a job."""
    return make_employer("anna@example.com")


@pytest.fixture
def worker():
    """Ivan, a crew of 3 with a phone number."""
    user = make_worker("ivan@example.com")
    user.name = "Ivan Petrenko"
    user.phone = "+49 151 2345678"
    user.save()
    return user


@pytest.fixture
def job(employer, worker):
    """Anna's open job, which Ivan applied to."""
    job = make_job(employer)
    Application.objects.create(job=job, worker=worker)
    return job


def worker_url(user):
    """The worker page of `user`."""
    return reverse("worker_detail", args=[user.pk])


# What the employer sees (R7; AC8)


def test_employer_the_worker_applied_to_sees_the_profile(client, employer, worker, job):
    """The employer sees what the worker offers, as on the worker's own profile card.

    1. Ivan (crew of 3, demolition, German, Minijob, work permit) applied to Anna's job
    2. Log in as Anna and open Ivan's worker page
    3. Expect: the title "Worker profile"; Ivan's name, "Crew of 3", the skill, the
       language, the legal status and "Confirmed by the worker"
    """
    client.force_login(employer)

    response = client.get(worker_url(worker))

    assertContains(response, ">Worker profile</h1>")
    assertContains(response, "Ivan Petrenko")
    assertContains(response, "Crew of 3")
    assertContains(response, "Demolition")
    assertContains(response, "German")
    assertContains(response, "Minijob")
    assertContains(response, "Confirmed by the worker")


def test_worker_page_shows_no_contact_details(client, employer, worker, job):
    """Phone and email stay hidden until the employer accepts the worker (#25).

    1. Ivan, who has a phone number, applied to Anna's job
    2. Log in as Anna and open Ivan's worker page
    3. Expect: neither Ivan's email nor his phone is on the page
    """
    client.force_login(employer)

    response = client.get(worker_url(worker))

    assertContains(response, "Ivan Petrenko")
    assertNotContains(response, "ivan@example.com")
    assertNotContains(response, "2345678")


def test_profile_stays_visible_after_the_job_is_cancelled(
    client, employer, worker, job
):
    """An application to a cancelled job still lets its employer see the worker (D2).

    1. Ivan applied to Anna's job; Anna cancels it
    2. Log in as Anna and open Ivan's worker page
    3. Expect: status 200 with Ivan's name
    """
    Job.objects.filter(pk=job.pk).update(status=Job.Status.CANCELLED)
    client.force_login(employer)

    response = client.get(worker_url(worker))

    assertContains(response, "Ivan Petrenko")


def test_worker_who_applied_to_two_jobs_is_shown_once(client, employer, worker, job):
    """Two applications to the same employer still give one page, not an error.

    1. Ivan applied to two of Anna's jobs
    2. Log in as Anna and open Ivan's worker page
    3. Expect: status 200 with Ivan's name (the lookup finds him once, not twice)
    """
    Application.objects.create(job=make_job(employer), worker=worker)
    client.force_login(employer)

    response = client.get(worker_url(worker))

    assertContains(response, "Ivan Petrenko")


# Who may open the page (R7, D2, D4, D10; AC9)


def test_other_employer_gets_404(client, worker, job):
    """An employer Ivan never applied to cannot see him, even with jobs of their own (D2).

    1. Ivan applied to Anna's job; Boris has a job of his own, Ivan did not apply to it
    2. Log in as Boris and open Ivan's worker page
    3. Expect: 404, and Ivan's name is not shown
    """
    boris = make_employer("boris@example.com")
    make_job(boris)
    client.force_login(boris)

    response = client.get(worker_url(worker))

    assert response.status_code == 404
    assertNotContains(response, "Ivan Petrenko", status_code=404)


def test_guest_is_sent_to_login(client, worker, job):
    """A guest opening a worker page is sent to the login page.

    1. Open Ivan's worker page without logging in
    2. Expect: a redirect to login, which brings the guest back afterwards
    """
    url = worker_url(worker)

    response = client.get(url)

    assertRedirects(response, f"{reverse('login')}?next={url}")


def test_worker_gets_403_also_for_their_own_page(client, worker, job):
    """Workers get "403 Forbidden"; their own page is the profile page (D10).

    1. Log in as Ivan and open his own worker page, then the page of Olga, another worker
    2. Expect: status 403 both times
    """
    olga = make_worker("olga@example.com")
    client.force_login(worker)

    assert client.get(worker_url(worker)).status_code == 403
    assert client.get(worker_url(olga)).status_code == 403


def test_unknown_id_and_employer_id_give_404(client, employer, job):
    """Only workers have a worker page: an unknown id and an employer's id give 404.

    1. Log in as Anna
    2. Open the worker page of id 999999, then of Anna's own id
    3. Expect: 404 both times
    """
    client.force_login(employer)

    assert client.get(reverse("worker_detail", args=[999999])).status_code == 404
    assert client.get(worker_url(employer)).status_code == 404


def test_worker_without_profile_gives_404(client, employer, worker, job):
    """A worker whose profile is gone has nothing to show: 404, not a server error.

    1. Ivan applied to Anna's job; then his profile is deleted (only possible in the admin)
    2. Log in as Anna and open Ivan's worker page
    3. Expect: 404
    """
    worker.worker_profile.delete()
    client.force_login(employer)

    assert client.get(worker_url(worker)).status_code == 404
