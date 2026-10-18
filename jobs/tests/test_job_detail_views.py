"""Integration tests: the job page and the "Apply" stub through the Django test client.

Each test goes through the whole stack: middleware, URL, view, template and database.
Ticket #19. Spec: docs/specs/job-detail.md (R1-R13), acceptance criteria AC2-AC10. AC1 is a unit test
in test_models.py.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

# The same helpers as the other job pages: an employer with a profile, a job next week.
from .test_views import NEXT_WEEK, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(19)]

User = get_user_model()

ADDRESS_HIDDEN = "The exact address is shown after the employer accepts you."


@pytest.fixture
def employer():
    """The employer who posted the job, with a company profile and a phone."""
    return make_employer("anna@example.com", name="Anna Huber", phone="+4917076543")


@pytest.fixture
def job(employer):
    """An open job next week, 08:00 for 6 hours, for 2 workers."""
    return make_job(employer)


@pytest.fixture
def worker():
    """A worker (no profile needed: the page and the stub do not check it, spec D5)."""
    return User.objects.create_user(
        email="ivan@example.com", password="x", role="worker"
    )


@pytest.fixture
def other_employer():
    """An employer who did not post the job."""
    return make_employer("boris@example.com")


def detail_url(job):
    """The job's page."""
    return reverse("job_detail", args=[job.pk])


def apply_url(job):
    """Where the "Apply" button posts to."""
    return reverse("job_apply", args=[job.pk])


# Who may open the page (spec R1, R2, D1; AC2)


@pytest.mark.parametrize(
    "who", ["guest", "worker", "other employer"], ids=lambda who: who
)
def test_everyone_sees_the_job_page(client, job, worker, other_employer, who):
    """Guests, workers and other employers all get the job page (spec D1).

    1. Save an open job next week
    2. Open its page as a guest, a worker or another employer
    3. Expect: status 200, the detail template is used, the job is in the context
    """
    users = {"guest": None, "worker": worker, "other employer": other_employer}
    if users[who]:
        client.force_login(users[who])

    response = client.get(detail_url(job))

    assert response.status_code == 200
    assert "jobs/job_detail.html" in [t.name for t in response.templates]
    assert response.context["job"] == job


def test_unknown_job_gives_404(client):
    """A job id that does not exist gives 404.

    1. Open /jobs/99999/ as a guest
    2. Expect: status 404
    """
    response = client.get(reverse("job_detail", args=[99999]))

    assert response.status_code == 404


# What the page shows (spec R4, R6; AC3)


def test_page_shows_all_job_details(client, employer):
    """The page shows type, rate, place, time, workers, description and who hires.

    1. Save a demolition job next week, 08:00 for 6 hours, 2 workers, 20.00 €/h, with a
       two-line description
    2. Open its page as a guest
    3. Expect: all of these are on the page, the description keeps its line break,
       the company name and its trade are shown
    """
    job = make_job(employer, description="Tear down a shed.\nBring gloves.")

    response = client.get(detail_url(job))

    assertContains(response, "Demolition")
    assertContains(response, "20.00 €/h")
    assertContains(response, "Sendling")
    assertContains(response, dateformat.format(NEXT_WEEK, "D j M"))
    assertContains(response, "08:00–14:00")
    assertContains(response, "(6 h)")
    assertContains(response, "Needs 2 workers")
    assertContains(response, "Tear down a shed.<br>Bring gloves.")
    assertContains(response, "Huber Bau GmbH")
    assertContains(response, employer.employer_profile.trade_names()[0])


def test_page_has_no_contact_details_of_the_employer(client, job):
    """Workers see who hires, but no phone or email (spec R6; AC10).

    1. Save a job of an employer with a phone
    2. Open its page as a guest
    3. Expect: the contact person's name is there, the phone and the email are not
    """
    response = client.get(detail_url(job))

    assertContains(response, "Anna Huber")
    assertNotContains(response, "+4917076543")
    assertNotContains(response, "anna@example.com")


def test_employer_without_profile_is_shown_by_name(client):
    """A job of an employer with no profile (made in the admin) shows the account's name.

    1. Save a job of an employer called "Karl Meier" who has no company profile
    2. Open its page as a guest
    3. Expect: status 200 and "Karl Meier" on the page
    """
    employer = User.objects.create_user(
        email="karl@example.com", password="x", role="employer", name="Karl Meier"
    )
    job = make_job(employer)

    response = client.get(detail_url(job))

    assert response.status_code == 200
    assertContains(response, "Karl Meier")


# The address (spec R5, D4; AC4)


def test_owner_sees_the_address(client, employer, job):
    """The employer who posted the job sees its exact address.

    1. Log in as the job's employer
    2. Open the job's page
    3. Expect: the address is there, the "shown after the employer accepts you" line is not
    """
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, "Lindwurmstraße 1")
    assertNotContains(response, ADDRESS_HIDDEN)


@pytest.mark.parametrize(
    "who", ["guest", "worker", "other employer"], ids=lambda who: who
)
def test_others_do_not_see_the_address(client, job, worker, other_employer, who):
    """Everyone but the job's employer sees the district only (spec D4).

    1. Open the job's page as a guest, a worker or another employer
    2. Expect: the address is not on the page; the "shown after the employer accepts you"
       line is
    """
    users = {"guest": None, "worker": worker, "other employer": other_employer}
    if users[who]:
        client.force_login(users[who])

    response = client.get(detail_url(job))

    assertNotContains(response, "Lindwurmstraße")
    assertContains(response, ADDRESS_HIDDEN)


# Status (spec R3, D1, D2; AC5)


@pytest.mark.parametrize(
    ("status", "label"),
    [("cancelled", "Cancelled"), ("filled", "Filled"), ("done", "Done")],
)
def test_job_that_is_not_open_shows_its_status_and_no_apply(
    client, employer, worker, status, label
):
    """A cancelled, filled or done job keeps its page, with its status and no "Apply".

    1. Save a job next week with status cancelled / filled / done
    2. Open its page as a worker
    3. Expect: status 200, the status label is shown, no form posts to job_apply
    """
    job = make_job(employer, status=status)
    client.force_login(worker)

    response = client.get(detail_url(job))

    assert response.status_code == 200
    assertContains(response, label)
    assertNotContains(response, apply_url(job))


def test_open_job_that_has_started_shows_past_and_no_apply(client, employer, worker):
    """An open job whose day has passed is shown as "Past", without "Apply" (spec D2).

    1. Save an open job yesterday
    2. Open its page as a worker
    3. Expect: "Past" is shown, no form posts to job_apply
    """
    job = make_job(employer, date=timezone.localdate() - datetime.timedelta(days=1))
    client.force_login(worker)

    response = client.get(detail_url(job))

    assertContains(response, "Past")
    assertNotContains(response, apply_url(job))


# Buttons by who looks (spec R8, D3, D5; AC6)


def test_worker_sees_apply_button(client, job, worker):
    """A worker gets an "Apply" button that posts to the stub.

    1. Log in as a worker
    2. Open an open upcoming job's page
    3. Expect: a POST form to job_apply with an "Apply" button; no "Log in to apply"
    """
    client.force_login(worker)

    response = client.get(detail_url(job))

    assertContains(response, f'action="{apply_url(job)}"')
    assertContains(response, "Apply")
    assertNotContains(response, "Log in to apply")


def test_guest_sees_log_in_to_apply(client, job):
    """A guest gets "Log in to apply", which comes back to the job after login.

    1. Open an open upcoming job's page as a guest
    2. Expect: a link to the login page with next= this job; no form to job_apply
    """
    response = client.get(detail_url(job))

    assertContains(response, "Log in to apply")
    assertContains(response, f'href="{reverse("login")}?next={detail_url(job)}"')
    assertNotContains(response, apply_url(job))


def test_other_employer_sees_no_apply_and_no_edit(client, job, other_employer):
    """An employer who did not post the job gets neither "Apply" nor "Edit".

    1. Log in as another employer
    2. Open the job's page
    3. Expect: no form to job_apply, no link to job_edit, no "Log in to apply"
    """
    client.force_login(other_employer)

    response = client.get(detail_url(job))

    assertNotContains(response, apply_url(job))
    assertNotContains(response, reverse("job_edit", args=[job.pk]))
    assertNotContains(response, "Log in to apply")


def test_owner_sees_edit_link(client, employer, job):
    """The job's employer gets an "Edit" link instead of "Apply".

    1. Log in as the job's employer
    2. Open the job's page
    3. Expect: a link to job_edit, no form to job_apply
    """
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertContains(response, f'href="{reverse("job_edit", args=[job.pk])}"')
    assertNotContains(response, apply_url(job))


def test_owner_sees_no_edit_link_on_a_cancelled_job(client, employer):
    """A job that is not open cannot be edited, so there is no "Edit" link (spec R8).

    1. Log in as the employer of a cancelled job
    2. Open the job's page
    3. Expect: no link to job_edit
    """
    job = make_job(employer, status="cancelled")
    client.force_login(employer)

    response = client.get(detail_url(job))

    assertNotContains(response, reverse("job_edit", args=[job.pk]))


# The "Apply" stub (spec R9, D3; AC7)


def test_apply_stub_says_not_available_and_comes_back(client, job, worker):
    """Pressing "Apply" brings the worker back to the job with a message (spec D3).

    1. Log in as a worker
    2. POST to the job's apply URL, following the redirect
    3. Expect: redirected to the job's page, "Applying is not available yet." is shown
    """
    client.force_login(worker)

    response = client.post(apply_url(job), follow=True)

    assertRedirects(response, detail_url(job))
    assertContains(response, "Applying is not available yet.")


def test_apply_stub_refuses_get(client, job, worker):
    """The apply URL takes only POST.

    1. Log in as a worker
    2. GET the job's apply URL
    3. Expect: status 405
    """
    client.force_login(worker)

    response = client.get(apply_url(job))

    assert response.status_code == 405


def test_apply_stub_sends_guest_to_login(client, job):
    """A guest who posts to the apply URL is sent to the login page.

    1. POST to the job's apply URL as a guest
    2. Expect: a redirect to the login page with next= the apply URL
    """
    response = client.post(apply_url(job))

    assertRedirects(
        response,
        f"{reverse('login')}?next={apply_url(job)}",
        fetch_redirect_response=False,
    )


def test_apply_stub_refuses_employers(client, job, other_employer):
    """An employer cannot apply.

    1. Log in as an employer
    2. POST to the job's apply URL
    3. Expect: status 403
    """
    client.force_login(other_employer)

    response = client.post(apply_url(job))

    assert response.status_code == 403


def test_apply_stub_gives_404_for_unknown_job(client, worker):
    """Applying to a job that does not exist gives 404.

    1. Log in as a worker
    2. POST to /jobs/99999/apply/
    3. Expect: status 404
    """
    client.force_login(worker)

    response = client.post(reverse("job_apply", args=[99999]))

    assert response.status_code == 404


# Links to the page (spec R10, R11, D6; AC8)


def test_job_list_card_links_to_the_job_page(client, job):
    """The job type on the home page's card links to the job page.

    1. Save an open job next week
    2. Open the home page as a guest
    3. Expect: a link to the job's page
    """
    response = client.get(reverse("home"))

    assertContains(response, f'href="{detail_url(job)}"')


def test_my_jobs_card_links_to_the_job_page(client, employer, job):
    """The job type on the employer's "My jobs" card links to the job page.

    1. Log in as the job's employer
    2. Open "My jobs"
    3. Expect: a link to the job's page
    """
    client.force_login(employer)

    response = client.get(reverse("my_jobs"))

    assertContains(response, f'href="{detail_url(job)}"')


def test_job_page_links_back_to_the_list(client, job):
    """The job page has a "← Jobs" link to the home page.

    1. Open the job's page as a guest
    2. Expect: a link to the home page with the text "Jobs"
    """
    response = client.get(detail_url(job))

    assertContains(response, f'href="{reverse("home")}"')
    assertContains(response, "← Jobs")


# Database queries (spec R12; AC9)


def test_page_needs_one_query(client, job, django_assert_num_queries):
    """The job, its employer and the profile come in one query (select_related).

    1. Open the job's page as a guest (no session, so no session query)
    2. Expect: exactly 1 database query
    """
    with django_assert_num_queries(1):
        client.get(detail_url(job))
