"""Integration tests: the job list on the home page through the Django test client (#18).

Each test goes through the whole stack: middleware, URL, view, template and database.
Spec: docs/specs/job-list.md (R1-R10, R12-R21), acceptance criteria AC3-AC10, AC15-AC19. AC1 and AC2 are unit
tests in test_models.py; AC11 is test_onboarding.py (a user without a role is still sent to
the role choice from the home page).
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import dateformat, timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Job

# The same helpers as the employer job pages: an employer with a profile, a job next week.
from .test_views import NEXT_WEEK, make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(18)]

User = get_user_model()


@pytest.fixture
def employer():
    """An employer with a company profile."""
    return make_employer("anna@example.com")


def jobs_on_page(response):
    """The jobs the page shows, in the order it shows them."""
    return list(response.context["jobs"])


# Which jobs are shown (#18, docs/specs/job-list.md R2, R3, R4; AC3, AC4, AC7)


def test_home_page_shows_an_open_upcoming_job(client, employer):
    """The home page lists an open job that has not started yet.

    1. Save an open job next week
    2. Open the home page as a guest
    3. Expect: status 200, the job is in the list, the job list template is used
    """
    job = make_job(employer)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert jobs_on_page(response) == [job]
    assert "jobs/job_list.html" in [t.name for t in response.templates]


@pytest.mark.parametrize("status", ["filled", "done", "cancelled"])
def test_home_page_hides_jobs_that_are_not_open(client, employer, status):
    """Filled, done and cancelled jobs are not on the list.

    1. Save a job with status filled / done / cancelled, next week
    2. Open the home page
    3. Expect: the list is empty
    """
    make_job(employer, status=status)

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == []


def test_home_page_hides_a_job_that_was_yesterday(client, employer):
    """A job whose day has passed is not on the list, though its status is still open.

    1. Save an open job yesterday
    2. Open the home page
    3. Expect: the list is empty; the job itself is still "open" (spec D2)
    """
    job = make_job(employer, date=timezone.localdate() - datetime.timedelta(days=1))

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == []
    job.refresh_from_db()
    assert job.status == Job.Status.OPEN


def test_jobs_are_listed_soonest_first(client, employer):
    """The list is ordered by date, then start time, not by when the job was posted.

    1. Post a job in two weeks, then one next week at 10:00, then one next week at 07:00
    2. Open the home page
    3. Expect: next week 07:00, next week 10:00, in two weeks
    """
    later = make_job(employer, date=NEXT_WEEK + datetime.timedelta(days=7))
    ten = make_job(employer, start_time=datetime.time(10, 0))
    seven = make_job(employer, start_time=datetime.time(7, 0))

    response = client.get(reverse("home"))

    assert jobs_on_page(response) == [seven, ten, later]


@pytest.mark.parametrize(
    "role", [None, "worker", "employer"], ids=["guest", "worker", "employer"]
)
def test_everyone_sees_the_list(client, employer, role):
    """Guests, workers and employers all see the same list (spec D1).

    1. Save an open job next week
    2. Open the home page as a guest, a worker or another employer
    3. Expect: status 200 and the job is in the list
    """
    job = make_job(employer)
    if role:
        user = User.objects.create_user(
            email="ivan@example.com", password="x", role=role
        )
        client.force_login(user)

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert jobs_on_page(response) == [job]


# Pages (#18, docs/specs/job-list.md R5, R6; AC5, AC6)


def test_21_jobs_make_two_pages(client, employer):
    """20 jobs per page; the count shows all jobs found, on every page.

    1. Save 21 open jobs next week
    2. Open the home page, then ?page=2
    3. Expect: 20 jobs and a "Next" link on page 1, 1 job and a "Previous" link on page 2,
       "Page 1 of 2" / "Page 2 of 2", and "21 open" on both
    """
    for _ in range(21):
        make_job(employer)

    first = client.get(reverse("home"))
    second = client.get(reverse("home"), {"page": 2})

    assert len(jobs_on_page(first)) == 20
    assert len(jobs_on_page(second)) == 1
    assertContains(first, "21 open")
    assertContains(second, "21 open")
    assertContains(first, "Page 1 of 2")
    assertContains(second, "Page 2 of 2")
    assertContains(first, 'href="?page=2"')
    assertNotContains(first, "Previous")
    assertContains(second, 'href="?page=1"')
    # "Next →", not "Next": the date filter has "Next 7 days" (#18 iteration 2).
    assertNotContains(second, "Next →")


def test_one_page_has_no_page_links(client, employer):
    """With all jobs on one page there is no page navigation.

    1. Save one open job
    2. Open the home page
    3. Expect: "1 open", no "Page 1 of 1", no page navigation
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertContains(response, "1 open")
    assertNotContains(response, "Page 1 of")
    assertNotContains(response, 'aria-label="Pages"')


def test_a_page_that_does_not_exist_gives_404(client, employer):
    """A page number past the last page is "not found".

    1. Save one open job (one page)
    2. Open the home page with ?page=99
    3. Expect: status 404
    """
    make_job(employer)

    response = client.get(reverse("home"), {"page": 99})

    assert response.status_code == 404


# The card (#18, docs/specs/job-list.md R7, R8; AC8)


def test_card_shows_what_a_worker_needs_and_no_address(client, employer):
    """The card shows type, rate, district, date, start-end time and the workers needed.

    1. Save a demolition job in Sendling next week, 08:00 for 6 hours, 2 workers, 20.00 €/h
    2. Open the home page
    3. Expect: "Demolition", "20.00 €/h", "Sendling", the date, "08:00–14:00",
       "Needs 2 workers"; not the address and not the description
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertContains(response, "Demolition")
    assertContains(response, "20.00 €/h")
    assertContains(response, "Sendling")
    assertContains(response, dateformat.format(NEXT_WEEK, "D j M"))
    assertContains(response, "08:00–14:00")
    assertContains(response, "Needs 2 workers")
    assertNotContains(response, "Lindwurmstraße 1")
    assertNotContains(response, "Tear down a garden shed.")


def test_card_says_one_worker_in_the_singular(client, employer):
    """One worker is "Needs 1 worker", not "workers".

    1. Save a job for one worker
    2. Open the home page
    3. Expect: "Needs 1 worker<", the singular form
    """
    make_job(employer, workers_needed=1)

    response = client.get(reverse("home"))

    assertContains(response, "Needs 1 worker<")


# Guests and the empty list (#18, docs/specs/job-list.md R9, R10; AC9, AC10)


def test_guest_sees_the_post_a_job_line(client):
    """A guest sees "Need workers? Post a job", and the link goes to signup.

    1. Open the home page as a guest
    2. Expect: "Need workers?" and a link to the signup page
    """
    response = client.get(reverse("home"))

    assertContains(response, "Need workers?")
    assertContains(response, f'href="{reverse("register")}" class="link font-semibold"')


@pytest.mark.parametrize("role", ["worker", "employer"])
def test_logged_in_users_do_not_see_the_post_a_job_line(client, role):
    """Logged-in users do not see the line for guests.

    1. Log in as a worker or an employer
    2. Open the home page
    3. Expect: no "Need workers?"
    """
    user = User.objects.create_user(email="ivan@example.com", password="x", role=role)
    client.force_login(user)

    response = client.get(reverse("home"))

    assertNotContains(response, "Need workers?")


def test_empty_list_says_there_are_no_jobs(client):
    """Without any open upcoming job the page says so.

    1. Open the home page with no jobs in the database
    2. Expect: "No open jobs right now." and "0 open"
    """
    response = client.get(reverse("home"))

    assertContains(response, "No open jobs right now.")
    assertContains(response, "0 open")


# Filters, iteration 2 (#18, docs/specs/job-list.md R12-R21; AC15-AC19)


def test_district_filter_shows_only_that_district(client, employer):
    """?district=sendling keeps Sendling jobs, the drop-down shows it, the count follows.

    1. Save a job in Sendling and a job in Laim
    2. Open the home page with ?district=sendling
    3. Expect: only the Sendling job, "1 open", "Sendling" selected in the drop-down,
       a "Reset filters" link to the home page
    """
    sendling = make_job(employer, district="sendling")
    make_job(employer, district="laim")

    response = client.get(reverse("home"), {"district": "sendling"})

    assert jobs_on_page(response) == [sendling]
    assertContains(response, "1 open")
    assertContains(response, '<option value="sendling" selected>')
    assertContains(
        response, f'<a href="{reverse("home")}" class="link">Reset filters</a>'
    )


def test_job_type_and_date_filters_work_together(client, employer):
    """Job type and "Next 7 days" both apply.

    1. Save a carrying job in 3 days, a demolition job in 3 days, a carrying job in 10 days
    2. Open the home page with ?job_type=carrying&date=7
    3. Expect: only the carrying job in 3 days
    """
    in_3_days = timezone.localdate() + datetime.timedelta(days=3)
    carrying_soon = make_job(employer, job_type="carrying", date=in_3_days)
    make_job(employer, job_type="demolition", date=in_3_days)
    make_job(
        employer,
        job_type="carrying",
        date=timezone.localdate() + datetime.timedelta(days=10),
    )

    response = client.get(reverse("home"), {"job_type": "carrying", "date": "7"})

    assert jobs_on_page(response) == [carrying_soon]


def test_empty_values_from_the_form_mean_all(client, employer):
    """What the browser sends with every drop-down on "all" filters nothing.

    1. Save two jobs
    2. Open the home page with ?date=&job_type=&district= (the form sent unchanged)
    3. Expect: both jobs, no "Reset filters"
    """
    make_job(employer, district="sendling")
    make_job(employer, district="laim")

    response = client.get(reverse("home"), {"date": "", "job_type": "", "district": ""})

    assert len(jobs_on_page(response)) == 2
    assertNotContains(response, "Reset filters")


def test_a_value_that_is_not_listed_is_ignored_without_an_error(client, employer):
    """?district=moon shows the whole list and no error (R16).

    1. Save two jobs in different districts
    2. Open the home page with ?district=moon
    3. Expect: both jobs, no "Select a valid choice", no red border, no "Reset filters"
    """
    make_job(employer, district="sendling")
    make_job(employer, district="laim")

    response = client.get(reverse("home"), {"district": "moon"})

    assert len(jobs_on_page(response)) == 2
    assertNotContains(response, "valid choice")
    assertNotContains(response, "select-error")
    assertNotContains(response, "Reset filters")


def test_page_links_keep_the_filter(client, employer):
    """With a filter on, "Next" keeps it, so page 2 shows the same district.

    1. Save 21 jobs in Sendling and 1 in Laim
    2. Open the home page with ?district=sendling, then follow to page 2 with the same filter
    3. Expect: 20 jobs on page 1, "21 open", the "Next" link has district=sendling and
       page=2; page 2 has the one remaining Sendling job
    """
    for _ in range(21):
        make_job(employer, district="sendling")
    make_job(employer, district="laim")

    first = client.get(reverse("home"), {"district": "sendling"})
    second = client.get(reverse("home"), {"district": "sendling", "page": 2})

    assert len(jobs_on_page(first)) == 20
    assertContains(first, "21 open")
    # {% querystring %} keeps the address's order and adds page=; & is escaped in HTML.
    assertContains(first, 'href="?district=sendling&amp;page=2"')
    assert len(jobs_on_page(second)) == 1
    assert jobs_on_page(second)[0].district == "sendling"


def test_no_match_says_so_and_offers_a_reset(client, employer):
    """A filter that finds nothing has its own text and a way back (R18, R19).

    1. Save a job in Sendling
    2. Open the home page with ?district=laim
    3. Expect: "No jobs match these filters.", not "No open jobs right now.",
       and "Reset filters"
    """
    make_job(employer, district="sendling")

    response = client.get(reverse("home"), {"district": "laim"})

    assertContains(response, "No jobs match these filters.")
    assertNotContains(response, "No open jobs right now.")
    assertContains(response, "Reset filters")


def test_no_filter_has_no_reset_link(client, employer):
    """Without a filter there is nothing to reset.

    1. Save a job
    2. Open the home page without parameters
    3. Expect: no "Reset filters"
    """
    make_job(employer)

    response = client.get(reverse("home"))

    assertNotContains(response, "Reset filters")


def test_filter_form_is_a_get_form_with_a_show_button(client):
    """The filters are a GET form: no CSRF token, the address can be shared (AC19, D9).

    1. Open the home page as a guest
    2. Expect: a form with method="get", the three drop-downs, a "Show" button, and no
       CSRF token on the page (a guest has no logout form either)
    """
    response = client.get(reverse("home"))

    assertContains(response, '<form method="get"')
    for name in ("date", "job_type", "district"):
        assertContains(response, f'<select name="{name}"')
    assertContains(response, ">Show</button>")
    assertNotContains(response, "csrfmiddlewaretoken")


def test_home_page_is_wider_than_other_pages(client):
    """The job list is wider for its left filter column; other pages keep their width (D13).

    1. Open the home page and the login page
    2. Expect: max-w-6xl on the home page's <main>, max-w-3xl on the login page's
    """
    home = client.get(reverse("home"))
    login = client.get(reverse("login"))

    assertContains(home, '<main class="mx-auto w-full max-w-6xl')
    assertContains(login, '<main class="mx-auto w-full max-w-3xl')
