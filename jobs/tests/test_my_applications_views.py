"""Integration tests: the worker dashboard "My applications" (#26).

Each test goes through the whole stack: middleware, URL, view, model, template and database.
Spec: docs/specs/my-applications.md, iteration 1 (R3-R12, D9, D11-D16, D20), acceptance
criteria AC4-AC11. The rules behind the tabs (Job.is_over, Application.tab) are in
test_my_applications.py; "My jobs" keeps its own tests (AC12). The swipe between the tabs is
JavaScript, checked by the E2E tests.
"""

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from jobs.models import Application, Job

from .test_application import make_worker
from .test_views import make_employer, make_job

pytestmark = [pytest.mark.django_db, pytest.mark.story(26)]

ADDRESS = "Lindwurmstraße 1"  # make_job's address
EMPLOYER_PHONE = "+49 170 7654321"
TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
URL = reverse_lazy("my_applications")  # lazy: read when a test runs


@pytest.fixture
def employer():
    """The employer who posted the jobs, with a name and a phone."""
    return make_employer("anna@example.com", name="Anna Huber", phone=EMPLOYER_PHONE)


@pytest.fixture
def ivan():
    """The worker whose page it is."""
    return make_worker("ivan@example.com")


@pytest.fixture
def ivan_client(client, ivan):
    """A browser logged in as Ivan."""
    client.force_login(ivan)
    return client


def apply(job, worker, status="pending", **fields):
    """Save an application of `worker` to `job`; an accepted one takes 1 worker."""
    taken = 1 if status == "accepted" else 0
    return Application.objects.create(
        job=job, worker=worker, status=status, workers_accepted=taken, **fields
    )


def groups(response):
    """The tabs on the page: (status, applications) in order."""
    return [(group["status"], group["items"]) for group in response.context["groups"]]


# Who can open the page (#26, docs/specs/my-applications.md R3; AC4, AC5)


def test_guest_is_sent_to_login(client):
    """A guest is asked to log in first.

    1. Open "My applications" without logging in
    2. Expect: a redirect to the login page
    """
    response = client.get(URL)

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_employer_gets_403(client, employer):
    """The page is for workers only.

    1. Log in as an employer
    2. Open "My applications"
    3. Expect: 403
    """
    client.force_login(employer)

    assert client.get(URL).status_code == 403


def test_worker_sees_only_own_applications(ivan_client, ivan, employer):
    """Another worker's applications are never on the page.

    1. Save an application of Ivan and one of Olga to two jobs
    2. Open "My applications" as Ivan
    3. Expect: only Ivan's application
    """
    mine = apply(make_job(employer), ivan)
    apply(make_job(employer), make_worker("olga@example.com"))

    response = ivan_client.get(URL)

    assert groups(response) == [("pending", [mine])]


# Tabs (R4, R5, D12, D20; AC6)


def test_tabs_come_in_order(ivan_client, ivan, employer):
    """Accepted first, then what waits, then what is closed, "Past" last (D12).

    1. Save one application of Ivan per tab, in the reverse order
    2. Open "My applications"
    3. Expect: the tabs accepted, pending, closed, rejected, cancelled, past
    """
    past = apply(make_job(employer, date=TODAY - DAY), ivan)
    cancelled = apply(make_job(employer), ivan, "cancelled")
    rejected = apply(make_job(employer), ivan, "rejected")
    closed = apply(make_job(employer), ivan, "closed")
    pending = apply(make_job(employer), ivan)
    accepted = apply(make_job(employer), ivan, "accepted")

    response = ivan_client.get(URL)

    assert groups(response) == [
        ("accepted", [accepted]),
        ("pending", [pending]),
        ("closed", [closed]),
        ("rejected", [rejected]),
        ("cancelled", [cancelled]),
        ("past", [past]),
    ]


def test_tab_badges_show_their_label_and_count(ivan_client, ivan, employer):
    """Each tab is a badge with its label and number, linking to its group.

    1. Save two pending and one "Job filled" application of Ivan
    2. Open "My applications"
    3. Expect: the badges "Pending 2" before "Job filled 1", each with its group
    """
    apply(make_job(employer), ivan)
    apply(make_job(employer), ivan)
    apply(make_job(employer), ivan, "closed")

    response = ivan_client.get(URL)

    html = response.content.decode()
    assertContains(response, 'href="#tab-pending"')
    assertContains(response, 'id="tab-closed"')
    assert html.index(">Pending 2</a>") < html.index(">Job filled 1</a>")


def test_a_tab_without_applications_is_left_out(ivan_client, ivan, employer):
    """Empty tabs get no badge.

    1. Save only a pending application of Ivan
    2. Open "My applications"
    3. Expect: only the "pending" tab; no badge for the others
    """
    apply(make_job(employer), ivan)

    response = ivan_client.get(URL)

    assert [status for status, _ in groups(response)] == ["pending"]
    for status in ["accepted", "closed", "rejected", "cancelled", "past"]:
        assertNotContains(response, f'href="#tab-{status}"')


def test_soonest_job_first_inside_a_tab(ivan_client, ivan, employer):
    """Inside a tab the job that comes first is on top (R4).

    1. Save Ivan's pending applications to a job in 9 days, then to one in 3 days
    2. Open "My applications"
    3. Expect: the job in 3 days first
    """
    later = apply(make_job(employer, date=TODAY + 9 * DAY), ivan)
    sooner = apply(make_job(employer, date=TODAY + 3 * DAY), ivan)

    response = ivan_client.get(URL)

    assert groups(response) == [("pending", [sooner, later])]


@pytest.mark.parametrize(
    ("status", "date", "colour"),
    [
        ("accepted", TODAY + DAY, "badge-success"),
        ("pending", TODAY + DAY, "badge-warning"),
        ("closed", TODAY + DAY, "badge-info"),
        ("rejected", TODAY + DAY, "badge-error"),
        ("cancelled", TODAY + DAY, "badge-secondary"),
        ("pending", TODAY - DAY, "badge-neutral"),
    ],
    ids=["accepted", "pending", "closed", "rejected", "cancelled", "past"],
)
def test_each_tab_knows_its_colour(ivan_client, ivan, employer, status, date, colour):
    """A tab is filled with the colour of its status badge; "Past" is grey (D20).

    1. Save an application of Ivan for this tab
    2. Open "My applications"
    3. Expect: its badge has data-colour with that colour
    """
    apply(make_job(employer, date=date), ivan, status)

    response = ivan_client.get(URL)

    assertContains(response, f'data-colour="{colour}"')


# Queries (R3, D11; AC7)


def count_queries(client):
    """How many database queries "My applications" makes."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get(URL)
    assert response.status_code == 200
    return len(queries)


def test_queries_do_not_grow_with_the_applications(ivan_client, ivan, employer):
    """Jobs and employers of all applications come at once, not one query per card.

    1. Save one accepted application of Ivan; count the page's queries
    2. Add an accepted and a pending one to jobs of other employers; count again
    3. Expect: the same number of queries (no "N+1")
    """
    apply(make_job(employer), ivan, "accepted")
    with_one = count_queries(ivan_client)

    for email, status in [("b@example.com", "accepted"), ("c@example.com", "pending")]:
        apply(make_job(make_employer(email)), ivan, status)
    with_three = count_queries(ivan_client)

    assert with_three == with_one


# The card (R6, R8, D13, D15)


def test_card_links_to_the_job_page(ivan_client, ivan, employer):
    """The title of the card opens the job page (R6).

    1. Save a pending application of Ivan
    2. Open "My applications"
    3. Expect: a link to the job's page
    """
    job = make_job(employer)
    apply(job, ivan)

    response = ivan_client.get(URL)

    assertContains(response, f'href="{reverse("job_detail", args=[job.pk])}"')


def test_card_shows_the_crew(ivan_client, ivan, employer):
    """How many people Ivan brings; part of a crew as "1 of 2 workers" (R6, D13).

    1. Save Ivan's pending application for 3 workers to a job for 5, and an accepted one
       with 1 of 2 taken
    2. Open "My applications"
    3. Expect: "3 workers" and "1 of 2 workers"
    """
    apply(make_job(employer, workers_needed=5), ivan, workers_offered=3)
    apply(make_job(employer), ivan, "accepted", workers_offered=2)

    response = ivan_client.get(URL)

    assertContains(response, "3 workers")
    assertContains(response, "1 of 2 workers")


def test_pending_card_shows_the_message(ivan_client, ivan, employer):
    """While waiting, Ivan sees what he wrote (R8, D15).

    1. Save Ivan's pending application with a message
    2. Open "My applications"
    3. Expect: "Your message:" with the text
    """
    apply(make_job(employer), ivan, message="We are a crew of two.")

    response = ivan_client.get(URL)

    assertContains(response, "Your message:")
    assertContains(response, "We are a crew of two.")


def test_decided_card_hides_the_message(ivan_client, ivan, employer):
    """After a decision the message no longer matters (D15).

    1. Save Ivan's accepted application with a message
    2. Open "My applications"
    3. Expect: neither "Your message:" nor the text
    """
    apply(make_job(employer), ivan, "accepted", message="We are a crew of two.")

    response = ivan_client.get(URL)

    assertNotContains(response, "Your message:")
    assertNotContains(response, "We are a crew of two.")


# The contact box (R7, D14; AC8)


def test_accepted_card_shows_the_contact(ivan_client, ivan, employer):
    """Accepted for a job today: the employer's name, phone and the address (R7).

    1. Save Ivan's accepted application to a job today
    2. Open "My applications"
    3. Expect: "Contact", Anna Huber, her phone and the job's address; never her email
    """
    apply(make_job(employer, date=TODAY), ivan, "accepted")

    response = ivan_client.get(URL)

    assertContains(response, "Contact")
    assertContains(response, "Anna Huber")
    assertContains(response, f'href="tel:{EMPLOYER_PHONE}"')
    assertContains(response, ADDRESS)
    assertNotContains(response, "anna@example.com")


def test_employer_without_a_phone_is_not_given(ivan_client, ivan):
    """An employer who gave no phone: "not given" (R7, contacts.md D1).

    1. Save Ivan's accepted application to a job of an employer without a phone
    2. Open "My applications"
    3. Expect: "not given"
    """
    apply(make_job(make_employer("b@example.com")), ivan, "accepted")

    response = ivan_client.get(URL)

    assertContains(response, "not given")


@pytest.mark.parametrize(
    ("status", "date"),
    [("pending", TODAY + DAY), ("accepted", TODAY - DAY)],
    ids=["pending", "accepted, the day after the job"],
)
def test_no_contact_without_shows_contacts(ivan_client, ivan, employer, status, date):
    """Pending, or accepted for a job that is over: no phone, no address (R7).

    1. Save Ivan's application in this status and date
    2. Open "My applications"
    3. Expect: neither the employer's phone nor the address nor "Contact"
    """
    apply(make_job(employer, date=date), ivan, status)

    response = ivan_client.get(URL)

    assertNotContains(response, EMPLOYER_PHONE)
    assertNotContains(response, ADDRESS)
    assertNotContains(response, "Contact")


# Why it is closed (R9, R10, D9, D16; AC9)


@pytest.mark.parametrize(
    ("status", "date", "job_status", "line"),
    [
        ("rejected", TODAY + DAY, "open", "The employer chose other workers."),
        ("closed", TODAY + DAY, "filled", "The job was filled by other workers."),
        ("cancelled", TODAY + DAY, "open", "The employer cancelled your place."),
        ("pending", TODAY + DAY, "cancelled", "The employer cancelled the job."),
        ("cancelled", TODAY + DAY, "cancelled", "The employer cancelled the job."),
        ("pending", TODAY - DAY, "open", "The job is over."),
        (
            "accepted",
            TODAY - DAY,
            "filled",
            "The job is over. The contacts are no longer shown.",
        ),
    ],
    ids=[
        "rejected",
        "job filled",
        "place cancelled",
        "pending, job cancelled",
        "accepted, job cancelled",
        "past",
        "accepted, job over",
    ],
)
def test_closed_card_says_why(
    ivan_client, ivan, employer, status, date, job_status, line
):
    """One short line says why the application is closed (R9, D16).

    1. Save Ivan's application in this status, to a job on this date and in this status
    2. Open "My applications"
    3. Expect: the line for that case
    """
    apply(make_job(employer, date=date, status=job_status), ivan, status)

    response = ivan_client.get(URL)

    assertContains(response, line)


def test_waiting_card_has_no_closed_line(ivan_client, ivan, employer):
    """A pending application of a coming job is not closed: no such line (R9).

    1. Save Ivan's pending application to an open job next week
    2. Open "My applications"
    3. Expect: none of the closed lines
    """
    apply(make_job(employer), ivan)

    response = ivan_client.get(URL)

    assertNotContains(response, "The employer")
    assertNotContains(response, "The job is over.")


def test_pending_application_of_a_cancelled_job_shows_job_cancelled(
    ivan_client, ivan, employer
):
    """The badge says "Job cancelled", not "Pending", here and on the job page (R10, D9).

    1. Save Ivan's pending application to a cancelled job
    2. Open "My applications", then the job's page
    3. Expect: both show the badge "Job cancelled" and no "Pending" badge
    """
    job = make_job(employer, status=Job.Status.CANCELLED)
    apply(job, ivan)

    for url in [URL, reverse("job_detail", args=[job.pk])]:
        response = ivan_client.get(url)

        assertContains(response, ">Job cancelled</span>")
        assertNotContains(response, ">Pending</span>")


# No applications, the menu (R11, R12; AC10, AC11)


def test_worker_without_applications_is_sent_to_the_jobs(ivan_client):
    """An empty page says so and links to the job list (R11).

    1. Open "My applications" as a worker who has not applied
    2. Expect: the empty text and a "Find a job" link to the job list, besides the logo's
    """
    response = ivan_client.get(URL)

    assertContains(response, "You have not applied to any job yet.")
    assertContains(response, "Find a job")
    assertContains(response, f'href="{reverse("home")}"', count=2)


def test_worker_menu_links_to_my_applications(ivan_client):
    """A worker finds the page in the menu (R12).

    1. Open the home page as a worker
    2. Expect: "My applications" linking to the page, once
    """
    response = ivan_client.get(reverse("home"))

    assertContains(response, f'href="{URL}"', count=1)
    assertContains(response, "My applications")


def test_employer_menu_has_no_my_applications(client, employer):
    """The link is a worker's only (R12).

    1. Open the home page as an employer
    2. Expect: no "My applications"
    """
    client.force_login(employer)

    response = client.get(reverse("home"))

    assertNotContains(response, "My applications")
